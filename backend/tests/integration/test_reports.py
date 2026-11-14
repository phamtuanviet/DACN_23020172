"""Đánh giá bác sĩ và số liệu dashboard (UC19, UC20, FR-RPT-01..03, AC-18, AC-19)."""

import asyncio
from collections import Counter
from datetime import date, time
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.errors import AppError
from app.core.timeutil import local_datetime
from app.db.enums import AppointmentStatus, Channel, UserRole
from app.db.models.appointments import Review
from app.modules.reports.schemas import ReviewCreate
from app.modules.reports.service import ReportService
from tests.integration.conftest import MutableClock
from tests.integration.factories import Clinic, add_appointment, bearer, build_clinic

pytestmark = pytest.mark.integration

LAST_FRIDAY = date(2026, 10, 9)  # trước TEST_NOW (Thứ Bảy 10/10/2026 09:00)
TODAY = date(2026, 10, 10)


@pytest.fixture
async def clinic(db: AsyncSession) -> Clinic:
    return await build_clinic(db, doctors=2, patients=2)


async def _completed(db: AsyncSession, clinic: Clinic, **kwargs: Any) -> int:
    return await add_appointment(
        db,
        clinic,
        day=LAST_FRIDAY,
        start=kwargs.pop("start", time(8, 0)),
        status=AppointmentStatus.COMPLETED,
        **kwargs,
    )


async def _review(
    client: AsyncClient,
    appointment_id: int,
    user_id: int,
    role: UserRole = UserRole.PATIENT,
    **body: Any,
) -> Any:
    return await client.post(
        f"/api/v1/appointments/{appointment_id}/review",
        json={"rating": 5, **body},
        headers=bearer(user_id, role),
    )


async def _review_count(db: AsyncSession) -> int:
    count = (await db.execute(select(func.count()).select_from(Review))).scalar_one()
    await db.commit()
    return int(count)


# ---------------------------------------------------------------------------- đánh giá
async def test_patient_reviews_a_completed_visit_exactly_once(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await _completed(db, clinic)
    patient = clinic.patient_ids[0]
    detail_url = f"/api/v1/appointments/{appointment_id}"
    before = (await app_client.get(detail_url, headers=bearer(patient, UserRole.PATIENT))).json()
    assert before["can_review"] is True
    assert before["review"] is None

    response = await _review(
        app_client, appointment_id, patient, rating=4, comment="  Bác sĩ giải thích rõ.  "
    )
    assert response.status_code == 201, response.text
    assert response.json() == {
        "rating": 4,
        "comment": "Bác sĩ giải thích rõ.",
        "created_at": "2026-10-10T09:00:00+07:00",
    }

    again = await _review(app_client, appointment_id, patient, rating=1)
    assert again.status_code == 409
    assert again.json()["code"] == "ALREADY_REVIEWED"
    assert await _review_count(db) == 1

    after = (await app_client.get(detail_url, headers=bearer(patient, UserRole.PATIENT))).json()
    assert after["can_review"] is False
    assert after["review"]["rating"] == 4


@pytest.mark.parametrize(
    "status",
    [
        AppointmentStatus.BOOKED,
        AppointmentStatus.ARRIVED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.NO_SHOW,
    ],
)
async def test_only_completed_visits_can_be_reviewed(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, status: AppointmentStatus
) -> None:
    appointment_id = await add_appointment(
        db, clinic, day=LAST_FRIDAY, start=time(8), status=status
    )
    response = await _review(app_client, appointment_id, clinic.patient_ids[0])
    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_TRANSITION"
    assert response.json()["details"] == {"status": status.value}
    detail = await app_client.get(
        f"/api/v1/appointments/{appointment_id}",
        headers=bearer(clinic.patient_ids[0], UserRole.PATIENT),
    )
    assert detail.json()["can_review"] is False
    assert await _review_count(db) == 0


async def test_only_the_owner_can_review(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    appointment_id = await _completed(db, clinic)
    other = await _review(app_client, appointment_id, clinic.patient_ids[1])
    assert other.status_code == 403
    for user_id, role in (
        (clinic.doctor_ids[0], UserRole.DOCTOR),  # bác sĩ của lịch
        (clinic.admin_id, UserRole.ADMIN),
    ):
        assert (await _review(app_client, appointment_id, user_id, role)).status_code == 403
    missing = await _review(app_client, 999_999, clinic.patient_ids[0])
    assert missing.status_code == 404

    # Lớp 2: gọi thẳng service (như tool của Agent) với vai trò khác vẫn bị chặn; chính chủ lịch
    # qua kênh Agent cũng không được, vì LLM không được chấm thay bệnh nhân (BR-06)
    service = ReportService(db, clock)
    for actor in (
        Actor(clinic.doctor_ids[0], UserRole.DOCTOR, Channel.WEB),
        Actor(clinic.admin_id, UserRole.ADMIN, Channel.ADMIN),
        Actor(clinic.patient_ids[1], UserRole.PATIENT, Channel.WEB),
        Actor(clinic.patient_ids[0], UserRole.PATIENT, Channel.AGENT),
    ):
        with pytest.raises(AppError) as error:
            await service.create_review(actor, appointment_id, ReviewCreate(rating=5))
        assert error.value.code == "FORBIDDEN"
    assert await _review_count(db) == 0


@pytest.mark.parametrize(
    "body",
    [
        {"rating": 0},
        {"rating": 6},
        {"rating": "năm"},
        {"rating": 5, "comment": "x" * 501},
        {"rating": 5, "comment": "có\x00ký tự lạ"},
    ],
)
async def test_review_input_is_validated(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, body: dict[str, Any]
) -> None:
    appointment_id = await _completed(db, clinic)
    response = await app_client.post(
        f"/api/v1/appointments/{appointment_id}/review",
        json=body,
        headers=bearer(clinic.patient_ids[0], UserRole.PATIENT),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_blank_comment_is_stored_as_empty(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    appointment_id = await _completed(db, clinic)
    response = await _review(app_client, appointment_id, clinic.patient_ids[0], comment="   ")
    assert response.status_code == 201
    assert response.json()["comment"] is None


async def test_doctor_does_not_see_individual_reviews(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """Bác sĩ chỉ thấy điểm trung bình trên hồ sơ; quản trị thấy đánh giá để theo dõi chất lượng."""
    appointment_id = await _completed(db, clinic)
    await _review(app_client, appointment_id, clinic.patient_ids[0], rating=2, comment="Chờ lâu")
    url = f"/api/v1/appointments/{appointment_id}"

    as_doctor = await app_client.get(url, headers=bearer(clinic.doctor_ids[0], UserRole.DOCTOR))
    assert as_doctor.status_code == 200
    assert as_doctor.json()["review"] is None
    assert as_doctor.json()["can_review"] is False

    as_admin = await app_client.get(url, headers=bearer(clinic.admin_id, UserRole.ADMIN))
    assert as_admin.json()["review"]["comment"] == "Chờ lâu"
    assert as_admin.json()["can_review"] is False


async def test_concurrent_reviews_of_one_visit_store_one(
    wide_pool: None, app_client: AsyncClient, db: AsyncSession
) -> None:
    clinic = await build_clinic(db, doctors=1, patients=1)
    appointment_id = await _completed(db, clinic)
    responses = await asyncio.gather(
        *(_review(app_client, appointment_id, clinic.patient_ids[0], rating=r) for r in range(1, 6))
    )
    statuses = Counter(r.status_code for r in responses)
    assert statuses == {201: 1, 409: 4}
    assert {r.json()["code"] for r in responses if r.status_code == 409} == {"ALREADY_REVIEWED"}
    assert await _review_count(db) == 1


async def test_doctor_profile_shows_average_rating(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """FR-RPT-03: điểm trung bình làm tròn một chữ số và số lượt, trên hồ sơ và danh sách."""
    for patient_index, (start, rating) in enumerate([(time(8), 5), (time(9), 4)]):
        appointment_id = await _completed(db, clinic, start=start, patient_index=patient_index)
        response = await _review(
            app_client, appointment_id, clinic.patient_ids[patient_index], rating=rating
        )
        assert response.status_code == 201
    third = await _completed(db, clinic, start=time(10))
    await _review(app_client, third, clinic.patient_ids[0], rating=4)

    profile = (await app_client.get(f"/api/v1/doctors/{clinic.doctor_ids[0]}")).json()
    assert profile["rating_average"] == 4.3  # 13 / 3 = 4,33…
    assert profile["rating_count"] == 3

    listed = {d["id"]: d for d in (await app_client.get("/api/v1/doctors")).json()}
    assert listed[clinic.doctor_ids[0]]["rating_count"] == 3
    assert listed[clinic.doctor_ids[1]]["rating_average"] is None
    assert listed[clinic.doctor_ids[1]]["rating_count"] == 0


async def test_rating_stays_hidden_until_enough_reviews(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """Dưới RATING_MIN_COUNT (3) lượt thì chưa hiện điểm: bác sĩ biết mình vừa khám ai, nên điểm
    của một, hai lượt lộ số sao của từng bệnh nhân. Số lượt vẫn hiện."""
    for patient_index, start in enumerate([time(8), time(9)]):
        appointment_id = await _completed(
            db, clinic, start=start, doctor_index=1, patient_index=patient_index
        )
        await _review(app_client, appointment_id, clinic.patient_ids[patient_index], rating=2)
    profile = (await app_client.get(f"/api/v1/doctors/{clinic.doctor_ids[1]}")).json()
    assert (profile["rating_average"], profile["rating_count"]) == (None, 2)


async def test_review_writes_share_the_appointment_write_limit(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """Đặt, đổi, hủy, đánh giá dùng chung 10 lần ghi mỗi phút mỗi người, kể cả khi đổi id lịch
    trên URL: không dò id lịch hẹn hàng loạt được."""
    headers = bearer(clinic.patient_ids[0], UserRole.PATIENT)
    statuses = [
        (await _review(app_client, 900_000 + i, clinic.patient_ids[0])).status_code
        for i in range(10)
    ]
    assert statuses == [404] * 10
    review = await _review(app_client, 900_100, clinic.patient_ids[0])
    cancel = await app_client.post("/api/v1/appointments/900101/cancel", json={}, headers=headers)
    assert (review.status_code, cancel.status_code) == (429, 429)
    assert review.json()["code"] == "RATE_LIMITED"
    other = await _review(app_client, 900_102, clinic.patient_ids[1])  # người khác: bộ đếm riêng
    assert other.status_code == 404


# ---------------------------------------------------------------------------- dashboard
async def _stats(client: AsyncClient, clinic: Clinic, **params: str) -> Any:
    response = await client.get(
        "/api/v1/admin/stats", params=params, headers=bearer(clinic.admin_id, UserRole.ADMIN)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_stats_match_the_appointments_in_the_database(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """AC-18: số theo ngày, theo bác sĩ, tỷ lệ hủy, vắng mặt, kênh đặt khớp dữ liệu."""
    S = AppointmentStatus
    created = local_datetime(date(2026, 10, 5), time(10))
    rows = [
        # (ngày, giờ, bác sĩ, bệnh nhân, trạng thái, kênh)
        (date(2026, 10, 7), time(8), 0, 0, S.COMPLETED, Channel.WEB),
        (date(2026, 10, 7), time(9), 0, 1, S.NO_SHOW, Channel.AGENT),
        (date(2026, 10, 7), time(10), 1, 0, S.CANCELLED, Channel.AGENT),
        (LAST_FRIDAY, time(8), 1, 1, S.COMPLETED, Channel.WEB),
        (LAST_FRIDAY, time(9), 1, 0, S.ARRIVED, Channel.WEB),
        (TODAY, time(8), 0, 0, S.COMPLETED, Channel.AGENT),
        (TODAY, time(10), 0, 1, S.BOOKED, Channel.WEB),
        (TODAY, time(11), 1, 0, S.BOOKED, Channel.AGENT),
        # ngoài khoảng: tuần trước (kỳ trước) và tuần sau
        (date(2026, 9, 30), time(8), 0, 0, S.CANCELLED, Channel.WEB),
        (date(2026, 9, 30), time(9), 0, 1, S.COMPLETED, Channel.WEB),
        (date(2026, 10, 12), time(8), 0, 0, S.BOOKED, Channel.WEB),
    ]
    for day, start, doctor, patient, status, channel in rows:
        await add_appointment(
            db,
            clinic,
            day=day,
            start=start,
            doctor_index=doctor,
            patient_index=patient,
            status=status,
            channel=channel,
            # lịch tuần sau được đặt hôm nay, các lịch khác đặt trước ngày khám
            created_at=local_datetime(TODAY, time(8))
            if day > TODAY
            else min(created, local_datetime(day, time(7))),
        )

    stats = await _stats(app_client, clinic, date_from="2026-10-04", date_to="2026-10-10")

    assert [d["day"] for d in stats["days"]] == [
        f"2026-10-{d:02d}" for d in range(4, 11)
    ]  # đủ 7 ngày, kể cả Chủ nhật không có lịch
    by_day = {d["day"]: d for d in stats["days"]}
    assert by_day["2026-10-04"]["total"] == 0
    assert by_day["2026-10-07"] == {
        "day": "2026-10-07",
        "total": 2,
        "booked": 0,
        "arrived": 0,
        "completed": 1,
        "cancelled": 1,
        "no_show": 1,
    }
    assert by_day["2026-10-10"]["total"] == 3
    assert stats["totals"] == {
        "total": 7,
        "booked": 2,
        "arrived": 1,
        "completed": 3,
        "cancelled": 1,
        "no_show": 1,
    }
    # hủy 1 / 8 lịch; vắng 1 / (1 đã đến + 3 đã khám + 1 vắng)
    assert stats["rates"] == {"cancel_rate": 0.125, "no_show_rate": 0.2}
    # kỳ trước 27/09–03/10: 1 hủy / 2 lịch, chưa có vắng mặt
    assert stats["previous_rates"] == {"cancel_rate": 0.5, "no_show_rate": 0.0}

    doctors = {d["id"]: d for d in stats["doctors"]}
    first, second = clinic.doctor_ids
    assert (doctors[first]["total"], doctors[first]["completed"]) == (4, 2)
    assert (doctors[second]["total"], doctors[second]["cancelled"]) == (3, 1)
    assert [d["id"] for d in stats["doctors"]] == [first, second]  # nhiều lịch nhất trước
    # đặt trong khoảng: 8 lịch có ngày khám trong khoảng + lịch tuần sau đặt hôm nay
    assert stats["channels"] == {"web": 5, "agent": 4}


async def test_stats_default_range_and_doctors_without_appointments(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    stats = await _stats(app_client, clinic)
    assert (stats["date_from"], stats["date_to"]) == ("2026-09-27", "2026-10-10")  # 14 ngày
    assert len(stats["days"]) == 14
    assert stats["rates"] == {"cancel_rate": None, "no_show_rate": None}
    # bác sĩ đang hoạt động vẫn có mặt dù chưa có lịch
    assert sorted(d["id"] for d in stats["doctors"]) == sorted(clinic.doctor_ids)
    assert all(d["total"] == 0 for d in stats["doctors"])

    later = await _stats(app_client, clinic, date_from="2026-10-12")
    assert (later["date_from"], later["date_to"]) == ("2026-10-12", "2026-10-25")


@pytest.mark.parametrize(
    "params",
    [
        {"date_from": "2026-10-10", "date_to": "2026-10-09"},
        {"date_from": "2026-09-01", "date_to": "2026-10-10"},  # 40 ngày
        {"date_from": "1999-12-31"},
        {"date_to": "khong-phai-ngay"},
    ],
)
async def test_stats_rejects_bad_ranges(
    app_client: AsyncClient, clinic: Clinic, params: dict[str, str]
) -> None:
    response = await app_client.get(
        "/api/v1/admin/stats", params=params, headers=bearer(clinic.admin_id, UserRole.ADMIN)
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_stats_are_admin_only(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    for user_id, role in (
        (clinic.patient_ids[0], UserRole.PATIENT),
        (clinic.doctor_ids[0], UserRole.DOCTOR),
    ):
        response = await app_client.get("/api/v1/admin/stats", headers=bearer(user_id, role))
        assert response.status_code == 403
    assert (await app_client.get("/api/v1/admin/stats")).status_code == 401

    service = ReportService(db, clock)
    for actor in (
        Actor(clinic.patient_ids[0], UserRole.PATIENT, Channel.AGENT),
        Actor(clinic.doctor_ids[0], UserRole.DOCTOR, Channel.WEB),
    ):
        with pytest.raises(AppError) as error:
            await service.stats(actor, None, None)
        assert error.value.code == "FORBIDDEN"


async def test_stats_count_days_in_clinic_time(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """Lịch 06:30 sáng giờ Việt Nam là 23:30 hôm trước theo UTC: vẫn tính vào đúng ngày khám."""
    await add_appointment(db, clinic, day=LAST_FRIDAY, start=time(6, 30))
    stats = await _stats(app_client, clinic, date_from="2026-10-08", date_to="2026-10-09")
    assert [d["total"] for d in stats["days"]] == [0, 1]
