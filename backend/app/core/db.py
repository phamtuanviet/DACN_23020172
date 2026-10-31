"""Kết nối database: engine async và một session cho mỗi request (docs mục 4.5, 11.2)."""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        # Lỗi SQL không chép giá trị tham số (lý do khám, email…) vào thông báo lỗi, log, Sentry.
        hide_parameters=True,
        connect_args={"options": f"-c timezone={settings.clinic_tz}"},
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependency của FastAPI. Service tự mở transaction bằng `async with session.begin()`."""
    async with get_sessionmaker()() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


_OUTER_TRANSACTION = "outer_transaction"


@asynccontextmanager
async def outer_transaction(session: AsyncSession) -> AsyncGenerator[None]:
    """Một transaction bao nhiều thao tác service, cùng commit hoặc cùng rollback.

    Dùng khi xác nhận đề xuất của Agent: khóa đề xuất, đặt lịch, đánh dấu đề xuất đã dùng phải
    nằm trong một transaction để bấm đúp không đặt hai lần (docs mục 6.4).
    """
    async with session.begin():
        session.info[_OUTER_TRANSACTION] = True
        try:
            yield
        finally:
            session.info.pop(_OUTER_TRANSACTION, None)


@asynccontextmanager
async def transaction(session: AsyncSession) -> AsyncGenerator[None]:
    """Ranh giới transaction của một thao tác service (docs mục 4.5).

    Bình thường mở transaction mới. Bên trong `outer_transaction` thì chạy trong SAVEPOINT: lỗi
    nghiệp vụ chỉ rollback phần của thao tác này, người gọi vẫn ghi được kết quả thất bại. Chỉ
    nhập vào transaction mở bằng `outer_transaction`, không nhập vào transaction tự mở ngầm
    (autobegin), để thao tác ghi không âm thầm mất khi session đóng mà chưa commit.
    """
    if session.info.get(_OUTER_TRANSACTION):
        async with session.begin_nested():
            yield
    else:
        async with session.begin():
            yield
