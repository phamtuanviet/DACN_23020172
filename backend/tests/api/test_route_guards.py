"""Duyệt tự động mọi route: thiếu token → 401, sai vai trò → 403 (docs mục 12, NFR-06).

Phân quyền lớp 1 ở router chặn trước khi chạm database, nên test chạy không cần PostgreSQL.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.core.config import Environment, Settings
from app.core.security import CurrentUser, get_current_user
from app.db.enums import UserRole
from app.main import create_app

PATIENT = CurrentUser(id=1, role=UserRole.PATIENT, full_name="Lan")
DOCTOR = CurrentUser(id=2, role=UserRole.DOCTOR, full_name="Minh")
ADMIN_ONLY = "/api/v1/admin"


def _routes(prefix: str) -> list[tuple[str, str]]:
    """Liệt kê route qua OpenAPI (giao diện công khai), thay tham số đường dẫn bằng 1."""
    app = create_app(Settings(_env_file=None, app_env=Environment.DEVELOPMENT))
    return [
        (method.upper(), re.sub(r"\{[^}]+\}", "1", path))
        for path, operations in app.openapi()["paths"].items()
        if path.startswith(prefix)
        for method in operations
    ]


ADMIN_ROUTES = _routes(ADMIN_ONLY)


def test_admin_routes_are_discovered() -> None:
    assert len(ADMIN_ROUTES) >= 13  # danh mục, ca làm, ngày nghỉ của Sprint 2


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
def test_admin_route_without_token_returns_401(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path)
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
@pytest.mark.parametrize("user", [PATIENT, DOCTOR], ids=["patient", "doctor"])
def test_admin_route_rejects_other_roles_with_403(
    client: TestClient, method: str, path: str, user: CurrentUser
) -> None:
    client.app.dependency_overrides[get_current_user] = lambda: user  # type: ignore[attr-defined]
    response = client.request(method, path)
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


@pytest.mark.parametrize("user", [DOCTOR], ids=["doctor"])
def test_only_patients_reach_booking(client: TestClient, user: CurrentUser) -> None:
    client.app.dependency_overrides[get_current_user] = lambda: user  # type: ignore[attr-defined]
    assert client.post("/api/v1/appointments", json={}).status_code == 403


def test_booking_without_token_returns_401(client: TestClient) -> None:
    assert client.post("/api/v1/appointments", json={}).status_code == 401


ADMIN = CurrentUser(id=3, role=UserRole.ADMIN, full_name="Hà")
APPOINTMENT_ROUTES = _routes("/api/v1/appointments")
# Vai trò bị router chặn (lớp 1) ở từng route lịch hẹn (docs mục 4.6, 8.2)
APPOINTMENT_FORBIDDEN = [
    ("POST", "/api/v1/appointments", DOCTOR),
    ("POST", "/api/v1/appointments", ADMIN),
    ("GET", "/api/v1/appointments/me", DOCTOR),
    ("GET", "/api/v1/appointments/me", ADMIN),
    ("PATCH", "/api/v1/appointments/1/reschedule", DOCTOR),
    ("POST", "/api/v1/appointments/1/cancel", DOCTOR),
    ("PATCH", "/api/v1/appointments/1/status", PATIENT),
]


def test_appointment_routes_are_discovered() -> None:
    assert len(APPOINTMENT_ROUTES) == 6  # đặt, của tôi, chi tiết, đổi, hủy, đổi trạng thái


@pytest.mark.parametrize(("method", "path"), APPOINTMENT_ROUTES)
def test_appointment_route_without_token_returns_401(
    client: TestClient, method: str, path: str
) -> None:
    response = client.request(method, path, json={})
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize(("method", "path", "user"), APPOINTMENT_FORBIDDEN)
def test_appointment_route_rejects_wrong_role_with_403(
    client: TestClient, method: str, path: str, user: CurrentUser
) -> None:
    client.app.dependency_overrides[get_current_user] = lambda: user  # type: ignore[attr-defined]
    response = client.request(method, path, json={})
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


AGENT_ROUTES = _routes("/api/v1/agent")


def test_agent_routes_are_discovered() -> None:
    assert len(AGENT_ROUTES) == 5  # trạng thái, chat, tải lại hội thoại, xác nhận, từ chối


@pytest.mark.parametrize(("method", "path"), AGENT_ROUTES)
def test_agent_route_without_token_returns_401(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path, json={})
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


@pytest.mark.parametrize(("method", "path"), AGENT_ROUTES)
@pytest.mark.parametrize("user", [DOCTOR, ADMIN], ids=["doctor", "admin"])
def test_agent_routes_are_for_patients_only(
    client: TestClient, method: str, path: str, user: CurrentUser
) -> None:
    """Chỉ bệnh nhân dùng Agent (FR-AGT-01); quản trị cũng không xác nhận đề xuất hộ."""
    client.app.dependency_overrides[get_current_user] = lambda: user  # type: ignore[attr-defined]
    response = client.request(method, path, json={})
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
