"""Quản trị xem, lọc mọi lịch hẹn và xử lý hàng chờ: lịch cần xử lý, yêu cầu gặp nhân viên
(UC16, FR-ADM-03, FR-ADM-04, BR-10, AC-08)."""

from datetime import date, time
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.db.enums import AppointmentStatus, Channel, NotificationType, UserRole
from app.db.models.appointments import Appointment, Notification
from app.modules.support.service import SupportService
from tests.integration.conftest import MutableClock
from tests.integration.factories import MONDAY, Clinic, add_appointment, at, bearer, build_clinic

pytestmark = pytest.mark.integration

TUESDAY = date(2026, 10, 13)


@pytest.fixture
async def clinic(db: AsyncSession) -> Clinic:
    return await build_clinic(db)


def admin(clinic: Clinic) -> dict[str, str]:
    return bearer(clinic.admin_id, UserRole.ADMIN)


async def listing(client: AsyncClient, clinic: Clinic, **params: Any) -> Response:
    return await client.get("/api/v1/admin/appointments", params=params, headers=admin(clinic))


def codes(response: Response) -> list[str]:
    return [item["code"] for item in response.json()["items"]]


async def test_admin_lists_and_filters_every_appointment(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    await add_appointment(db, clinic, start=time(8, 0), code="LH-261001-AAAA")
    await add_appointment(
        db,
        clinic,
        doctor_index=1,
        patient_index=1,
        start=time(9, 0),
        status=AppointmentStatus.CANCELLED,
        code="LH-261001-BBBB",
    )
    agent = await add_appointment(
        db, clinic, patient_index=1, day=TUESDAY, start=time(10, 0), code="LH-261002-CCCC"
    )
    async with db.begin():
        await db.execute(
            update(Appointment).where(Appointment.id == agent).values(channel=Channel.AGENT)
        )

    everything = await listing(app_client, clinic)
    assert everything.status_code == 200
    assert codes(everything) == ["LH-261001-AAAA", "LH-261001-BBBB", "LH-261002-CCCC"]
    first = everything.json()["items"][0]
    assert first["patient"] == {
        "id": clinic.patient_ids[0],
        "name": "Bệnh Nhân 0",
        "phone": "0900000000",
        "email": "benhnhan0@example.com",
    }
    assert first["can_change"] is True  # quản trị không bị giới hạn 2 giờ
    assert first["needs_attention"] is False and first["attention_source"] is None

    monday = MONDAY.isoformat()
    by_day = await listing(app_client, clinic, date_from=monday, date_to=monday)
    assert codes(by_day) == ["LH-261001-AAAA", "LH-261001-BBBB"]
    by_doctor = await listing(app_client, clinic, doctor_id=clinic.doctor_ids[1])
    assert codes(by_doctor) == ["LH-261001-BBBB"]
    assert codes(await listing(app_client, clinic, status="CANCELLED")) == ["LH-261001-BBBB"]
    assert codes(await listing(app_client, clinic, channel="AGENT")) == ["LH-261002-CCCC"]
    assert codes(await listing(app_client, clinic, q="aaaa")) == ["LH-261001-AAAA"]
    assert codes(await listing(app_client, clinic, q="benh nhan 1")) == [
        "LH-261001-BBBB",
        "LH-261002-CCCC",
    ]
    assert codes(await listing(app_client, clinic, q="0900 000 001")) == [
        "LH-261001-BBBB",
        "LH-261002-CCCC",
    ]
    assert codes(await listing(app_client, clinic, q="50%_")) == []

    paged = await listing(app_client, clinic, page=2, page_size=1)
    assert paged.json()["total"] == 3
    assert codes(paged) == ["LH-261001-BBBB"]
    backwards = await listing(app_client, clinic, date_from="2026-10-13", date_to=monday)
    assert backwards.status_code == 422


async def test_ac08_time_off_flags_appointment_and_admin_resolves_the_queue(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(8, 0))
    payload = {"start_at": at(MONDAY, 7), "end_at": at(MONDAY, 12), "reason": "Hội thảo"}
    base = f"/api/v1/admin/doctors/{clinic.doctor_ids[0]}/time-offs"

    preview = await app_client.post(
        base, json=payload, params={"dry_run": True}, headers=admin(clinic)
    )
    assert [a["id"] for a in preview.json()["affected"]] == [appointment_id]
    saved = await app_client.post(base, json=payload, headers=admin(clinic))
    assert saved.status_code == 201

    queue = await listing(app_client, clinic, needs_attention=True)
    assert [item["id"] for item in queue.json()["items"]] == [appointment_id]
    assert queue.json()["items"][0]["attention_source"] == "TIME_OFF"

    resolved = await app_client.patch(
        f"/api/v1/admin/appointments/{appointment_id}/attention",
        json={"needs_attention": False},
        headers=admin(clinic),
    )
    assert resolved.status_code == 200
    assert resolved.json()["needs_attention"] is False
    assert (await listing(app_client, clinic, needs_attention=True)).json()["items"] == []

    detail = await app_client.get(f"/api/v1/appointments/{appointment_id}", headers=admin(clinic))
    flags = [h["new"]["needs_attention"] for h in detail.json()["history"] if h["action"] == "FLAG"]
    assert flags == [True, False]
    as_patient = await app_client.get(
        f"/api/v1/appointments/{appointment_id}",
        headers=bearer(clinic.patient_ids[0], UserRole.PATIENT),
    )
    assert all(h["action"] != "FLAG" for h in as_patient.json()["history"])


async def test_manual_flag_only_for_booked_appointments(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    booked = await add_appointment(db, clinic, start=time(8, 0))
    cancelled = await add_appointment(
        db, clinic, start=time(9, 0), status=AppointmentStatus.CANCELLED
    )

    async def flag(appointment_id: int) -> Response:
        return await app_client.patch(
            f"/api/v1/admin/appointments/{appointment_id}/attention",
            json={"needs_attention": True},
            headers=admin(clinic),
        )

    flagged = await flag(booked)
    assert flagged.json()["attention_source"] == "MANUAL"
    rejected = await flag(cancelled)
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "INVALID_TRANSITION"
    assert (await flag(999_999)).status_code == 404


async def test_admin_moves_a_flagged_appointment_to_another_doctor(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """Đổi lịch từ hàng chờ: không giới hạn 2 giờ, gỡ cờ, email RESCHEDULED ghi kênh ADMIN."""
    appointment_id = await add_appointment(db, clinic, start=time(8, 0), needs_attention=True)
    moved = await app_client.patch(
        f"/api/v1/appointments/{appointment_id}/reschedule",
        json={"start_at": at(MONDAY, 10), "doctor_id": clinic.doctor_ids[1]},
        headers=admin(clinic),
    )
    assert moved.status_code == 200
    row = (await listing(app_client, clinic, doctor_id=clinic.doctor_ids[1])).json()["items"][0]
    assert row["needs_attention"] is False
    emails = list((await db.execute(select(Notification.type))).scalars())
    assert emails == [NotificationType.RESCHEDULED]


async def test_support_requests_queue(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    patient = Actor(clinic.patient_ids[0], UserRole.PATIENT, Channel.AGENT)
    created = await SupportService(db, clock).create(
        patient, summary="Muốn đặt lịch khám cho mẹ 70 tuổi.", conversation_id=None
    )
    base = "/api/v1/admin/support-requests"

    opened = await app_client.get(base, params={"status": "OPEN"}, headers=admin(clinic))
    assert opened.status_code == 200
    item = opened.json()[0]
    assert item["id"] == created.id
    assert item["summary"] == "Muốn đặt lịch khám cho mẹ 70 tuổi."
    assert item["patient"]["phone"] == "0900000000"
    assert item["handled_by"] is None

    done = await app_client.patch(
        f"{base}/{created.id}", json={"status": "DONE"}, headers=admin(clinic)
    )
    assert done.status_code == 200
    assert done.json()["status"] == "DONE"
    assert done.json()["handled_by"] == "Quản trị"
    assert done.json()["handled_at"] is not None
    assert (
        await app_client.get(base, params={"status": "OPEN"}, headers=admin(clinic))
    ).json() == []

    reopened = await app_client.patch(
        f"{base}/{created.id}", json={"status": "OPEN"}, headers=admin(clinic)
    )
    assert reopened.json()["handled_by"] is None
    missing = await app_client.patch(
        f"{base}/999999", json={"status": "DONE"}, headers=admin(clinic)
    )
    assert missing.status_code == 404
    invalid = await app_client.patch(
        f"{base}/{created.id}", json={"status": "CLOSED"}, headers=admin(clinic)
    )
    assert invalid.status_code == 422
