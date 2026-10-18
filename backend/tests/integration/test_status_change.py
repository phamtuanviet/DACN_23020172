"""Đổi trạng thái buổi khám theo sơ đồ (FR-APT-06, FR-DOC-02, BR-11, docs mục 4.6, 5.5)."""

from datetime import date, time

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import local_datetime
from app.db.enums import AppointmentStatus, HistoryAction, UserRole
from app.db.models.appointments import AppointmentHistory
from tests.integration.conftest import MutableClock
from tests.integration.factories import (
    MONDAY,
    Clinic,
    add_appointment,
    bearer,
    build_clinic,
    fetch,
)

pytestmark = pytest.mark.integration

LAST_FRIDAY = date(2026, 10, 9)


@pytest.fixture
async def clinic(db: AsyncSession) -> Clinic:
    return await build_clinic(db)


async def set_status(
    client: AsyncClient, appointment_id: int, status: str, headers: dict[str, str]
) -> Response:
    return await client.patch(
        f"/api/v1/appointments/{appointment_id}/status", json={"status": status}, headers=headers
    )


async def test_doctor_marks_arrived_then_completed_on_the_day(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(9, 0), needs_attention=True)
    clock.at = local_datetime(MONDAY, time(8, 50))  # bệnh nhân đến sớm 10 phút
    doctor = bearer(clinic.doctor_ids[0], UserRole.DOCTOR, clock.at)

    arrived = await set_status(app_client, appointment_id, "ARRIVED", doctor)
    completed = await set_status(app_client, appointment_id, "COMPLETED", doctor)

    assert arrived.status_code == completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"
    assert completed.json()["can_change"] is False
    after = await fetch(db, appointment_id)
    assert after.needs_attention is False
    rows = list(
        (await db.execute(select(AppointmentHistory).order_by(AppointmentHistory.id))).scalars()
    )
    assert [r.action for r in rows] == [HistoryAction.STATUS_CHANGE] * 2
    assert [r.new_value["status"] for r in rows if r.new_value] == ["ARRIVED", "COMPLETED"]


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (AppointmentStatus.BOOKED, "COMPLETED"),
        (AppointmentStatus.CANCELLED, "ARRIVED"),
        (AppointmentStatus.COMPLETED, "NO_SHOW"),
        (AppointmentStatus.ARRIVED, "ARRIVED"),
    ],
)
async def test_transitions_outside_the_state_machine_are_rejected(
    app_client: AsyncClient,
    db: AsyncSession,
    clinic: Clinic,
    clock: MutableClock,
    current: AppointmentStatus,
    target: str,
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(9, 0), status=current)
    clock.at = local_datetime(MONDAY, time(9, 30))
    admin = bearer(clinic.admin_id, UserRole.ADMIN, clock.at)
    response = await set_status(app_client, appointment_id, target, admin)
    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_TRANSITION"
    assert response.json()["details"] == {"status": current.value}


async def test_doctor_updates_only_own_appointments_of_today(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    today = await add_appointment(db, clinic, start=time(9, 0))
    yesterday = await add_appointment(db, clinic, day=LAST_FRIDAY, start=time(9, 0))
    clock.at = local_datetime(MONDAY, time(9, 30))
    doctor = bearer(clinic.doctor_ids[0], UserRole.DOCTOR, clock.at)
    other_doctor = bearer(clinic.doctor_ids[1], UserRole.DOCTOR, clock.at)

    assert (await set_status(app_client, today, "ARRIVED", other_doctor)).status_code == 403
    late = await set_status(app_client, yesterday, "NO_SHOW", doctor)
    assert late.status_code == 409 and late.json()["code"] == "INVALID_TRANSITION"
    admin = bearer(clinic.admin_id, UserRole.ADMIN, clock.at)
    fixed = await set_status(app_client, yesterday, "NO_SHOW", admin)  # quản trị sửa ngày đã qua
    assert fixed.status_code == 200


async def test_no_show_only_after_the_start_time_and_never_for_future_days(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(9, 0))
    clock.at = local_datetime(MONDAY, time(8, 0))
    doctor = bearer(clinic.doctor_ids[0], UserRole.DOCTOR, clock.at)
    early = await set_status(app_client, appointment_id, "NO_SHOW", doctor)
    assert early.status_code == 409

    clock.at = local_datetime(date(2026, 10, 11), time(9, 0))  # hôm trước ngày khám
    admin = bearer(clinic.admin_id, UserRole.ADMIN, clock.at)
    future = await set_status(app_client, appointment_id, "ARRIVED", admin)
    assert future.status_code == 409

    clock.at = local_datetime(MONDAY, time(9, 16))
    doctor = bearer(clinic.doctor_ids[0], UserRole.DOCTOR, clock.at)
    no_show = await set_status(app_client, appointment_id, "NO_SHOW", doctor)
    assert no_show.status_code == 200


async def test_patients_and_cancellation_do_not_go_through_status(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(9, 0))
    patient = bearer(clinic.patient_ids[0], UserRole.PATIENT)
    assert (await set_status(app_client, appointment_id, "ARRIVED", patient)).status_code == 403
    admin = bearer(clinic.admin_id, UserRole.ADMIN)
    cancelled = await set_status(app_client, appointment_id, "CANCELLED", admin)
    assert cancelled.status_code == 422  # hủy đi qua /cancel để có lý do và email
