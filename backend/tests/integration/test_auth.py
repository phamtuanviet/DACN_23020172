"""Luồng tài khoản trên PostgreSQL thật: FR-AUTH-01..06, NFR-05..07, docs mục 4.6."""

from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import UserRole
from app.db.models.users import RefreshToken, User
from app.modules.auth.service import create_user
from tests.conftest import TEST_NOW
from tests.integration.conftest import MutableClock

pytestmark = pytest.mark.integration

PASSWORD = "matkhau123"
NEW_PASSWORD = "matkhau456"


async def register(client: AsyncClient, **overrides: Any) -> Response:
    payload: dict[str, Any] = {
        "full_name": "Nguyễn Thị Lan",
        "email": "lan@example.com",
        "phone": "0912345678",
        "date_of_birth": "1994-03-12",
        "gender": "FEMALE",
        "password": PASSWORD,
        "privacy_consent": True,
    }
    payload.update(overrides)
    return await client.post("/api/v1/auth/register", json=payload)


async def login(client: AsyncClient, email: str, password: str) -> Response:
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def refresh(client: AsyncClient, token: str) -> Response:
    """Gửi đúng một refresh token, không lẫn với cookie đang có trong client."""
    client.cookies.clear()
    return await client.post("/api/v1/auth/refresh", headers={"Cookie": f"refresh_token={token}"})


def bearer(response: Response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def refresh_cookie(response: Response) -> str:
    token = response.cookies.get("refresh_token")
    assert token
    return token


async def test_register_creates_patient_and_logs_in(
    app_client: AsyncClient, db: AsyncSession
) -> None:
    response = await register(app_client)

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["role"] == "PATIENT"
    assert body["user"]["email"] == "lan@example.com"
    set_cookie = response.headers["set-cookie"].lower()
    assert "httponly" in set_cookie
    assert "path=/api/v1/auth" in set_cookie
    assert "samesite=strict" in set_cookie

    me = await app_client.get("/api/v1/me", headers=bearer(response))
    assert me.status_code == 200
    assert me.json()["date_of_birth"] == "1994-03-12"
    assert me.json()["gender"] == "FEMALE"

    user = (await db.execute(select(User))).scalar_one()
    assert user.privacy_consent_at == TEST_NOW
    assert user.password_hash.startswith("$argon2id$")
    stored = (await db.execute(select(RefreshToken))).scalar_one()
    assert stored.token_hash != refresh_cookie(response)  # chỉ lưu băm


async def test_register_rejects_duplicate_email_ignoring_case(app_client: AsyncClient) -> None:
    await register(app_client)
    response = await register(app_client, email="LAN@Example.com")
    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_TAKEN"


async def test_register_rejects_birth_date_in_the_future(app_client: AsyncClient) -> None:
    response = await register(app_client, date_of_birth="2026-10-11")
    assert response.status_code == 422
    assert response.json()["details"]["fields"][0]["loc"] == ["body", "date_of_birth"]


async def test_wrong_password_and_unknown_email_return_the_same_error(
    app_client: AsyncClient,
) -> None:
    await register(app_client)
    wrong_password = await login(app_client, "lan@example.com", "saimatkhau1")
    unknown_email = await login(app_client, "khongco@example.com", PASSWORD)
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["message"] == "Email hoặc mật khẩu không đúng."


async def test_five_wrong_passwords_lock_the_account_for_15_minutes(
    app_client: AsyncClient, clock: MutableClock
) -> None:
    await register(app_client)
    for _ in range(4):
        assert (await login(app_client, "lan@example.com", "saimatkhau1")).status_code == 401

    fifth = await login(app_client, "lan@example.com", "saimatkhau1")
    assert fifth.status_code == 429
    assert fifth.json()["code"] == "ACCOUNT_LOCKED"
    locked_until = TEST_NOW + timedelta(minutes=15)
    assert fifth.json()["details"]["locked_until"] == locked_until.isoformat()

    still_locked = await login(app_client, "lan@example.com", PASSWORD)
    assert still_locked.status_code == 429

    clock.advance(minutes=15)
    assert (await login(app_client, "Lan@Example.com", PASSWORD)).status_code == 200


async def test_refresh_rotates_token_and_revokes_family_on_reuse(
    app_client: AsyncClient, clock: MutableClock
) -> None:
    first = refresh_cookie(await register(app_client))

    rotated = await refresh(app_client, first)
    assert rotated.status_code == 200
    second = refresh_cookie(rotated)
    assert second != first

    # Tab thứ hai gửi lại token vừa xoay trong vài giây: vẫn được cấp phiên, không coi là đánh cắp.
    clock.advance(seconds=10)
    sibling = await refresh(app_client, first)
    assert sibling.status_code == 200
    third = refresh_cookie(sibling)

    # Dùng lại token cũ sau khoảng ân hạn: thu hồi cả family, mọi token cùng family hết dùng được.
    clock.advance(minutes=5)
    assert (await refresh(app_client, first)).status_code == 401
    assert (await refresh(app_client, second)).status_code == 401
    assert (await refresh(app_client, third)).status_code == 401


async def test_refresh_token_expires_after_7_days(
    app_client: AsyncClient, clock: MutableClock
) -> None:
    token = refresh_cookie(await register(app_client))
    clock.advance(days=7)
    assert (await refresh(app_client, token)).status_code == 401


async def test_logout_revokes_refresh_token_and_clears_cookie(app_client: AsyncClient) -> None:
    token = refresh_cookie(await register(app_client))
    app_client.cookies.clear()
    response = await app_client.post(
        "/api/v1/auth/logout", headers={"Cookie": f"refresh_token={token}"}
    )
    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert (await refresh(app_client, token)).status_code == 401


async def test_change_password_revokes_every_other_session(app_client: AsyncClient) -> None:
    registered = await register(app_client)
    first = refresh_cookie(registered)
    second = refresh_cookie(await login(app_client, "lan@example.com", PASSWORD))

    changed = await app_client.post(
        "/api/v1/me/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=bearer(registered),
    )
    assert changed.status_code == 200
    current = refresh_cookie(changed)

    assert (await refresh(app_client, first)).status_code == 401
    assert (await refresh(app_client, second)).status_code == 401
    assert (await refresh(app_client, current)).status_code == 200
    assert (await login(app_client, "lan@example.com", PASSWORD)).status_code == 401
    assert (await login(app_client, "lan@example.com", NEW_PASSWORD)).status_code == 200


async def test_change_password_rejects_wrong_current_password(app_client: AsyncClient) -> None:
    registered = await register(app_client)
    response = await app_client.post(
        "/api/v1/me/password",
        json={"current_password": "saimatkhau1", "new_password": NEW_PASSWORD},
        headers=bearer(registered),
    )
    assert response.status_code == 422
    assert response.json()["details"]["fields"][0]["loc"] == ["body", "current_password"]


async def test_update_me_changes_profile_but_not_email(app_client: AsyncClient) -> None:
    registered = await register(app_client)
    response = await app_client.patch(
        "/api/v1/me",
        json={"full_name": "Nguyễn Thị Lan Anh", "phone": "+84987654321", "gender": "OTHER"},
        headers=bearer(registered),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Nguyễn Thị Lan Anh"
    assert body["phone"] == "0987654321"
    assert body["gender"] == "OTHER"
    assert body["email"] == "lan@example.com"


async def test_doctor_profile_has_no_birth_date(app_client: AsyncClient, db: AsyncSession) -> None:
    async with db.begin():
        await create_user(
            db,
            email="bs.minh@example.com",
            password=PASSWORD,
            role=UserRole.DOCTOR,
            full_name="ThS. BS. Trần Minh",
        )
    logged_in = await login(app_client, "bs.minh@example.com", PASSWORD)
    assert logged_in.json()["user"]["role"] == "DOCTOR"

    response = await app_client.patch(
        "/api/v1/me", json={"date_of_birth": "1985-01-01"}, headers=bearer(logged_in)
    )
    assert response.status_code == 422


async def test_deactivated_account_loses_access_immediately(
    app_client: AsyncClient, db: AsyncSession
) -> None:
    registered = await register(app_client)
    async with db.begin():
        user = (await db.execute(select(User))).scalar_one()
        user.is_active = False

    assert (await app_client.get("/api/v1/me", headers=bearer(registered))).status_code == 401
    assert (await login(app_client, "lan@example.com", PASSWORD)).status_code == 401
    assert (await refresh(app_client, refresh_cookie(registered))).status_code == 401


async def test_login_is_limited_to_10_attempts_per_minute_per_ip(app_client: AsyncClient) -> None:
    for _ in range(10):
        assert (await login(app_client, "khongco@example.com", PASSWORD)).status_code == 401
    eleventh = await login(app_client, "khongco@example.com", PASSWORD)
    assert eleventh.status_code == 429
    assert eleventh.json()["code"] == "RATE_LIMITED"
