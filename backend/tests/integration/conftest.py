"""Hạ tầng test tích hợp (cần PostgreSQL và Valkey: docker compose up -d db valkey).

Test chạy trên database riêng `<tên database>_test` cùng máy chủ với DATABASE_URL, migrate một lần
bằng Alembic rồi dọn sạch trước mỗi test; dữ liệu dev không bị đụng tới.
"""

import os
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core.clock import get_clock
from app.core.config import Environment, Settings, get_settings
from app.core.db import get_engine, get_sessionmaker
from app.core.ratelimit import limiter
from app.db import models  # noqa: F401  — đăng ký mọi bảng vào metadata
from app.db.base import Base
from app.main import create_app
from tests.conftest import TEST_NOW

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_URL = "postgresql+psycopg://dacn:dacn@localhost:5432/dacn"


class MutableClock:
    """Đồng hồ cố định nhưng tua được, để test hết hạn khóa, hết hạn token."""

    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at

    def advance(self, **delta: float) -> None:
        self.at += timedelta(**delta)


def _clear_caches() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@pytest.fixture(scope="session")
def test_database_url() -> Iterator[str]:
    base = make_url(os.environ.get("DATABASE_URL", DEFAULT_URL))
    test_url = base.set(database=f"{base.database}_test")
    if not str(test_url.database).endswith("_test"):
        raise RuntimeError("Database test phải có hậu tố _test")
    # Tạo lại từ đầu mỗi lần chạy: migration luôn được kiểm trên database trống.
    server = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{test_url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{test_url.database}"'))
    server.dispose()

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
    _clear_caches()
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")
    yield os.environ["DATABASE_URL"]

    if previous is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous
    _clear_caches()


@pytest.fixture
def clock() -> MutableClock:
    return MutableClock(TEST_NOW)


@pytest.fixture
async def app_client(test_database_url: str, clock: MutableClock) -> AsyncIterator[AsyncClient]:
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    async with get_engine().begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    limiter.reset()

    app = create_app(Settings(_env_file=None, app_env=Environment.DEVELOPMENT))
    app.dependency_overrides[get_clock] = lambda: clock
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client
    await get_engine().dispose()


@pytest.fixture
async def db(app_client: AsyncClient) -> AsyncIterator[AsyncSession]:
    """Session riêng để chuẩn bị hoặc kiểm tra dữ liệu ngoài API."""
    async with get_sessionmaker()() as session:
        yield session
