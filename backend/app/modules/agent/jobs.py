"""Job nền của module agent (chạy trong worker). Cả hai job idempotent, chạy lặp lại vẫn an toàn."""

from datetime import timedelta

import structlog

from app.core.clock import get_clock
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.modules.agent import repository as repo

log = structlog.get_logger(__name__)


async def expire_proposals() -> None:
    """Chuyển đề xuất PENDING quá hạn sang EXPIRED (docs mục 10.5).

    Chỉ để dữ liệu gọn: endpoint xác nhận tự kiểm tra hạn, không phụ thuộc job này (BR-06).
    """
    async with get_sessionmaker()() as session, session.begin():
        count = await repo.expire_due(session, get_clock().now())
    if count:
        log.info("agent.proposals_expired", count=count)


async def purge_old_conversations() -> None:
    """Xóa hội thoại không hoạt động quá CHAT_RETENTION_DAYS ngày (docs mục 7.7)."""
    days = get_settings().chat_retention_days
    async with get_sessionmaker()() as session, session.begin():
        count = await repo.purge_conversations(session, get_clock().now() - timedelta(days=days))
    if count:
        log.info("agent.conversations_purged", count=count, retention_days=days)
