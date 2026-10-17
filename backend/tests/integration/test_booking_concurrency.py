"""Chống trùng lịch khi nhiều request cùng lúc (AC-03, NFR-04, BR-03, docs mục 10.2, 12).

Mỗi request chạy transaction riêng trên kết nối riêng (pool được nới cho đủ 20 kết nối), nên các
transaction thật sự chồng lên nhau: chính exclusion constraint quyết định ai thắng.
"""

import asyncio
from collections import Counter
from collections.abc import Iterator

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import UserRole
from app.db.models.appointments import Appointment
from tests.integration.conftest import _clear_caches
from tests.integration.factories import MONDAY, at, bearer, build_clinic

pytestmark = pytest.mark.integration

CONCURRENT_REQUESTS = 20


@pytest.fixture
def wide_pool(monkeypatch: pytest.MonkeyPatch, test_database_url: str) -> Iterator[None]:
    """Pool mặc định 4 + 2 kết nối sẽ xếp hàng các request; nới ra để 20 request chạy song song."""
    monkeypatch.setenv("DB_POOL_SIZE", str(CONCURRENT_REQUESTS + 5))
    _clear_caches()
    yield
    monkeypatch.undo()
    _clear_caches()


async def test_twenty_patients_booking_the_same_slot_create_exactly_one_appointment(
    wide_pool: None, app_client: AsyncClient, db: AsyncSession
) -> None:
    clinic = await build_clinic(db, doctors=1, patients=CONCURRENT_REQUESTS)
    start_at = at(MONDAY, 8, 0)

    async def attempt(patient_id: int) -> tuple[int, str | None]:
        response = await app_client.post(
            "/api/v1/appointments",
            json={
                "service_id": clinic.service_id,
                "doctor_id": clinic.doctor_ids[0],
                "start_at": start_at,
            },
            headers=bearer(patient_id, UserRole.PATIENT),
        )
        return response.status_code, response.json().get("code")

    results = await asyncio.gather(*(attempt(p) for p in clinic.patient_ids))

    statuses = Counter(status for status, _ in results)
    assert statuses == {201: 1, 409: CONCURRENT_REQUESTS - 1}
    assert {code for status, code in results if status == 409} == {"SLOT_TAKEN"}
    count = (await db.execute(select(func.count()).select_from(Appointment))).scalar_one()
    assert count == 1


async def test_parallel_bookings_of_one_patient_respect_the_three_appointment_limit(
    wide_pool: None, app_client: AsyncClient, db: AsyncSession
) -> None:
    """Khóa dòng bệnh nhân (FOR UPDATE): 6 request cùng lúc ở 6 khung khác nhau chỉ 3 lịch thành
    công, thay vì mỗi request cùng đếm thấy 0 lịch rồi cùng đặt (BR-09, docs mục 5.4)."""
    clinic = await build_clinic(db, doctors=1, patients=1)
    headers = bearer(clinic.patient_ids[0], UserRole.PATIENT)

    async def attempt(hour: int, minute: int) -> tuple[int, str | None]:
        response = await app_client.post(
            "/api/v1/appointments",
            json={
                "service_id": clinic.service_id,
                "doctor_id": clinic.doctor_ids[0],
                "start_at": at(MONDAY, hour, minute),
            },
            headers=headers,
        )
        return response.status_code, response.json().get("code")

    slots = [(8, 0), (8, 40), (9, 20), (10, 0), (10, 40), (11, 0)]
    results = await asyncio.gather(*(attempt(h, m) for h, m in slots))

    assert Counter(status for status, _ in results) == {201: 3, 409: 3}
    assert {code for status, code in results if status == 409} == {"MAX_ACTIVE_APPOINTMENTS"}
