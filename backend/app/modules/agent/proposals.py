"""Tạo, xác nhận, từ chối đề xuất; xác nhận chỉ đến từ giao diện (docs mục 6.4, BR-06).

LLM chỉ tạo được đề xuất (tool `propose_booking`). Lịch hẹn chỉ thay đổi khi bệnh nhân bấm Xác nhận
trên thẻ: endpoint confirm có JWT của bệnh nhân, khóa đề xuất, rồi gọi đúng service của web với
Actor kênh AGENT, nên mọi kiểm tra ở mục 5.4 chạy lại từ đầu (AC-12).
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import outer_transaction
from app.core.errors import AppError, field_error, forbidden, not_found, validation_error
from app.core.timeutil import format_when, to_local
from app.core.validation import MAX_ID
from app.db.enums import Channel, MessageRole, ProposalStatus, ProposalType, UserRole
from app.db.models.agent import AgentProposal
from app.modules.agent import repository as repo
from app.modules.agent.schemas import ConfirmOut, ProposalDisplay, ProposalOut
from app.modules.appointments.schemas import (
    AppointmentOut,
    BookRequest,
    CancelRequest,
    RescheduleRequest,
    SlotStart,
)
from app.modules.appointments.service import AppointmentService, Preview

log = structlog.get_logger(__name__)

TYPE_LABELS = {
    ProposalType.BOOK: "đặt lịch",
    ProposalType.RESCHEDULE: "đổi lịch",
    ProposalType.CANCEL: "hủy lịch",
}


# ---------------------------------------------------------------------------- lỗi
def proposal_not_found() -> AppError:
    return not_found("Không tìm thấy đề xuất.")


def proposal_expired() -> AppError:
    return AppError(
        "PROPOSAL_EXPIRED",
        "Đề xuất đã hết hạn nên chưa có gì thay đổi. Bạn nhắn trợ lý để tìm lại khung giờ.",
        status=409,
        details={"proposal_status": ProposalStatus.EXPIRED.value},
    )


def proposal_not_pending(status: ProposalStatus) -> AppError:
    return AppError(
        "PROPOSAL_NOT_PENDING",
        "Đề xuất này đã được xử lý trước đó.",
        status=409,
        details={"proposal_status": status.value},
    )


# ---------------------------------------------------------------------------- tham số của tool
class ProposeArgs(BaseModel):
    """Tham số của tool `propose_booking` do LLM điền; danh tính bệnh nhân không nằm ở đây."""

    action: Literal["BOOK", "RESCHEDULE", "CANCEL"] = Field(
        description="BOOK: đặt mới; RESCHEDULE: đổi giờ một lịch đang có; CANCEL: hủy một lịch"
    )
    service_id: int | None = Field(
        default=None, ge=1, le=MAX_ID, description="BOOK: id dịch vụ từ search_services"
    )
    doctor_id: int | None = Field(
        default=None,
        ge=1,
        le=MAX_ID,
        description="BOOK, RESCHEDULE: doctor_id của khung đã chọn trong find_available_slots",
    )
    start_at: SlotStart | None = Field(
        default=None,
        description="BOOK, RESCHEDULE: start_at của khung đã chọn, chép nguyên từ "
        "find_available_slots (ISO 8601 có +07:00)",
    )
    reason: str | None = Field(
        default=None, max_length=500, description="BOOK: lý do khám người dùng đã nói, nếu có"
    )
    appointment_id: int | None = Field(
        default=None,
        ge=1,
        le=MAX_ID,
        description="RESCHEDULE, CANCEL: id lịch lấy từ get_my_appointments",
    )
    cancel_reason: str | None = Field(
        default=None, max_length=500, description="CANCEL: lý do hủy người dùng đã nói, nếu có"
    )

    @model_validator(mode="after")
    def _required_by_action(self) -> "ProposeArgs":
        required = {
            "BOOK": ("service_id", "doctor_id", "start_at"),
            "RESCHEDULE": ("appointment_id", "doctor_id", "start_at"),
            "CANCEL": ("appointment_id",),
        }[self.action]
        missing = [name for name in required if getattr(self, name) is None]
        if missing:
            raise ValueError(f"{self.action} cần thêm: {', '.join(missing)}.")
        return self


# ---------------------------------------------------------------------------- chuyển đổi
def _display(kind: ProposalType, preview: Preview, reason: str | None) -> ProposalDisplay:
    display = ProposalDisplay(
        service=preview.service_name,
        doctor=preview.doctor_name,
        when=format_when(preview.start_at, preview.end_at),
        reason=reason,
        code=preview.code,
    )
    if kind is ProposalType.RESCHEDULE and preview.old_start_at and preview.old_end_at:
        display.old_when = format_when(preview.old_start_at, preview.old_end_at)
        if preview.old_doctor_name and preview.old_doctor_name != preview.doctor_name:
            display.old_doctor = preview.old_doctor_name
    return display


def proposal_out(proposal: AgentProposal, now: datetime | None = None) -> ProposalOut:
    """`now`: đề xuất PENDING đã quá hạn (job chưa kịp chạy) hiện là EXPIRED."""
    payload = proposal.payload
    result: dict[str, Any] = payload.get("result") or {}
    status = proposal.status
    if status is ProposalStatus.PENDING and now is not None and now >= proposal.expires_at:
        status = ProposalStatus.EXPIRED
    return ProposalOut(
        id=proposal.id,
        type=proposal.type,
        status=status,
        expires_at=to_local(proposal.expires_at),
        display=ProposalDisplay.model_validate(payload["display"]),
        appointment_id=proposal.appointment_id,
        appointment_code=result.get("code"),
        error=result.get("error"),
    )


def _notice(proposal: AgentProposal, appointment: AppointmentOut) -> str:
    """Tin ASSISTANT ghi vào hội thoại sau khi xác nhận (UC09 bước 9), không tốn lượt gọi LLM."""
    when = format_when(appointment.start_at, appointment.end_at)
    if proposal.type is ProposalType.BOOK:
        return (
            f"Đã đặt lịch {appointment.code}: {appointment.service.name}, "
            f"{appointment.doctor.name}, {when}. Bạn xem lại trong Lịch của tôi."
        )
    if proposal.type is ProposalType.RESCHEDULE:
        return (
            f"Đã đổi lịch {appointment.code} sang {when}, {appointment.doctor.name}. "
            "Mã lịch giữ nguyên."
        )
    return f"Đã hủy lịch {appointment.code} ({appointment.service.name}, {when})."


# ---------------------------------------------------------------------------- service
class ProposalService:
    def __init__(self, session: AsyncSession, clock: Clock, settings: Settings) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings

    async def create(
        self, actor: Actor, conversation_id: uuid.UUID, args: ProposeArgs
    ) -> ProposalOut:
        """Kiểm tra trước như khi ghi thật (khung còn trống, BR-07, BR-08, BR-09, lịch thuộc
        bệnh nhân) rồi lưu đề xuất PENDING hết hạn sau 10 phút; không đạt thì ném lỗi cho LLM
        thay vì hiện thẻ chắc chắn thất bại (docs mục 6.3). Đề xuất cũ đang chờ bị thay thế."""
        await self._ensure_own_conversation(actor, conversation_id)
        appointments = AppointmentService(self._session, self._clock, self._settings)
        kind = ProposalType(args.action)
        try:
            payload, preview, reason = await self._preview(appointments, actor, kind, args)
        except ValidationError as exc:
            raise validation_error(exc) from exc
        display = _display(kind, preview, reason)
        now = self._clock.now()
        async with self._session.begin():
            await repo.expire_pending(self._session, conversation_id, now)
            proposal = AgentProposal(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                type=kind,
                appointment_id=preview.appointment_id,
                payload={**payload, "display": display.model_dump()},
                status=ProposalStatus.PENDING,
                expires_at=now + timedelta(minutes=self._settings.proposal_ttl_min),
                created_at=now,
            )
            self._session.add(proposal)
            await self._session.flush()
        log.info("agent.proposal_created", proposal_id=str(proposal.id), type=kind.value)
        return proposal_out(proposal)

    async def _preview(
        self,
        appointments: AppointmentService,
        actor: Actor,
        kind: ProposalType,
        args: ProposeArgs,
    ) -> tuple[dict[str, Any], Preview, str | None]:
        """Payload (dữ liệu để thực thi), kết quả kiểm tra trước, lý do hiện trên thẻ."""
        if kind is ProposalType.BOOK:
            book = BookRequest(
                service_id=_need(args.service_id, "service_id"),
                doctor_id=_need(args.doctor_id, "doctor_id"),
                start_at=_need(args.start_at, "start_at"),
                reason=args.reason,
            )
            preview = await appointments.preview_book(actor, book)
            payload = {
                "service_id": preview.service_id,
                "doctor_id": preview.doctor_id,
                "start_at": preview.start_at.isoformat(),
                "end_at": preview.end_at.isoformat(),
                "reason": book.reason,
            }
            return payload, preview, book.reason
        appointment_id = _need(args.appointment_id, "appointment_id")
        if kind is ProposalType.RESCHEDULE:
            change = RescheduleRequest(
                start_at=_need(args.start_at, "start_at"),
                doctor_id=_need(args.doctor_id, "doctor_id"),
            )
            preview = await appointments.preview_reschedule(actor, appointment_id, change)
            payload = {
                "doctor_id": preview.doctor_id,
                "start_at": preview.start_at.isoformat(),
                "end_at": preview.end_at.isoformat(),
            }
            return payload, preview, None
        cancel = CancelRequest(reason=args.cancel_reason)
        preview = await appointments.preview_cancel(actor, appointment_id)
        return {"cancel_reason": cancel.reason}, preview, cancel.reason

    # ------------------------------------------------------------ xác nhận, từ chối
    async def confirm(self, actor: Actor, proposal_id: uuid.UUID) -> ConfirmOut:
        """Thực thi đề xuất đúng một lần (FR-AGT-04, BR-06).

        Khóa đề xuất `FOR UPDATE` trong cùng transaction với thao tác ghi: bấm đúp thì lần sau
        chờ lần trước rồi nhận lại kết quả cũ, không ghi thêm. Hạn 10 phút kiểm tra ngay tại đây,
        không phụ thuộc worker. Service từ chối (khung vừa bị đặt, quá mốc 2 giờ…) thì đề xuất
        chuyển FAILED, lỗi trả nguyên mã của web kèm khung thay thế.
        """
        now = self._clock.now()
        agent_actor = _agent_actor(actor)
        failure: AppError | None = None
        expired = False
        appointment: AppointmentOut | None = None
        async with outer_transaction(self._session):
            proposal = await self._lock_own(actor, proposal_id)
            if proposal.status is ProposalStatus.CONFIRMED:
                pass  # bấm lại: trả kết quả cũ sau transaction
            elif proposal.status is ProposalStatus.PENDING and now >= proposal.expires_at:
                proposal.status = ProposalStatus.EXPIRED
                proposal.decided_at = now
                expired = True
            elif proposal.status is ProposalStatus.EXPIRED:
                raise proposal_expired()
            elif proposal.status is not ProposalStatus.PENDING:
                raise proposal_not_pending(proposal.status)
            else:
                appointments = AppointmentService(self._session, self._clock, self._settings)
                # Bất biến: book, reschedule, cancel chỉ ném AppError bên trong transaction() của
                # chúng (SAVEPOINT bị rollback) hoặc trước khi ghi; nên FAILED luôn đi cùng việc
                # không có lịch nào được ghi.
                try:
                    appointment = await self._execute(appointments, agent_actor, proposal)
                except AppError as err:
                    failure = err
                    notice = repo.add_message(
                        self._session,
                        proposal.conversation_id,
                        MessageRole.ASSISTANT,
                        f"Chưa {TYPE_LABELS[proposal.type]} được: {err.message}",
                        now,
                    )
                    await self._session.flush()
                    self._decide(
                        proposal,
                        ProposalStatus.FAILED,
                        now,
                        {"error": err.message, "message_id": notice.id},
                    )
                else:
                    notice = repo.add_message(
                        self._session,
                        proposal.conversation_id,
                        MessageRole.ASSISTANT,
                        _notice(proposal, appointment),
                        now,
                    )
                    await self._session.flush()
                    proposal.appointment_id = appointment.id
                    self._decide(
                        proposal,
                        ProposalStatus.CONFIRMED,
                        now,
                        {"code": appointment.code, "message_id": notice.id},
                    )
                await repo.touch_conversation(self._session, proposal.conversation_id, now)
        if expired:
            raise proposal_expired()
        if failure is not None:
            details = {**failure.details, "proposal_status": ProposalStatus.FAILED.value}
            log.info("agent.proposal_failed", proposal_id=str(proposal_id), code=failure.code)
            raise AppError(failure.code, failure.message, status=failure.status, details=details)
        if appointment is None:  # đã xác nhận từ trước
            assert proposal.appointment_id is not None
            detail = await AppointmentService(self._session, self._clock, self._settings).get(
                agent_actor, proposal.appointment_id
            )
            appointment = AppointmentOut.model_validate(
                detail.model_dump(include=set(AppointmentOut.model_fields))
            )
        else:
            log.info("agent.proposal_confirmed", proposal_id=str(proposal_id))
        return ConfirmOut(proposal=proposal_out(proposal), appointment=appointment)

    async def reject(self, actor: Actor, proposal_id: uuid.UUID) -> ProposalOut:
        """Bệnh nhân bấm Hủy trên thẻ: không ghi gì vào lịch hẹn (UC09 7a)."""
        now = self._clock.now()
        async with self._session.begin():
            proposal = await self._lock_own(actor, proposal_id)
            if proposal.status is ProposalStatus.PENDING:
                if now >= proposal.expires_at:
                    proposal.status = ProposalStatus.EXPIRED
                    proposal.decided_at = now
                else:
                    notice = repo.add_message(
                        self._session,
                        proposal.conversation_id,
                        MessageRole.ASSISTANT,
                        f"Bạn đã bỏ qua đề xuất {TYPE_LABELS[proposal.type]} "
                        f"({proposal.payload['display']['when']}). Chưa có gì thay đổi.",
                        now,
                    )
                    await self._session.flush()
                    self._decide(proposal, ProposalStatus.REJECTED, now, {"message_id": notice.id})
                    await repo.touch_conversation(self._session, proposal.conversation_id, now)
            elif proposal.status not in (ProposalStatus.REJECTED, ProposalStatus.EXPIRED):
                raise proposal_not_pending(proposal.status)
        return proposal_out(proposal)

    async def _ensure_own_conversation(self, actor: Actor, conversation_id: uuid.UUID) -> None:
        """Phân quyền lớp 2 (docs mục 4.6): chỉ bệnh nhân, trong hội thoại của chính mình."""
        if actor.role is not UserRole.PATIENT or actor.user_id is None:
            raise forbidden()
        async with self._session.begin():
            conversation = await repo.get_conversation(self._session, conversation_id)
        if conversation is None or conversation.patient_id != actor.user_id:
            raise forbidden()

    async def _lock_own(self, actor: Actor, proposal_id: uuid.UUID) -> AgentProposal:
        """Chỉ bệnh nhân chủ hội thoại của đề xuất (docs mục 6.4); người khác nhận 403.

        Đọc chủ đề xuất không khóa trước, như docs mục 5.4: người không có quyền không giữ được
        khóa dòng đề xuất của người khác. Sau khi khóa, kiểm lại trên dòng mới nhất.
        """
        if actor.role is not UserRole.PATIENT or actor.user_id is None:
            raise forbidden()
        owner = await repo.proposal_owner(self._session, proposal_id)
        if owner is None:
            raise proposal_not_found()
        if owner != actor.user_id:
            raise forbidden()
        row = await repo.lock_proposal(self._session, proposal_id)
        if row is None:
            raise proposal_not_found()
        proposal, patient_id = row
        if patient_id != actor.user_id:
            raise forbidden()
        return proposal

    async def _execute(
        self, appointments: AppointmentService, actor: Actor, proposal: AgentProposal
    ) -> AppointmentOut:
        """Payload do backend dựng lúc tạo đề xuất, không phải văn bản của LLM (docs mục 6.4)."""
        payload = proposal.payload
        if proposal.type is ProposalType.BOOK:
            return await appointments.book(
                actor,
                BookRequest(
                    service_id=payload["service_id"],
                    doctor_id=payload["doctor_id"],
                    start_at=datetime.fromisoformat(payload["start_at"]),
                    reason=payload.get("reason"),
                ),
            )
        assert proposal.appointment_id is not None  # ràng buộc appointment_required
        if proposal.type is ProposalType.RESCHEDULE:
            return await appointments.reschedule(
                actor,
                proposal.appointment_id,
                RescheduleRequest(
                    start_at=datetime.fromisoformat(payload["start_at"]),
                    doctor_id=payload["doctor_id"],
                ),
            )
        return await appointments.cancel(
            actor, proposal.appointment_id, CancelRequest(reason=payload.get("cancel_reason"))
        )

    @staticmethod
    def _decide(
        proposal: AgentProposal, status: ProposalStatus, now: datetime, result: dict[str, Any]
    ) -> None:
        proposal.status = status
        proposal.decided_at = now
        proposal.payload = {**proposal.payload, "result": result}


def _need[T](value: T | None, field: str) -> T:
    """ProposeArgs đã kiểm tra trường bắt buộc theo action; hàm này chỉ để kiểu chặt chẽ."""
    if value is None:
        raise field_error(field, "Thiếu thông tin bắt buộc.")
    return value


def _agent_actor(actor: Actor) -> Actor:
    """Thực thi với kênh AGENT để lịch sử thay đổi và thống kê biết lịch đặt qua trợ lý."""
    return Actor(user_id=actor.user_id, role=actor.role, channel=Channel.AGENT)
