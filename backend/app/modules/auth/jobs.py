"""Job nền của module auth (chạy trong worker)."""

import structlog

log = structlog.get_logger(__name__)


async def purge_expired_tokens() -> None:
    """Xóa refresh token hết hạn quá 30 ngày (docs mục 7.7)."""
    log.debug("job.todo", job="purge_expired_tokens")
