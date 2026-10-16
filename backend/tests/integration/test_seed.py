"""Dữ liệu mẫu (docs mục 7.5): đúng số lượng, chỉ nạp vào database trống.

Tài khoản demo đăng nhập được, bác sĩ bị khóa thì không.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed import DEMO_PASSWORD, seed_database
from tests.integration.conftest import MutableClock

pytestmark = pytest.mark.integration


async def test_seed_fills_an_empty_database_once(
    db: AsyncSession, clock: MutableClock, app_client: AsyncClient
) -> None:
    counts = await seed_database(db, clock)
    assert counts == {
        "chuyên khoa": 6,
        "dịch vụ": 20,
        "bác sĩ": 20,
        "ca làm": 200,
        "ngày nghỉ": 8,
        "bệnh nhân": 50,
        "quản trị": 2,
    }
    with pytest.raises(RuntimeError):
        await seed_database(db, clock)

    for email, role in [
        ("lan@demo.local", "PATIENT"),
        ("minh.tran@demo.local", "DOCTOR"),
        ("admin@demo.local", "ADMIN"),
    ]:
        response = await app_client.post(
            "/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD}
        )
        assert response.status_code == 200
        assert response.json()["user"]["role"] == role

    locked_doctor = await app_client.post(
        "/api/v1/auth/login", json={"email": "linh.doan@demo.local", "password": DEMO_PASSWORD}
    )
    assert locked_doctor.status_code == 401
