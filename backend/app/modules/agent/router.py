"""HTTP của module agent: khai báo endpoint, nhận DTO, tạo Actor, gọi service.

Không chứa nghiệp vụ, không truy vấn database (docs mục 4.2). Chỉ bệnh nhân dùng Agent; quyền
trên từng hội thoại, đề xuất kiểm ở service. Không có endpoint nào cho LLM ghi lịch: lịch chỉ đổi
qua `/agent/proposals/{id}/confirm` mà giao diện gọi bằng JWT của bệnh nhân (docs mục 6.4, 6.6).
"""

import uuid
from collections.abc import AsyncIterable
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.core.db import SessionDep
from app.core.ratelimit import APPOINTMENT_WRITE_LIMIT, limiter, user_or_ip
from app.core.security import ClockDep, PatientActorDep, SettingsDep
from app.modules.agent.llm import ChatModel, ChatModelDep
from app.modules.agent.proposals import ProposalService
from app.modules.agent.schemas import (
    AgentStatus,
    ChatRequest,
    ConfirmOut,
    ConversationOut,
    ProposalOut,
)
from app.modules.agent.service import ChatService, Turn

router = APIRouter(prefix="/agent", tags=["agent"])


def get_chat_service(session: SessionDep, clock: ClockDep, settings: SettingsDep) -> ChatService:
    return ChatService(session, clock, settings)


def get_proposal_service(
    session: SessionDep, clock: ClockDep, settings: SettingsDep
) -> ProposalService:
    return ProposalService(session, clock, settings)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
ProposalServiceDep = Annotated[ProposalService, Depends(get_proposal_service)]


@dataclass(frozen=True)
class PreparedTurn:
    service: ChatService
    turn: Turn
    model: ChatModel


async def prepare_turn(
    body: ChatRequest, actor: PatientActorDep, service: ChatServiceDep, model: ChatModelDep
) -> PreparedTurn:
    """Kiểm tra và lưu tin nhắn trước khi mở luồng SSE, để lỗi trả đúng mã HTTP."""
    turn = await service.start_turn(actor, body, model)
    assert model is not None  # start_turn đã trả 503 khi chưa cấu hình mô hình
    return PreparedTurn(service, turn, model)


@router.get("/status")
async def agent_status(
    actor: PatientActorDep, service: ChatServiceDep, model: ChatModelDep
) -> AgentStatus:
    return await service.status(actor, model_ready=model is not None)


@router.post("/chat", response_class=EventSourceResponse)
async def chat(
    prepared: Annotated[PreparedTurn, Depends(prepare_turn)],
) -> AsyncIterable[ServerSentEvent]:
    """Gửi tin nhắn, nhận phản hồi dạng SSE: meta, token, tool, services, slots, proposal, error,
    done (docs mục 8.4). 429 AGENT_QUOTA_EXCEEDED khi hết 50 tin nhắn trong ngày, 503
    AGENT_UNAVAILABLE khi trợ lý tạm ngưng."""
    async for event in prepared.service.stream(prepared.turn, prepared.model):
        yield event


@router.get("/conversations/{conversation_id}/messages")
async def conversation_messages(
    conversation_id: uuid.UUID, actor: PatientActorDep, service: ChatServiceDep
) -> ConversationOut:
    return await service.history(actor, conversation_id)


@router.post("/proposals/{proposal_id}/confirm")
@limiter.limit(APPOINTMENT_WRITE_LIMIT, key_func=user_or_ip)
async def confirm_proposal(
    request: Request,
    proposal_id: uuid.UUID,
    actor: PatientActorDep,
    service: ProposalServiceDep,
) -> ConfirmOut:
    """Bệnh nhân bấm Xác nhận trên thẻ. Thất bại thì trả nguyên mã lỗi của web (SLOT_TAKEN kèm
    khung thay thế, CHANGE_DEADLINE_PASSED…) với `details.proposal_status`."""
    return await service.confirm(actor, proposal_id)


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: uuid.UUID, actor: PatientActorDep, service: ProposalServiceDep
) -> ProposalOut:
    return await service.reject(actor, proposal_id)
