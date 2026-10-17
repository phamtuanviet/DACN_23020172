"""Dữ liệu vào bất thường trả 422 thay vì 500; ẩn chuyên khoa thì bác sĩ của nó cũng ẩn;
hàm dùng chung của appointments vẫn kiểm quyền khi được gọi thẳng (docs mục 4.6, 4.7)."""

from datetime import date, time

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.errors import AppError
from app.core.timeutil import local_datetime
from app.db.enums import Channel, Gender, UserRole
from app.db.models.catalog import DoctorService, Specialty
from app.db.models.schedule import Shift
from app.db.models.users import Doctor, User
from app.modules.appointments.service import booked_for_doctor, flag_for_attention
from app.modules.catalog.schemas import ServiceUpdate, SpecialtyCreate
from app.modules.catalog.service import CatalogService
from app.modules.schedule.schemas import ShiftIn
from app.modules.schedule.service import ScheduleService
from tests.integration.conftest import MutableClock
from tests.integration.factories import (
    MONDAY,
    Clinic,
    add_appointment,
    at,
    bearer,
    build_clinic,
)

pytestmark = pytest.mark.integration

TOO_BIG = "9223372036854775808"  # 2^63, vượt kiểu bigint


@pytest.fixture
async def clinic(db: AsyncSession) -> Clinic:
    return await build_clinic(db)


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/doctors/99999999999999999999",
        f"/api/v1/services?specialty_id={TOO_BIG}",
        f"/api/v1/doctors?service_id={TOO_BIG}",
        f"/api/v1/availability?service_id={TOO_BIG}",
        f"/api/v1/availability/earliest?service_id={TOO_BIG}",
        "/api/v1/services?q=%00",
        "/api/v1/doctors?q=a%00b",
        "/api/v1/availability?service_id=1&date_from=9999-12-31",
        "/api/v1/availability?service_id=1&date_from=0001-01-01",
    ],
)
async def test_out_of_range_input_is_rejected_with_422(
    app_client: AsyncClient, clinic: Clinic, url: str
) -> None:
    response = await app_client.get(url)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_booking_rejects_nul_in_reason_and_oversized_ids(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    headers = bearer(clinic.patient_ids[0], UserRole.PATIENT)
    nul = await app_client.post(
        "/api/v1/appointments",
        json={"service_id": clinic.service_id, "start_at": at(MONDAY, 8), "reason": "Ho\u0000"},
        headers=headers,
    )
    assert nul.status_code == 422
    too_big = await app_client.post(
        "/api/v1/appointments",
        json={"service_id": int(TOO_BIG), "start_at": at(MONDAY, 8)},
        headers=headers,
    )
    assert too_big.status_code == 422


async def test_admin_input_with_nul_or_extreme_dates_is_rejected(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    admin = bearer(clinic.admin_id, UserRole.ADMIN)
    name = await app_client.post(
        "/api/v1/admin/specialties", json={"name": "Nhi\u0000"}, headers=admin
    )
    assert name.status_code == 422
    time_off = await app_client.post(
        f"/api/v1/admin/doctors/{clinic.doctor_ids[0]}/time-offs",
        json={"start_at": "9999-12-31T00:00:00+00:00", "end_at": "9999-12-31T12:00:00+00:00"},
        headers=admin,
    )
    assert time_off.status_code == 422
    since = await app_client.get(
        f"/api/v1/admin/doctors/{clinic.doctor_ids[0]}/time-offs",
        params={"since": "0001-01-01"},
        headers=admin,
    )
    assert since.status_code == 422


async def test_doctor_of_hidden_specialty_is_hidden_and_cannot_be_booked(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """Bác sĩ thuộc chuyên khoa đã ẩn nhưng làm dịch vụ của chuyên khoa đang hoạt động."""
    async with db.begin():
        hidden = Specialty(name="Mắt", is_active=False)
        db.add(hidden)
        user = User(
            email="bs.mat@example.com", password_hash="x", role=UserRole.DOCTOR, full_name="BS. Mắt"
        )
        db.add(user)
        await db.flush()
        db.add(Doctor(user_id=user.id, specialty_id=hidden.id, title="BS.", gender=Gender.MALE))
        await db.flush()
        db.add(DoctorService(doctor_id=user.id, service_id=clinic.service_id))
        db.add(
            Shift(
                doctor_id=user.id,
                weekday=1,
                start_time=time(8, 0),
                end_time=time(11, 30),
                valid_from=date(2026, 10, 1),
            )
        )

    services = await app_client.get(
        "/api/v1/services", params={"specialty_id": clinic.specialty_id}
    )
    listed = {d["id"] for s in services.json() for d in s["doctors"]}
    assert user.id not in listed

    slots = await app_client.get(
        "/api/v1/availability", params={"service_id": clinic.service_id, "date_from": "2026-10-12"}
    )
    offered = {d["id"] for slot in slots.json()["days"][0]["slots"] for d in slot["doctors"]}
    assert offered and user.id not in offered

    booking = await app_client.post(
        "/api/v1/appointments",
        json={"service_id": clinic.service_id, "doctor_id": user.id, "start_at": at(MONDAY, 8)},
        headers=bearer(clinic.patient_ids[0], UserRole.PATIENT),
    )
    assert booking.status_code == 400
    assert booking.json()["code"] == "DOCTOR_SERVICE_MISMATCH"


async def test_shared_schedule_helpers_check_the_actor(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """Tool của Agent gọi thẳng service: bệnh nhân không được gắn cờ hay xem lịch theo bác sĩ."""
    appointment_id = await add_appointment(db, clinic, start=time(9, 0), patient_index=1)
    patient = Actor(clinic.patient_ids[0], UserRole.PATIENT, Channel.AGENT)
    async with db.begin():
        with pytest.raises(AppError) as flag_error:
            await flag_for_attention(db, patient, [appointment_id], source={"source": "TEST"})
        with pytest.raises(AppError) as read_error:
            await booked_for_doctor(
                db, patient, clinic.doctor_ids[0], start=local_datetime(MONDAY, time(0))
            )
    assert flag_error.value.code == read_error.value.code == "FORBIDDEN"


async def test_admin_services_refuse_non_admin_actors_when_called_directly(
    db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    """Lớp 2 ở service: không đi qua router vẫn bị chặn (docs mục 4.6)."""
    catalog = CatalogService(db, clock)
    schedule = ScheduleService(db, clock)
    doctor_id = clinic.doctor_ids[0]
    shift = ShiftIn(weekday=7, start_time=time(8), end_time=time(9), valid_from=date(2026, 10, 1))
    calls = [
        lambda actor: catalog.admin_list_specialties(actor),
        lambda actor: catalog.create_specialty(actor, SpecialtyCreate(name="Nhi")),
        lambda actor: catalog.update_service(
            actor, clinic.service_id, ServiceUpdate(is_active=False)
        ),
        lambda actor: schedule.list_shifts(actor, doctor_id),
        lambda actor: schedule.create_shift(actor, doctor_id, shift),
        lambda actor: schedule.delete_time_off(actor, doctor_id, 1),
    ]
    for actor in (
        Actor(clinic.patient_ids[0], UserRole.PATIENT, Channel.AGENT),
        Actor(doctor_id, UserRole.DOCTOR, Channel.WEB),
    ):
        for call in calls:
            with pytest.raises(AppError) as error:
                await call(actor)
            assert error.value.code == "FORBIDDEN"
