"""Truy vấn database của module support (SQLAlchemy). Không ra quyết định nghiệp vụ."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.enums import SupportStatus
from app.db.models.agent import Conversation, SupportRequest
from app.db.models.users import User

MAX_LISTED = 200


@dataclass(frozen=True, slots=True)
class SupportRow:
    request: SupportRequest
    patient_name: str
    patient_phone: str | None
    patient_email: str
    handled_by: str | None


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


async def list_requests(
    session: AsyncSession, *, status: SupportStatus | None, request_id: int | None = None
) -> list[SupportRow]:
    """Hàng chờ của quản trị: yêu cầu đang mở cũ nhất trước (xử lý theo thứ tự đến), đã xử lý
    thì mới nhất trước."""
    handler = aliased(User, name="handler")
    stmt = (
        select(SupportRequest, User.full_name, User.phone, User.email, handler.full_name)
        .join(User, User.id == SupportRequest.patient_id)
        .outerjoin(handler, handler.id == SupportRequest.handled_by)
        .limit(MAX_LISTED)
    )
    if status is not None:
        stmt = stmt.where(SupportRequest.status == status)
    if request_id is not None:
        stmt = stmt.where(SupportRequest.id == request_id)
    if status is SupportStatus.OPEN:
        stmt = stmt.order_by(SupportRequest.created_at, SupportRequest.id)
    else:
        stmt = stmt.order_by(SupportRequest.created_at.desc(), SupportRequest.id.desc())
    rows = (await session.execute(stmt)).all()
    return [SupportRow(*row) for row in rows]


async def lock_request(session: AsyncSession, request_id: int) -> SupportRequest | None:
    stmt = (
        select(SupportRequest)
        .where(SupportRequest.id == request_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()
