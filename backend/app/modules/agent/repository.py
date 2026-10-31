"""Truy vấn database của module agent (SQLAlchemy). Không ra quyết định nghiệp vụ."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import MessageRole, ProposalStatus
from app.db.models.agent import AgentProposal, Conversation, Message, ToolCallLog

# Khóa advisory theo bệnh nhân khi đếm hạn mức (namespace riêng của module agent).
_QUOTA_LOCK = 4_217


async def lock_quota(session: AsyncSession, patient_id: int) -> None:
    """Hai lượt chat đồng thời của cùng bệnh nhân không cùng đếm thấy 49 rồi cùng vượt 50."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:ns, :key)"),
        {"ns": _QUOTA_LOCK, "key": patient_id % 2_147_483_647},
    )


async def get_conversation(
    session: AsyncSession, conversation_id: uuid.UUID
) -> Conversation | None:
    return await session.get(Conversation, conversation_id)


def add_conversation(session: AsyncSession, patient_id: int, now: datetime) -> Conversation:
    conversation = Conversation(
        id=uuid.uuid4(), patient_id=patient_id, created_at=now, last_message_at=now
    )
    session.add(conversation)
    return conversation


async def count_user_messages(session: AsyncSession, patient_id: int, since: datetime) -> int:
    """Tin nhắn USER của bệnh nhân từ `since` (00:00 hôm nay, giờ Việt Nam) — FR-AGT-09."""
    stmt = (
        select(func.count())
        .select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.patient_id == patient_id,
            Message.role == MessageRole.USER,
            Message.created_at >= since,
        )
    )
    return (await session.execute(stmt)).scalar_one()


def add_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    role: MessageRole,
    content: str,
    now: datetime,
) -> Message:
    message = Message(conversation_id=conversation_id, role=role, content=content, created_at=now)
    session.add(message)
    return message


async def touch_conversation(
    session: AsyncSession, conversation_id: uuid.UUID, now: datetime
) -> None:
    await session.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(last_message_at=func.greatest(Conversation.last_message_at, now))
    )


async def recent_messages(
    session: AsyncSession, conversation_id: uuid.UUID, limit: int
) -> list[Message]:
    """`limit` dòng gần nhất, xếp lại theo thời gian tăng dần (docs mục 6.5)."""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    rows = list((await session.execute(stmt)).scalars())
    rows.reverse()
    return rows


def add_tool_log(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    tool_name: str,
    args: dict[str, Any],
    result: dict[str, Any],
    success: bool,
    latency_ms: int,
    now: datetime,
) -> None:
    session.add(
        ToolCallLog(
            conversation_id=conversation_id,
            tool_name=tool_name,
            args=args,
            result=result,
            success=success,
            latency_ms=latency_ms,
            created_at=now,
        )
    )


# ---------------------------------------------------------------------------- đề xuất
async def proposal_owner(session: AsyncSession, proposal_id: uuid.UUID) -> int | None:
    """Bệnh nhân chủ hội thoại của đề xuất, đọc không khóa (kiểm quyền trước khi khóa)."""
    stmt = (
        select(Conversation.patient_id)
        .join(AgentProposal, AgentProposal.conversation_id == Conversation.id)
        .where(AgentProposal.id == proposal_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def lock_proposal(
    session: AsyncSession, proposal_id: uuid.UUID
) -> tuple[AgentProposal, int] | None:
    """Khóa đề xuất `FOR UPDATE` (bấm đúp chờ nhau), kèm bệnh nhân chủ hội thoại."""
    stmt = (
        select(AgentProposal, Conversation.patient_id)
        .join(Conversation, Conversation.id == AgentProposal.conversation_id)
        .where(AgentProposal.id == proposal_id)
        .with_for_update(of=AgentProposal)
        .execution_options(populate_existing=True)
    )
    row = (await session.execute(stmt)).first()
    return (row[0], row[1]) if row else None


async def proposals_of(
    session: AsyncSession, conversation_id: uuid.UUID
) -> dict[uuid.UUID, AgentProposal]:
    stmt = select(AgentProposal).where(AgentProposal.conversation_id == conversation_id)
    return {p.id: p for p in (await session.execute(stmt)).scalars()}


async def expire_pending(session: AsyncSession, conversation_id: uuid.UUID, now: datetime) -> None:
    """Mỗi hội thoại chỉ một đề xuất đang chờ: đề xuất mới thay thế đề xuất cũ (docs mục 6.4)."""
    await session.execute(
        update(AgentProposal)
        .where(
            AgentProposal.conversation_id == conversation_id,
            AgentProposal.status == ProposalStatus.PENDING,
        )
        .values(status=ProposalStatus.EXPIRED, decided_at=now)
    )


async def expire_due(session: AsyncSession, now: datetime) -> int:
    """Job: đề xuất PENDING đã quá hạn chuyển sang EXPIRED (docs mục 10.5)."""
    result = await session.execute(
        update(AgentProposal)
        .where(AgentProposal.status == ProposalStatus.PENDING, AgentProposal.expires_at <= now)
        .values(status=ProposalStatus.EXPIRED, decided_at=now)
    )
    return int(getattr(result, "rowcount", 0) or 0)


async def purge_conversations(session: AsyncSession, before: datetime) -> int:
    """Xóa hội thoại không hoạt động từ trước `before`; tin nhắn, đề xuất, log tool xóa theo
    (CASCADE), yêu cầu hỗ trợ giữ lại nhưng bỏ liên kết (docs mục 7.7)."""
    result = await session.execute(
        delete(Conversation).where(Conversation.last_message_at < before)
    )
    return int(getattr(result, "rowcount", 0) or 0)


async def messages_of(
    session: AsyncSession, conversation_id: uuid.UUID, limit: int
) -> Sequence[Message]:
    """`limit` dòng gần nhất để tải lại khung chat, theo thời gian tăng dần."""
    return await recent_messages(session, conversation_id, limit)
