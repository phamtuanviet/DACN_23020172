"""Ca làm và ngày nghỉ qua API (UC15, FR-ADM-02, BR-10, docs mục 5.7) trên PostgreSQL thật."""

from datetime import date, time
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import Channel, HistoryAction, UserRole
from app.db.models.appointments import Appointment, AppointmentHistory
from app.db.models.schedule import TimeOff
from tests.integration.factories import MONDAY, Clinic, add_appointment, at, bearer, build_clinic

pytestmark = pytest.mark.integration
SUNDAY = date(2026, 10, 18)


@pytest.fixture
async def clinic(db: AsyncSession) -> Clinic:
    return await build_clinic(db)


def admin(clinic: Clinic) -> dict[str, str]:
    return bearer(clinic.admin_id, UserRole.ADMIN)


def base(clinic: Clinic, doctor_index: int = 0) -> str:
    return f"/api/v1/admin/doctors/{clinic.doctor_ids[doctor_index]}"


async def add_shift(client: AsyncClient, clinic: Clinic, **fields: Any) -> Response:
    payload = {"weekday": 7, "start_time": "08:00", "end_time": "11:00", "valid_from": "2026-10-01"}
    return await client.post(
        f"{base(clinic)}/shifts", json={**payload, **fields}, headers=admin(clinic)
    )


async def slot_times(client: AsyncClient, clinic: Clinic, day: date) -> list[str]:
    response = await client.get(
        "/api/v1/availability",
        params={
            "service_id": clinic.service_id,
            "doctor_id": clinic.doctor_ids[0],
            "date_from": day.isoformat(),
        },
    )
    return [s["start_at"][11:16] for s in response.json()["days"][0]["slots"]]


async def test_new_shift_opens_slots_immediately(app_client: AsyncClient, clinic: Clinic) -> None:
    assert await slot_times(app_client, clinic, SUNDAY) == []
    created = await add_shift(app_client, clinic, end_time="09:00")
    assert created.status_code == 201
    assert created.json()["weekday"] == 7
    assert await slot_times(app_client, clinic, SUNDAY) == ["08:00", "08:20", "08:40"]
    listed = await app_client.get(f"{base(clinic)}/shifts", headers=admin(clinic))
    assert len(listed.json()) == 7


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"start_time": "10:00", "end_time": "12:00"}, 409),  # chồng 08:00–11:00
        ({"start_time": "11:00", "end_time": "12:00"}, 201),  # nối tiếp, không chồng
        ({"valid_from": "2026-09-01", "valid_to": "2026-09-30"}, 201),  # khác khoảng hiệu lực
        ({"weekday": 6}, 409),  # Thứ Bảy đã có ca 08:00–11:30 của bác sĩ
    ],
)
async def test_overlapping_shift_is_rejected(
    app_client: AsyncClient, clinic: Clinic, fields: dict[str, str], expected: int
) -> None:
    assert (await add_shift(app_client, clinic)).status_code == 201
    response = await add_shift(app_client, clinic, **fields)
    assert response.status_code == expected
    if expected == 409:
        assert response.json()["code"] == "SHIFT_OVERLAP"


@pytest.mark.parametrize(
    ("fields", "field"),
    [
        ({"start_time": "11:00", "end_time": "11:00"}, "end_time"),
        ({"weekday": 8}, "weekday"),
        ({"start_time": "08:00:30"}, "start_time"),
        ({"valid_to": "2026-09-01"}, "valid_to"),
    ],
)
async def test_invalid_shift_is_rejected_at_the_field(
    app_client: AsyncClient, clinic: Clinic, fields: dict[str, str], field: str
) -> None:
    response = await add_shift(app_client, clinic, **fields)
    assert response.status_code == 422
    assert response.json()["details"]["fields"][0]["loc"] == ["body", field]


async def test_time_off_dry_run_lists_affected_appointments_without_writing(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(9, 0))
    await add_appointment(db, clinic, start=time(11, 0), patient_index=1)  # ngoài khoảng nghỉ
    response = await app_client.post(
        f"{base(clinic)}/time-offs",
        params={"dry_run": True},
        json={"start_at": at(MONDAY, 8, 30), "end_at": at(MONDAY, 10, 0), "reason": "Công tác"},
        headers=admin(clinic),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True and body["time_off"] is None
    [affected] = body["affected"]
    assert affected["id"] == appointment_id
    assert affected["patient_name"] == "Bệnh Nhân 0"
    assert affected["start_at"] == "2026-10-12T09:00:00+07:00"
    assert (await db.execute(select(TimeOff))).first() is None
    appointment = await db.get(Appointment, appointment_id)
    assert appointment is not None and appointment.needs_attention is False


async def test_time_off_flags_affected_appointments_and_removes_slots(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(9, 0))
    response = await app_client.post(
        f"{base(clinic)}/time-offs",
        json={"start_at": at(MONDAY, 8, 30), "end_at": at(MONDAY, 10, 0), "reason": "Công tác"},
        headers=admin(clinic),
    )
    assert response.status_code == 201
    assert response.json()["time_off"]["reason"] == "Công tác"
    assert [a["id"] for a in response.json()["affected"]] == [appointment_id]

    appointment = await db.get(Appointment, appointment_id)
    assert appointment is not None and appointment.needs_attention is True
    assert appointment.status.value == "BOOKED"  # không bao giờ tự hủy lịch
    flag = (await db.execute(select(AppointmentHistory))).scalar_one()
    assert flag.action is HistoryAction.FLAG
    assert flag.channel is Channel.ADMIN
    assert flag.actor_id == clinic.admin_id
    assert flag.new_value is not None and flag.new_value["source"] == "TIME_OFF"
    assert await slot_times(app_client, clinic, MONDAY) == [
        "08:00", "10:00", "10:20", "10:40", "11:00",
    ]  # fmt: skip

    listed = await app_client.get(
        f"{base(clinic)}/time-offs", params={"since": "2026-10-12"}, headers=admin(clinic)
    )
    [time_off] = listed.json()
    deleted = await app_client.delete(
        f"{base(clinic)}/time-offs/{time_off['id']}", headers=admin(clinic)
    )
    assert deleted.status_code == 204
    assert "08:40" in await slot_times(app_client, clinic, MONDAY)


async def test_shrinking_a_shift_flags_appointments_left_outside(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    inside = await add_appointment(db, clinic, start=time(8, 0))
    outside = await add_appointment(db, clinic, start=time(11, 0), patient_index=1)
    shifts = (await app_client.get(f"{base(clinic)}/shifts", headers=admin(clinic))).json()
    monday = next(s for s in shifts if s["weekday"] == 1)

    preview = await app_client.patch(
        f"{base(clinic)}/shifts/{monday['id']}",
        params={"dry_run": True},
        json={"end_time": "10:30"},
        headers=admin(clinic),
    )
    assert preview.status_code == 200
    assert [a["id"] for a in preview.json()["affected"]] == [outside]
    assert preview.json()["shift"]["end_time"] == "10:30:00"

    applied = await app_client.patch(
        f"{base(clinic)}/shifts/{monday['id']}",
        json={"end_time": "10:30"},
        headers=admin(clinic),
    )
    assert applied.status_code == 200
    flagged = {a.id: a.needs_attention for a in (await db.execute(select(Appointment))).scalars()}
    assert flagged == {inside: False, outside: True}
    assert (await slot_times(app_client, clinic, MONDAY))[-1] == "10:00"

    invalid = await app_client.patch(
        f"{base(clinic)}/shifts/{monday['id']}",
        json={"start_time": "10:30"},
        headers=admin(clinic),
    )
    assert invalid.status_code == 422
    assert invalid.json()["details"]["fields"][0]["loc"] == ["body", "end_time"]


async def test_deleting_a_shift_flags_its_appointments(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(8, 0))
    shifts = (await app_client.get(f"{base(clinic)}/shifts", headers=admin(clinic))).json()
    monday = next(s for s in shifts if s["weekday"] == 1)
    response = await app_client.delete(
        f"{base(clinic)}/shifts/{monday['id']}", headers=admin(clinic)
    )
    assert response.status_code == 200
    assert [a["id"] for a in response.json()["affected"]] == [appointment_id]
    assert await slot_times(app_client, clinic, MONDAY) == []
    appointment = await db.get(Appointment, appointment_id)
    assert appointment is not None and appointment.needs_attention is True


async def test_schedule_endpoints_require_admin_and_existing_doctor(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    patient = bearer(clinic.patient_ids[0], UserRole.PATIENT)
    assert (await app_client.get(f"{base(clinic)}/shifts", headers=patient)).status_code == 403
    assert (await app_client.get(f"{base(clinic)}/time-offs")).status_code == 401
    missing = await app_client.get("/api/v1/admin/doctors/9999/shifts", headers=admin(clinic))
    assert missing.status_code == 404
