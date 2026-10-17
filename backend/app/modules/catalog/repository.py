"""Truy vấn của module catalog: specialties, services, doctors, doctor_services.

Không ra quyết định nghiệp vụ (docs mục 4.2). Tìm kiếm không dấu dùng `unaccent` + `ILIKE`, quét
tuần tự vì mỗi bảng chỉ vài chục dòng (docs mục 7.2).
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import ColumnElement, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.appointments import Appointment
from app.db.models.catalog import DoctorService, Service, Specialty
from app.db.models.schedule import Shift
from app.db.models.users import Doctor, User


@dataclass(frozen=True, slots=True)
class SpecialtyRow:
    specialty: Specialty
    service_count: int
    doctor_count: int
    min_price_vnd: int | None


@dataclass(frozen=True, slots=True)
class ServiceRow:
    service: Service
    specialty_name: str


@dataclass(frozen=True, slots=True)
class DoctorRow:
    doctor: Doctor
    name: str
    specialty_name: str


def _active_user() -> ColumnElement[bool]:
    return and_(User.is_active.is_(True), User.anonymized_at.is_(None))


def _matches_all(text: ColumnElement[str], tokens: Sequence[str]) -> list[ColumnElement[bool]]:
    """Mỗi từ khóa phải xuất hiện (bỏ dấu, không phân biệt hoa thường) ở đâu đó trong `text`."""
    conditions: list[ColumnElement[bool]] = []
    for token in tokens:
        escaped = token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(func.unaccent(text).ilike(func.unaccent(f"%{escaped}%")))
    return conditions


# ---------------------------------------------------------------------------- chuyên khoa
async def list_specialties(session: AsyncSession, *, include_hidden: bool) -> list[SpecialtyRow]:
    service_count = (
        select(func.count())
        .where(Service.specialty_id == Specialty.id, Service.is_active.is_(True))
        .scalar_subquery()
    )
    min_price = (
        select(func.min(Service.ref_price_vnd))
        .where(Service.specialty_id == Specialty.id, Service.is_active.is_(True))
        .scalar_subquery()
    )
    doctor_count = (
        select(func.count())
        .select_from(Doctor)
        .join(User, User.id == Doctor.user_id)
        .where(Doctor.specialty_id == Specialty.id, _active_user())
        .scalar_subquery()
    )
    stmt = select(Specialty, service_count, doctor_count, min_price).order_by(Specialty.id)
    if not include_hidden:
        stmt = stmt.where(Specialty.is_active.is_(True))
    rows = (await session.execute(stmt)).all()
    return [SpecialtyRow(row[0], row[1], row[2], row[3]) for row in rows]


async def get_specialty(session: AsyncSession, specialty_id: int) -> Specialty | None:
    return await session.get(Specialty, specialty_id)


async def specialty_name_taken(
    session: AsyncSession, name: str, *, exclude_id: int | None = None
) -> bool:
    stmt = select(Specialty.id).where(func.lower(Specialty.name) == name.lower())
    if exclude_id is not None:
        stmt = stmt.where(Specialty.id != exclude_id)
    return (await session.execute(stmt)).first() is not None


# ---------------------------------------------------------------------------- dịch vụ
async def search_services(
    session: AsyncSession,
    *,
    tokens: Sequence[str],
    specialty_id: int | None,
    include_hidden: bool,
) -> list[ServiceRow]:
    stmt = (
        select(Service, Specialty.name)
        .join(Specialty, Specialty.id == Service.specialty_id)
        .order_by(Service.specialty_id, Service.id)
    )
    if not include_hidden:
        stmt = stmt.where(Service.is_active.is_(True), Specialty.is_active.is_(True))
    if specialty_id is not None:
        stmt = stmt.where(Service.specialty_id == specialty_id)
    text = func.concat_ws(" ", Service.name, Specialty.name, Service.scope_description)
    stmt = stmt.where(*_matches_all(text, tokens))
    rows = (await session.execute(stmt)).all()
    return [ServiceRow(row[0], row[1]) for row in rows]


async def get_service_row(session: AsyncSession, service_id: int) -> ServiceRow | None:
    stmt = (
        select(Service, Specialty.name)
        .join(Specialty, Specialty.id == Service.specialty_id)
        .where(Service.id == service_id)
    )
    row = (await session.execute(stmt)).first()
    return ServiceRow(row[0], row[1]) if row else None


async def bookable_services(session: AsyncSession, service_ids: Sequence[int]) -> list[Service]:
    """Dịch vụ đặt được: dịch vụ và chuyên khoa của nó đều đang hoạt động."""
    if not service_ids:
        return []
    stmt = (
        select(Service)
        .join(Specialty, Specialty.id == Service.specialty_id)
        .where(
            Service.id.in_(service_ids),
            Service.is_active.is_(True),
            Specialty.is_active.is_(True),
        )
        .order_by(Service.id)
    )
    return list((await session.execute(stmt)).scalars())


async def service_name_taken(
    session: AsyncSession, specialty_id: int, name: str, *, exclude_id: int | None = None
) -> bool:
    stmt = select(Service.id).where(
        Service.specialty_id == specialty_id, func.lower(Service.name) == name.lower()
    )
    if exclude_id is not None:
        stmt = stmt.where(Service.id != exclude_id)
    return (await session.execute(stmt)).first() is not None


async def doctors_by_service(
    session: AsyncSession, service_ids: Sequence[int]
) -> dict[int, list[tuple[int, str]]]:
    """Bác sĩ đang hoạt động (chuyên khoa của bác sĩ cũng đang hoạt động) theo từng dịch vụ:
    {service_id: [(doctor_id, họ tên)]}."""
    if not service_ids:
        return {}
    stmt = (
        select(DoctorService.service_id, User.id, User.full_name)
        .join(Doctor, Doctor.user_id == DoctorService.doctor_id)
        .join(User, User.id == Doctor.user_id)
        .join(Specialty, Specialty.id == Doctor.specialty_id)
        .where(
            DoctorService.service_id.in_(service_ids), _active_user(), Specialty.is_active.is_(True)
        )
        .order_by(User.id)
    )
    result: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for service_id, doctor_id, name in (await session.execute(stmt)).all():
        result[service_id].append((doctor_id, name))
    return result


async def appointment_counts(session: AsyncSession, service_ids: Sequence[int]) -> dict[int, int]:
    if not service_ids:
        return {}
    stmt = (
        select(Appointment.service_id, func.count())
        .where(Appointment.service_id.in_(service_ids))
        .group_by(Appointment.service_id)
    )
    return {service_id: count for service_id, count in (await session.execute(stmt)).all()}


# ---------------------------------------------------------------------------- bác sĩ
async def search_doctors(
    session: AsyncSession,
    *,
    tokens: Sequence[str],
    specialty_id: int | None,
    service_id: int | None,
) -> list[DoctorRow]:
    """Bác sĩ đang hoạt động, thuộc chuyên khoa đang hoạt động."""
    stmt = (
        select(Doctor, User.full_name, Specialty.name)
        .join(User, User.id == Doctor.user_id)
        .join(Specialty, Specialty.id == Doctor.specialty_id)
        .where(_active_user(), Specialty.is_active.is_(True))
        .order_by(User.id)
    )
    if specialty_id is not None:
        stmt = stmt.where(Doctor.specialty_id == specialty_id)
    if service_id is not None:
        stmt = stmt.where(
            exists().where(
                DoctorService.doctor_id == Doctor.user_id, DoctorService.service_id == service_id
            )
        )
    stmt = stmt.where(*_matches_all(func.concat_ws(" ", User.full_name, Specialty.name), tokens))
    rows = (await session.execute(stmt)).all()
    return [DoctorRow(row[0], row[1], row[2]) for row in rows]


async def get_active_doctor(session: AsyncSession, doctor_id: int) -> DoctorRow | None:
    stmt = (
        select(Doctor, User.full_name, Specialty.name)
        .join(User, User.id == Doctor.user_id)
        .join(Specialty, Specialty.id == Doctor.specialty_id)
        .where(Doctor.user_id == doctor_id, _active_user(), Specialty.is_active.is_(True))
    )
    row = (await session.execute(stmt)).first()
    return DoctorRow(row[0], row[1], row[2]) if row else None


async def services_by_doctor(
    session: AsyncSession, doctor_ids: Sequence[int]
) -> dict[int, list[Service]]:
    """Dịch vụ đang hoạt động (chuyên khoa cũng đang hoạt động) mà từng bác sĩ thực hiện."""
    if not doctor_ids:
        return {}
    stmt = (
        select(DoctorService.doctor_id, Service)
        .join(Service, Service.id == DoctorService.service_id)
        .join(Specialty, Specialty.id == Service.specialty_id)
        .where(
            DoctorService.doctor_id.in_(doctor_ids),
            Service.is_active.is_(True),
            Specialty.is_active.is_(True),
        )
        .order_by(Service.id)
    )
    result: dict[int, list[Service]] = defaultdict(list)
    for doctor_id, service in (await session.execute(stmt)).all():
        result[doctor_id].append(service)
    return result


async def current_shifts(session: AsyncSession, doctor_id: int, today: date) -> list[Shift]:
    """Ca làm hiệu lực hôm nay, để hiện "Lịch làm việc" trên hồ sơ bác sĩ."""
    stmt = (
        select(Shift)
        .where(
            Shift.doctor_id == doctor_id,
            Shift.valid_from <= today,
            or_(Shift.valid_to.is_(None), Shift.valid_to >= today),
        )
        .order_by(Shift.weekday, Shift.start_time)
    )
    return list((await session.execute(stmt)).scalars())
