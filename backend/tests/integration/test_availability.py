"""Khung trống qua API (UC04, FR-SCH-01..05, docs mục 5.1, 5.2, 8.3) trên PostgreSQL thật."""

from datetime import date, time
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.catalog import Service
from tests.integration.factories import (
    Clinic,
    add_appointment,
    add_time_off,
    build_clinic,
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def clinic(db: AsyncSession) -> Clinic:
    return await build_clinic(db, patients=2)


async def availability(client: AsyncClient, **params: Any) -> Response:
    return await client.get("/api/v1/availability", params=params)


def starts(day: dict[str, Any]) -> list[str]:
    return [slot["start_at"][11:16] for slot in day["slots"]]


async def test_doctor_day_matches_the_worked_example(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """Ca 08:00–11:30, dịch vụ 20 phút, đã có lịch 08:40–09:10 (docs mục 5.1)."""
    await add_appointment(db, clinic, start=time(8, 40), minutes=30)
    response = await availability(
        app_client,
        service_id=clinic.service_id,
        doctor_id=clinic.doctor_ids[0],
        date_from="2026-10-12",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == {
        "id": clinic.service_id,
        "name": "Khám da liễu tổng quát",
        "duration_min": 20,
    }
    [day] = body["days"]
    assert day["date"] == "2026-10-12"
    assert day["status"] == "OPEN"
    assert starts(day) == [
        "08:00", "08:20", "09:10", "09:30", "09:50", "10:10", "10:30", "10:50", "11:10",
    ]  # fmt: skip
    assert day["slots"][0]["start_at"] == "2026-10-12T08:00:00+07:00"
    assert day["slots"][0]["end_at"] == "2026-10-12T08:20:00+07:00"
    assert body["nearest_dates"] == []


async def test_any_doctor_merges_slots_and_lists_least_busy_doctor_first(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    await add_appointment(db, clinic, doctor_index=0, start=time(10, 0))
    response = await availability(
        app_client,
        service_id=clinic.service_id,
        date_from="2026-10-12",
        time_from="10:00",
        time_to="10:40",
    )
    [day] = response.json()["days"]
    doc0, doc1 = clinic.doctor_ids
    assert [(s["start_at"][11:16], [d["id"] for d in s["doctors"]]) for s in day["slots"]] == [
        ("10:00", [doc1]),
        ("10:20", [doc1, doc0]),  # bác sĩ 1 chưa có lịch nào trong ngày nên đứng trước
    ]


async def test_day_status_tells_day_off_from_fully_booked(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    await add_time_off(db, clinic, day=date(2026, 10, 13), start=time(0, 0), end=time(23, 59))
    wednesday = date(2026, 10, 14)
    await add_appointment(db, clinic, day=wednesday, start=time(8, 0), minutes=105)
    await add_appointment(
        db, clinic, day=wednesday, start=time(9, 45), minutes=105, patient_index=1
    )
    response = await availability(
        app_client,
        service_id=clinic.service_id,
        doctor_id=clinic.doctor_ids[0],
        date_from="2026-10-12",
        date_to="2026-10-18",
    )
    statuses = {d["date"]: d["status"] for d in response.json()["days"]}
    assert statuses == {
        "2026-10-12": "OPEN",
        "2026-10-13": "OFF",  # nghỉ cả ngày
        "2026-10-14": "FULL",  # có ca nhưng kín lịch
        "2026-10-15": "OPEN",
        "2026-10-16": "OPEN",
        "2026-10-17": "OPEN",
        "2026-10-18": "OFF",  # Chủ nhật không có ca
    }


async def test_full_day_suggests_three_nearest_dates_with_slots(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    await add_time_off(db, clinic, day=date(2026, 10, 19), start=time(0, 0), end=time(23, 59))
    response = await availability(
        app_client,
        service_id=clinic.service_id,
        doctor_id=clinic.doctor_ids[0],
        date_from="2026-10-18",
    )
    body = response.json()
    assert body["days"][0]["slots"] == []
    assert body["nearest_dates"] == ["2026-10-20", "2026-10-21", "2026-10-22"]


async def test_past_slots_of_today_are_hidden(app_client: AsyncClient, clinic: Clinic) -> None:
    """Bây giờ là 09:00 Thứ Bảy 10/10: khung 09:00 đã bắt đầu nên không còn đặt được."""
    response = await availability(
        app_client, service_id=clinic.service_id, doctor_id=clinic.doctor_ids[0]
    )
    [today] = response.json()["days"]
    assert today["date"] == "2026-10-10"
    assert starts(today)[0] == "09:20"


async def test_slots_after_the_thirty_day_window_are_hidden(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    """Cửa sổ kết thúc 09:00 Thứ Hai 09/11 (BR-07)."""
    response = await availability(
        app_client,
        service_id=clinic.service_id,
        doctor_id=clinic.doctor_ids[0],
        date_from="2026-11-09",
        date_to="2026-11-10",
    )
    first, second = response.json()["days"]
    assert starts(first) == ["08:00", "08:20", "08:40", "09:00"]
    assert second["slots"] == []


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"date_from": "2026-10-12", "date_to": "2026-10-11"}, "date_to"),
        ({"date_from": "2026-10-12", "date_to": "2026-11-12"}, "date_to"),
        ({"time_from": "10:00", "time_to": "09:00"}, "time_to"),
    ],
)
async def test_invalid_ranges_are_rejected(
    app_client: AsyncClient, clinic: Clinic, params: dict[str, str], field: str
) -> None:
    response = await availability(app_client, service_id=clinic.service_id, **params)
    assert response.status_code == 422
    assert response.json()["details"]["fields"][0]["loc"] == ["query", field]


async def test_hidden_service_and_wrong_doctor(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    async with db.begin():
        service = await db.get(Service, clinic.acne_service_id)
        assert service is not None
        service.is_active = False
    hidden = await availability(app_client, service_id=clinic.acne_service_id)
    assert hidden.status_code == 404
    wrong_doctor = await availability(
        app_client, service_id=clinic.service_id, doctor_id=clinic.admin_id
    )
    assert wrong_doctor.status_code == 400
    assert wrong_doctor.json()["code"] == "DOCTOR_SERVICE_MISMATCH"


async def test_earliest_slot_by_service_and_by_doctor(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    today = date(2026, 10, 10)
    await add_appointment(db, clinic, doctor_index=0, day=today, start=time(9, 20))
    doc0, doc1 = clinic.doctor_ids

    overall = await app_client.get(
        "/api/v1/availability/earliest", params={"service_id": clinic.service_id}
    )
    [item] = overall.json()["items"]
    assert item["service_id"] == clinic.service_id
    assert item["doctor"]["id"] == doc1
    assert item["start_at"] == "2026-10-10T09:20:00+07:00"

    per_doctor = await app_client.get(
        "/api/v1/availability/earliest",
        params={"service_id": [clinic.service_id, clinic.acne_service_id], "by_doctor": True},
    )
    found = {
        (i["service_id"], i["doctor"]["id"]): i["start_at"][11:16]
        for i in per_doctor.json()["items"]
    }
    assert found == {
        (clinic.service_id, doc1): "09:20",
        (clinic.service_id, doc0): "09:40",
        (clinic.acne_service_id, doc0): "09:40",  # lưới 30 phút: 09:30 chồng lịch 09:20–09:40
        (clinic.acne_service_id, doc1): "09:30",
    }
