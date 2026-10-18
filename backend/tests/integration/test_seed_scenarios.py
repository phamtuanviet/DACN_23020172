"""Tiêu chí "Xong khi" của Sprint 2, 3 và NFR-01 trên đúng dữ liệu mẫu của seed (docs mục 7.5).

- Gõ "da lieu" ra đúng các dịch vụ Da liễu (FR-CAT-04).
- Hồ sơ bác sĩ hiện khung trống thật của 7 ngày tới (UC03, FR-SCH-01..03).
- `/availability` p95 < 500 ms với dữ liệu seed (NFR-01).
- Lịch mẫu có vòng đời thật: đã khám, vắng mặt, đã hủy, đã đổi giờ (Sprint 3).
"""

import time as clock_time
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.enums import AppointmentStatus, HistoryAction
from app.db.models.appointments import Appointment, AppointmentHistory
from app.db.seed import DEMO_PASSWORD, seed_database
from tests.conftest import TEST_NOW
from tests.integration.conftest import MutableClock

pytestmark = pytest.mark.integration
TODAY = date(2026, 10, 10)  # Thứ Bảy, TEST_NOW 09:00


@pytest.fixture
async def seeded(db: AsyncSession, clock: MutableClock, app_client: AsyncClient) -> None:
    await seed_database(db, clock)


async def test_typing_da_lieu_finds_the_dermatology_services(
    seeded: None, app_client: AsyncClient
) -> None:
    response = await app_client.get("/api/v1/services", params={"q": "da lieu"})
    services = response.json()
    assert [s["name"] for s in services] == [
        "Khám da liễu tổng quát",
        "Tư vấn trị mụn",
        "Khám viêm da cơ địa",
    ]  # "Laser trị nám" đã ẩn nên không hiện
    assert {s["specialty"]["name"] for s in services} == {"Da liễu"}


async def test_doctor_profile_shows_real_free_slots_for_the_next_seven_days(
    seeded: None, app_client: AsyncClient, db: AsyncSession
) -> None:
    [doctor] = (await app_client.get("/api/v1/doctors", params={"q": "tran minh"})).json()
    profile = (await app_client.get(f"/api/v1/doctors/{doctor['id']}")).json()
    assert profile["name"] == "ThS. BS. Trần Minh"
    service = profile["services"][0]

    response = await app_client.get(
        "/api/v1/availability",
        params={
            "service_id": service["id"],
            "doctor_id": doctor["id"],
            "date_from": TODAY.isoformat(),
            "date_to": (TODAY + timedelta(days=6)).isoformat(),
        },
    )
    days = response.json()["days"]
    assert [d["date"] for d in days] == [(TODAY + timedelta(days=i)).isoformat() for i in range(7)]
    assert days[1]["status"] == "OFF"  # Chủ nhật 11/10 không có ca
    assert all(d["status"] == "OPEN" for d in days if d["date"] != "2026-10-11")

    booked = (
        await db.execute(
            select(Appointment.start_at, Appointment.end_at).where(
                Appointment.doctor_id == doctor["id"],
                Appointment.status == AppointmentStatus.BOOKED,
            )
        )
    ).all()
    for day in days:
        for slot in day["slots"]:
            start = slot["start_at"]
            assert start > "2026-10-10T09:00:00+07:00"  # không có khung đã qua
            assert slot["start_at"][11:16] >= "08:00" and slot["end_at"][11:16] <= "17:00"
            for booked_start, booked_end in booked:
                assert not (
                    booked_start.isoformat() < slot["end_at"]
                    and slot["start_at"] < booked_end.isoformat()
                ), "khung trống chồng lên lịch đã đặt"


async def test_availability_p95_is_under_500_ms_with_seed_data(
    seeded: None, app_client: AsyncClient
) -> None:
    services = (await app_client.get("/api/v1/services")).json()
    requests: list[dict[str, str | int]] = []
    for service in services:
        week = {"date_from": TODAY.isoformat(), "date_to": (TODAY + timedelta(days=6)).isoformat()}
        requests.append({"service_id": service["id"], **week})
        requests.append({"service_id": service["id"], "date_from": TODAY.isoformat()})
    month = {"date_from": TODAY.isoformat(), "date_to": (TODAY + timedelta(days=30)).isoformat()}
    requests += [{"service_id": s["id"], **month} for s in services[:5]]

    durations: list[float] = []
    for params in requests:
        started = clock_time.perf_counter()
        response = await app_client.get("/api/v1/availability", params=params)
        durations.append(clock_time.perf_counter() - started)
        assert response.status_code == 200
    durations.sort()
    p95 = durations[int(len(durations) * 0.95) - 1]
    assert p95 < 0.5, f"p95 = {p95 * 1000:.0f} ms"


async def test_seeded_appointments_have_a_realistic_lifecycle(
    seeded: None, app_client: AsyncClient, db: AsyncSession
) -> None:
    """Lịch mẫu đi qua chính service (Sprint 3): đủ trạng thái cuối, có lịch đổi giờ, lịch sử
    có mốc thời gian hợp lý và không bác sĩ nào khám hai người cùng lúc."""
    grouped = select(Appointment.status, func.count()).group_by(Appointment.status)
    counts = {status: count for status, count in (await db.execute(grouped)).all()}
    for status in ("BOOKED", "COMPLETED", "NO_SHOW", "CANCELLED"):
        assert counts.get(AppointmentStatus(status), 0) > 0, status
    assert AppointmentStatus.ARRIVED not in counts  # buổi khám đã qua đều có kết quả
    stale = await db.execute(
        select(func.count()).where(
            Appointment.status == AppointmentStatus.BOOKED, Appointment.end_at <= TEST_NOW
        )
    )
    assert stale.scalar_one() == 0
    actions = set((await db.execute(select(AppointmentHistory.action))).scalars())
    assert {HistoryAction.CREATE, HistoryAction.RESCHEDULE, HistoryAction.CANCEL} <= actions
    assert HistoryAction.STATUS_CHANGE in actions
    future_history = await db.execute(
        select(func.count()).where(AppointmentHistory.created_at > TEST_NOW)
    )
    assert future_history.scalar_one() == 0  # mốc thời gian theo đồng hồ của seed

    other = aliased(Appointment)
    overlapping = await db.execute(
        select(func.count())
        .select_from(Appointment)
        .join(
            other,
            (other.doctor_id == Appointment.doctor_id)
            & (other.id > Appointment.id)
            & (other.start_at < Appointment.end_at)
            & (Appointment.start_at < other.end_at),
        )
        .where(
            Appointment.status != AppointmentStatus.CANCELLED,
            other.status != AppointmentStatus.CANCELLED,
        )
    )
    assert overlapping.scalar_one() == 0
    await db.commit()

    login = await app_client.post(
        "/api/v1/auth/login", json={"email": "lan@demo.local", "password": DEMO_PASSWORD}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    upcoming = (await app_client.get("/api/v1/appointments/me", headers=headers)).json()
    history = (
        await app_client.get("/api/v1/appointments/me?scope=history", headers=headers)
    ).json()
    assert upcoming["total"] == 2 and history["total"] >= 2
