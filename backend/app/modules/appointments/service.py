"""Nghiệp vụ của module appointments: quy tắc, phân quyền theo bản ghi, ranh giới transaction.

Không biết về HTTP; nhận `Actor` thay vì request để web và Agent dùng chung. Transaction đặt lịch
theo docs mục 5.4: READ COMMITTED, vài khóa dòng có chủ đích, exclusion constraint làm chốt chặn
cuối cùng chống trùng lịch (BR-01, BR-03).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import AppError, forbidden, violated_constraint
from app.core.timeutil import to_local
from app.db.enums import AppointmentStatus, HistoryAction, NotificationType
from app.db.models.appointments import Appointment, AppointmentHistory
from app.modules.appointments import policy
from app.modules.appointments import repository as repo
from app.modules.appointments.codes import new_appointment_code
from app.modules.appointments.schemas import AppointmentOut, BookRequest, ServiceRef
from app.modules.catalog.schemas import DoctorRef
from app.modules.catalog.service import (
    ServiceInfo,
    active_doctor_ids,
    get_bookable_service,
    service_exists,
)
from app.modules.notifications import outbox
from app.modules.scheduling.service import (
    BookingWindow,
    Candidate,
    doctor_service_mismatch,
    ensure_slot_bookable,
    service_not_found,
    slot_taken,
)

log = structlog.get_logger(__name__)

CODE_ATTEMPTS = 3  # mã trùng (rất hiếm) thì sinh lại, tối đa 3 lần (docs mục 5.6)
CODE_UNIQUE = "uq_appointments_code"
DOCTOR_OVERLAP = "excl_doctor_overlap"
PATIENT_OVERLAP = "excl_patient_overlap"


# ---------------------------------------------------------------------------- lỗi
def booking_window_error(days: int) -> AppError:
    return AppError(
        "BOOKING_WINDOW",
        f"Chỉ đặt được lịch cho thời điểm sắp tới, trong vòng {days} ngày.",
        status=400,
    )


def patient_overlap() -> AppError:
    return AppError("PATIENT_OVERLAP", "Bạn đã có một lịch hẹn khác trùng giờ này.", status=409)


def max_active_appointments(limit: int) -> AppError:
    return AppError(
        "MAX_ACTIVE_APPOINTMENTS",
        f"Bạn đang có {limit} lịch hẹn chờ khám. Hãy hủy hoặc khám xong một lịch rồi đặt thêm.",
        status=409,
        details={"limit": limit},
    )


# ---------------------------------------------------------------------------- dùng chung
def history_value(appointment: Appointment) -> dict[str, Any]:
    """Giá trị lưu vào appointment_history: trạng thái và thời điểm, không có lý do khám."""
    return {
        "status": appointment.status.value,
        "doctor_id": appointment.doctor_id,
        "service_id": appointment.service_id,
        "start_at": to_local(appointment.start_at).isoformat(),
        "end_at": to_local(appointment.end_at).isoformat(),
    }


@dataclass(frozen=True, slots=True)
class AffectedAppointment:
    """Lịch bị ảnh hưởng khi quản trị thêm ngày nghỉ hoặc sửa ca (BR-10); chỉ quản trị xem."""

    id: int
    code: str
    start_at: datetime
    end_at: datetime
    service_name: str
    patient_name: str
    needs_attention: bool


def _affected(row: repo.AppointmentRow) -> AffectedAppointment:
    a = row.appointment
    return AffectedAppointment(
        a.id, a.code, a.start_at, a.end_at, row.service_name, row.patient_name, a.needs_attention
    )


async def booked_for_doctor(
    session: AsyncSession,
    actor: Actor,
    doctor_id: int,
    *,
    start: datetime,
    end: datetime | None = None,
) -> list[AffectedAppointment]:
    """Lịch BOOKED của bác sĩ chồng khoảng [start, end); module schedule dùng (docs mục 5.7)."""
    policy.ensure_can_manage_schedule(actor)
    rows = await repo.booked_for_doctor(session, doctor_id, start=start, end=end)
    return [_affected(row) for row in rows]


async def flag_for_attention(
    session: AsyncSession, actor: Actor, appointment_ids: Sequence[int], *, source: dict[str, Any]
) -> list[int]:
    """Gắn cờ "cần xử lý" và ghi history FLAG (BR-10). Không bao giờ tự hủy lịch.

    Chạy trong transaction của người gọi; bỏ qua lịch không còn BOOKED hoặc đã có cờ.
    """
    policy.ensure_can_manage_schedule(actor)
    flagged: list[int] = []
    for appointment in await repo.lock_appointments(session, appointment_ids):
        if appointment.status is not AppointmentStatus.BOOKED or appointment.needs_attention:
            continue
        appointment.needs_attention = True
        session.add(
            AppointmentHistory(
                appointment_id=appointment.id,
                actor_id=actor.user_id,
                channel=actor.channel,
                action=HistoryAction.FLAG,
                old_value={"needs_attention": False},
                new_value={"needs_attention": True, **source},
            )
        )
        flagged.append(appointment.id)
    return flagged


# ---------------------------------------------------------------------------- service
class AppointmentService:
    def __init__(self, session: AsyncSession, clock: Clock, settings: Settings) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings

    async def book(self, actor: Actor, data: BookRequest) -> AppointmentOut:
        """Đặt lịch (UC05 bước 8, FR-APT-01); cũng là đường thực thi đề xuất BOOK của Agent.

        `doctor_id` rỗng: chọn bác sĩ còn trống ít lịch nhất trong ngày; bác sĩ đó vừa bị người
        khác đặt mất thì thử bác sĩ kế tiếp trước khi báo SLOT_TAKEN (docs mục 5.1).
        """
        patient_id = policy.ensure_can_book(actor)
        window = BookingWindow.starting(self._clock.now(), self._settings)
        if not window.contains(data.start_at):
            raise booking_window_error(self._settings.booking_window_days)
        async with self._session.begin():
            patient = await repo.lock_patient(self._session, patient_id)
            if patient is None or not patient.is_active or patient.anonymized_at is not None:
                raise forbidden()
            service = await self._bookable_service(data.service_id)
            doctor_ids = (
                [data.doctor_id]
                if data.doctor_id is not None
                else await active_doctor_ids(self._session, service.id)
            )
            await repo.lock_doctors_shared(self._session, doctor_ids)
            candidates = await ensure_slot_bookable(
                self._session, service, data.start_at, window, doctor_id=data.doctor_id
            )
            limit = self._settings.max_active_appointments
            if await repo.count_upcoming_booked(self._session, patient_id, window.now) >= limit:
                raise max_active_appointments(limit)
            inserted = await self._insert(actor, patient_id, service, data, candidates, window)
            if inserted is None:
                raise await slot_taken(
                    self._session, service, data.start_at, window, doctor_id=data.doctor_id
                )
            appointment, doctor = inserted
            self._session.add(
                AppointmentHistory(
                    appointment_id=appointment.id,
                    actor_id=actor.user_id,
                    channel=actor.channel,
                    action=HistoryAction.CREATE,
                    old_value=None,
                    new_value=history_value(appointment),
                )
            )
            await outbox.enqueue(
                self._session,
                appointment_id=appointment.id,
                type=NotificationType.BOOKED,
                recipient_email=patient.email,
                scheduled_at=window.now,
            )
        log.info(
            "appointment.booked",
            appointment_id=appointment.id,
            doctor_id=appointment.doctor_id,
            channel=actor.channel.value,
        )
        return self._out(appointment, service, doctor, actor, window.now)

    async def _bookable_service(self, service_id: int) -> ServiceInfo:
        service = await get_bookable_service(self._session, service_id)
        if service is not None:
            return service
        if await service_exists(self._session, service_id):
            raise doctor_service_mismatch()  # dịch vụ hoặc chuyên khoa đã bị ẩn
        raise service_not_found()

    async def _insert(
        self,
        actor: Actor,
        patient_id: int,
        service: ServiceInfo,
        data: BookRequest,
        candidates: list[Candidate],
        window: BookingWindow,
    ) -> tuple[Appointment, Candidate] | None:
        """INSERT trong SAVEPOINT để lỗi constraint không làm hỏng cả transaction.

        - `excl_doctor_overlap`: người khác vừa đặt khung này của bác sĩ → thử bác sĩ kế tiếp.
        - `excl_patient_overlap`: bệnh nhân đã có lịch trùng giờ (BR-09).
        - `uq_appointments_code`: mã trùng → sinh mã khác.
        Trả None khi mọi bác sĩ ứng viên đều vừa bị đặt mất.
        """
        end_at = data.start_at + timedelta(minutes=service.duration_min)
        for candidate in candidates:
            for attempt in range(1, CODE_ATTEMPTS + 1):
                appointment = Appointment(
                    code=new_appointment_code(window.today),
                    patient_id=patient_id,
                    doctor_id=candidate.doctor_id,
                    service_id=service.id,
                    start_at=data.start_at,
                    end_at=end_at,
                    status=AppointmentStatus.BOOKED,
                    channel=actor.channel,
                    reason=data.reason,
                    needs_attention=False,
                )
                try:
                    async with self._session.begin_nested():
                        self._session.add(appointment)
                        await self._session.flush()
                except IntegrityError as exc:
                    constraint = violated_constraint(exc)
                    if constraint == CODE_UNIQUE and attempt < CODE_ATTEMPTS:
                        continue
                    if constraint == DOCTOR_OVERLAP:
                        log.info("appointment.slot_taken", doctor_id=candidate.doctor_id)
                        break
                    if constraint == PATIENT_OVERLAP:
                        raise patient_overlap() from exc
                    raise
                return appointment, candidate
        return None

    def _out(
        self,
        appointment: Appointment,
        service: ServiceInfo,
        doctor: Candidate,
        actor: Actor,
        now: datetime,
    ) -> AppointmentOut:
        deadline = timedelta(hours=self._settings.change_deadline_hours)
        return AppointmentOut(
            id=appointment.id,
            code=appointment.code,
            status=appointment.status,
            channel=appointment.channel,
            service=ServiceRef(id=service.id, name=service.name),
            doctor=DoctorRef(id=doctor.doctor_id, name=doctor.name),
            start_at=to_local(appointment.start_at),
            end_at=to_local(appointment.end_at),
            can_change=policy.can_change(appointment, actor, now, deadline),
        )
