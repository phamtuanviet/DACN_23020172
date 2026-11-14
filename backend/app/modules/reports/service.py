"""Nghiệp vụ của module reports: quy tắc, phân quyền theo bản ghi, ranh giới transaction.

Không biết về HTTP; nhận `Actor` thay vì request để web và Agent dùng chung.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, time, timedelta

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.clock import Clock
from app.core.db import transaction
from app.core.errors import AppError, field_error, forbidden, violated_constraint
from app.core.timeutil import local_datetime, to_local
from app.db.enums import AppointmentStatus, Channel, UserRole
from app.db.models.appointments import Review
from app.modules.appointments.schemas import ReviewOut
from app.modules.appointments.service import review_out, reviewable_appointment
from app.modules.reports import repository as repo
from app.modules.reports.schemas import (
    ChannelSplit,
    DayStats,
    DoctorStats,
    Rates,
    ReviewCreate,
    StatsOut,
    StatusCounts,
)

log = structlog.get_logger(__name__)

REVIEW_UNIQUE = "uq_reviews_appointment_id"
MAX_STATS_DAYS = 31  # FR-RPT-01: dashboard xem tối đa khoảng 30 ngày
DEFAULT_STATS_DAYS = 14


def already_reviewed() -> AppError:
    return AppError("ALREADY_REVIEWED", "Bạn đã đánh giá lịch hẹn này rồi.", status=409)


def _counts(by_status: Mapping[AppointmentStatus, int]) -> StatusCounts:
    get = by_status.get
    cancelled = get(AppointmentStatus.CANCELLED, 0)
    return StatusCounts(
        total=sum(by_status.values()) - cancelled,
        booked=get(AppointmentStatus.BOOKED, 0),
        arrived=get(AppointmentStatus.ARRIVED, 0),
        completed=get(AppointmentStatus.COMPLETED, 0),
        cancelled=cancelled,
        no_show=get(AppointmentStatus.NO_SHOW, 0),
    )


def _ratio(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _rates(counts: StatusCounts) -> Rates:
    """Tỷ lệ hủy trên mọi lịch; tỷ lệ vắng mặt trên các lịch đã biết kết quả (Đã đến, Đã khám,
    Vắng mặt). Lịch Đã đặt đã qua giờ mà chưa ai cập nhật không tính vào đâu."""
    attended = counts.arrived + counts.completed + counts.no_show
    return Rates(
        cancel_rate=_ratio(counts.cancelled, counts.total + counts.cancelled),
        no_show_rate=_ratio(counts.no_show, attended),
    )


def _group[K](
    rows: Iterable[tuple[K, AppointmentStatus, int]],
) -> dict[K, dict[AppointmentStatus, int]]:
    grouped: dict[K, dict[AppointmentStatus, int]] = defaultdict(dict)
    for key, status, count in rows:
        grouped[key][status] = count
    return grouped


class ReportService:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    # ------------------------------------------------------------ đánh giá (UC20)
    async def create_review(
        self, actor: Actor, appointment_id: int, data: ReviewCreate
    ) -> ReviewOut:
        """Bệnh nhân đánh giá 1–5 sao, nhận xét tối đa 500 ký tự cho lịch Đã khám của mình, mỗi
        lịch một lần (FR-RPT-02, AC-19). Lỗi: FORBIDDEN, NOT_FOUND, INVALID_TRANSITION,
        ALREADY_REVIEWED.

        Nhận xét là dữ liệu cá nhân: không vào log. Chỉ bệnh nhân tự gửi trên web: Agent không có
        tool đánh giá, và nếu sau này có thì cũng không được chấm thay bệnh nhân (BR-06).
        """
        if actor.role is not UserRole.PATIENT or actor.channel is Channel.AGENT:
            raise forbidden()
        review = Review(
            appointment_id=appointment_id,
            rating=data.rating,
            comment=data.comment,
            created_at=self._clock.now(),
        )
        try:
            async with transaction(self._session):
                await reviewable_appointment(self._session, actor, appointment_id)
                if await repo.review_exists(self._session, appointment_id):
                    raise already_reviewed()
                await repo.add_review(self._session, review)
        except IntegrityError as exc:  # hai lần gửi cùng lúc: UNIQUE chặn lần sau
            if violated_constraint(exc) == REVIEW_UNIQUE:
                raise already_reviewed() from exc
            raise
        log.info("review.created", appointment_id=appointment_id)
        return review_out(review)

    # ------------------------------------------------------------ dashboard (UC19)
    async def stats(self, actor: Actor, date_from: date | None, date_to: date | None) -> StatsOut:
        """Số liệu dashboard (FR-RPT-01): số lịch theo ngày, tỷ lệ hủy, tỷ lệ vắng mặt, số lịch
        theo bác sĩ, tỷ lệ đặt qua web và Agent. Mặc định 14 ngày tính đến hôm nay."""
        if actor.role is not UserRole.ADMIN:
            raise forbidden()
        today = to_local(self._clock.now()).date()
        date_to = date_to or (
            today if date_from is None else date_from + timedelta(DEFAULT_STATS_DAYS - 1)
        )
        date_from = date_from or date_to - timedelta(DEFAULT_STATS_DAYS - 1)
        if date_to < date_from:
            raise field_error(
                "date_to", "Ngày kết thúc không được trước ngày bắt đầu.", location="query"
            )
        days = (date_to - date_from).days + 1
        if days > MAX_STATS_DAYS:
            raise field_error(
                "date_to", f"Xem tối đa {MAX_STATS_DAYS} ngày mỗi lần.", location="query"
            )
        start = local_datetime(date_from, time(0))
        end = local_datetime(date_to + timedelta(days=1), time(0))
        previous_start = local_datetime(date_from - timedelta(days=days), time(0))
        async with self._session.begin():
            by_day = _group(await repo.counts_by_day(self._session, start, end))
            by_doctor = _group(await repo.counts_by_doctor(self._session, start, end))
            previous = await repo.counts_by_status(self._session, previous_start, start)
            channels = await repo.bookings_by_channel(self._session, start, end)
            names = await repo.doctor_names(self._session, sorted(by_doctor))

        totals: dict[AppointmentStatus, int] = defaultdict(int)
        for counts in by_day.values():
            for status, count in counts.items():
                totals[status] += count
        total_counts = _counts(totals)
        doctors = [
            DoctorStats(
                id=doctor_id, name=name, **_counts(by_doctor.get(doctor_id, {})).model_dump()
            )
            for doctor_id, name in names.items()
        ]
        doctors.sort(key=lambda d: (-d.total, d.name))
        return StatsOut(
            date_from=date_from,
            date_to=date_to,
            totals=total_counts,
            rates=_rates(total_counts),
            previous_rates=_rates(_counts(previous)),
            days=[
                DayStats(day=day, **_counts(by_day.get(day, {})).model_dump())
                for day in (date_from + timedelta(days=i) for i in range(days))
            ],
            doctors=doctors,
            channels=ChannelSplit(
                web=channels.get(Channel.WEB, 0), agent=channels.get(Channel.AGENT, 0)
            ),
        )
