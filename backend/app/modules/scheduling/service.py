"""Nghiệp vụ của module scheduling: nạp dữ liệu cho Engine, khung trống, khung thay thế.

Không biết về HTTP; nhận `Actor` thay vì request để web và Agent dùng chung. Module chỉ đọc: mọi
quyết định ghi (đặt, đổi lịch) nằm ở appointments, gọi `ensure_slot_bookable` trong transaction
của mình (docs mục 5.3).
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import AppError, field_error, not_found
from app.core.timeutil import local_datetime, to_local
from app.core.validation import MAX_DATE, MIN_DATE
from app.modules.catalog.schemas import DoctorRef
from app.modules.catalog.service import ServiceInfo, get_bookable_service, get_bookable_services
from app.modules.scheduling import repository as repo
from app.modules.scheduling.engine import (
    Interval,
    Slot,
    compute_slots,
    earliest_slots,
    has_working_time,
    nearest_dates,
)
from app.modules.scheduling.schemas import (
    Alternative,
    AvailabilityOut,
    DayOut,
    DayStatus,
    EarliestItem,
    EarliestOut,
    ServiceSummary,
    SlotOut,
)

MAX_RANGE_DAYS = 31
NEAREST_LIMIT = 3  # FR-SCH-05
ALTERNATIVES_LIMIT = 3  # SLOT_TAKEN kèm tối đa 3 khung gần nhất (BR-03)


# ---------------------------------------------------------------------------- lỗi
def slot_not_offered() -> AppError:
    return AppError(
        "SLOT_NOT_OFFERED",
        "Giờ này không có trong lịch khám của bác sĩ, vui lòng chọn một khung giờ trống.",
        status=400,
    )


def doctor_service_mismatch() -> AppError:
    return AppError(
        "DOCTOR_SERVICE_MISMATCH",
        "Bác sĩ không thực hiện dịch vụ này hoặc đã ngừng nhận lịch.",
        status=400,
    )


def service_not_found() -> AppError:
    return not_found("Không tìm thấy dịch vụ.")


# ---------------------------------------------------------------------------- dữ liệu cho Engine
@dataclass(frozen=True, slots=True)
class BookingWindow:
    """Cửa sổ đặt lịch: sau `now`, không quá `now + 30 ngày` (BR-07)."""

    now: datetime
    end: datetime

    @classmethod
    def starting(cls, now: datetime, settings: Settings) -> "BookingWindow":
        return cls(now, now + timedelta(days=settings.booking_window_days))

    @property
    def today(self) -> date:
        return to_local(self.now).date()

    @property
    def last_day(self) -> date:
        return to_local(self.end).date()

    def contains(self, moment: datetime) -> bool:
        return self.now < moment <= self.end


@dataclass
class Snapshot:
    """Ca làm, ngày nghỉ, lịch BOOKED/ARRIVED của các bác sĩ trong một khoảng ngày."""

    doctors: repo.DoctorShifts
    time_offs: dict[int, list[Interval]]
    booked: dict[int, list[Interval]]
    _counts: Counter[tuple[int, date]] | None = field(default=None, init=False, repr=False)

    def busy(self, doctor_ids: list[int] | None = None) -> dict[int, list[Interval]]:
        result: dict[int, list[Interval]] = {}
        for source in (self.time_offs, self.booked):
            for doctor_id, items in source.items():
                if doctor_ids is None or doctor_id in doctor_ids:
                    result.setdefault(doctor_id, []).extend(items)
        return result

    def booked_count(self, doctor_id: int, day: date) -> int:
        """Số lịch của bác sĩ trong ngày: "Bác sĩ bất kỳ" chọn người ít lịch nhất (UC05 2a)."""
        if self._counts is None:
            self._counts = Counter(
                (doctor_id, to_local(item.start).date())
                for doctor_id, items in self.booked.items()
                for item in items
            )
        return self._counts[(doctor_id, day)]

    def doctor_ref(self, doctor_id: int) -> DoctorRef:
        return DoctorRef(id=doctor_id, name=self.doctors.names[doctor_id])


async def load_snapshot(
    session: AsyncSession,
    service_ids: list[int],
    first_day: date,
    last_day: date,
    *,
    doctor_id: int | None = None,
    exclude_appointment_id: int | None = None,
) -> Snapshot:
    """Ba truy vấn có chỉ mục cho cả khoảng ngày (docs mục 5.1)."""
    doctors = await repo.doctors_with_shifts(
        session, service_ids, first_day, last_day, doctor_id=doctor_id
    )
    ids = list(doctors.names)
    start = local_datetime(first_day, time(0))
    end = local_datetime(last_day + timedelta(days=1), time(0))
    time_offs = await repo.time_offs_overlapping(session, ids, start, end)
    booked = await repo.booked_overlapping(
        session, ids, start, end, exclude_appointment_id=exclude_appointment_id
    )
    return Snapshot(doctors, time_offs, booked)


def _days(first_day: date, last_day: date) -> list[date]:
    return [first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)]


# ---------------------------------------------------------------------------- dùng cho appointments
@dataclass(frozen=True, slots=True)
class Candidate:
    doctor_id: int
    name: str
    booked_that_day: int


async def ensure_slot_bookable(
    session: AsyncSession,
    service: ServiceInfo,
    start_at: datetime,
    window: BookingWindow,
    *,
    doctor_id: int | None,
    exclude_appointment_id: int | None = None,
) -> list[Candidate]:
    """BR-02 (docs mục 5.3): `start_at` phải trùng một khung do Engine sinh ra.

    Trả các bác sĩ còn trống đúng khung đó, ít lịch trong ngày nhất đứng trước. Chạy trong
    transaction của người gọi, sau khi đã khóa dòng bác sĩ `FOR SHARE`.
    - `SLOT_NOT_OFFERED`: giờ này không thuộc lưới giờ (ngoài ca, trong ngày nghỉ, lệch bước).
    - `SLOT_TAKEN`: lưới giờ có khung này nhưng lịch khác đã chiếm (kèm khung thay thế).
    """
    day = to_local(start_at).date()
    snapshot = await load_snapshot(
        session,
        [service.id],
        day,
        day,
        doctor_id=doctor_id,
        exclude_appointment_id=exclude_appointment_id,
    )
    if doctor_id is not None and doctor_id not in snapshot.doctors.names:
        raise doctor_service_mismatch()
    shifts = snapshot.doctors.shifts
    duration = timedelta(minutes=service.duration_min)
    slots = compute_slots(shifts, snapshot.busy(), duration, [day], window.now, window.end)
    free = [s.doctor_id for s in slots if s.start == start_at]
    if free:
        candidates = [
            Candidate(d, snapshot.doctors.names[d], snapshot.booked_count(d, day)) for d in free
        ]
        return sorted(candidates, key=lambda c: (c.booked_that_day, c.doctor_id))
    offered = compute_slots(shifts, snapshot.time_offs, duration, [day], window.now, window.end)
    if any(s.start == start_at for s in offered):
        raise await slot_taken(session, service, start_at, window, doctor_id=doctor_id)
    raise slot_not_offered()


async def slot_taken(
    session: AsyncSession,
    service: ServiceInfo,
    start_at: datetime,
    window: BookingWindow,
    *,
    doctor_id: int | None,
) -> AppError:
    """409 SLOT_TAKEN kèm tối đa 3 khung còn trống gần giờ đã chọn nhất (BR-03, UC05 8a)."""
    alternatives = await find_alternatives(session, service, start_at, window, doctor_id=doctor_id)
    return AppError(
        "SLOT_TAKEN",
        "Khung giờ vừa được người khác đặt, vui lòng chọn khung khác.",
        status=409,
        details={"alternatives": [a.model_dump(mode="json") for a in alternatives]},
    )


async def find_alternatives(
    session: AsyncSession,
    service: ServiceInfo,
    around: datetime,
    window: BookingWindow,
    *,
    doctor_id: int | None,
    limit: int = ALTERNATIVES_LIMIT,
) -> list[Alternative]:
    """Khung trống gần `around` nhất: cùng bác sĩ nếu đã chọn, không thì bác sĩ bất kỳ.

    Tìm trong 7 ngày kể từ ngày đã chọn trước, chưa đủ mới quét tiếp tới hết cửa sổ 30 ngày.
    """
    first = max(to_local(around).date(), window.today)
    duration = timedelta(minutes=service.duration_min)
    found: dict[datetime, Slot] = {}  # mỗi giờ bắt đầu một khung
    spans = [(first, first + timedelta(days=6)), (first + timedelta(days=7), window.last_day)]
    for span_first, span_last in spans:
        span_last = min(span_last, window.last_day)
        if span_first > span_last or len(found) >= limit:
            break
        snapshot = await load_snapshot(
            session, [service.id], span_first, span_last, doctor_id=doctor_id
        )
        slots = compute_slots(
            snapshot.doctors.shifts,
            snapshot.busy(),
            duration,
            _days(span_first, span_last),
            window.now,
            window.end,
        )
        for slot in slots:
            found.setdefault(slot.start, slot)
    nearest = sorted(found.values(), key=lambda s: (abs(s.start - around), s.start))[:limit]
    return [
        Alternative(doctor_id=s.doctor_id, start_at=to_local(s.start), end_at=to_local(s.end))
        for s in sorted(nearest, key=lambda s: s.start)
    ]


# ---------------------------------------------------------------------------- API công khai
@dataclass(frozen=True, slots=True)
class AvailabilityQuery:
    service_id: int
    doctor_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    time_from: time | None = None
    time_to: time | None = None


class SchedulingService:
    def __init__(self, session: AsyncSession, clock: Clock, settings: Settings) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings

    async def availability(self, query: AvailabilityQuery) -> AvailabilityOut:
        """Khung trống theo ngày (FR-SCH-01..05); khoảng đã kín thì kèm ngày gần nhất còn khung."""
        window = BookingWindow.starting(self._clock.now(), self._settings)
        date_from = query.date_from or window.today
        date_to = query.date_to or date_from
        _validate_query(date_from, date_to, query.time_from, query.time_to)
        days = _days(date_from, date_to)
        async with self._session.begin():
            service = await get_bookable_service(self._session, query.service_id)
            if service is None:
                raise service_not_found()
            snapshot = await load_snapshot(
                self._session, [service.id], date_from, date_to, doctor_id=query.doctor_id
            )
            if query.doctor_id is not None and query.doctor_id not in snapshot.doctors.names:
                raise doctor_service_mismatch()
            duration = timedelta(minutes=service.duration_min)
            slots = compute_slots(
                snapshot.doctors.shifts,
                snapshot.busy(),
                duration,
                days,
                window.now,
                window.end,
                query.time_from,
                query.time_to,
            )
            nearest: list[date] = []
            if not slots:
                nearest = await self._nearest_dates(
                    service, query, max(date_to + timedelta(days=1), window.today), window
                )
        return AvailabilityOut(
            service=ServiceSummary(
                id=service.id, name=service.name, duration_min=service.duration_min
            ),
            days=_group_by_day(days, slots, snapshot),
            nearest_dates=nearest,
        )

    async def earliest(self, service_ids: list[int], *, by_doctor: bool) -> EarliestOut:
        """Khung trống sớm nhất trong 30 ngày của mỗi dịch vụ (hoặc của từng bác sĩ)."""
        window = BookingWindow.starting(self._clock.now(), self._settings)
        async with self._session.begin():
            services = await get_bookable_services(self._session, list(dict.fromkeys(service_ids)))
            if not services:
                return EarliestOut(items=[])
            snapshot = await load_snapshot(
                self._session, [s.id for s in services], window.today, window.last_day
            )
        days = _days(window.today, window.last_day)
        items: list[EarliestItem] = []
        for service in services:
            doctor_ids = snapshot.doctors.by_service.get(service.id, [])
            shifts = [rule for rule in snapshot.doctors.shifts if rule.doctor_id in doctor_ids]
            found = earliest_slots(
                shifts,
                snapshot.busy(doctor_ids),
                timedelta(minutes=service.duration_min),
                days,
                window.now,
                window.end,
            )
            chosen = sorted(found.values(), key=lambda s: (s.start, s.doctor_id))
            items.extend(
                EarliestItem(
                    service_id=service.id,
                    doctor=snapshot.doctor_ref(s.doctor_id),
                    start_at=to_local(s.start),
                    end_at=to_local(s.end),
                )
                for s in (chosen if by_doctor else chosen[:1])
            )
        return EarliestOut(items=items)

    async def _nearest_dates(
        self, service: ServiceInfo, query: AvailabilityQuery, first_day: date, window: BookingWindow
    ) -> list[date]:
        if first_day > window.last_day:
            return []
        snapshot = await load_snapshot(
            self._session, [service.id], first_day, window.last_day, doctor_id=query.doctor_id
        )
        return nearest_dates(
            snapshot.doctors.shifts,
            snapshot.busy(),
            timedelta(minutes=service.duration_min),
            _days(first_day, window.last_day),
            window.now,
            window.end,
            query.time_from,
            query.time_to,
            limit=NEAREST_LIMIT,
        )


def _validate_query(
    date_from: date, date_to: date, time_from: time | None, time_to: time | None
) -> None:
    if date_from < MIN_DATE or date_to > MAX_DATE:
        # Router đã chặn; kiểm lại vì tool của Agent gọi thẳng service.
        raise field_error("date_from", "Ngày nằm ngoài phạm vi cho phép.", location="query")
    if date_to < date_from:
        raise field_error("date_to", "Ngày kết thúc phải sau ngày bắt đầu.", location="query")
    if (date_to - date_from).days >= MAX_RANGE_DAYS:
        raise field_error("date_to", "Chỉ xem được tối đa 31 ngày một lần.", location="query")
    if time_from is not None and time_to is not None and time_to <= time_from:
        raise field_error("time_to", "Giờ kết thúc phải sau giờ bắt đầu.", location="query")


def _group_by_day(days: list[date], slots: list[Slot], snapshot: Snapshot) -> list[DayOut]:
    """Gộp khung theo ngày và theo giờ bắt đầu; mỗi khung kèm danh sách bác sĩ còn trống."""
    by_day: dict[date, dict[datetime, list[Slot]]] = {}
    for slot in slots:
        by_day.setdefault(to_local(slot.start).date(), {}).setdefault(slot.start, []).append(slot)
    result: list[DayOut] = []
    for day in days:
        day_slots = [
            SlotOut(
                start_at=to_local(start),
                end_at=to_local(group[0].end),
                doctors=[
                    snapshot.doctor_ref(s.doctor_id)
                    for s in sorted(
                        group, key=lambda s: (snapshot.booked_count(s.doctor_id, day), s.doctor_id)
                    )
                ],
            )
            for start, group in sorted(by_day.get(day, {}).items())
        ]
        if day_slots:
            status = DayStatus.OPEN
        elif has_working_time(snapshot.doctors.shifts, snapshot.time_offs, day):
            status = DayStatus.FULL
        else:
            status = DayStatus.OFF
        result.append(DayOut(date=day, status=status, slots=day_slots))
    return result
