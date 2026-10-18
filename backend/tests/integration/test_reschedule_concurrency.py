"""Đổi lịch khi nhiều request cùng lúc (AC-04, BR-04, NFR-09, docs mục 5.4).

Mỗi request chạy transaction riêng trên kết nối riêng (`wide_pool`), nên chính khóa dòng và
exclusion constraint quyết định ai thắng. Không request nào được trả 500 (deadlock, lỗi khóa).
"""

import asyncio
from collections import Counter
from datetime import time

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import local_datetime
from app.db.enums import AppointmentStatus, UserRole
from app.db.models.appointments import Appointment
from tests.integration.factories import MONDAY, add_appointment, at, bearer, build_clinic, fetch

pytestmark = pytest.mark.integration

PATIENTS = 10


async def test_patients_racing_to_move_into_one_slot_leave_exactly_one_winner(
    wide_pool: None, app_client: AsyncClient, db: AsyncSession
) -> None:
    """10 bệnh nhân cùng dời lịch vào khung 10:00: 1 thành công, 9 nhận SLOT_TAKEN và giữ nguyên
    lịch cũ (AC-04)."""
    clinic = await build_clinic(db, doctors=PATIENTS, patients=PATIENTS)
    ids = [
        await add_appointment(db, clinic, start=time(8, 0), doctor_index=i, patient_index=i)
        for i in range(PATIENTS)
    ]

    async def attempt(i: int) -> tuple[int, str | None]:
        response = await app_client.patch(
            f"/api/v1/appointments/{ids[i]}/reschedule",
            json={"start_at": at(MONDAY, 10), "doctor_id": clinic.doctor_ids[0]},
            headers=bearer(clinic.patient_ids[i], UserRole.PATIENT),
        )
        return response.status_code, response.json().get("code")

    results = await asyncio.gather(*(attempt(i) for i in range(PATIENTS)))

    assert Counter(status for status, _ in results) == {200: 1, 409: PATIENTS - 1}
    assert {code for status, code in results if status == 409} == {"SLOT_TAKEN"}
    for i, (status, _) in enumerate(results):
        if status == 409:
            assert (await fetch(db, ids[i])).start_at == local_datetime(MONDAY, time(8))


async def test_reschedule_racing_with_new_bookings_never_double_books(
    wide_pool: None, app_client: AsyncClient, db: AsyncSession
) -> None:
    clinic = await build_clinic(db, doctors=1, patients=PATIENTS)
    moving = await add_appointment(db, clinic, start=time(8, 0))

    async def move() -> int:
        response = await app_client.patch(
            f"/api/v1/appointments/{moving}/reschedule",
            json={"start_at": at(MONDAY, 10), "doctor_id": clinic.doctor_ids[0]},
            headers=bearer(clinic.patient_ids[0], UserRole.PATIENT),
        )
        return response.status_code

    async def book(i: int) -> int:
        response = await app_client.post(
            "/api/v1/appointments",
            json={
                "service_id": clinic.service_id,
                "doctor_id": clinic.doctor_ids[0],
                "start_at": at(MONDAY, 10),
            },
            headers=bearer(clinic.patient_ids[i], UserRole.PATIENT),
        )
        return response.status_code

    statuses = await asyncio.gather(move(), *(book(i) for i in range(1, PATIENTS)))

    assert 500 not in statuses
    assert sum(status in (200, 201) for status in statuses) == 1
    at_ten = await db.execute(
        select(func.count()).where(
            Appointment.start_at == local_datetime(MONDAY, time(10)),
            Appointment.status == AppointmentStatus.BOOKED,
        )
    )
    assert at_ten.scalar_one() == 1


@pytest.mark.parametrize("round_", range(5))
async def test_moving_away_while_admin_adds_time_off_never_leaves_a_stale_flag(
    wide_pool: None, app_client: AsyncClient, db: AsyncSession, round_: int
) -> None:
    """Bệnh nhân dời lịch sang bác sĩ khác đúng lúc quản trị thêm ngày nghỉ cho bác sĩ cũ: dù bên
    nào xong trước, lịch cuối cùng ở bác sĩ mới và không mang cờ "cần xử lý"; không deadlock."""
    clinic = await build_clinic(db, doctors=2, patients=1)
    appointment_id = await add_appointment(db, clinic, start=time(9, 0))

    move = app_client.patch(
        f"/api/v1/appointments/{appointment_id}/reschedule",
        json={"start_at": at(MONDAY, 10), "doctor_id": clinic.doctor_ids[1]},
        headers=bearer(clinic.patient_ids[0], UserRole.PATIENT),
    )
    time_off = app_client.post(
        f"/api/v1/admin/doctors/{clinic.doctor_ids[0]}/time-offs",
        json={"start_at": at(MONDAY, 8), "end_at": at(MONDAY, 12)},
        headers=bearer(clinic.admin_id, UserRole.ADMIN),
    )
    moved, added = await asyncio.gather(move, time_off)

    assert (moved.status_code, added.status_code) == (200, 201)
    final = await fetch(db, appointment_id)
    assert final.doctor_id == clinic.doctor_ids[1]
    assert final.needs_attention is False
