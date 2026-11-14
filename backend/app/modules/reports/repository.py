"""Truy vấn database của module reports (SQLAlchemy). Không ra quyết định nghiệp vụ.

Ghi `reviews`; số liệu dashboard chỉ đọc `appointments` bằng truy vấn gom nhóm, ngày tính theo giờ
của phòng khám (docs mục 7.6).
"""

from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import ColumnElement, Date, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import clinic_tz
from app.db.enums import AppointmentStatus, Channel
from app.db.models.appointments import Appointment, Review
from app.db.models.users import Doctor, User


async def review_exists(session: AsyncSession, appointment_id: int) -> bool:
    stmt = select(Review.id).where(Review.appointment_id == appointment_id)
    return (await session.execute(stmt)).first() is not None


async def add_review(session: AsyncSession, review: Review) -> None:
    session.add(review)
    await session.flush()


def _starts_in(start: datetime, end: datetime) -> ColumnElement[bool]:
    return and_(Appointment.start_at >= start, Appointment.start_at < end)


async def counts_by_day(
    session: AsyncSession, start: datetime, end: datetime
) -> list[tuple[date, AppointmentStatus, int]]:
    """Số lịch theo ngày khám (giờ phòng khám) và trạng thái, trong [start, end).

    Đổi múi giờ trong subquery để GROUP BY không lặp lại biểu thức có tham số (PostgreSQL coi
    `timezone($1, …)` và `timezone($2, …)` là hai biểu thức khác nhau).
    """
    local = (
        select(
            cast(func.timezone(clinic_tz().key, Appointment.start_at), Date).label("day"),
            Appointment.status,
        )
        .where(_starts_in(start, end))
        .subquery()
    )
    stmt = select(local.c.day, local.c.status, func.count()).group_by(local.c.day, local.c.status)
    return [(d, s, n) for d, s, n in (await session.execute(stmt)).all()]


async def counts_by_doctor(
    session: AsyncSession, start: datetime, end: datetime
) -> list[tuple[int, AppointmentStatus, int]]:
    stmt = (
        select(Appointment.doctor_id, Appointment.status, func.count())
        .where(_starts_in(start, end))
        .group_by(Appointment.doctor_id, Appointment.status)
    )
    return [(d, s, n) for d, s, n in (await session.execute(stmt)).all()]


async def counts_by_status(
    session: AsyncSession, start: datetime, end: datetime
) -> dict[AppointmentStatus, int]:
    stmt = (
        select(Appointment.status, func.count())
        .where(_starts_in(start, end))
        .group_by(Appointment.status)
    )
    return {s: n for s, n in (await session.execute(stmt)).all()}


async def bookings_by_channel(
    session: AsyncSession, start: datetime, end: datetime
) -> dict[Channel, int]:
    """Lịch được tạo trong [start, end), theo kênh đặt."""
    stmt = (
        select(Appointment.channel, func.count())
        .where(Appointment.created_at >= start, Appointment.created_at < end)
        .group_by(Appointment.channel)
    )
    return {c: n for c, n in (await session.execute(stmt)).all()}


async def doctor_names(session: AsyncSession, with_ids: Sequence[int]) -> dict[int, str]:
    """Bác sĩ có tài khoản đang hoạt động, cộng các bác sĩ trong `with_ids` (kể cả đã khóa)."""
    active = and_(User.is_active.is_(True), User.anonymized_at.is_(None))
    stmt = (
        select(User.id, User.full_name)
        .join(Doctor, Doctor.user_id == User.id)
        .where(or_(active, User.id.in_(with_ids)) if with_ids else active)
    )
    return {doctor_id: name for doctor_id, name in (await session.execute(stmt)).all()}
