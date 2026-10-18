"""Xem lịch: sắp tới, lịch sử, chi tiết và quyền xem (UC08, FR-APT-04, FR-APT-05, AC-05)."""

from datetime import date, time
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import local_datetime
from app.db.enums import AppointmentStatus, UserRole
from tests.integration.factories import (
    MONDAY,
    Clinic,
    add_appointment,
    at,
    bearer,
    build_clinic,
    fetch,
)

pytestmark = pytest.mark.integration

LAST_FRIDAY = date(2026, 10, 9)  # trước TEST_NOW (Thứ Bảy 10/10/2026 09:00)
TUESDAY = date(2026, 10, 13)


@pytest.fixture
async def clinic(db: AsyncSession) -> Clinic:
    return await build_clinic(db, patients=3)


async def _list(
    client: AsyncClient, clinic: Clinic, patient: int = 0, **params: str | int
) -> dict[str, Any]:
    response = await client.get(
        "/api/v1/appointments/me",
        params=params,
        headers=bearer(clinic.patient_ids[patient], UserRole.PATIENT),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_upcoming_and_history_are_split_and_ordered(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    later = await add_appointment(db, clinic, day=TUESDAY, start=time(8, 0))
    sooner = await add_appointment(db, clinic, start=time(9, 0))
    cancelled = await add_appointment(
        db, clinic, start=time(10, 0), status=AppointmentStatus.CANCELLED
    )
    done = await add_appointment(
        db, clinic, day=LAST_FRIDAY, start=time(8, 0), status=AppointmentStatus.COMPLETED
    )
    stale = await add_appointment(db, clinic, day=LAST_FRIDAY, start=time(9, 0))
    await add_appointment(db, clinic, start=time(11, 0), patient_index=1)  # của người khác

    upcoming = await _list(app_client, clinic)
    assert [i["id"] for i in upcoming["items"]] == [sooner, later]  # gần nhất trước
    assert upcoming["total"] == 2
    assert upcoming["items"][0]["can_change"] is True
    assert upcoming["items"][0]["change_until"] == "2026-10-12T07:00:00+07:00"

    history = await _list(app_client, clinic, scope="history")
    # mới nhất trước; lịch BOOKED đã qua giờ (chưa ai cập nhật) cũng nằm ở lịch sử
    assert [i["id"] for i in history["items"]] == [cancelled, stale, done]
    assert all(i["can_change"] is False for i in history["items"])
    assert history["items"][0]["change_until"] is None


async def test_status_filter_and_pagination(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    for hour in (8, 9, 10):
        await add_appointment(db, clinic, start=time(hour, 0), status=AppointmentStatus.CANCELLED)
    await add_appointment(
        db, clinic, day=LAST_FRIDAY, start=time(8, 0), status=AppointmentStatus.NO_SHOW
    )

    cancelled = await _list(app_client, clinic, scope="history", status="CANCELLED")
    assert cancelled["total"] == 3
    page = await _list(app_client, clinic, scope="history", page=2, page_size=3)
    assert page["total"] == 4 and page["page"] == 2 and page["page_size"] == 3
    assert [i["status"] for i in page["items"]] == ["NO_SHOW"]


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 101}, {"scope": "all"}])
async def test_list_rejects_bad_paging(
    app_client: AsyncClient, clinic: Clinic, params: dict[str, str | int]
) -> None:
    response = await app_client.get(
        "/api/v1/appointments/me",
        params=params,
        headers=bearer(clinic.patient_ids[0], UserRole.PATIENT),
    )
    assert response.status_code == 422


async def test_only_patients_list_their_own_appointments(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    assert (await app_client.get("/api/v1/appointments/me")).status_code == 401
    for user_id, role in (
        (clinic.doctor_ids[0], UserRole.DOCTOR),
        (clinic.admin_id, UserRole.ADMIN),
    ):
        response = await app_client.get("/api/v1/appointments/me", headers=bearer(user_id, role))
        assert response.status_code == 403


async def test_detail_shows_history_but_hides_attention_flag_from_patient(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    patient = bearer(clinic.patient_ids[0], UserRole.PATIENT)
    booked = await app_client.post(
        "/api/v1/appointments",
        json={
            "service_id": clinic.service_id,
            "doctor_id": clinic.doctor_ids[0],
            "start_at": at(MONDAY, 8),
            "reason": "Nổi mẩn đỏ ở tay",
        },
        headers=patient,
    )
    appointment_id = booked.json()["id"]
    moved = await app_client.patch(
        f"/api/v1/appointments/{appointment_id}/reschedule",
        json={"start_at": at(MONDAY, 9), "doctor_id": clinic.doctor_ids[1]},
        headers=patient,
    )
    assert moved.status_code == 200
    admin = bearer(clinic.admin_id, UserRole.ADMIN)
    time_off = await app_client.post(
        f"/api/v1/admin/doctors/{clinic.doctor_ids[1]}/time-offs",
        json={"start_at": at(MONDAY, 8), "end_at": at(MONDAY, 12)},
        headers=admin,
    )
    assert time_off.status_code == 201

    detail = await app_client.get(f"/api/v1/appointments/{appointment_id}", headers=patient)
    assert detail.status_code == 200
    body = detail.json()
    assert body["reason"] == "Nổi mẩn đỏ ở tay"
    assert body["needs_attention"] is True
    assert body["patient"] == {"id": clinic.patient_ids[0], "name": "Bệnh Nhân 0", "age": 36}
    assert [h["action"] for h in body["history"]] == ["CREATE", "RESCHEDULE"]
    create, reschedule = body["history"]
    assert create["by_me"] is True and create["actor_role"] == "PATIENT"
    assert create["created_at"] == "2026-10-10T09:00:00+07:00"
    assert reschedule["old"]["doctor"] == {"id": clinic.doctor_ids[0], "name": "BS. Bác Sĩ 0"}
    assert reschedule["old"]["start_at"] == "2026-10-12T08:00:00+07:00"
    assert reschedule["new"]["doctor"] == {"id": clinic.doctor_ids[1], "name": "BS. Bác Sĩ 1"}
    assert reschedule["new"]["start_at"] == "2026-10-12T09:00:00+07:00"

    as_admin = await app_client.get(f"/api/v1/appointments/{appointment_id}", headers=admin)
    actions = [h["action"] for h in as_admin.json()["history"]]
    assert actions == ["CREATE", "RESCHEDULE", "FLAG"]
    assert as_admin.json()["history"][2]["by_me"] is True


async def test_doctor_sees_own_appointment_without_contact_details(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """Bác sĩ chỉ thấy họ tên, tuổi, dịch vụ, giờ, lý do khám (docs mục 4.6)."""
    appointment_id = await add_appointment(db, clinic, start=time(9, 0))
    cancel = await app_client.post(
        f"/api/v1/appointments/{appointment_id}/cancel",
        json={"reason": "Lý do riêng tư"},
        headers=bearer(clinic.patient_ids[0], UserRole.PATIENT),
    )
    assert cancel.status_code == 200
    own = await app_client.get(
        f"/api/v1/appointments/{appointment_id}",
        headers=bearer(clinic.doctor_ids[0], UserRole.DOCTOR),
    )
    assert own.status_code == 200
    body = own.json()
    assert body["patient"] == {"id": clinic.patient_ids[0], "name": "Bệnh Nhân 0", "age": 36}
    assert body["cancel_reason"] is None
    for private in (clinic.emails[clinic.patient_ids[0]], "0900000000", "1990-01-01", "riêng tư"):
        assert private not in own.text
    other = await app_client.get(
        f"/api/v1/appointments/{appointment_id}",
        headers=bearer(clinic.doctor_ids[1], UserRole.DOCTOR),
    )
    assert other.status_code == 403


async def test_attention_flag_history_is_for_admins_only(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(9, 0))
    flagged = await app_client.post(
        f"/api/v1/admin/doctors/{clinic.doctor_ids[0]}/time-offs",
        json={"start_at": at(MONDAY, 8), "end_at": at(MONDAY, 12)},
        headers=bearer(clinic.admin_id, UserRole.ADMIN),
    )
    assert flagged.status_code == 201
    for user_id, role, actions in (
        (clinic.doctor_ids[0], UserRole.DOCTOR, []),
        (clinic.patient_ids[0], UserRole.PATIENT, []),
        (clinic.admin_id, UserRole.ADMIN, ["FLAG"]),
    ):
        response = await app_client.get(
            f"/api/v1/appointments/{appointment_id}", headers=bearer(user_id, role)
        )
        assert [h["action"] for h in response.json()["history"]] == actions


async def test_patient_cannot_view_change_or_cancel_another_patients_appointment(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """AC-05: bệnh nhân A gọi API xem, đổi, hủy lịch của bệnh nhân B thì nhận 403."""
    appointment_id = await add_appointment(db, clinic, start=time(9, 0), patient_index=1)
    intruder = bearer(clinic.patient_ids[0], UserRole.PATIENT)
    base = f"/api/v1/appointments/{appointment_id}"

    view = await app_client.get(base, headers=intruder)
    move = await app_client.patch(
        f"{base}/reschedule",
        json={"start_at": at(MONDAY, 10), "doctor_id": clinic.doctor_ids[0]},
        headers=intruder,
    )
    cancel = await app_client.post(f"{base}/cancel", json={}, headers=intruder)

    for response in (view, move, cancel):
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"
    appointment = await fetch(db, appointment_id)
    assert appointment.status is AppointmentStatus.BOOKED
    assert appointment.start_at == local_datetime(MONDAY, time(9))


async def test_unknown_appointment_is_not_found(app_client: AsyncClient, clinic: Clinic) -> None:
    response = await app_client.get(
        "/api/v1/appointments/999999", headers=bearer(clinic.patient_ids[0], UserRole.PATIENT)
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
