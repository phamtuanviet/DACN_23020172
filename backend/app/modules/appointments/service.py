"""Nghiệp vụ của module appointments: quy tắc, phân quyền theo bản ghi, ranh giới transaction.

Không biết về HTTP; nhận `Actor` thay vì request để web và Agent dùng chung. Transaction đặt, đổi,
hủy theo docs mục 5.4: READ COMMITTED, vài khóa dòng có chủ đích, exclusion constraint làm chốt
chặn cuối cùng chống trùng lịch (BR-01, BR-03, BR-04).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import AppError, field_error, forbidden, not_found, violated_constraint
from app.core.timeutil import to_local
from app.db.enums import AppointmentStatus, HistoryAction, NotificationType, UserRole
from app.db.models.appointments import Appointment, AppointmentHistory
from app.modules.appointments import policy
from app.modules.appointments import repository as repo
from app.modules.appointments.codes import new_appointment_code
from app.modules.appointments.schemas import (
    AppointmentDetail,
    AppointmentOut,
    AppointmentPage,
    BookRequest,
    CancelRequest,
    HistoryEntry,
    HistoryState,
    PatientBrief,
    RescheduleRequest,
    Scope,
    ServiceRef,
    StatusChangeRequest,
)
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
MAX_PAGE_SIZE = 100  # docs mục 8.1


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


def appointment_not_found() -> AppError:
    return not_found("Không tìm thấy lịch hẹn.")


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
    session: AsyncSession,
    actor: Actor,
    doctor_id: int,
    appointments: Sequence[AffectedAppointment],
    *,
    source: dict[str, Any],
) -> list[int]:
    """Gắn cờ "cần xử lý" và ghi history FLAG (BR-10). Không bao giờ tự hủy lịch.

    Chạy trong transaction của người gọi. Danh sách được liệt kê trước khi khóa, nên dưới khóa
    kiểm lại và bỏ qua lịch không còn BOOKED, đã có cờ, hoặc vừa được dời sang bác sĩ, giờ khác.
    """
    policy.ensure_can_manage_schedule(actor)
    listed = {a.id: (a.start_at, a.end_at) for a in appointments}
    flagged: list[int] = []
    for appointment in await repo.lock_appointments(session, list(listed)):
        moved = appointment.doctor_id != doctor_id or (
            (appointment.start_at, appointment.end_at) != listed[appointment.id]
        )
        if appointment.status is not AppointmentStatus.BOOKED or appointment.needs_attention:
            continue
        if moved:  # bệnh nhân vừa đổi lịch trong lúc quản trị sửa lịch làm việc
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


def _age(birthday: date | None, today: date) -> int | None:
    if birthday is None:
        return None
    return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))


def _history_state(value: dict[str, Any] | None, doctors: dict[int, str]) -> HistoryState | None:
    if value is None:
        return None
    doctor_id = value.get("doctor_id")
    return HistoryState(
        status=value.get("status"),
        doctor=DoctorRef(id=doctor_id, name=doctors.get(doctor_id, "")) if doctor_id else None,
        start_at=value.get("start_at"),
        end_at=value.get("end_at"),
        needs_attention=value.get("needs_attention"),
    )


# ---------------------------------------------------------------------------- service
class AppointmentService:
    def __init__(self, session: AsyncSession, clock: Clock, settings: Settings) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings

    # ------------------------------------------------------------ đặt lịch
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
            self._record(appointment, actor, HistoryAction.CREATE, None, window.now)
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
        return self._out(appointment, service.name, doctor.name, actor, window.now)

    # ------------------------------------------------------------ xem
    async def list_mine(
        self,
        actor: Actor,
        *,
        scope: Scope,
        status: AppointmentStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AppointmentPage:
        """Lịch sắp tới và lịch sử của chính bệnh nhân, lọc theo trạng thái (UC08, FR-APT-04)."""
        patient_id = policy.ensure_can_list_own(actor)
        if page < 1:
            raise field_error("page", "Trang bắt đầu từ 1.", location="query")
        if not 1 <= page_size <= MAX_PAGE_SIZE:
            raise field_error("page_size", "Mỗi trang 1–100 lịch.", location="query")
        now = self._clock.now()
        async with self._session.begin():
            rows, total = await repo.list_for_patient(
                self._session,
                patient_id,
                scope=scope,
                status=status,
                now=now,
                offset=(page - 1) * page_size,
                limit=page_size,
            )
        items = [
            self._out(row.appointment, row.service_name, row.doctor_name, actor, now)
            for row in rows
        ]
        return AppointmentPage(items=items, total=total, page=page, page_size=page_size)

    async def get(self, actor: Actor, appointment_id: int) -> AppointmentDetail:
        """Chi tiết, ghi chú bác sĩ, lịch sử thay đổi (FR-APT-05, FR-DOC-03).

        Chủ lịch, bác sĩ của lịch, quản trị (AC-05). Cờ "cần xử lý" là việc nội bộ của quản trị
        nên dòng FLAG chỉ quản trị thấy.
        """
        now = self._clock.now()
        async with self._session.begin():
            row = await repo.detail(self._session, appointment_id)
            if row is None:
                raise appointment_not_found()
            policy.ensure_can_view(row.appointment, actor)
            entries = await repo.history_of(self._session, appointment_id)
            if actor.role is not UserRole.ADMIN:
                entries = [e for e in entries if e.action is not HistoryAction.FLAG]
            doctor_ids = {
                value["doctor_id"]
                for e in entries
                for value in (e.old_value, e.new_value)
                if value and value.get("doctor_id")
            }
            doctors = await repo.doctor_names(self._session, sorted(doctor_ids))
            roles = await repo.roles_of(
                self._session, sorted({e.actor_id for e in entries if e.actor_id is not None})
            )
        appointment = row.appointment
        base = self._out(appointment, row.service_name, row.doctor_name, actor, now)
        return AppointmentDetail(
            **base.model_dump(),
            reason=appointment.reason,
            # bác sĩ chỉ thấy họ tên, tuổi, dịch vụ, giờ, lý do khám (docs mục 4.6)
            cancel_reason=None if actor.role is UserRole.DOCTOR else appointment.cancel_reason,
            doctor_note=appointment.doctor_note,
            needs_attention=appointment.needs_attention,
            patient=PatientBrief(
                id=appointment.patient_id,
                name=row.patient_name,
                age=_age(row.patient_birthday, to_local(now).date()),
            ),
            created_at=to_local(appointment.created_at),
            history=[
                HistoryEntry(
                    action=e.action,
                    channel=e.channel,
                    actor_role=roles.get(e.actor_id) if e.actor_id is not None else None,
                    by_me=e.actor_id is not None and e.actor_id == actor.user_id,
                    created_at=to_local(e.created_at),
                    old=_history_state(e.old_value, doctors),
                    new=_history_state(e.new_value, doctors),
                )
                for e in entries
            ],
        )

    # ------------------------------------------------------------ đổi, hủy
    async def reschedule(
        self, actor: Actor, appointment_id: int, data: RescheduleRequest
    ) -> AppointmentOut:
        """Đổi lịch bằng một câu UPDATE trên chính dòng đó: giữ mã, giữ dịch vụ (UC06, BR-04).

        Khóa bác sĩ của khung mới `FOR SHARE` trước rồi mới khóa lịch hẹn `FOR UPDATE`, cùng thứ
        tự với quản trị thêm ngày nghỉ (khóa bác sĩ rồi gắn cờ lịch) để không deadlock. Khung mới
        bị chiếm thì cả transaction rollback, lịch cũ còn nguyên (AC-04).
        """
        window = BookingWindow.starting(self._clock.now(), self._settings)
        doctor_id = data.doctor_id
        async with self._session.begin():
            await self._find_for_change(actor, appointment_id, window.now)
            await repo.lock_doctors_shared(self._session, [doctor_id])
            appointment = await self._lock_for_change(actor, appointment_id, window.now)
            if not window.contains(data.start_at):
                raise booking_window_error(self._settings.booking_window_days)
            if appointment.doctor_id == doctor_id and appointment.start_at == data.start_at:
                raise field_error("start_at", "Hãy chọn khung giờ khác với lịch hiện tại.")
            service = await self._bookable_service(appointment.service_id)
            candidates = await ensure_slot_bookable(
                self._session,
                service,
                data.start_at,
                window,
                doctor_id=doctor_id,
                exclude_appointment_id=appointment.id,
            )
            old = history_value(appointment)
            await self._move(appointment, doctor_id, data.start_at, service, window)
            self._record(appointment, actor, HistoryAction.RESCHEDULE, old, window.now)
            await outbox.enqueue(
                self._session,
                appointment_id=appointment.id,
                type=NotificationType.RESCHEDULED,
                recipient_email=await repo.user_email(self._session, appointment.patient_id),
                scheduled_at=window.now,
            )
        log.info(
            "appointment.rescheduled",
            appointment_id=appointment.id,
            doctor_id=doctor_id,
            channel=actor.channel.value,
        )
        return self._out(appointment, service.name, candidates[0].name, actor, window.now)

    async def cancel(
        self, actor: Actor, appointment_id: int, data: CancelRequest
    ) -> AppointmentOut:
        """Hủy lịch (UC07, FR-APT-03): khung giờ được trả lại ngay vì constraint chỉ áp cho lịch
        BOOKED/ARRIVED. Lý do hủy là dữ liệu cá nhân: không ghi vào log, history."""
        now = self._clock.now()
        async with self._session.begin():
            await self._find_for_change(actor, appointment_id, now)
            appointment = await self._lock_for_change(actor, appointment_id, now)
            old = history_value(appointment)
            appointment.status = AppointmentStatus.CANCELLED
            appointment.cancel_reason = data.reason
            appointment.needs_attention = False
            await self._session.flush()
            self._record(appointment, actor, HistoryAction.CANCEL, old, now)
            await outbox.enqueue(
                self._session,
                appointment_id=appointment.id,
                type=NotificationType.CANCELLED,
                recipient_email=await repo.user_email(self._session, appointment.patient_id),
                scheduled_at=now,
            )
            service_name, doctor_name = await repo.labels(self._session, appointment)
        log.info(
            "appointment.cancelled", appointment_id=appointment.id, channel=actor.channel.value
        )
        return self._out(appointment, service_name, doctor_name, actor, now)

    async def change_status(
        self, actor: Actor, appointment_id: int, data: StatusChangeRequest
    ) -> AppointmentOut:
        """Đã đến, Đã khám, Vắng mặt theo sơ đồ trạng thái (FR-APT-06, FR-DOC-02)."""
        now = self._clock.now()
        target = AppointmentStatus(data.status)
        async with self._session.begin():
            current = await repo.get_appointment(self._session, appointment_id)
            if current is None:
                raise appointment_not_found()
            policy.ensure_can_set_status_owner(current, actor)
            appointment = await repo.lock_appointment(self._session, appointment_id)
            if appointment is None:
                raise appointment_not_found()
            policy.ensure_can_set_status_owner(appointment, actor)
            policy.ensure_valid_status_change(appointment, actor, target, now)
            old = history_value(appointment)
            appointment.status = target
            appointment.needs_attention = False  # lịch rời BOOKED thì không còn cần xử lý
            await self._session.flush()
            self._record(appointment, actor, HistoryAction.STATUS_CHANGE, old, now)
            service_name, doctor_name = await repo.labels(self._session, appointment)
        log.info(
            "appointment.status_changed",
            appointment_id=appointment.id,
            status=target.value,
            channel=actor.channel.value,
        )
        return self._out(appointment, service_name, doctor_name, actor, now)

    # ------------------------------------------------------------ nội bộ
    async def _find_for_change(
        self, actor: Actor, appointment_id: int, now: datetime
    ) -> Appointment:
        """Đọc không khóa và kiểm tra quyền trước: người không có quyền không giữ được khóa dòng
        của lịch người khác, và đổi lịch biết trước bác sĩ cần khóa."""
        appointment = await repo.get_appointment(self._session, appointment_id)
        if appointment is None:
            raise appointment_not_found()
        self._ensure_can_change(appointment, actor, now)
        return appointment

    async def _lock_for_change(
        self, actor: Actor, appointment_id: int, now: datetime
    ) -> Appointment:
        """Khóa `FOR UPDATE` rồi kiểm tra lại trên dữ liệu mới nhất: request khác có thể vừa hủy
        hoặc dời lịch này."""
        appointment = await repo.lock_appointment(self._session, appointment_id)
        if appointment is None:
            raise appointment_not_found()
        self._ensure_can_change(appointment, actor, now)
        return appointment

    def _ensure_can_change(self, appointment: Appointment, actor: Actor, now: datetime) -> None:
        policy.ensure_can_change(
            appointment,
            actor,
            now,
            deadline_hours=self._settings.change_deadline_hours,
            clinic_phone=self._settings.clinic_phone,
        )

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
                    created_at=window.now,
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

    async def _move(
        self,
        appointment: Appointment,
        doctor_id: int,
        start_at: datetime,
        service: ServiceInfo,
        window: BookingWindow,
    ) -> None:
        """UPDATE trong SAVEPOINT: lỗi constraint không làm hỏng transaction, nên vẫn tìm được
        khung thay thế trước khi rollback toàn bộ (docs mục 5.4)."""
        try:
            async with self._session.begin_nested():
                appointment.doctor_id = doctor_id
                appointment.start_at = start_at
                appointment.end_at = start_at + timedelta(minutes=service.duration_min)
                appointment.needs_attention = False
                await self._session.flush()
        except IntegrityError as exc:
            constraint = violated_constraint(exc)
            if constraint == DOCTOR_OVERLAP:
                log.info("appointment.slot_taken", doctor_id=doctor_id)
                raise await slot_taken(
                    self._session, service, start_at, window, doctor_id=doctor_id
                ) from exc
            if constraint == PATIENT_OVERLAP:
                raise patient_overlap() from exc
            raise

    def _record(
        self,
        appointment: Appointment,
        actor: Actor,
        action: HistoryAction,
        old_value: dict[str, Any] | None,
        now: datetime,
    ) -> None:
        """Một dòng appointment_history cho mỗi thay đổi (FR-APT-05)."""
        self._session.add(
            AppointmentHistory(
                appointment_id=appointment.id,
                actor_id=actor.user_id,
                channel=actor.channel,
                action=action,
                old_value=old_value,
                new_value=history_value(appointment),
                created_at=now,
            )
        )

    def _out(
        self,
        appointment: Appointment,
        service_name: str,
        doctor_name: str,
        actor: Actor,
        now: datetime,
    ) -> AppointmentOut:
        deadline = timedelta(hours=self._settings.change_deadline_hours)
        booked = appointment.status is AppointmentStatus.BOOKED
        return AppointmentOut(
            id=appointment.id,
            code=appointment.code,
            status=appointment.status,
            channel=appointment.channel,
            service=ServiceRef(id=appointment.service_id, name=service_name),
            doctor=DoctorRef(id=appointment.doctor_id, name=doctor_name),
            start_at=to_local(appointment.start_at),
            end_at=to_local(appointment.end_at),
            can_change=policy.can_change(appointment, actor, now, deadline),
            change_until=to_local(appointment.start_at - deadline) if booked else None,
        )
