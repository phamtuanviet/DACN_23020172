"""Truy vấn database của module support (SQLAlchemy). Không ra quyết định nghiệp vụ."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import SupportStatus
from app.db.models.agent import Conversation, SupportRequest


async def open_request(
    session: AsyncSession, patient_id: int, conversation_id: uuid.UUID | None
) -> SupportRequest | None:
    """Yêu cầu còn mở của bệnh nhân trong cùng hội thoại (tránh tạo trùng khi bấm nhiều lần)."""
    stmt = (
        select(SupportRequest)
        .where(
            SupportRequest.patient_id == patient_id,
            SupportRequest.conversation_id == conversation_id,
            SupportRequest.status == SupportStatus.OPEN,
        )
        .order_by(SupportRequest.id.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def conversation_owner(session: AsyncSession, conversation_id: uuid.UUID) -> int | None:
    """Chủ hội thoại, để kiểm quyền lớp 2 (chỉ đọc bảng của module agent, không ghi)."""
    stmt = select(Conversation.patient_id).where(Conversation.id == conversation_id)
    return (await session.execute(stmt)).scalar_one_or_none()
