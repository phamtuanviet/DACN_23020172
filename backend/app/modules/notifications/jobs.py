"""Job nền của module notifications (chạy trong worker, docs mục 10.5)."""

from app.core.clock import get_clock
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.modules.notifications.mailer import SmtpMailer
from app.modules.notifications.service import NotificationSender
from app.modules.notifications.service import enqueue_reminders as enqueue


async def send_notifications() -> None:
    """Gửi email PENDING đến hạn: mỗi email một transaction, FOR UPDATE SKIP LOCKED.

    Ngoài development, bỏ qua địa chỉ thuộc tên miền .local (tài khoản demo @demo.local, RFC 6762):
    gửi qua SES sẽ bị trả về và làm giảm uy tín tên miền gửi.
    """
    settings = get_settings()
    sender = NotificationSender(get_sessionmaker(), get_clock(), settings, SmtpMailer(settings))
    await sender.send_due()


async def enqueue_reminders() -> None:
    """Thêm email nhắc 24 giờ trước giờ khám, giữ advisory lock (FR-NTF-02)."""
    await enqueue(get_sessionmaker(), get_clock(), get_settings())
