"""Đổi và hủy lịch (UC06, UC07, FR-APT-02, FR-APT-03, AC-04, AC-06, NFR-09, docs mục 5.3–5.4)."""

from datetime import time
from unittest.mock import patch

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.timeutil import local_datetime
from app.db.enums import AppointmentStatus, Channel, HistoryAction, NotificationType, UserRole
from app.db.models.appointments import AppointmentHistory, Notification
from app.modules.appointments.service import AffectedAppointment, flag_for_attention
from app.modules.scheduling.service import Candidate
from tests.integration.conftest import MutableClock
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


@pytest.fixture
async def clinic(db: AsyncSession) -> Clinic:
    return await build_clinic(db, patients=3)


async def reschedule(
    client: AsyncClient,
    clinic: Clinic,
    appointment_id: int,
    start_at: str,
    *,
    doctor: int = 0,
    patient: int = 0,
    headers: dict[str, str] | None = None,
) -> Response:
    return await client.patch(
        f"/api/v1/appointments/{appointment_id}/reschedule",
        json={"start_at": start_at, "doctor_id": clinic.doctor_ids[doctor]},
        headers=headers or bearer(clinic.patient_ids[patient], UserRole.PATIENT),
    )


async def cancel(
    client: AsyncClient,
    clinic: Clinic,
    appointment_id: int,
    *,
    reason: str | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    return await client.post(
        f"/api/v1/appointments/{appointment_id}/cancel",
        json={"reason": reason},
        headers=headers or bearer(clinic.patient_ids[0], UserRole.PATIENT),
    )


async def history(db: AsyncSession, appointment_id: int) -> list[AppointmentHistory]:
    stmt = (
        select(AppointmentHistory)
        .where(AppointmentHistory.appointment_id == appointment_id)
        .order_by(AppointmentHistory.id)
    )
    rows = list((await db.execute(stmt)).scalars())
    await db.commit()
    return rows


async def notifications(db: AsyncSession) -> list[NotificationType]:
    rows = [
        n.type for n in (await db.execute(select(Notification).order_by(Notification.id))).scalars()
    ]
    await db.commit()
    return rows


# ---------------------------------------------------------------------------- đổi lịch
async def test_reschedule_keeps_code_and_records_history_and_email(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(8, 0), needs_attention=True)
    before = await fetch(db, appointment_id)

    response = await reschedule(app_client, clinic, appointment_id, at(MONDAY, 9, 20))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == appointment_id and body["code"] == before.code
    assert body["start_at"] == "2026-10-12T09:20:00+07:00"
    assert body["end_at"] == "2026-10-12T09:40:00+07:00"
    assert body["doctor"]["id"] == clinic.doctor_ids[0]
    after = await fetch(db, appointment_id)
    assert after.needs_attention is False  # đã dời vào khung hợp lệ: gỡ cờ (docs mục 5.7)
    rows = await history(db, appointment_id)
    assert [r.action for r in rows] == [HistoryAction.RESCHEDULE]
    assert rows[0].channel is Channel.WEB
    assert rows[0].old_value is not None and rows[0].new_value is not None
    assert rows[0].old_value["start_at"] == "2026-10-12T08:00:00+07:00"
    assert rows[0].new_value["start_at"] == "2026-10-12T09:20:00+07:00"
    assert await notifications(db) == [NotificationType.RESCHEDULED]


async def test_reschedule_to_another_doctor_of_the_same_service(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(8, 0))
    response = await reschedule(app_client, clinic, appointment_id, at(MONDAY, 8), doctor=1)
    assert response.status_code == 200
    assert response.json()["doctor"] == {"id": clinic.doctor_ids[1], "name": "BS. Bác Sĩ 1"}


async def test_reschedule_to_a_slot_just_taken_fails_and_keeps_the_old_appointment(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """AC-04 (BR-04): khung mới vừa bị người khác đặt thì thất bại, lịch cũ còn nguyên."""
    appointment_id = await add_appointment(db, clinic, start=time(8, 0))
    await add_appointment(db, clinic, start=time(9, 0), patient_index=1)

    response = await reschedule(app_client, clinic, appointment_id, at(MONDAY, 9))

    assert response.status_code == 409
    assert response.json()["code"] == "SLOT_TAKEN"
    assert response.json()["details"]["alternatives"]
    unchanged = await fetch(db, appointment_id)
    assert unchanged.start_at == local_datetime(MONDAY, time(8))
    assert unchanged.status is AppointmentStatus.BOOKED
    assert await history(db, appointment_id) == []
    assert await notifications(db) == []


async def test_constraint_violation_during_reschedule_rolls_back_everything(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """AC-04, NFR-09: kiểm tra trước vẫn thấy khung trống (tranh chấp), exclusion constraint chặn
    ở câu UPDATE; transaction rollback, lịch cũ còn nguyên."""
    appointment_id = await add_appointment(db, clinic, start=time(8, 0))
    await add_appointment(db, clinic, start=time(9, 0), patient_index=1)

    async def stale_view(*_args: object, **_kwargs: object) -> list[Candidate]:
        return [Candidate(clinic.doctor_ids[0], "BS. Bác Sĩ 0", 0)]

    with patch("app.modules.appointments.service.ensure_slot_bookable", stale_view):
        response = await reschedule(app_client, clinic, appointment_id, at(MONDAY, 9))

    assert response.status_code == 409
    assert response.json()["code"] == "SLOT_TAKEN"
    unchanged = await fetch(db, appointment_id)
    assert unchanged.start_at == local_datetime(MONDAY, time(8))
    assert await history(db, appointment_id) == []
    assert await notifications(db) == []


async def test_reschedule_into_own_other_appointment_is_patient_overlap(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(8, 0))
    await add_appointment(db, clinic, start=time(9, 0), doctor_index=1)
    response = await reschedule(app_client, clinic, appointment_id, at(MONDAY, 9))
    assert response.status_code == 409
    assert response.json()["code"] == "PATIENT_OVERLAP"


async def test_reschedule_may_overlap_its_own_old_time(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """Constraint chỉ so khoảng mới với lịch khác: dời 08:20–08:50 sang 08:30–09:00 vẫn hợp lệ."""
    appointment_id = await add_appointment(
        db, clinic, start=time(8, 20), minutes=30, service_id=clinic.acne_service_id
    )
    response = await reschedule(app_client, clinic, appointment_id, at(MONDAY, 8, 30))
    assert response.status_code == 200, response.text
    assert response.json()["end_at"] == "2026-10-12T09:00:00+07:00"


async def test_reschedule_accepts_the_slot_shown_by_availability(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """Lịch dài ngắn khác nhau làm lưới lệch: /availability (tính lịch đang đổi là bận) hiện 09:00,
    còn lưới bỏ lịch đó thì là 08:30, 08:50, 09:10. Khung đang hiển thị vẫn phải đổi được."""
    await add_appointment(
        db,
        clinic,
        start=time(8, 0),
        minutes=30,
        service_id=clinic.acne_service_id,
        patient_index=1,
    )
    appointment_id = await add_appointment(db, clinic, start=time(8, 40))
    shown = await app_client.get(
        "/api/v1/availability",
        params={
            "service_id": clinic.service_id,
            "doctor_id": clinic.doctor_ids[0],
            "date_from": "2026-10-12",
            "time_to": "09:30",
        },
    )
    starts = [s["start_at"][11:16] for s in shown.json()["days"][0]["slots"]]
    assert starts == ["09:00"]

    response = await reschedule(app_client, clinic, appointment_id, at(MONDAY, 9))
    assert response.status_code == 200, response.text


async def test_reschedule_rejects_same_slot_and_times_outside_the_window(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(8, 0))
    same = await reschedule(app_client, clinic, appointment_id, at(MONDAY, 8))
    assert same.status_code == 422
    for start_at in ("2026-10-10T08:40:00+07:00", "2026-11-10T08:00:00+07:00"):
        response = await reschedule(app_client, clinic, appointment_id, start_at)
        assert response.status_code == 400
        assert response.json()["code"] == "BOOKING_WINDOW"
    off_grid = await reschedule(app_client, clinic, appointment_id, at(MONDAY, 8, 10))
    assert off_grid.json()["code"] == "SLOT_NOT_OFFERED"


async def test_only_patient_owner_or_admin_may_reschedule_or_cancel(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(8, 0))
    doctor = bearer(clinic.doctor_ids[0], UserRole.DOCTOR)
    moved = await reschedule(app_client, clinic, appointment_id, at(MONDAY, 9), headers=doctor)
    cancelled = await cancel(app_client, clinic, appointment_id, headers=doctor)
    assert moved.status_code == cancelled.status_code == 403


# ---------------------------------------------------------------------------- mốc 2 giờ
async def test_patient_cannot_change_within_two_hours_of_the_visit(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    """AC-06 (BR-08): còn dưới 2 giờ thì bị từ chối kèm hướng dẫn gọi phòng khám."""
    appointment_id = await add_appointment(db, clinic, start=time(8, 0))
    clock.at = local_datetime(MONDAY, time(6, 1))  # còn 1 giờ 59 phút
    patient = bearer(clinic.patient_ids[0], UserRole.PATIENT, clock.at)

    moved = await reschedule(app_client, clinic, appointment_id, at(MONDAY, 9), headers=patient)
    cancelled = await cancel(app_client, clinic, appointment_id, headers=patient)

    for response in (moved, cancelled):
        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "CHANGE_DEADLINE_PASSED"
        assert "gọi phòng khám" in body["message"]
        assert "clinic_phone" in body["details"]
    listed = await app_client.get("/api/v1/appointments/me", headers=patient)
    assert listed.json()["items"][0]["can_change"] is False
    assert (await fetch(db, appointment_id)).status is AppointmentStatus.BOOKED


async def test_exactly_two_hours_before_is_still_allowed(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(8, 0))
    clock.at = local_datetime(MONDAY, time(6, 0))
    patient = bearer(clinic.patient_ids[0], UserRole.PATIENT, clock.at)
    response = await cancel(app_client, clinic, appointment_id, headers=patient)
    assert response.status_code == 200


async def test_admin_is_not_bound_by_the_two_hour_deadline(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    """FR-ADM-03: quản trị đổi, hủy mọi lịch BOOKED, ghi kênh ADMIN."""
    first = await add_appointment(db, clinic, start=time(8, 0))
    second = await add_appointment(db, clinic, start=time(8, 20), patient_index=1)
    clock.at = local_datetime(MONDAY, time(7, 30))
    admin = bearer(clinic.admin_id, UserRole.ADMIN, clock.at)

    moved = await reschedule(app_client, clinic, first, at(MONDAY, 10), headers=admin)
    cancelled = await cancel(app_client, clinic, second, headers=admin)

    assert moved.status_code == cancelled.status_code == 200
    assert moved.json()["can_change"] is True
    assert [r.channel for r in await history(db, first)] == [Channel.ADMIN]


# ---------------------------------------------------------------------------- hủy lịch
async def test_cancel_frees_the_slot_and_keeps_the_reason_out_of_history(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(8, 0), needs_attention=True)

    response = await cancel(app_client, clinic, appointment_id, reason="  Bận việc đột xuất ")

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert response.json()["can_change"] is False
    cancelled = await fetch(db, appointment_id)
    assert cancelled.cancel_reason == "Bận việc đột xuất"
    assert cancelled.needs_attention is False
    rows = await history(db, appointment_id)
    assert [r.action for r in rows] == [HistoryAction.CANCEL]
    assert rows[0].new_value is not None and rows[0].new_value["status"] == "CANCELLED"
    assert "Bận việc" not in str(rows[0].new_value)
    assert await notifications(db) == [NotificationType.CANCELLED]

    other = await app_client.post(
        "/api/v1/appointments",
        json={
            "service_id": clinic.service_id,
            "doctor_id": clinic.doctor_ids[0],
            "start_at": at(MONDAY, 8),
        },
        headers=bearer(clinic.patient_ids[1], UserRole.PATIENT),
    )
    assert other.status_code == 201  # khung được trả lại ngay


async def test_cancelled_appointment_cannot_be_changed_again(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(8, 0))
    assert (await cancel(app_client, clinic, appointment_id)).status_code == 200

    again = await cancel(app_client, clinic, appointment_id)
    moved = await reschedule(app_client, clinic, appointment_id, at(MONDAY, 9))

    for response in (again, moved):
        assert response.status_code == 409
        assert response.json()["code"] == "INVALID_TRANSITION"


async def test_cancel_reason_is_validated(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(8, 0))
    too_long = await cancel(app_client, clinic, appointment_id, reason="x" * 501)
    nul = await cancel(app_client, clinic, appointment_id, reason="a\u0000b")
    assert too_long.status_code == nul.status_code == 422


# ---------------------------------------------------------------------------- NFR-09
@pytest.mark.parametrize("operation", ["book", "reschedule", "cancel"])
async def test_failure_midway_leaves_no_partial_change(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, operation: str
) -> None:
    """NFR-09: lỗi giữa transaction (ở đây: ghi email thất bại) thì không còn dấu vết nào."""
    appointment_id = await add_appointment(db, clinic, start=time(8, 0))
    patient = bearer(clinic.patient_ids[0], UserRole.PATIENT)
    with (
        patch(
            "app.modules.appointments.service.outbox.enqueue",
            side_effect=RuntimeError("mất kết nối giả lập"),
        ),
        pytest.raises(RuntimeError),
    ):
        if operation == "book":
            await app_client.post(
                "/api/v1/appointments",
                json={"service_id": clinic.service_id, "start_at": at(MONDAY, 10)},
                headers=patient,
            )
        elif operation == "reschedule":
            await reschedule(app_client, clinic, appointment_id, at(MONDAY, 10))
        else:
            await cancel(app_client, clinic, appointment_id)

    unchanged = await fetch(db, appointment_id)
    assert unchanged.status is AppointmentStatus.BOOKED
    assert unchanged.start_at == local_datetime(MONDAY, time(8))
    listed = await app_client.get("/api/v1/appointments/me", headers=patient)
    assert listed.json()["total"] == 1  # không có lịch mồ côi
    assert await history(db, appointment_id) == []


# ---------------------------------------------------------------------------- an toàn
async def test_appointment_writes_are_rate_limited_per_user(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """Mỗi lần đặt, đổi, hủy sinh một email: tối đa 10 lần/phút cho mỗi người dùng."""
    appointment_id = await add_appointment(db, clinic, start=time(8, 0))
    statuses = []
    for i in range(11):
        hour, minute = divmod(9 * 60 + 20 * (i % 2), 60)
        response = await reschedule(app_client, clinic, appointment_id, at(MONDAY, hour, minute))
        statuses.append(response.status_code)
    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429
    other = await cancel(
        app_client, clinic, appointment_id, headers=bearer(clinic.admin_id, UserRole.ADMIN)
    )
    assert other.status_code == 200  # người khác có bộ đếm riêng


async def test_flagging_skips_an_appointment_moved_after_it_was_listed(
    db: AsyncSession, clinic: Clinic
) -> None:
    """Quản trị liệt kê lịch bị ảnh hưởng rồi mới khóa: lịch vừa được dời sang bác sĩ khác trong
    khoảng đó không bị gắn cờ nhầm."""
    appointment_id = await add_appointment(db, clinic, start=time(9, 0), doctor_index=1)
    stale = AffectedAppointment(
        id=appointment_id,
        code="LH-TEST",
        start_at=local_datetime(MONDAY, time(8)),
        end_at=local_datetime(MONDAY, time(8, 20)),
        service_name="Khám da liễu tổng quát",
        patient_name="Bệnh Nhân 0",
        needs_attention=False,
    )
    admin = Actor(clinic.admin_id, UserRole.ADMIN, Channel.ADMIN)
    async with db.begin():
        flagged = await flag_for_attention(
            db, admin, clinic.doctor_ids[0], [stale], source={"source": "TIME_OFF", "ref_id": 1}
        )
    assert flagged == []
    assert (await fetch(db, appointment_id)).needs_attention is False
