"""Quản trị tạo, sửa, khóa tài khoản bác sĩ và gán dịch vụ (UC14, FR-ADM-01, FR-AUTH-05,
FR-CAT-03), kèm AC-07: danh mục, bác sĩ, ca làm mới có hiệu lực ngay cho bệnh nhân."""

from datetime import time, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.clock import FixedClock
from app.core.errors import AppError
from app.db.enums import Channel, UserRole
from app.db.models.users import User
from app.modules.catalog.schemas import DoctorUpdate
from app.modules.catalog.service import CatalogService
from tests.conftest import TEST_NOW
from tests.integration.factories import MONDAY, Clinic, add_appointment, bearer, build_clinic

pytestmark = pytest.mark.integration

PASSWORD = "Matkhau123"


@pytest.fixture
async def clinic(db: AsyncSession) -> Clinic:
    return await build_clinic(db)


def admin(clinic: Clinic) -> dict[str, str]:
    return bearer(clinic.admin_id, UserRole.ADMIN)


async def create_doctor(client: AsyncClient, clinic: Clinic, **fields: Any) -> Response:
    payload = {
        "email": "Thu.Ha@Example.com",
        "password": PASSWORD,
        "title": "BS.CKI",
        "full_name": "Nguyễn  Thu Hà",
        "gender": "FEMALE",
        "specialty_id": clinic.specialty_id,
        "bio": "12 năm kinh nghiệm da liễu.",
        "service_ids": [clinic.service_id],
    }
    return await client.post(
        "/api/v1/admin/doctors", json={**payload, **fields}, headers=admin(clinic)
    )


async def update_doctor(
    client: AsyncClient, clinic: Clinic, doctor_id: int, **fields: Any
) -> Response:
    return await client.patch(
        f"/api/v1/admin/doctors/{doctor_id}", json=fields, headers=admin(clinic)
    )


async def test_admin_creates_a_doctor_who_can_log_in_and_is_listed_publicly(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    created = await create_doctor(app_client, clinic)

    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "BS.CKI Nguyễn Thu Hà"
    assert (body["title"], body["full_name"]) == ("BS.CKI", "Nguyễn Thu Hà")
    assert body["email"] == "thu.ha@example.com"
    assert body["service_ids"] == [clinic.service_id]
    assert body["is_active"] is True and body["upcoming_count"] == 0

    login = await app_client.post(
        "/api/v1/auth/login", json={"email": "thu.ha@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "DOCTOR"

    public = await app_client.get("/api/v1/doctors", params={"service_id": clinic.service_id})
    assert body["id"] in [d["id"] for d in public.json()]
    listed = await app_client.get(
        "/api/v1/admin/doctors", params={"q": "thu ha"}, headers=admin(clinic)
    )
    assert [d["id"] for d in listed.json()] == [body["id"]]


async def test_duplicate_email_and_foreign_services_are_rejected(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    taken = await create_doctor(app_client, clinic, email="bacsi0@example.com")
    assert taken.status_code == 409
    assert taken.json()["code"] == "EMAIL_TAKEN"

    other = await app_client.post(
        "/api/v1/admin/specialties", json={"name": "Nhi khoa"}, headers=admin(clinic)
    )
    child = await app_client.post(
        "/api/v1/admin/services",
        json={
            "specialty_id": other.json()["id"],
            "name": "Khám nhi tổng quát",
            "scope_description": "Trẻ dưới 16 tuổi: sốt, ho, tiêu hóa.",
            "duration_min": 20,
            "ref_price_vnd": 220_000,
        },
        headers=admin(clinic),
    )
    foreign = await create_doctor(app_client, clinic, service_ids=[child.json()["id"]])
    assert foreign.status_code == 422
    assert foreign.json()["details"]["fields"][0]["loc"] == ["body", "service_ids"]

    weak = await create_doctor(app_client, clinic, password="12345678")
    assert weak.status_code == 422
    missing = await create_doctor(app_client, clinic, service_ids=[999_999])
    assert missing.status_code == 422


async def test_ac07_new_catalog_doctor_and_shift_show_up_in_availability(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    """AC-07: quản trị tạo chuyên khoa, dịch vụ có thời lượng, bác sĩ, ca làm lặp lại; khung giờ
    trống mới xuất hiện ngay cho bệnh nhân."""
    headers = admin(clinic)
    specialty = await app_client.post(
        "/api/v1/admin/specialties", json={"name": "Mắt"}, headers=headers
    )
    service = await app_client.post(
        "/api/v1/admin/services",
        json={
            "specialty_id": specialty.json()["id"],
            "name": "Khám mắt tổng quát",
            "scope_description": "Đo thị lực, khô mắt, đỏ mắt, mỏi mắt.",
            "duration_min": 30,
            "ref_price_vnd": 200_000,
        },
        headers=headers,
    )
    doctor = await create_doctor(
        app_client,
        clinic,
        email="mat@example.com",
        specialty_id=specialty.json()["id"],
        service_ids=[service.json()["id"]],
    )
    doctor_id = doctor.json()["id"]
    shift = await app_client.post(
        f"/api/v1/admin/doctors/{doctor_id}/shifts",
        json={"weekday": 1, "start_time": "08:00", "end_time": "09:30", "valid_from": "2026-10-01"},
        headers=headers,
    )
    assert shift.status_code == 201

    availability = await app_client.get(
        "/api/v1/availability",
        params={"service_id": service.json()["id"], "date_from": MONDAY.isoformat()},
    )
    slots = availability.json()["days"][0]["slots"]
    assert [s["start_at"][11:16] for s in slots] == ["08:00", "08:30", "09:00"]
    assert {d["id"] for s in slots for d in s["doctors"]} == {doctor_id}


async def test_locking_a_doctor_signs_them_out_and_hides_them_but_keeps_appointments(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    doctor_id = clinic.doctor_ids[0]
    appointment_id = await add_appointment(db, clinic, start=time(9, 0))
    doctor_token = bearer(doctor_id, UserRole.DOCTOR)
    assert (await app_client.get("/api/v1/me", headers=doctor_token)).status_code == 200

    locked = await update_doctor(app_client, clinic, doctor_id, is_active=False)

    assert locked.status_code == 200
    assert locked.json()["is_active"] is False
    assert locked.json()["upcoming_count"] == 1
    assert (await app_client.get("/api/v1/me", headers=doctor_token)).status_code == 401
    public = await app_client.get("/api/v1/doctors", params={"service_id": clinic.service_id})
    assert doctor_id not in [d["id"] for d in public.json()]
    # Lịch đã đặt giữ nguyên, quản trị đổi sang bác sĩ khác hoặc hủy (BR-10)
    kept = await app_client.get(f"/api/v1/appointments/{appointment_id}", headers=admin(clinic))
    assert kept.json()["status"] == "BOOKED"

    unlocked = await update_doctor(app_client, clinic, doctor_id, is_active=True)
    assert unlocked.json()["is_active"] is True
    assert (await app_client.get("/api/v1/me", headers=doctor_token)).status_code == 200


async def test_locking_ends_refresh_and_unlocking_clears_failed_logins(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    """Khóa: phiên cũ không làm mới được nữa, kể cả sau khi mở khóa. Mở khóa: gỡ luôn khóa tạm do
    nhập sai mật khẩu."""
    doctor_id = (await create_doctor(app_client, clinic)).json()["id"]
    login = await app_client.post(
        "/api/v1/auth/login", json={"email": "thu.ha@example.com", "password": PASSWORD}
    )
    token = login.cookies.get("refresh_token")
    assert login.status_code == 200 and token
    async with db.begin():
        await db.execute(
            update(User)
            .where(User.id == doctor_id)
            .values(failed_login_count=3, locked_until=TEST_NOW + timedelta(minutes=10))
        )

    async def refresh() -> int:
        app_client.cookies.clear()
        response = await app_client.post(
            "/api/v1/auth/refresh", headers={"Cookie": f"refresh_token={token}"}
        )
        return response.status_code

    assert (await update_doctor(app_client, clinic, doctor_id, is_active=False)).status_code == 200
    assert await refresh() == 401
    assert (await update_doctor(app_client, clinic, doctor_id, is_active=True)).status_code == 200
    assert await refresh() == 401
    user = await db.get(User, doctor_id, populate_existing=True)
    assert user is not None and (user.failed_login_count, user.locked_until) == (0, None)
    await db.commit()


async def test_rename_and_specialty_change_keep_data_consistent(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    doctor_id = clinic.doctor_ids[1]
    renamed = await update_doctor(
        app_client, clinic, doctor_id, title="ThS. BS.", full_name="Bác Sĩ Một"
    )
    assert renamed.json()["name"] == "ThS. BS. Bác Sĩ Một"
    assert renamed.json()["full_name"] == "Bác Sĩ Một"

    other = await app_client.post(
        "/api/v1/admin/specialties", json={"name": "Nội tổng quát"}, headers=admin(clinic)
    )
    moved = await update_doctor(app_client, clinic, doctor_id, specialty_id=other.json()["id"])
    assert moved.status_code == 200
    assert moved.json()["specialty"]["name"] == "Nội tổng quát"
    assert moved.json()["service_ids"] == []  # dịch vụ da liễu bị bỏ gán theo chuyên khoa mới

    back = await update_doctor(
        app_client,
        clinic,
        doctor_id,
        specialty_id=clinic.specialty_id,
        service_ids=[clinic.acne_service_id, clinic.acne_service_id],
    )
    assert back.json()["service_ids"] == [clinic.acne_service_id]
    cleared = await update_doctor(app_client, clinic, doctor_id, bio=None)
    assert cleared.json()["bio"] is None
    # Chức danh (≤ 50) + họ tên (≤ 100) lưu chung một cột 100 ký tự
    too_long = await update_doctor(app_client, clinic, doctor_id, full_name="Bác Sĩ " + "A" * 92)
    assert too_long.status_code == 422
    assert too_long.json()["details"]["fields"][0]["loc"] == ["body", "full_name"]
    assert (await update_doctor(app_client, clinic, 999_999, title="BS.")).status_code == 404
    # Tên công khai kèm chức danh chỉ quản trị sửa; bác sĩ không tự đổi qua PATCH /me
    self_rename = await app_client.patch(
        "/api/v1/me", json={"full_name": "Bác Sĩ Giỏi"}, headers=bearer(doctor_id, UserRole.DOCTOR)
    )
    assert self_rename.status_code == 422
    assert self_rename.json()["details"]["fields"][0]["loc"] == ["body", "full_name"]


async def test_service_layer_rejects_non_admins(db: AsyncSession, clinic: Clinic) -> None:
    """Lớp 2: service tự kiểm tra vai trò dù router đã chặn (docs mục 4.6)."""
    service = CatalogService(db, FixedClock(TEST_NOW))
    doctor = Actor(clinic.doctor_ids[0], UserRole.DOCTOR, Channel.WEB)
    with pytest.raises(AppError) as error:
        await service.update_doctor(doctor, clinic.doctor_ids[0], DoctorUpdate(is_active=False))
    assert error.value.status == 403
    with pytest.raises(AppError):
        await service.admin_list_doctors(doctor, None, None)
