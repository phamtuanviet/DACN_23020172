"""Truy vấn của module appointments: appointments, appointment_history; khóa dòng (docs mục 5.4).

Không ra quyết định nghiệp vụ (docs mục 4.2). Thứ tự khóa luôn là bệnh nhân → bác sĩ → lịch hẹn.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AppointmentStatus
from app.db.models.appointments import Appointment
from app.db.models.catalog import Service
from app.db.models.users import Doctor, User


@dataclass(frozen=True, slots=True)
class AppointmentRow:
    appointment: Appointment
    service_name: str
    patient_name: str


async def lock_patient(session: AsyncSession, patient_id: int) -> User | None:
    """`FOR UPDATE`: hai request của cùng bệnh nhân không cùng đếm thấy 2 lịch rồi cùng đặt thêm."""
    stmt = select(User).where(User.id == patient_id).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def lock_doctors_shared(session: AsyncSession, doctor_ids: Sequence[int]) -> None:
    """`FOR SHARE` theo id tăng dần: đặt lịch song song không chặn nhau, chỉ chờ khi quản trị đang
    sửa ca làm hoặc ngày nghỉ của bác sĩ đó (khóa `FOR UPDATE`)."""
    if not doctor_ids:
        return
    stmt = (
        select(Doctor.user_id)
        .where(Doctor.user_id.in_(doctor_ids))
        .order_by(Doctor.user_id)
        .with_for_update(read=True)
    )
    await session.execute(stmt)


async def count_upcoming_booked(session: AsyncSession, patient_id: int, now: datetime) -> int:
    """Lịch BOOKED sắp tới của bệnh nhân (BR-09: tối đa 3)."""
    stmt = select(func.count()).where(
        Appointment.patient_id == patient_id,
        Appointment.status == AppointmentStatus.BOOKED,
        Appointment.start_at > now,
    )
    return (await session.execute(stmt)).scalar_one()


async def booked_for_doctor(
    session: AsyncSession,
    doctor_id: int,
    *,
    start: datetime,
    end: datetime | None = None,
) -> list[AppointmentRow]:
    """Lịch BOOKED của bác sĩ chồng khoảng [start, end) (end rỗng: mọi lịch kết thúc sau start)."""
    stmt = (
        select(Appointment, Service.name, User.full_name)
        .join(Service, Service.id == Appointment.service_id)
        .join(User, User.id == Appointment.patient_id)
        .where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == AppointmentStatus.BOOKED,
            Appointment.end_at > start,
        )
        .order_by(Appointment.start_at)
    )
    if end is not None:
        stmt = stmt.where(Appointment.start_at < end)
    rows = (await session.execute(stmt)).all()
    return [AppointmentRow(row[0], row[1], row[2]) for row in rows]


async def lock_appointments(session: AsyncSession, ids: Sequence[int]) -> list[Appointment]:
    if not ids:
        return []
    stmt = select(Appointment).where(Appointment.id.in_(ids)).order_by(Appointment.id)
    return list((await session.execute(stmt.with_for_update())).scalars())
