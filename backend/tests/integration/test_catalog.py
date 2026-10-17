"""Danh mục qua API (FR-CAT-01..05, UC03, UC13) trên PostgreSQL thật."""

from datetime import time
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import UserRole
from app.db.models.catalog import Service, Specialty
from app.db.models.users import User
from tests.integration.factories import Clinic, add_appointment, bearer, build_clinic

pytestmark = pytest.mark.integration


@pytest.fixture
async def clinic(db: AsyncSession) -> Clinic:
    clinic = await build_clinic(db)
    async with db.begin():  # chuyên khoa đã ẩn cùng một dịch vụ của nó
        hidden = Specialty(name="Mắt", description="Đo thị lực.", is_active=False)
        db.add(hidden)
        await db.flush()
        db.add(
            Service(
                specialty_id=hidden.id,
                name="Khám mắt tổng quát",
                scope_description="Đo thị lực, khám đỏ mắt, khô mắt.",
                duration_min=20,
                ref_price_vnd=180_000,
            )
        )
    return clinic


def names(items: list[dict[str, Any]]) -> list[str]:
    return [item["name"] for item in items]


def admin(clinic: Clinic) -> dict[str, str]:
    return bearer(clinic.admin_id, UserRole.ADMIN)


async def test_public_specialties_have_counts_and_hide_inactive(
    app_client: AsyncClient, clinic: Clinic
) -> None:
    response = await app_client.get("/api/v1/specialties")
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": clinic.specialty_id,
            "name": "Da liễu",
            "description": "Bệnh về da, tóc, móng.",
            "service_count": 2,
            "doctor_count": 2,
            "min_price_vnd": 250_000,
        }
    ]


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("da lieu", ["Khám da liễu tổng quát", "Tư vấn trị mụn"]),  # khớp cả tên chuyên khoa
        ("DA LIỄU", ["Khám da liễu tổng quát", "Tư vấn trị mụn"]),
        ("tri mun", ["Tư vấn trị mụn"]),
        ("trị   mụn", ["Tư vấn trị mụn"]),
        ("ngua", ["Khám da liễu tổng quát"]),  # khớp phạm vi khám "ngứa"
        ("kham mat", []),  # dịch vụ thuộc chuyên khoa đã ẩn
        ("100%", []),  # ký tự đại diện của LIKE được coi là chữ thường
    ],
)
async def test_service_search_ignores_diacritics_and_case(
    app_client: AsyncClient, clinic: Clinic, q: str, expected: list[str]
) -> None:
    response = await app_client.get("/api/v1/services", params={"q": q})
    assert response.status_code == 200
    assert names(response.json()) == expected


async def test_services_list_only_active_doctors(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    async with db.begin():
        locked = await db.get(User, clinic.doctor_ids[1])
        assert locked is not None
        locked.is_active = False
    response = await app_client.get(
        "/api/v1/services", params={"specialty_id": clinic.specialty_id}
    )
    [general, acne] = response.json()
    assert general["specialty"] == {"id": clinic.specialty_id, "name": "Da liễu"}
    assert general["duration_min"] == 20 and general["ref_price_vnd"] == 250_000
    assert [d["id"] for d in general["doctors"]] == [clinic.doctor_ids[0]]
    assert [d["id"] for d in acne["doctors"]] == [clinic.doctor_ids[0]]


async def test_doctor_search_and_filters(app_client: AsyncClient, clinic: Clinic) -> None:
    by_name = await app_client.get("/api/v1/doctors", params={"q": "bac si 1"})
    assert [d["id"] for d in by_name.json()] == [clinic.doctor_ids[1]]
    by_specialty = await app_client.get("/api/v1/doctors", params={"q": "da lieu"})
    assert [d["id"] for d in by_specialty.json()] == clinic.doctor_ids
    by_service = await app_client.get(
        "/api/v1/doctors", params={"service_id": clinic.acne_service_id}
    )
    doctor = by_service.json()[0]
    assert doctor["specialty"]["name"] == "Da liễu"
    assert names(doctor["services"]) == ["Khám da liễu tổng quát", "Tư vấn trị mụn"]


async def test_doctor_profile_shows_services_and_weekly_hours(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    response = await app_client.get(f"/api/v1/doctors/{clinic.doctor_ids[0]}")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "BS. Bác Sĩ 0"
    assert body["gender"] == "MALE"
    assert [h["weekday"] for h in body["working_hours"]] == [1, 2, 3, 4, 5, 6]
    assert body["working_hours"][0] == {
        "weekday": 1,
        "start_time": "08:00:00",
        "end_time": "11:30:00",
    }

    async with db.begin():
        locked = await db.get(User, clinic.doctor_ids[0])
        assert locked is not None
        locked.is_active = False
    assert (await app_client.get(f"/api/v1/doctors/{clinic.doctor_ids[0]}")).status_code == 404
    assert (await app_client.get("/api/v1/doctors/9999")).status_code == 404


async def test_admin_adds_edits_and_hides_a_service(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic
) -> None:
    created = await app_client.post(
        "/api/v1/admin/services",
        json={
            "specialty_id": clinic.specialty_id,
            "name": "  Khám   viêm da cơ địa ",
            "scope_description": "Chàm, viêm da cơ địa tái phát.",
            "duration_min": 20,
            "ref_price_vnd": 250_000,
        },
        headers=admin(clinic),
    )
    assert created.status_code == 201
    service = created.json()
    assert service["name"] == "Khám viêm da cơ địa"
    assert service["is_active"] is True and service["appointment_count"] == 0

    duplicate = await app_client.post(
        "/api/v1/admin/services",
        json={**service, "specialty_id": clinic.specialty_id, "name": "khám viêm da cơ địa"},
        headers=admin(clinic),
    )
    assert duplicate.status_code == 422
    assert duplicate.json()["details"]["fields"][0]["loc"] == ["body", "name"]

    edited = await app_client.patch(
        f"/api/v1/admin/services/{service['id']}",
        json={"duration_min": 30, "ref_price_vnd": 280_000},
        headers=admin(clinic),
    )
    assert edited.json()["duration_min"] == 30 and edited.json()["name"] == service["name"]

    await add_appointment(db, clinic, start=time(8, 0))
    hidden = await app_client.patch(
        f"/api/v1/admin/services/{clinic.service_id}",
        json={"is_active": False},
        headers=admin(clinic),
    )
    assert hidden.status_code == 200
    assert hidden.json()["is_active"] is False
    assert hidden.json()["appointment_count"] == 1  # đã có lịch hẹn: chỉ ẩn, không xóa
    public = await app_client.get("/api/v1/services")
    assert clinic.service_id not in [s["id"] for s in public.json()]
    every = await app_client.get("/api/v1/admin/services", headers=admin(clinic))
    assert clinic.service_id in [s["id"] for s in every.json()]


@pytest.mark.parametrize(
    ("payload", "field", "message"),
    [
        ({"duration_min": 7}, "duration_min", "Thời lượng từ 10 đến 120 phút, là bội số của 5."),
        ({"duration_min": 125}, "duration_min", "Thời lượng từ 10 đến 120 phút, là bội số của 5."),
        ({"ref_price_vnd": -1}, "ref_price_vnd", "Giá tham khảo từ 0 đến 100.000.000 ₫."),
        ({"name": "A"}, "name", "Tên cần ít nhất 2 ký tự."),
    ],
)
async def test_service_validation_messages_are_in_vietnamese(
    app_client: AsyncClient,
    clinic: Clinic,
    payload: dict[str, Any],
    field: str,
    message: str,
) -> None:
    response = await app_client.post(
        "/api/v1/admin/services",
        json={
            "specialty_id": clinic.specialty_id,
            "name": "Dịch vụ mới",
            "scope_description": "Mô tả phạm vi khám đủ dài.",
            "duration_min": 20,
            "ref_price_vnd": 100_000,
            **payload,
        },
        headers=admin(clinic),
    )
    assert response.status_code == 422
    [error] = response.json()["details"]["fields"]
    assert error["loc"] == ["body", field]
    assert error["message"] == message


async def test_admin_manages_specialties(app_client: AsyncClient, clinic: Clinic) -> None:
    every = await app_client.get("/api/v1/admin/specialties", headers=admin(clinic))
    assert [(s["name"], s["is_active"]) for s in every.json()] == [
        ("Da liễu", True),
        ("Mắt", False),
    ]

    created = await app_client.post(
        "/api/v1/admin/specialties", json={"name": "Nhi", "description": " "}, headers=admin(clinic)
    )
    assert created.status_code == 201
    assert created.json()["description"] is None
    duplicate = await app_client.post(
        "/api/v1/admin/specialties", json={"name": "da liễu"}, headers=admin(clinic)
    )
    assert duplicate.status_code == 422

    renamed = await app_client.patch(
        f"/api/v1/admin/specialties/{created.json()['id']}",
        json={"name": "Nhi khoa", "is_active": False},
        headers=admin(clinic),
    )
    assert renamed.json()["name"] == "Nhi khoa" and renamed.json()["is_active"] is False
    public = await app_client.get("/api/v1/specialties")
    assert names(public.json()) == ["Da liễu"]
    missing = await app_client.patch(
        "/api/v1/admin/specialties/9999", json={"name": "Không có"}, headers=admin(clinic)
    )
    assert missing.status_code == 404


async def test_catalog_admin_requires_admin_role(app_client: AsyncClient, clinic: Clinic) -> None:
    patient = bearer(clinic.patient_ids[0], UserRole.PATIENT)
    doctor = bearer(clinic.doctor_ids[0], UserRole.DOCTOR)
    for headers in (patient, doctor):
        assert (await app_client.get("/api/v1/admin/services", headers=headers)).status_code == 403
        response = await app_client.post(
            "/api/v1/admin/specialties", json={"name": "Nhi"}, headers=headers
        )
        assert response.status_code == 403
    assert (await app_client.get("/api/v1/admin/specialties")).status_code == 401
