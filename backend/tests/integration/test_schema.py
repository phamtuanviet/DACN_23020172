"""Ràng buộc đặt ở database (ERD mục 5): kiểm trên schema do Alembic tạo, không qua service."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import local_datetime
from app.db.enums import AppointmentStatus, Channel, Gender, UserRole
from app.db.models.appointments import Appointment
from app.db.models.catalog import Service, Specialty
from app.db.models.users import Doctor, User

pytestmark = pytest.mark.integration

DAY = date(2026, 10, 17)


@dataclass
class World:
    specialty_id: int
    service_id: int
    doctor_ids: list[int]
    patient_ids: list[int]


@pytest.fixture
async def world(db: AsyncSession, app_client: AsyncClient) -> AsyncIterator[World]:
    """Hai bác sĩ, hai bệnh nhân, một dịch vụ 20 phút; mỗi test chạy trong savepoint."""
    async with db.begin():
        specialty = Specialty(name="Da liễu")
        db.add(specialty)
        await db.flush()
        service = Service(
            specialty_id=specialty.id,
            name="Khám da liễu tổng quát",
            scope_description="Các vấn đề về da, tóc, móng.",
            duration_min=20,
            ref_price_vnd=250_000,
        )
        roles = [UserRole.DOCTOR, UserRole.DOCTOR, UserRole.PATIENT, UserRole.PATIENT]
        users = [
            User(email=f"u{i}@example.com", password_hash="x", role=role, full_name=f"Người {i}")
            for i, role in enumerate(roles)
        ]
        db.add_all([service, *users])
        await db.flush()
        db.add_all(
            Doctor(user_id=u.id, specialty_id=specialty.id, title="BS.", gender=Gender.MALE)
            for u in users[:2]
        )
        await db.flush()
        yield World(specialty.id, service.id, [u.id for u in users[:2]], [u.id for u in users[2:]])


async def _book(
    db: AsyncSession,
    world: World,
    code: str,
    start: time,
    *,
    doctor: int = 0,
    patient: int = 0,
    status: AppointmentStatus = AppointmentStatus.BOOKED,
) -> None:
    begin = local_datetime(DAY, start)
    async with db.begin_nested():
        db.add(
            Appointment(
                code=code,
                patient_id=world.patient_ids[patient],
                doctor_id=world.doctor_ids[doctor],
                service_id=world.service_id,
                start_at=begin,
                end_at=begin + timedelta(minutes=20),
                status=status,
                channel=Channel.WEB,
            )
        )


def _constraint(error: pytest.ExceptionInfo[IntegrityError]) -> str | None:
    return getattr(getattr(error.value.orig, "diag", None), "constraint_name", None)


async def test_doctor_cannot_have_two_overlapping_active_appointments(
    db: AsyncSession, world: World
) -> None:
    await _book(db, world, "LH-261017-AAAA", time(8, 0))
    with pytest.raises(IntegrityError) as error:
        await _book(db, world, "LH-261017-BBBB", time(8, 10), patient=1)
    assert _constraint(error) == "excl_doctor_overlap"


async def test_patient_cannot_have_two_overlapping_active_appointments(
    db: AsyncSession, world: World
) -> None:
    await _book(db, world, "LH-261017-CCCC", time(9, 0))
    with pytest.raises(IntegrityError) as error:
        await _book(db, world, "LH-261017-DDDD", time(9, 10), doctor=1)
    assert _constraint(error) == "excl_patient_overlap"


async def test_back_to_back_appointments_are_allowed(db: AsyncSession, world: World) -> None:
    await _book(db, world, "LH-261017-EEEE", time(8, 0))
    await _book(db, world, "LH-261017-FFFF", time(8, 20), patient=1)  # khoảng [) chạm nhau


async def test_cancelled_appointment_frees_the_slot(db: AsyncSession, world: World) -> None:
    await _book(db, world, "LH-261017-GGGG", time(10, 0), status=AppointmentStatus.CANCELLED)
    await _book(db, world, "LH-261017-HHHH", time(10, 0), patient=1)


async def test_service_duration_must_be_10_to_120_in_steps_of_5(
    db: AsyncSession, world: World
) -> None:
    with pytest.raises(IntegrityError) as error:
        async with db.begin_nested():
            db.add(
                Service(
                    specialty_id=world.specialty_id,
                    name="Khám lẻ phút",
                    scope_description="x",
                    duration_min=12,
                    ref_price_vnd=100_000,
                )
            )
    assert _constraint(error) == "ck_services_duration"
