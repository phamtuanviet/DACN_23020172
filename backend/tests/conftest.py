"""Fixture dùng chung. Test không đọc file .env của máy lập trình (_env_file=None)."""

from collections.abc import Iterator
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.core.clock import FixedClock, get_clock
from app.core.config import Environment, Settings
from app.main import create_app

# Mốc thời gian chuẩn của mọi test: Thứ Bảy 10/10/2026 09:00 giờ Việt Nam.
TEST_NOW = datetime(2026, 10, 10, 9, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, app_env=Environment.DEVELOPMENT)


@pytest.fixture
def fixed_clock() -> FixedClock:
    return FixedClock(TEST_NOW)


@pytest.fixture
def client(settings: Settings, fixed_clock: FixedClock) -> Iterator[TestClient]:
    app = create_app(settings)
    app.dependency_overrides[get_clock] = lambda: fixed_clock
    with TestClient(app) as test_client:
        yield test_client
