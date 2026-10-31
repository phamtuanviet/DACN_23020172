"""Một lượt chat với Agent: hạn mức, lưu tin nhắn, chạy đồ thị, phát SSE (docs mục 6.1, 8.4).

Không biết về HTTP; nhận `Actor`. Lượt chat không giữ kết nối database trong lúc chờ LLM: mỗi bước
đọc, ghi mở một session ngắn rồi trả kết nối ngay (docs mục 11.2).
"""

import asyncio
import time as perf
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, time

import anthropic
import anyio
import httpx
import openai
import structlog
from fastapi.sse import ServerSentEvent
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import get_sessionmaker
from app.core.errors import forbidden, not_found
from app.core.timeutil import local_datetime, to_local
from app.db.enums import MessageRole, UserRole
from app.db.models.agent import AgentProposal, Conversation, Message
from app.modules.agent import repository as repo
from app.modules.agent.graph import Event, run_graph
from app.modules.agent.guard import Guard, agent_unavailable, quota_exceeded
from app.modules.agent.llm import ChatModel, system_message
from app.modules.agent.memory import HISTORY_LIMIT, parse_tool_row, rebuild
from app.modules.agent.prompts import PROMPT_VERSION
from app.modules.agent.proposals import proposal_out
from app.modules.agent.schemas import (
    AgentStatus,
    ChatItem,
    ChatRequest,
    ConversationOut,
    DoneEvent,
    ErrorEvent,
    MetaEvent,
    ServiceOption,
    ToolStatus,
)
from app.modules.agent.tools import AgentContext, end_label
from app.modules.scheduling.schemas import SlotOption

log = structlog.get_logger(__name__)

HISTORY_ITEMS = 200  # tải lại khung chat: tối đa 200 dòng gần nhất
# Lượt giao diện tự gửi: nội dung do backend đặt, không lấy chữ từ request (docs mục 6.4).
TRIGGER_TEXTS = {
    "proposal_failed": "Khung giờ trong đề xuất vừa có người khác đặt nên chưa đặt được. "
    "Bạn tìm giúp mình khung trống khác gần nhất nhé.",
}
TIMEOUT_MESSAGE = (
    "Trợ lý phản hồi quá lâu nên đã dừng. Bạn thử lại, hoặc đặt lịch trên trang Đặt lịch."
)
UNAVAILABLE_MESSAGE = (
    "Trợ lý đang gặp sự cố. Bạn thử lại sau ít phút, hoặc đặt lịch trên trang Đặt lịch."
)
# Lỗi của nhà cung cấp LLM (mạng, 429, 5xx…): tính vào ngắt mạch (docs mục 6.8).
PROVIDER_ERRORS = (openai.APIError, anthropic.APIError, httpx.HTTPError)


def _patient_id(actor: Actor) -> int:
    if actor.role is not UserRole.PATIENT or actor.user_id is None:
        raise forbidden()
    return actor.user_id


def _day_start(now: datetime) -> datetime:
    """00:00 hôm nay theo giờ Việt Nam: hạn mức tính theo ngày của phòng khám (FR-AGT-09)."""
    return local_datetime(to_local(now).date(), time(0))


def _sse(event: str, payload: BaseModel) -> ServerSentEvent:
    return ServerSentEvent(event=event, data=payload.model_dump(mode="json"))


async def _with_deadline(source: AsyncIterator[Event], seconds: float) -> AsyncIterator[Event]:
    """Lấy từng sự kiện nhưng dừng bằng TimeoutError khi quá hạn của cả lượt.

    Thời hạn chỉ bọc lần chờ sự kiện kế tiếp, không bọc `yield`: hủy theo thời hạn mà trúng lúc
    generator đang dừng ở `yield` sẽ hủy nhầm task phát SSE của FastAPI.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    iterator = aiter(source)
    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError
            try:
                event = await asyncio.wait_for(anext(iterator), remaining)
            except StopAsyncIteration:
                return
            yield event
    finally:
        # Dọn đồ thị kể cả khi bị hủy: dừng lần gọi LLM đang chạy thay vì để nó chạy ngầm.
        aclose = getattr(iterator, "aclose", None)
        if aclose is not None:
            with anyio.CancelScope(shield=True):
                await aclose()


@dataclass(frozen=True)
class Turn:
    patient_id: int
    conversation_id: uuid.UUID
    user_message_id: int
    remaining_quota: int


class ChatService:
    def __init__(self, session: AsyncSession, clock: Clock, settings: Settings) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings
        self._guard = Guard(settings)

    async def status(self, actor: Actor, *, model_ready: bool) -> AgentStatus:
        """Số tin nhắn còn lại hôm nay và trợ lý có đang nhận tin không, để khung chat hiện đúng
        trạng thái ngay khi mở."""
        patient_id = _patient_id(actor)
        now = self._clock.now()
        limit = self._settings.agent_daily_message_limit
        async with self._session.begin():
            used = await repo.count_user_messages(self._session, patient_id, _day_start(now))
        available = model_ready and await self._guard.is_open(now)
        return AgentStatus(
            available=available, daily_limit=limit, remaining_quota=max(limit - used, 0)
        )

    async def start_turn(self, actor: Actor, request: ChatRequest, model: ChatModel | None) -> Turn:
        """Bước 1–3 của một lượt (docs mục 6.1), chạy trước khi mở luồng SSE nên lỗi trả đúng mã
        HTTP: hội thoại của người khác 403, hết hạn mức 429, trợ lý tạm ngưng 503."""
        patient_id = _patient_id(actor)
        now = self._clock.now()
        if model is None:
            raise agent_unavailable()
        await self._guard.ensure_open(now)
        limit = self._settings.agent_daily_message_limit
        text = TRIGGER_TEXTS[request.trigger] if request.trigger else request.message
        async with self._session.begin():
            await repo.lock_quota(self._session, patient_id)
            conversation = await self._own_or_new(patient_id, request.conversation_id, now)
            used = await repo.count_user_messages(self._session, patient_id, _day_start(now))
            if used >= limit:
                raise quota_exceeded(limit)
            message = repo.add_message(self._session, conversation.id, MessageRole.USER, text, now)
            conversation.last_message_at = now
            await self._session.flush()
        return Turn(patient_id, conversation.id, message.id, limit - used - 1)

    async def _own_or_new(
        self, patient_id: int, conversation_id: uuid.UUID | None, now: datetime
    ) -> Conversation:
        if conversation_id is None:
            return repo.add_conversation(self._session, patient_id, now)
        conversation = await repo.get_conversation(self._session, conversation_id)
        if conversation is None:
            raise not_found("Không tìm thấy hội thoại.")
        if conversation.patient_id != patient_id:
            raise forbidden()
        return conversation

    async def stream(self, turn: Turn, model: ChatModel) -> AsyncIterator[ServerSentEvent]:
        """Bước 4–8: dựng ngữ cảnh, chạy đồ thị trong 30 giây, phát SSE, lưu câu trả lời."""
        yield _sse(
            "meta",
            MetaEvent(conversation_id=turn.conversation_id, user_message_id=turn.user_message_id),
        )
        sessions = get_sessionmaker()
        started = perf.perf_counter()
        async with sessions() as session, session.begin():
            rows = await repo.recent_messages(session, turn.conversation_id, HISTORY_LIMIT)
        messages = [system_message(self._clock.now(), self._settings), *rebuild(rows)]
        ctx = AgentContext(
            turn.patient_id, turn.conversation_id, self._clock, self._settings, sessions
        )
        parts: list[str] = []
        new_bubble = False
        first_token_ms: int | None = None
        error: ErrorEvent | None = None
        outcome = "cancelled"  # giữ nguyên nếu trình duyệt ngắt kết nối giữa chừng
        assistant_id: int | None = None
        try:
            events = run_graph(model, ctx, messages)
            async for name, payload in _with_deadline(events, self._settings.llm_timeout_s):
                if name == "token":
                    if first_token_ms is None:
                        first_token_ms = round((perf.perf_counter() - started) * 1000)
                    if new_bubble and parts:
                        parts.append("\n\n")
                    new_bubble = False
                    parts.append(getattr(payload, "text", ""))
                elif name == "tool":
                    new_bubble = True
                yield _sse(name, payload)
            outcome = "ok"
        except (TimeoutError, GraphRecursionError) as exc:
            # Quá hạn lúc đang chờ nhà cung cấp thì tính như một lần nhà cung cấp lỗi.
            outcome = "provider_timeout" if ctx.usage.pending_input else "timeout"
            log.warning("agent.turn_stopped", cause=type(exc).__name__)
            error = ErrorEvent(code="AGENT_TIMEOUT", message=TIMEOUT_MESSAGE)
        except PROVIDER_ERRORS as exc:  # không chép nội dung lỗi vào log
            outcome = "provider_error"
            log.warning("agent.llm_error", error=type(exc).__name__)
            error = ErrorEvent(code="AGENT_UNAVAILABLE", message=UNAVAILABLE_MESSAGE)
        except Exception as exc:  # lỗi của chính hệ thống: không tính vào ngắt mạch
            outcome = "crashed"
            log.error("agent.turn_crashed", error=type(exc).__name__)
            error = ErrorEvent(code="AGENT_UNAVAILABLE", message=UNAVAILABLE_MESSAGE)
        finally:
            # Chạy cả khi trình duyệt ngắt kết nối (task phát SSE bị hủy): chi phí của mọi lần
            # gọi LLM đã tốn vẫn vào trần ngày, chữ đã gửi đi vẫn được lưu (docs mục 6.8).
            with anyio.CancelScope(shield=True):
                assistant_id = await self._settle(turn, ctx, "".join(parts).strip(), outcome)
                log.info(
                    "agent.turn",
                    conversation_id=str(turn.conversation_id),
                    outcome=outcome,
                    first_token_ms=first_token_ms,
                    total_ms=round((perf.perf_counter() - started) * 1000),
                    llm_calls=ctx.usage.llm_calls,
                    tool_calls=ctx.tool_calls,
                    input_tokens=ctx.usage.input_tokens,
                    output_tokens=ctx.usage.output_tokens,
                    model=self._settings.llm_model,
                    prompt_version=PROMPT_VERSION,
                )
        if error is not None:
            yield _sse("error", error)
        yield _sse(
            "done",
            DoneEvent(assistant_message_id=assistant_id, remaining_quota=turn.remaining_quota),
        )

    async def _settle(self, turn: Turn, ctx: AgentContext, text: str, outcome: str) -> int | None:
        """Cuối lượt: cập nhật ngắt mạch, cộng chi phí (cả lần gọi dở dang), lưu câu trả lời."""
        if outcome in ("provider_error", "provider_timeout"):
            await self._guard.record_failure()
        elif outcome in ("ok", "timeout"):
            await self._guard.record_success()
        ctx.usage.settle_pending()
        await self._guard.charge(ctx.usage, self._clock.now())
        return await self._save_answer(turn.conversation_id, text)

    async def _save_answer(self, conversation_id: uuid.UUID, text: str) -> int | None:
        if not text:
            return None
        now = self._clock.now()
        async with get_sessionmaker()() as session, session.begin():
            message = repo.add_message(session, conversation_id, MessageRole.ASSISTANT, text, now)
            await repo.touch_conversation(session, conversation_id, now)
            await session.flush()
            return message.id

    # ------------------------------------------------------------ tải lại hội thoại
    async def history(self, actor: Actor, conversation_id: uuid.UUID) -> ConversationOut:
        """Tin nhắn, trạng thái tool, nút khung giờ và thẻ đề xuất với trạng thái hiện tại, để
        mở lại trang vẫn thấy đúng hội thoại (docs mục 9.5). Chỉ chủ hội thoại."""
        patient_id = _patient_id(actor)
        now = self._clock.now()
        limit = self._settings.agent_daily_message_limit
        async with self._session.begin():
            conversation = await repo.get_conversation(self._session, conversation_id)
            if conversation is None:
                raise not_found("Không tìm thấy hội thoại.")
            if conversation.patient_id != patient_id:
                raise forbidden()
            rows = await repo.messages_of(self._session, conversation_id, HISTORY_ITEMS)
            proposals = await repo.proposals_of(self._session, conversation_id)
            used = await repo.count_user_messages(self._session, patient_id, _day_start(now))
        # Thông báo "Đã đặt lịch…" ghi lúc xác nhận đã hiện trên chính thẻ đề xuất.
        notices = {(p.payload.get("result") or {}).get("message_id") for p in proposals.values()}
        items = [
            item
            for row in rows
            if row.id not in notices
            for item in [_item(row, proposals, now)]
            if item is not None
        ]
        return ConversationOut(
            id=conversation.id, items=items, remaining_quota=max(limit - used, 0)
        )


def _item(
    row: Message, proposals: dict[uuid.UUID, AgentProposal], now: datetime
) -> ChatItem | None:
    created_at = to_local(row.created_at)
    if row.role is MessageRole.USER:
        hidden = row.content in TRIGGER_TEXTS.values()
        return ChatItem(
            id=row.id, kind="user", created_at=created_at, text=row.content, hidden=hidden
        )
    if row.role is MessageRole.ASSISTANT:
        return ChatItem(id=row.id, kind="assistant", created_at=created_at, text=row.content)
    data = parse_tool_row(row.content)
    if data is None:
        return None
    name, args, result = str(data["name"]), data.get("args") or {}, data["result"]
    ok = "error" not in result
    item = ChatItem(
        id=row.id,
        kind="tool",
        created_at=created_at,
        tool=ToolStatus(name=name, status="end", label=end_label(name, args, result), ok=ok),
    )
    if not ok:
        return item
    try:
        if name == "search_services":
            item.services = [ServiceOption.model_validate(s) for s in result.get("services", [])]
        elif name == "find_available_slots":
            slots = result.get("slots") or result.get("alternatives") or []
            item.slots = [SlotOption.model_validate(s) for s in slots]
        elif name == "propose_booking":
            proposal = proposals.get(uuid.UUID(str(result.get("proposal_id"))))
            item.proposal = proposal_out(proposal, now) if proposal else None
    except (ValidationError, ValueError):
        log.warning("agent.bad_tool_row", message_id=row.id)
    return item
