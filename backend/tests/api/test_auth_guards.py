"""Phân quyền lớp 1 ở router, không cần database (NFR-06)."""

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_error_handlers
from app.core.security import CurrentUser, get_current_user, require_roles
from app.db.enums import UserRole


def test_me_without_token_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_me_with_garbage_token_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/me", headers={"Authorization": "Bearer khong-phai-jwt"})
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_refresh_without_cookie_returns_401(client: TestClient) -> None:
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


def test_require_roles_blocks_other_roles_with_403() -> None:
    app = FastAPI()
    register_error_handlers(app)
    router = APIRouter(dependencies=[Depends(require_roles(UserRole.ADMIN))])

    @router.get("/admin-only")
    async def admin_only() -> dict[str, str]:
        return {"ok": "yes"}

    app.include_router(router)
    as_patient = CurrentUser(id=1, role=UserRole.PATIENT, full_name="Lan")
    as_admin = CurrentUser(id=2, role=UserRole.ADMIN, full_name="Hà")

    with TestClient(app) as test_client:
        app.dependency_overrides[get_current_user] = lambda: as_patient
        denied = test_client.get("/admin-only")
        app.dependency_overrides[get_current_user] = lambda: as_admin
        allowed = test_client.get("/admin-only")

    assert denied.status_code == 403
    assert denied.json()["code"] == "FORBIDDEN"
    assert allowed.status_code == 200
