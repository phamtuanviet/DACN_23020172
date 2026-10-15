"""Job nền của module agent (chạy trong worker)."""

import structlog

log = structlog.get_logger(__name__)


async def expire_proposals() -> None:
    """Chuyển đề xuất PENDING quá hạn sang EXPIRED (docs mục 10.5)."""
    log.debug("job.todo", job="expire_proposals")


async def purge_old_conversations() -> None:
    """Xóa hội thoại quá CHAT_RETENTION_DAYS ngày (docs mục 7.7)."""
    log.debug("job.todo", job="purge_old_conversations")
