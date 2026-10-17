"""Truy vấn của module schedule: shifts, time_offs. Không ra quyết định nghiệp vụ (docs mục 4.2)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.schedule import Shift, TimeOff
from app.db.models.users import Doctor


async def lock_doctor(session: AsyncSession, doctor_id: int) -> Doctor | None:
    """`FOR UPDATE` dòng bác sĩ: sửa lịch làm việc chờ các lượt đặt lịch đang giữ `FOR SHARE`, và
    ngược lại, nên không có lịch mới lọt vào ngày nghỉ mà không bị gắn cờ (docs mục 5.4)."""
    stmt = select(Doctor).where(Doctor.user_id == doctor_id).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def doctor_exists(session: AsyncSession, doctor_id: int) -> bool:
    return await session.get(Doctor, doctor_id) is not None


async def shifts_of(session: AsyncSession, doctor_id: int) -> list[Shift]:
    stmt = (
        select(Shift)
        .where(Shift.doctor_id == doctor_id)
        .order_by(Shift.weekday, Shift.start_time, Shift.valid_from)
    )
    return list((await session.execute(stmt)).scalars())


async def get_shift(session: AsyncSession, doctor_id: int, shift_id: int) -> Shift | None:
    stmt = select(Shift).where(Shift.id == shift_id, Shift.doctor_id == doctor_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def time_offs_of(session: AsyncSession, doctor_id: int, since: datetime) -> list[TimeOff]:
    stmt = (
        select(TimeOff)
        .where(TimeOff.doctor_id == doctor_id, TimeOff.end_at > since)
        .order_by(TimeOff.start_at)
    )
    return list((await session.execute(stmt)).scalars())


async def get_time_off(session: AsyncSession, doctor_id: int, time_off_id: int) -> TimeOff | None:
    stmt = select(TimeOff).where(TimeOff.id == time_off_id, TimeOff.doctor_id == doctor_id)
    return (await session.execute(stmt)).scalar_one_or_none()
