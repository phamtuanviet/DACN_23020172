"""Truy vấn của module appointments: appointments, appointment_history; khóa dòng (docs mục 5.4).

Không ra quyết định nghiệp vụ (docs mục 4.2). Thứ tự khóa luôn là bệnh nhân → bác sĩ → lịch hẹn.
Câu khóa dòng dùng `populate_existing`: dòng đã nạp trước đó trong session được đọc lại sau khi
chờ khóa, nên kiểm tra nghiệp vụ luôn chạy trên dữ liệu mới nhất.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Select, and_, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.enums import AppointmentStatus, UserRole
from app.db.models.appointments import Appointment, AppointmentHistory
from app.db.models.catalog import Service
from app.db.models.users import Doctor, PatientProfile, User
from app.modules.appointments.schemas import Scope

ACTIVE_STATUSES = (AppointmentStatus.BOOKED, AppointmentStatus.ARRIVED)


@dataclass(frozen=True, slots=True)
class AppointmentRow:
    appointment: Appointment
    service_name: str
    patient_name: str


@dataclass(frozen=True, slots=True)
class ListedAppointment:
    appointment: Appointment
    service_name: str
    doctor_name: str


@dataclass(frozen=True, slots=True)
class DetailRow:
    appointment: Appointment
    service_name: str
    doctor_name: str
    patient_name: str
    patient_birthday: date | None


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
    stmt = (
        select(Appointment)
        .where(Appointment.id.in_(ids))
        .order_by(Appointment.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return list((await session.execute(stmt)).scalars())


async def get_appointment(session: AsyncSession, appointment_id: int) -> Appointment | None:
    """Đọc không khóa: kiểm tra quyền và biết bác sĩ cần khóa trước khi khóa chính lịch hẹn."""
    return await session.get(Appointment, appointment_id)


async def lock_appointment(session: AsyncSession, appointment_id: int) -> Appointment | None:
    stmt = (
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def user_email(session: AsyncSession, user_id: int) -> str:
    return (await session.execute(select(User.email).where(User.id == user_id))).scalar_one()


def _scope_filter(scope: Scope, now: datetime) -> Select[Appointment]:
    upcoming = and_(Appointment.status.in_(ACTIVE_STATUSES), Appointment.end_at > now)
    return select(Appointment).where(upcoming if scope is Scope.UPCOMING else not_(upcoming))


async def list_for_patient(
    session: AsyncSession,
    patient_id: int,
    *,
    scope: Scope,
    status: AppointmentStatus | None,
    now: datetime,
    offset: int,
    limit: int,
) -> tuple[list[ListedAppointment], int]:
    """Lịch của bệnh nhân theo phạm vi: sắp tới xếp gần nhất trước, lịch sử xếp mới nhất trước.

    Dùng chỉ mục `appointments (patient_id, start_at DESC)`.
    """
    base = _scope_filter(scope, now).where(Appointment.patient_id == patient_id)
    if status is not None:
        base = base.where(Appointment.status == status)
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    order = (
        (Appointment.start_at, Appointment.id)
        if scope is Scope.UPCOMING
        else (Appointment.start_at.desc(), Appointment.id.desc())
    )
    stmt = (
        base.add_columns(Service.name, User.full_name)
        .join(Service, Service.id == Appointment.service_id)
        .join(User, User.id == Appointment.doctor_id)
        .order_by(*order)
        .offset(offset)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [ListedAppointment(row[0], row[1], row[2]) for row in rows], total


async def detail(session: AsyncSession, appointment_id: int) -> DetailRow | None:
    doctor = aliased(User, name="doctor_user")
    stmt = (
        select(
            Appointment,
            Service.name,
            doctor.full_name,
            User.full_name,
            PatientProfile.date_of_birth,
        )
        .join(Service, Service.id == Appointment.service_id)
        .join(doctor, doctor.id == Appointment.doctor_id)
        .join(User, User.id == Appointment.patient_id)
        .outerjoin(PatientProfile, PatientProfile.user_id == Appointment.patient_id)
        .where(Appointment.id == appointment_id)
    )
    row = (await session.execute(stmt)).one_or_none()
    if row is None:
        return None
    return DetailRow(row[0], row[1], row[2], row[3], row[4])


async def labels(session: AsyncSession, appointment: Appointment) -> tuple[str, str]:
    """Tên dịch vụ và họ tên bác sĩ của lịch hẹn, để trả kết quả sau khi ghi."""
    service = select(Service.name).where(Service.id == appointment.service_id).scalar_subquery()
    doctor = select(User.full_name).where(User.id == appointment.doctor_id).scalar_subquery()
    row = (await session.execute(select(service, doctor))).one()
    return row[0], row[1]


async def history_of(session: AsyncSession, appointment_id: int) -> list[AppointmentHistory]:
    stmt = (
        select(AppointmentHistory)
        .where(AppointmentHistory.appointment_id == appointment_id)
        .order_by(AppointmentHistory.created_at, AppointmentHistory.id)
    )
    return list((await session.execute(stmt)).scalars())


async def roles_of(session: AsyncSession, user_ids: Sequence[int]) -> dict[int, UserRole]:
    """Vai trò của người thao tác trong lịch sử (không trả họ tên nhân viên cho bệnh nhân)."""
    if not user_ids:
        return {}
    stmt = select(User.id, User.role).where(User.id.in_(user_ids))
    return {user_id: role for user_id, role in (await session.execute(stmt)).all()}


async def doctor_names(session: AsyncSession, doctor_ids: Sequence[int]) -> dict[int, str]:
    if not doctor_ids:
        return {}
    stmt = select(User.id, User.full_name).where(User.id.in_(doctor_ids))
    return {user_id: name for user_id, name in (await session.execute(stmt)).all()}
