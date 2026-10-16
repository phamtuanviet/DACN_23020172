"""Model ORM nhóm appointments.

Bảng: appointments (kèm 2 exclusion constraint), appointment_history, reviews, notifications.

Cột, ràng buộc, chỉ mục theo ERD và docs mục 7.4.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin
from app.db.enums import (
    AppointmentStatus,
    Channel,
    HistoryAction,
    NotificationStatus,
    NotificationType,
)

# Lịch Đã đặt, Đã đến mới giữ khung giờ; Đã hủy, Vắng mặt, Đã khám tự trả lại khung (ERD mục 5.1).
ACTIVE_STATUSES_SQL = "status IN ('BOOKED', 'ARRIVED')"
TIME_RANGE_SQL = "tstzrange(start_at, end_at, '[)')"


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="time_order"),
        # BR-01: một bác sĩ không có hai lịch chồng thời gian
        ExcludeConstraint(
            ("doctor_id", "="),
            (text(TIME_RANGE_SQL), "&&"),
            name="excl_doctor_overlap",
            using="gist",
            where=text(ACTIVE_STATUSES_SQL),
        ),
        # BR-09: một bệnh nhân không có hai lịch trùng giờ
        ExcludeConstraint(
            ("patient_id", "="),
            (text(TIME_RANGE_SQL), "&&"),
            name="excl_patient_overlap",
            using="gist",
            where=text(ACTIVE_STATUSES_SQL),
        ),
        Index("ix_appointments_doctor_id_start_at", "doctor_id", "start_at"),
        Index("ix_appointments_patient_id_start_at", "patient_id", text("start_at DESC")),
        Index(
            "ix_appointments_needs_attention",
            "start_at",
            postgresql_where=text("needs_attention"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)  # LH-YYMMDD-XXXX
    patient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))
    doctor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("doctors.user_id", ondelete="RESTRICT")
    )
    service_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("services.id", ondelete="RESTRICT")
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointment_status"), server_default=text("'BOOKED'")
    )
    channel: Mapped[Channel] = mapped_column(Enum(Channel, name="channel"))
    reason: Mapped[str | None] = mapped_column(String(500))
    cancel_reason: Mapped[str | None] = mapped_column(String(500))
    doctor_note: Mapped[str | None] = mapped_column(String(1000))
    needs_attention: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class AppointmentHistory(CreatedAtMixin, Base):
    """Nhật ký mọi thay đổi của lịch hẹn: ai, khi nào, kênh nào, cũ → mới (FR-APT-05)."""

    __tablename__ = "appointment_history"
    __table_args__ = (
        Index("ix_appointment_history_appointment_id_created_at", "appointment_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("appointments.id", ondelete="RESTRICT")
    )
    actor_id: Mapped[int | None] = mapped_column(  # NULL = tác vụ hệ thống
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    channel: Mapped[Channel] = mapped_column(Enum(Channel, name="channel"))
    action: Mapped[HistoryAction] = mapped_column(Enum(HistoryAction, name="history_action"))
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Review(CreatedAtMixin, Base):
    """Đánh giá sau khám (P2); bác sĩ suy ra qua lịch hẹn."""

    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="rating"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("appointments.id", ondelete="RESTRICT"), unique=True
    )
    rating: Mapped[int] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(String(500))


class Notification(Base):
    """Hàng đợi và nhật ký email (P1)."""

    __tablename__ = "notifications"
    __table_args__ = (
        # Mỗi lịch chỉ nhắc một lần (FR-NTF-02)
        Index(
            "uq_notifications_reminder",
            "appointment_id",
            "type",
            unique=True,
            postgresql_where=text("type = 'REMINDER'"),
        ),
        Index(
            "ix_notifications_pending",
            "scheduled_at",
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("appointments.id", ondelete="RESTRICT")
    )
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType, name="notification_type"))
    recipient_email: Mapped[str] = mapped_column(String(255))
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status"), server_default=text("'PENDING'")
    )
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
