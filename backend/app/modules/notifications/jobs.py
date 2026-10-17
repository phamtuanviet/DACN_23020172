"""Job nền của module notifications (chạy trong worker)."""

import structlog

log = structlog.get_logger(__name__)


async def send_notifications() -> None:
    """Gửi email PENDING đến hạn: mỗi email một transaction, FOR UPDATE SKIP LOCKED.

    Xem docs mục 10.5. Ngoài development, bỏ qua địa chỉ thuộc tên miền .local (tài khoản demo
    @demo.local, RFC 6762): gửi qua SES sẽ bị trả về và làm giảm uy tín tên miền gửi.
    """
    log.debug("job.todo", job="send_notifications")


async def enqueue_reminders() -> None:
    """Thêm email nhắc 24 giờ trước giờ khám, giữ advisory lock (FR-NTF-02)."""
    log.debug("job.todo", job="enqueue_reminders")
