"""Health check cho Caddy, Docker và giám sát uptime (docs mục 8.2)."""

import asyncio

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.core.db import get_engine
from app.core.valkey import get_valkey

router = APIRouter(prefix="/health", tags=["health"])
CHECK_TIMEOUT_S = 2


@router.get("/live")
async def live() -> dict[str, str]:
    """Tiến trình còn chạy."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response) -> dict[str, object]:
    """Sẵn sàng nhận request: kết nối được database và Valkey."""
    checks = {"database": await _check_database(), "valkey": await _check_valkey()}
    healthy = all(checks.values())
    if not healthy:
        response.status_code = 503
    return {"status": "ok" if healthy else "unavailable", "checks": checks}


async def _check_database() -> bool:
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_S), get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _check_valkey() -> bool:
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_S):
            return bool(await get_valkey().ping())
    except Exception:
        return False
