"""khởi tạo schema: 18 bảng, 11 enum, exclusion constraint chống trùng lịch

Theo ERD (17 bảng) và System Design mục 7.3, 7.4 (thêm refresh_tokens, privacy_consent_at,
anonymized_at, chỉ mục hội thoại). Exclusion constraint, partial index và enum viết tường minh
vì autogenerate không phát hiện đầy đủ.

Revision ID: 0001
Revises:
Create Date: 2026-10-16 10:30:00+07:00
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUMS: dict[str, tuple[str, ...]] = {
    "user_role": ("PATIENT", "DOCTOR", "ADMIN"),
    "gender": ("MALE", "FEMALE", "OTHER"),
    "appointment_status": ("BOOKED", "ARRIVED", "COMPLETED", "CANCELLED", "NO_SHOW"),
    "channel": ("WEB", "AGENT", "ADMIN", "SYSTEM"),
    "history_action": ("CREATE", "RESCHEDULE", "CANCEL", "STATUS_CHANGE", "NOTE_UPDATE", "FLAG"),
    "notification_type": ("BOOKED", "RESCHEDULED", "CANCELLED", "REMINDER"),
    "notification_status": ("PENDING", "SENT", "FAILED"),
    "message_role": ("USER", "ASSISTANT", "TOOL"),
    "proposal_type": ("BOOK", "RESCHEDULE", "CANCEL"),
    "proposal_status": ("PENDING", "CONFIRMED", "REJECTED", "EXPIRED", "FAILED"),
    "support_status": ("OPEN", "DONE"),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def _id() -> sa.Column[int]:
    return sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False)


def _created_at() -> sa.Column[datetime]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _updated_at() -> sa.Column[datetime]:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _fk(table: str, column: str, target: str, ondelete: str) -> sa.ForeignKeyConstraint:
    referred_table = target.split(".")[0]
    return sa.ForeignKeyConstraint(
        [column], [target], name=op.f(f"fk_{table}_{column}_{referred_table}"), ondelete=ondelete
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")  # exclusion constraint trên bigint
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")  # tìm kiếm không dấu (FR-CAT-04)
    bind = op.get_bind()
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=False)  # trùng tên → lỗi ngay

    # ------------------------------------------------------------------ người dùng
    op.create_table(
        "users",
        _id(),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", _enum("user_role"), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "failed_login_count", sa.SmallInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("privacy_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index("uq_users_lower_email", "users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "specialties",
        _id(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_specialties")),
        sa.UniqueConstraint("name", name=op.f("uq_specialties_name")),
    )

    op.create_table(
        "patient_profiles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("gender", _enum("gender"), nullable=False),
        _fk("patient_profiles", "user_id", "users.id", "RESTRICT"),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_patient_profiles")),
    )

    op.create_table(
        "doctors",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("specialty_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(50), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("gender", _enum("gender"), nullable=False),
        _fk("doctors", "user_id", "users.id", "RESTRICT"),
        _fk("doctors", "specialty_id", "specialties.id", "RESTRICT"),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_doctors")),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by", sa.UUID(), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        _created_at(),
        _fk("refresh_tokens", "user_id", "users.id", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])

    # ------------------------------------------------------------------ danh mục
    op.create_table(
        "services",
        _id(),
        sa.Column("specialty_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("scope_description", sa.Text(), nullable=False),
        sa.Column("duration_min", sa.SmallInteger(), nullable=False),
        sa.Column("ref_price_vnd", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(
            "duration_min BETWEEN 10 AND 120 AND duration_min % 5 = 0",
            name=op.f("ck_services_duration"),
        ),
        sa.CheckConstraint("ref_price_vnd >= 0", name=op.f("ck_services_price")),
        _fk("services", "specialty_id", "specialties.id", "RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
        sa.UniqueConstraint("specialty_id", "name", name=op.f("uq_services_specialty_id_name")),
    )

    op.create_table(
        "doctor_services",
        sa.Column("doctor_id", sa.BigInteger(), nullable=False),
        sa.Column("service_id", sa.BigInteger(), nullable=False),
        _fk("doctor_services", "doctor_id", "doctors.user_id", "CASCADE"),
        _fk("doctor_services", "service_id", "services.id", "CASCADE"),
        sa.PrimaryKeyConstraint("doctor_id", "service_id", name=op.f("pk_doctor_services")),
    )

    # ------------------------------------------------------------------ lịch làm việc
    op.create_table(
        "shifts",
        _id(),
        sa.Column("doctor_id", sa.BigInteger(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.CheckConstraint("weekday BETWEEN 1 AND 7", name=op.f("ck_shifts_weekday")),
        sa.CheckConstraint("end_time > start_time", name=op.f("ck_shifts_time_order")),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from", name=op.f("ck_shifts_valid_range")
        ),
        _fk("shifts", "doctor_id", "doctors.user_id", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shifts")),
    )
    op.create_index("ix_shifts_doctor_id_weekday", "shifts", ["doctor_id", "weekday"])

    op.create_table(
        "time_offs",
        _id(),
        sa.Column("doctor_id", sa.BigInteger(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("end_at > start_at", name=op.f("ck_time_offs_time_order")),
        _fk("time_offs", "doctor_id", "doctors.user_id", "CASCADE"),
        _fk("time_offs", "created_by", "users.id", "RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_time_offs")),
    )
    op.create_index("ix_time_offs_doctor_id_start_at", "time_offs", ["doctor_id", "start_at"])

    # ------------------------------------------------------------------ lịch hẹn
    op.create_table(
        "appointments",
        _id(),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("patient_id", sa.BigInteger(), nullable=False),
        sa.Column("doctor_id", sa.BigInteger(), nullable=False),
        sa.Column("service_id", sa.BigInteger(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            _enum("appointment_status"),
            server_default=sa.text("'BOOKED'"),
            nullable=False,
        ),
        sa.Column("channel", _enum("channel"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("cancel_reason", sa.String(500), nullable=True),
        sa.Column("doctor_note", sa.String(1000), nullable=True),
        sa.Column(
            "needs_attention", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint("end_at > start_at", name=op.f("ck_appointments_time_order")),
        _fk("appointments", "patient_id", "users.id", "RESTRICT"),
        _fk("appointments", "doctor_id", "doctors.user_id", "RESTRICT"),
        _fk("appointments", "service_id", "services.id", "RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointments")),
        sa.UniqueConstraint("code", name=op.f("uq_appointments_code")),
    )
    # BR-01, BR-09 (ERD mục 5.1). Khoảng [) cho phép hai lịch sát nhau; lịch đã hủy, vắng mặt,
    # đã khám không nằm trong WHERE nên tự trả lại khung giờ. Vi phạm → SQLSTATE 23P01.
    op.execute(
        """
        ALTER TABLE appointments
          ADD CONSTRAINT excl_doctor_overlap EXCLUDE USING gist (
            doctor_id WITH =,
            tstzrange(start_at, end_at, '[)') WITH &&
          ) WHERE (status IN ('BOOKED', 'ARRIVED')),
          ADD CONSTRAINT excl_patient_overlap EXCLUDE USING gist (
            patient_id WITH =,
            tstzrange(start_at, end_at, '[)') WITH &&
          ) WHERE (status IN ('BOOKED', 'ARRIVED'))
        """
    )
    op.create_index(
        "ix_appointments_doctor_id_start_at", "appointments", ["doctor_id", "start_at"]
    )
    op.create_index(
        "ix_appointments_patient_id_start_at",
        "appointments",
        ["patient_id", sa.text("start_at DESC")],
    )
    op.create_index(
        "ix_appointments_needs_attention",
        "appointments",
        ["start_at"],
        postgresql_where=sa.text("needs_attention"),
    )

    op.create_table(
        "appointment_history",
        _id(),
        sa.Column("appointment_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("channel", _enum("channel"), nullable=False),
        sa.Column("action", _enum("history_action"), nullable=False),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        _created_at(),
        _fk("appointment_history", "appointment_id", "appointments.id", "RESTRICT"),
        _fk("appointment_history", "actor_id", "users.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointment_history")),
    )
    op.create_index(
        "ix_appointment_history_appointment_id_created_at",
        "appointment_history",
        ["appointment_id", "created_at"],
    )

    op.create_table(
        "reviews",
        _id(),
        sa.Column("appointment_id", sa.BigInteger(), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.String(500), nullable=True),
        _created_at(),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name=op.f("ck_reviews_rating")),
        _fk("reviews", "appointment_id", "appointments.id", "RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reviews")),
        sa.UniqueConstraint("appointment_id", name=op.f("uq_reviews_appointment_id")),
    )

    op.create_table(
        "notifications",
        _id(),
        sa.Column("appointment_id", sa.BigInteger(), nullable=False),
        sa.Column("type", _enum("notification_type"), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column(
            "status",
            _enum("notification_status"),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        _fk("notifications", "appointment_id", "appointments.id", "RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(
        "uq_notifications_reminder",
        "notifications",
        ["appointment_id", "type"],
        unique=True,
        postgresql_where=sa.text("type = 'REMINDER'"),
    )
    op.create_index(
        "ix_notifications_pending",
        "notifications",
        ["scheduled_at"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )

    # ------------------------------------------------------------------ AI Agent
    op.create_table(
        "conversations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("patient_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "last_message_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        _created_at(),
        _fk("conversations", "patient_id", "users.id", "RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    op.create_index(
        "ix_conversations_patient_id_last_message_at",
        "conversations",
        ["patient_id", sa.text("last_message_at DESC")],
    )

    op.create_table(
        "messages",
        _id(),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("role", _enum("message_role"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        _created_at(),
        _fk("messages", "conversation_id", "conversations.id", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index(
        "ix_messages_conversation_id_created_at", "messages", ["conversation_id", "created_at"]
    )

    op.create_table(
        "agent_proposals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("type", _enum("proposal_type"), nullable=False),
        sa.Column("appointment_id", sa.BigInteger(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "status", _enum("proposal_status"), server_default=sa.text("'PENDING'"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "type = 'BOOK' OR appointment_id IS NOT NULL",
            name=op.f("ck_agent_proposals_appointment_required"),
        ),
        _fk("agent_proposals", "conversation_id", "conversations.id", "CASCADE"),
        _fk("agent_proposals", "appointment_id", "appointments.id", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_proposals")),
    )
    op.create_index("ix_agent_proposals_conversation_id", "agent_proposals", ["conversation_id"])
    op.create_index(
        "ix_agent_proposals_pending_expires_at",
        "agent_proposals",
        ["expires_at"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )

    op.create_table(
        "tool_call_logs",
        _id(),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("tool_name", sa.String(50), nullable=False),
        sa.Column("args", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        _created_at(),
        _fk("tool_call_logs", "conversation_id", "conversations.id", "CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_call_logs")),
    )
    op.create_index(
        "ix_tool_call_logs_conversation_id_created_at",
        "tool_call_logs",
        ["conversation_id", "created_at"],
    )
    op.create_index("ix_tool_call_logs_tool_name", "tool_call_logs", ["tool_name"])

    op.create_table(
        "support_requests",
        _id(),
        sa.Column("patient_id", sa.BigInteger(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "status", _enum("support_status"), server_default=sa.text("'OPEN'"), nullable=False
        ),
        sa.Column("handled_by", sa.BigInteger(), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _fk("support_requests", "patient_id", "users.id", "RESTRICT"),
        _fk("support_requests", "conversation_id", "conversations.id", "SET NULL"),
        _fk("support_requests", "handled_by", "users.id", "RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_requests")),
    )
    op.create_index(
        "ix_support_requests_conversation_id", "support_requests", ["conversation_id"]
    )


def downgrade() -> None:
    for table in (
        "support_requests",
        "tool_call_logs",
        "agent_proposals",
        "messages",
        "conversations",
        "notifications",
        "reviews",
        "appointment_history",
        "appointments",
        "time_offs",
        "shifts",
        "doctor_services",
        "services",
        "refresh_tokens",
        "doctors",
        "patient_profiles",
        "specialties",
        "users",
    ):
        op.drop_table(table)
    bind = op.get_bind()
    for name in reversed(list(ENUMS)):
        postgresql.ENUM(name=name).drop(bind)
    # Giữ extension btree_gist, unaccent: có thể đang được dùng ngoài schema này.
