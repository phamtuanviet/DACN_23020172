"""Đặt lịch qua API (UC05, FR-APT-01, FR-APT-05, docs mục 5.3–5.6) trên PostgreSQL thật."""

import re
from datetime import time
from unittest.mock import patch

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import (
    Channel,
    Gender,
    HistoryAction,
    NotificationStatus,
    NotificationType,
    UserRole,
)
from app.db.models.appointments import Appointment, AppointmentHistory, Notification
from app.db.models.catalog import Service
from app.db.models.users import Doctor, User
from app.modules.scheduling.service import Candidate
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


@pytest.fixture
async def clinic(db: AsyncSession) -> Clinic:
    return await build_clinic(db, patients=3)


async def book(
    client: AsyncClient,
    clinic: Clinic,
    start_at: str,
    *,
    patient: int = 0,
    doctor: int | None = 0,
    service_id: int | None = None,
    reason: str | None = None,
) -> Response:
    return await client.post(
        "/api/v1/appointments",
        json={
            "service_id": service_id or clinic.service_id,
            "doctor_id": clinic.doctor_ids[doctor] if doctor is not None else None,
            "start_at": start_at,
            "reason": reason,
        },
        headers=bearer(clinic.patient_ids[patient], UserRole.PATIENT),
    )


async def test_booking_creates_appointment_history_and_confirmation_email(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    response = await book(app_client, clinic, at(MONDAY, 8, 20), reason="  Nổi mẩn đỏ ở tay  ")

    assert response.status_code == 201
    body = response.json()
    assert re.fullmatch(r"LH-261010-[0-9A-HJKMNP-TV-Z]{4}", body["code"])
    assert body["status"] == "BOOKED"
    assert body["channel"] == "WEB"
    assert body["start_at"] == "2026-10-12T08:20:00+07:00"
    assert body["end_at"] == "2026-10-12T08:40:00+07:00"
    assert body["service"] == {"id": clinic.service_id, "name": "Khám da liễu tổng quát"}
    assert body["doctor"] == {"id": clinic.doctor_ids[0], "name": "BS. Bác Sĩ 0"}
    assert body["can_change"] is True

    appointment = (await db.execute(select(Appointment))).scalar_one()
    assert appointment.reason == "Nổi mẩn đỏ ở tay"
    assert appointment.patient_id == clinic.patient_ids[0]
    history = (await db.execute(select(AppointmentHistory))).scalar_one()
    assert history.action is HistoryAction.CREATE
    assert history.channel is Channel.WEB
    assert history.actor_id == clinic.patient_ids[0]
    assert history.new_value is not None
    assert history.new_value["start_at"] == "2026-10-12T08:20:00+07:00"
    assert "reason" not in history.new_value  # lý do khám không chép sang lịch sử
    email = (await db.execute(select(Notification))).scalar_one()
    assert email.type is NotificationType.BOOKED
    assert email.status is NotificationStatus.PENDING
    assert email.recipient_email == clinic.emails[clinic.patient_ids[0]]


async def test_booked_slot_disappears_and_grid_restarts_after_it(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    """Dịch vụ 30 phút đặt lúc 08:00: lưới 20 phút bắt đầu lại ngay 08:30 (FR-SCH-02)."""
    acne = await book(app_client, clinic, at(MONDAY, 8, 0), service_id=clinic.acne_service_id)
    assert acne.status_code == 201
    response = await app_client.get(
        "/api/v1/availability",
        params={
            "service_id": clinic.service_id,
            "doctor_id": clinic.doctor_ids[0],
            "date_from": "2026-10-12",
            "time_to": "10:00",
        },
    )
    starts = [s["start_at"][11:16] for s in response.json()["days"][0]["slots"]]
    assert starts == ["08:30", "08:50", "09:10", "09:30"]


@pytest.mark.parametrize(
    "start_at",
    [
        "2026-10-10T08:40:00+07:00",  # đã qua (bây giờ là 09:00 cùng ngày)
        "2026-11-10T08:00:00+07:00",  # quá 30 ngày
    ],
)
async def test_booking_outside_window_is_rejected(
    app_client: AsyncClient, clinic: Clinic, start_at: str
) -> None:
    response = await book(app_client, clinic, start_at)
    assert response.status_code == 400
    assert response.json()["code"] == "BOOKING_WINDOW"


async def test_start_time_must_be_a_slot_generated_by_the_engine(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    await add_time_off(db, clinic, day=MONDAY, start=time(10, 0), end=time(11, 30))
    misaligned = await book(app_client, clinic, at(MONDAY, 8, 10))
    sunday = await book(app_client, clinic, "2026-10-18T08:00:00+07:00")
    in_time_off = await book(app_client, clinic, at(MONDAY, 10, 20))
    for response in (misaligned, sunday, in_time_off):
        assert response.status_code == 400
        assert response.json()["code"] == "SLOT_NOT_OFFERED"


async def test_start_time_with_utc_offset_is_accepted(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    response = await book(app_client, clinic, "2026-10-12T01:00:00+00:00")  # 08:00 giờ Việt Nam
    assert response.status_code == 201
    assert response.json()["start_at"] == "2026-10-12T08:00:00+07:00"


async def test_hidden_or_unknown_service_cannot_be_booked(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    async with db.begin():
        service = await db.get(Service, clinic.acne_service_id)
        assert service is not None
        service.is_active = False
    hidden = await book(app_client, clinic, at(MONDAY, 8, 0), service_id=clinic.acne_service_id)
    assert hidden.status_code == 400
    assert hidden.json()["code"] == "DOCTOR_SERVICE_MISMATCH"
    unknown = await book(app_client, clinic, at(MONDAY, 8, 0), service_id=9999)
    assert unknown.status_code == 404


async def test_doctor_must_perform_the_service(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    async with db.begin():
        user = User(
            email="khac@example.com",
            password_hash="x",
            role=UserRole.DOCTOR,
            full_name="BS. Khác",
        )
        db.add(user)
        await db.flush()
        db.add(
            Doctor(
                user_id=user.id, specialty_id=clinic.specialty_id, title="BS.", gender=Gender.FEMALE
            )
        )
    response = await app_client.post(
        "/api/v1/appointments",
        json={"service_id": clinic.service_id, "doctor_id": user.id, "start_at": at(MONDAY, 8)},
        headers=bearer(clinic.patient_ids[0], UserRole.PATIENT),
    )
    assert response.status_code == 400
    assert response.json()["code"] == "DOCTOR_SERVICE_MISMATCH"


async def test_second_booking_of_same_slot_gets_slot_taken_with_alternatives(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    assert (await book(app_client, clinic, at(MONDAY, 9, 0))).status_code == 201
    second = await book(app_client, clinic, at(MONDAY, 9, 0), patient=1)
    assert second.status_code == 409
    body = second.json()
    assert body["code"] == "SLOT_TAKEN"
    alternatives = body["details"]["alternatives"]
    assert [a["start_at"][11:16] for a in alternatives] == ["08:20", "08:40", "09:20"]
    assert {a["doctor_id"] for a in alternatives} == {clinic.doctor_ids[0]}


async def test_patient_cannot_hold_two_appointments_at_the_same_time(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    assert (await book(app_client, clinic, at(MONDAY, 8, 0), doctor=0)).status_code == 201
    overlap = await book(app_client, clinic, at(MONDAY, 8, 0), doctor=1)
    assert overlap.status_code == 409
    assert overlap.json()["code"] == "PATIENT_OVERLAP"


async def test_patient_can_hold_at_most_three_upcoming_appointments(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    for hour in (8, 9, 10):
        assert (await book(app_client, clinic, at(MONDAY, hour))).status_code == 201
    fourth = await book(app_client, clinic, at(MONDAY, 11))
    assert fourth.status_code == 409
    assert fourth.json()["code"] == "MAX_ACTIVE_APPOINTMENTS"
    assert (await book(app_client, clinic, at(MONDAY, 11), patient=1)).status_code == 201


async def test_any_doctor_picks_the_doctor_with_fewest_appointments_that_day(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    await add_appointment(db, clinic, doctor_index=0, patient_index=2, start=time(10, 0))
    response = await book(app_client, clinic, at(MONDAY, 8, 0), doctor=None)
    assert response.status_code == 201
    assert response.json()["doctor"]["id"] == clinic.doctor_ids[1]


async def test_any_doctor_retries_next_doctor_when_first_was_just_taken(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """Giả lập tranh chấp: Engine vẫn chọn bác sĩ 0, nhưng khung đó vừa bị đặt (23P01)."""
    await add_appointment(db, clinic, doctor_index=0, patient_index=2, start=time(8, 0))
    stale = [
        Candidate(clinic.doctor_ids[0], "BS. Bác Sĩ 0", 0),
        Candidate(clinic.doctor_ids[1], "BS. Bác Sĩ 1", 0),
    ]

    async def ensure_with_stale_view(*_args: object, **_kwargs: object) -> list[Candidate]:
        return stale

    with patch("app.modules.appointments.service.ensure_slot_bookable", ensure_with_stale_view):
        response = await book(app_client, clinic, at(MONDAY, 8, 0), doctor=None)
    assert response.status_code == 201
    assert response.json()["doctor"]["id"] == clinic.doctor_ids[1]


async def test_only_patients_can_book(app_client: AsyncClient, clinic: Clinic) -> None:
    payload = {"service_id": clinic.service_id, "start_at": at(MONDAY, 8)}
    anonymous = await app_client.post("/api/v1/appointments", json=payload)
    assert anonymous.status_code == 401
    for user_id, role in (
        (clinic.doctor_ids[0], UserRole.DOCTOR),
        (clinic.admin_id, UserRole.ADMIN),
    ):
        response = await app_client.post(
            "/api/v1/appointments", json=payload, headers=bearer(user_id, role)
        )
        assert response.status_code == 403


async def test_naive_start_time_and_long_reason_are_rejected(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    headers = bearer(clinic.patient_ids[0], UserRole.PATIENT)
    naive = await app_client.post(
        "/api/v1/appointments",
        json={"service_id": clinic.service_id, "start_at": "2026-10-12T08:00:00"},
        headers=headers,
    )
    assert naive.status_code == 422
    long_reason = await app_client.post(
        "/api/v1/appointments",
        json={"service_id": clinic.service_id, "start_at": at(MONDAY, 8), "reason": "x" * 501},
        headers=headers,
    )
    assert long_reason.status_code == 422
