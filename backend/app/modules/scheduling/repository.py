"""Truy vấn của module scheduling (chỉ đọc): ca làm, ngày nghỉ, lịch BOOKED/ARRIVED.

Không ra quyết định nghiệp vụ (docs mục 4.2). Ba truy vấn ở docs mục 5.1, mỗi truy vấn dùng một
chỉ mục của ERD mục 5.3: `shifts (doctor_id, weekday)`, `time_offs (doctor_id, start_at)`,
`appointments (doctor_id, start_at)`.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AppointmentStatus
from app.db.models.appointments import Appointment
from app.db.models.catalog import DoctorService, Specialty
from app.db.models.schedule import Shift, TimeOff
from app.db.models.users import Doctor, User
from app.modules.scheduling.engine import Interval, ShiftRule

ACTIVE_STATUSES = (AppointmentStatus.BOOKED, AppointmentStatus.ARRIVED)
# Một lịch dài tối đa 120 phút (CHECK ck_services_duration), nên lịch chồng khoảng [start, end)
# phải bắt đầu sau start − 120 phút: cận dưới này giúp chỉ mục không quét cả lịch sử cũ.
MAX_APPOINTMENT_LENGTH = timedelta(minutes=120)


@dataclass
class DoctorShifts:
    names: dict[int, str] = field(default_factory=dict)  # bác sĩ → họ tên, theo id tăng dần
    by_service: dict[int, list[int]] = field(default_factory=dict)  # dịch vụ → bác sĩ
    shifts: list[ShiftRule] = field(default_factory=list)


async def doctors_with_shifts(
    session: AsyncSession,
    service_ids: Sequence[int],
    first_day: date,
    last_day: date,
    *,
    doctor_id: int | None = None,
) -> DoctorShifts:
    """Truy vấn (1): bác sĩ đang hoạt động (thuộc chuyên khoa đang hoạt động) thực hiện dịch vụ,
    kèm ca làm hiệu lực trong khoảng.

    LEFT JOIN để bác sĩ chưa có ca vẫn có mặt (khung trống rỗng, không phải "không thực hiện").
    """
    stmt = (
        select(
            DoctorService.service_id,
            User.id,
            User.full_name,
            Shift.id,
            Shift.weekday,
            Shift.start_time,
            Shift.end_time,
            Shift.valid_from,
            Shift.valid_to,
        )
        .join(Doctor, Doctor.user_id == DoctorService.doctor_id)
        .join(User, User.id == Doctor.user_id)
        .join(Specialty, Specialty.id == Doctor.specialty_id)
        .outerjoin(
            Shift,
            and_(
                Shift.doctor_id == Doctor.user_id,
                Shift.valid_from <= last_day,
                or_(Shift.valid_to.is_(None), Shift.valid_to >= first_day),
            ),
        )
        .where(
            DoctorService.service_id.in_(service_ids),
            User.is_active.is_(True),
            User.anonymized_at.is_(None),
            Specialty.is_active.is_(True),  # chuyên khoa của bác sĩ bị ẩn thì bác sĩ cũng ẩn
        )
        .order_by(User.id, Shift.weekday, Shift.start_time)
    )
    if doctor_id is not None:
        stmt = stmt.where(User.id == doctor_id)
    result = DoctorShifts()
    seen_shifts: set[int] = set()
    for row in (await session.execute(stmt)).all():
        service_id, user_id, name, shift_id = row[0], row[1], row[2], row[3]
        result.names[user_id] = name
        doctors = result.by_service.setdefault(service_id, [])
        if user_id not in doctors:
            doctors.append(user_id)
        if shift_id is not None and shift_id not in seen_shifts:
            seen_shifts.add(shift_id)
            result.shifts.append(ShiftRule(user_id, row[4], row[5], row[6], row[7], row[8]))
    return result


async def time_offs_overlapping(
    session: AsyncSession, doctor_ids: Sequence[int], start: datetime, end: datetime
) -> dict[int, list[Interval]]:
    """Truy vấn (2): ngày nghỉ chồng khoảng [start, end)."""
    if not doctor_ids:
        return {}
    stmt = select(TimeOff.doctor_id, TimeOff.start_at, TimeOff.end_at).where(
        TimeOff.doctor_id.in_(doctor_ids), TimeOff.start_at < end, TimeOff.end_at > start
    )
    result: dict[int, list[Interval]] = {}
    for doctor_id, start_at, end_at in (await session.execute(stmt)).all():
        result.setdefault(doctor_id, []).append(Interval(start_at, end_at))
    return result


async def booked_overlapping(
    session: AsyncSession,
    doctor_ids: Sequence[int],
    start: datetime,
    end: datetime,
    *,
    exclude_appointment_id: int | None = None,
) -> dict[int, list[Interval]]:
    """Truy vấn (3): lịch BOOKED/ARRIVED chồng khoảng; khi đổi lịch thì bỏ chính lịch đang đổi."""
    if not doctor_ids:
        return {}
    stmt = select(Appointment.doctor_id, Appointment.start_at, Appointment.end_at).where(
        Appointment.doctor_id.in_(doctor_ids),
        Appointment.status.in_(ACTIVE_STATUSES),
        Appointment.start_at < end,
        Appointment.start_at > start - MAX_APPOINTMENT_LENGTH,
        Appointment.end_at > start,
    )
    if exclude_appointment_id is not None:
        stmt = stmt.where(Appointment.id != exclude_appointment_id)
    result: dict[int, list[Interval]] = {}
    for doctor_id, start_at, end_at in (await session.execute(stmt)).all():
        result.setdefault(doctor_id, []).append(Interval(start_at, end_at))
    return result
