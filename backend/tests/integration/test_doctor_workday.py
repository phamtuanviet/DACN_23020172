"""Một ngày làm việc của bác sĩ: lịch khám ngày/tuần (UC12, FR-DOC-01, AC-09), cập nhật trạng
thái và ghi chú sau khám mà bệnh nhân thấy ngay (UC18, FR-DOC-02, FR-DOC-03, AC-17)."""

from datetime import date, time

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import local_datetime
from app.db.enums import AppointmentStatus, UserRole
from app.db.models.appointments import Appointment
from tests.integration.conftest import MutableClock
from tests.integration.factories import (
    MONDAY,
    Clinic,
    add_appointment,
    add_time_off,
    at,
    bearer,
    build_clinic,
)

pytestmark = pytest.mark.integration

TUESDAY, WEDNESDAY, SUNDAY = date(2026, 10, 13), date(2026, 10, 14), date(2026, 10, 18)
LAST_FRIDAY = date(2026, 10, 9)


@pytest.fixture
async def clinic(db: AsyncSession) -> Clinic:
    return await build_clinic(db)


async def schedule(
    client: AsyncClient,
    clinic: Clinic,
    first: date,
    last: date,
    doctor_index: int = 0,
    headers: dict[str, str] | None = None,
) -> Response:
    return await client.get(
        "/api/v1/doctor/schedule",
        params={"date_from": first.isoformat(), "date_to": last.isoformat()},
        headers=headers or bearer(clinic.doctor_ids[doctor_index], UserRole.DOCTOR),
    )


async def note(
    client: AsyncClient, appointment_id: int, text: str | None, headers: dict[str, str]
) -> Response:
    return await client.patch(
        f"/api/v1/appointments/{appointment_id}/note", json={"note": text}, headers=headers
    )


async def test_ac09_doctor_sees_only_own_appointments_by_day_and_week(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    booked = await app_client.post(
        "/api/v1/appointments",
        json={
            "service_id": clinic.service_id,
            "doctor_id": clinic.doctor_ids[0],
            "start_at": at(MONDAY, 9),
            "reason": "Nổi mẩn đỏ ở tay",
        },
        headers=bearer(clinic.patient_ids[0], UserRole.PATIENT),
    )
    assert booked.status_code == 201
    await add_appointment(db, clinic, doctor_index=1, patient_index=1, start=time(9, 0))
    await add_appointment(
        db,
        clinic,
        patient_index=1,
        day=TUESDAY,
        start=time(10, 0),
        status=AppointmentStatus.CANCELLED,
    )
    await add_time_off(db, clinic, day=WEDNESDAY, start=time(8, 0), end=time(12, 0))

    day = await schedule(app_client, clinic, MONDAY, MONDAY)

    assert day.status_code == 200
    body = day.json()
    assert [a["id"] for a in body["appointments"]] == [booked.json()["id"]]
    item = body["appointments"][0]
    assert item["patient"] == {"id": clinic.patient_ids[0], "name": "Bệnh Nhân 0", "age": 36}
    assert item["reason"] == "Nổi mẩn đỏ ở tay"
    assert item["service"]["name"] == "Khám da liễu tổng quát"
    assert item["has_note"] is False
    # Bác sĩ không thấy email, số điện thoại của bệnh nhân (docs mục 4.6)
    for secret in [*clinic.emails.values(), "0900000000", "date_of_birth", "email", "phone"]:
        assert secret not in day.text
    assert [(w["start_at"][11:16], w["end_at"][11:16]) for w in body["work"]] == [
        ("08:00", "11:30")
    ]
    assert [t["reason"] for t in body["upcoming_time_offs"]] == ["Nghỉ phép"]

    week = (await schedule(app_client, clinic, MONDAY, SUNDAY)).json()
    assert [a["status"] for a in week["appointments"]] == ["BOOKED", "CANCELLED"]
    assert len(week["work"]) == 6  # Thứ Hai–Thứ Bảy, Chủ nhật không có ca
    assert [t["start_at"][:10] for t in week["time_offs"]] == [WEDNESDAY.isoformat()]

    other = (await schedule(app_client, clinic, MONDAY, MONDAY, doctor_index=1)).json()
    assert [a["patient"]["id"] for a in other["appointments"]] == [clinic.patient_ids[1]]


async def test_schedule_range_is_validated(app_client: AsyncClient, clinic: Clinic) -> None:
    backwards = await schedule(app_client, clinic, TUESDAY, MONDAY)
    assert backwards.status_code == 422
    too_long = await schedule(app_client, clinic, MONDAY, date(2026, 11, 12))
    assert too_long.status_code == 422
    assert too_long.json()["details"]["fields"][0]["loc"] == ["query", "date_to"]


async def test_ac17_status_and_note_written_by_the_doctor_reach_the_patient(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(9, 0))
    clock.at = local_datetime(MONDAY, time(8, 55))
    doctor = bearer(clinic.doctor_ids[0], UserRole.DOCTOR, clock.at)
    patient = bearer(clinic.patient_ids[0], UserRole.PATIENT, clock.at)

    too_early = await note(app_client, appointment_id, "Chưa khám", doctor)
    assert too_early.status_code == 409
    assert too_early.json()["code"] == "INVALID_TRANSITION"

    arrived = await app_client.patch(
        f"/api/v1/appointments/{appointment_id}/status",
        json={"status": "ARRIVED"},
        headers=doctor,
    )
    assert arrived.status_code == 200
    text = "Viêm da tiếp xúc nhẹ ở cẳng tay. Bôi thuốc theo đơn 7 ngày."
    saved = await note(app_client, appointment_id, f"  {text}  ", doctor)
    assert saved.status_code == 200
    assert saved.json()["doctor_note"] == text
    # Lưu lại cùng nội dung không ghi thêm lịch sử
    await note(app_client, appointment_id, text, doctor)

    seen = await app_client.get(f"/api/v1/appointments/{appointment_id}", headers=patient)
    assert seen.json()["status"] == "ARRIVED"
    assert seen.json()["doctor_note"] == text
    actions = [(h["action"], h["actor_role"]) for h in seen.json()["history"]]
    assert actions == [("STATUS_CHANGE", "DOCTOR"), ("NOTE_UPDATE", "DOCTOR")]
    mine = await app_client.get("/api/v1/appointments/me", headers=patient)
    assert [a["status"] for a in mine.json()["items"]] == ["ARRIVED"]
    today = await schedule(app_client, clinic, MONDAY, MONDAY, headers=doctor)
    flagged = today.json()["appointments"]
    assert flagged[0]["has_note"] is True

    cleared = await note(app_client, appointment_id, "   ", doctor)
    assert cleared.json()["doctor_note"] is None


async def test_only_the_doctor_of_the_appointment_writes_notes(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(
        db, clinic, day=LAST_FRIDAY, start=time(9, 0), status=AppointmentStatus.COMPLETED
    )
    other_doctor = bearer(clinic.doctor_ids[1], UserRole.DOCTOR)
    assert (await note(app_client, appointment_id, "x", other_doctor)).status_code == 403
    admin = bearer(clinic.admin_id, UserRole.ADMIN)
    assert (await note(app_client, appointment_id, "x", admin)).status_code == 403
    owner = bearer(clinic.doctor_ids[0], UserRole.DOCTOR)
    too_long = await note(app_client, appointment_id, "a" * 1001, owner)
    assert too_long.status_code == 422
    # Ngày đã qua vẫn ghi nốt được ghi chú cho lịch đã khám
    assert (await note(app_client, appointment_id, "a" * 1000, owner)).status_code == 200
    # Body thiếu `note` (gõ sai tên trường) bị từ chối, không âm thầm xóa ghi chú
    for body in ({}, {"text": "Sai tên trường"}):
        response = await app_client.patch(
            f"/api/v1/appointments/{appointment_id}/note", json=body, headers=owner
        )
        assert response.status_code == 422
    kept = await app_client.get(f"/api/v1/appointments/{appointment_id}", headers=owner)
    assert kept.json()["doctor_note"] == "a" * 1000
    assert (await note(app_client, 999_999, "x", owner)).status_code == 404


async def test_doctor_sees_previous_visits_with_them_only(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    mine = await add_appointment(
        db, clinic, day=LAST_FRIDAY, start=time(8, 0), status=AppointmentStatus.COMPLETED
    )
    await add_appointment(
        db,
        clinic,
        doctor_index=1,
        day=LAST_FRIDAY,
        start=time(9, 0),
        status=AppointmentStatus.COMPLETED,
    )
    async with db.begin():
        await db.execute(
            update(Appointment).where(Appointment.id == mine).values(doctor_note="Dị ứng mỹ phẩm")
        )
    upcoming = await add_appointment(db, clinic, start=time(9, 0))

    as_doctor = await app_client.get(
        f"/api/v1/appointments/{upcoming}", headers=bearer(clinic.doctor_ids[0], UserRole.DOCTOR)
    )
    visits = as_doctor.json()["previous_visits"]
    assert [(v["id"], v["doctor_note"]) for v in visits] == [(mine, "Dị ứng mỹ phẩm")]
    assert set(visits[0]) == {"id", "start_at", "service", "status", "doctor_note"}
    for contact in (clinic.emails[clinic.patient_ids[0]], "0900000000"):
        assert contact not in as_doctor.text  # bác sĩ không thấy email, số điện thoại

    as_patient = await app_client.get(
        f"/api/v1/appointments/{upcoming}",
        headers=bearer(clinic.patient_ids[0], UserRole.PATIENT),
    )
    assert as_patient.json()["previous_visits"] == []
