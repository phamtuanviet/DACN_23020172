"""Model ORM nhóm agent: conversations, messages, agent_proposals, tool_call_logs, support_requests.

Cột, ràng buộc, chỉ mục theo ERD và docs mục 7.4.
"""

import uuid
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
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin
from app.db.enums import MessageRole, ProposalStatus, ProposalType, SupportStatus


class Conversation(CreatedAtMixin, Base):
    """Phiên chat; id là UUID vì lộ ra giao diện (ERD mục 6)."""

    __tablename__ = "conversations"
    __table_args__ = (
        # Bổ sung ở docs mục 7.4: đếm hạn mức tin nhắn, mở lại hội thoại gần nhất
        Index(
            "ix_conversations_patient_id_last_message_at",
            "patient_id",
            text("last_message_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Message(CreatedAtMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, name="message_role"))
    content: Mapped[str] = mapped_column(Text)


class AgentProposal(CreatedAtMixin, Base):
    """Đề xuất đặt/đổi/hủy chờ bệnh nhân xác nhận (BR-06)."""

    __tablename__ = "agent_proposals"
    __table_args__ = (
        # Đổi, hủy phải chỉ rõ lịch nào; BOOK gán lịch sau khi xác nhận thành công
        CheckConstraint("type = 'BOOK' OR appointment_id IS NOT NULL", name="appointment_required"),
        # FK có chỉ mục để job dọn hội thoại cũ (CASCADE) không quét tuần tự cả bảng
        Index("ix_agent_proposals_conversation_id", "conversation_id"),
        Index(
            "ix_agent_proposals_pending_expires_at",
            "expires_at",
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    type: Mapped[ProposalType] = mapped_column(Enum(ProposalType, name="proposal_type"))
    appointment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("appointments.id", ondelete="SET NULL")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[ProposalStatus] = mapped_column(
        Enum(ProposalStatus, name="proposal_status"), server_default=text("'PENDING'")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ToolCallLog(CreatedAtMixin, Base):
    """Log mỗi lần Agent gọi tool, phục vụ đánh giá (FR-AGT-08)."""

    __tablename__ = "tool_call_logs"
    __table_args__ = (
        Index("ix_tool_call_logs_conversation_id_created_at", "conversation_id", "created_at"),
        Index("ix_tool_call_logs_tool_name", "tool_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    tool_name: Mapped[str] = mapped_column(String(50))
    args: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    success: Mapped[bool] = mapped_column(Boolean)
    latency_ms: Mapped[int] = mapped_column(Integer)


class SupportRequest(CreatedAtMixin, Base):
    """Yêu cầu chuyển sang nhân viên từ Agent (FR-AGT-07)."""

    __tablename__ = "support_requests"
    __table_args__ = (Index("ix_support_requests_conversation_id", "conversation_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    patient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    summary: Mapped[str] = mapped_column(Text)
    status: Mapped[SupportStatus] = mapped_column(
        Enum(SupportStatus, name="support_status"), server_default=text("'OPEN'")
    )
    handled_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
