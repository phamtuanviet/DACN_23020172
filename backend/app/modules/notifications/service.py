"""Nghiệp vụ của module notifications: gửi email trong hàng đợi, thử lại, tạo email nhắc.

Theo docs mục 10.5. Mỗi email một transaction ngắn: khóa một dòng đến hạn (`SKIP LOCKED`), gửi,
ghi kết quả. Gửi lỗi không bao giờ ảnh hưởng thao tác đặt lịch, vì email đã nằm trong hàng đợi
từ lúc lịch hẹn commit (FR-NTF-03). Log chỉ ghi id, loại email, số lần thử: không ghi địa chỉ
email, họ tên hay nội dung.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.clock import Clock
from app.core.config import Settings
from app.core.validation import is_plain_email
from app.db.enums import AppointmentStatus, Channel, NotificationStatus, NotificationType
from app.db.models.appointments import Notification
from app.modules.notifications import repository as repo
from app.modules.notifications.content import AppointmentFacts, ClinicInfo, build_email
from app.modules.notifications.mailer import SEND_ERRORS, Mailer, render

log = structlog.get_logger(__name__)

BATCH_SIZE = 20  # mỗi lượt 30 giây gửi tối đa 20 email
RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=15))
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1  # lần đầu + 3 lần thử lại (FR-NTF-03)
BACKLOG_ALERT = timedelta(minutes=10)  # email chờ quá lâu: cảnh báo (docs mục 11.7)
STALE_AFTER = timedelta(hours=24)  # chờ quá lâu thì nội dung đã cũ, không gửi nữa
STALE_REASON = "Chờ quá 24 giờ chưa gửi, nội dung đã cũ."
# Địa chỉ đăng ký chưa xác minh: một tài khoản đặt, hủy liên tục không biến phòng khám thành
# nguồn gửi thư hàng loạt tới hộp thư của người khác. Không áp cho email nhắc (mỗi lịch một lần,
# mỗi bệnh nhân tối đa 3 lịch chờ khám) và email phòng khám đổi, hủy lịch.
RECIPIENT_LIMIT = 5
RECIPIENT_WINDOW = timedelta(hours=1)
REMINDER_JOB_KEY = 1
LOCAL_DOMAIN = ".local"  # RFC 6762: tài khoản demo @demo.local không có hộp thư thật


@dataclass(frozen=True, slots=True)
class Skip:
    """Email không gửi: đánh FAILED với 0 lần thử, `reason` lưu ở last_error."""

    code: str  # ghi vào log bằng khóa `code`
    reason: str
    alert: bool = False  # thư lẽ ra tới bệnh nhân: log warning để cảnh báo (docs mục 11.7)


class NotificationSender:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        clock: Clock,
        settings: Settings,
        mailer: Mailer,
    ) -> None:
        self._sessions = sessions
        self._clock = clock
        self._settings = settings
        self._mailer = mailer

    async def send_due(self, limit: int = BATCH_SIZE) -> int:
        """Gửi tối đa `limit` email đến hạn; trả số email gửi thành công."""
        await self._drop_stale()
        sent = 0
        for _ in range(limit):
            outcome = await self._send_one()
            if outcome is None:
                break
            sent += int(outcome)
        await self._check_backlog()
        return sent

    async def _send_one(self) -> bool | None:
        """None: hết email đến hạn. True: đã gửi. False: lỗi (hẹn thử lại) hoặc bỏ qua."""
        now = self._clock.now()
        async with self._sessions() as session, session.begin():
            notification = await repo.claim_due(session, now)
            if notification is None:
                return None
            row = await repo.email_row(session, notification)
            skip = await self._skip(session, notification, row, now)
            if skip is not None or row is None:
                skip = skip or Skip("missing", "Không tìm thấy lịch hẹn.")
                notification.status = NotificationStatus.FAILED
                notification.last_error = skip.reason
                (log.warning if skip.alert else log.info)(
                    "notification.dropped" if skip.alert else "notification.skipped",
                    notification_id=notification.id,
                    type=notification.type.value,
                    code=skip.code,  # `reason` bị bộ lọc log che
                )
                return False
            try:
                content = build_email(notification.type, self._facts(row), self._clinic(), now)
                await self._mailer.send(render(content, notification.recipient_email))
            except SEND_ERRORS as exc:
                self._failed(notification, now, exc)
                return False
            except Exception as exc:  # lỗi lập trình: vẫn đếm lần thử để không gửi lặp vô hạn
                self._failed(notification, now, exc, unexpected=True)
                return False
            notification.status = NotificationStatus.SENT
            notification.attempts += 1
            notification.sent_at = now
            notification.last_error = None
        log.info(
            "notification.sent",
            notification_id=notification.id,
            type=notification.type.value,
            attempts=notification.attempts,
        )
        return True

    async def _skip(
        self,
        session: AsyncSession,
        notification: Notification,
        row: repo.EmailRow | None,
        now: datetime,
    ) -> Skip | None:
        """Email không nên gửi, phân biệt với gửi lỗi thật."""
        if row is None:
            return Skip("missing", "Không tìm thấy lịch hẹn.")
        if row.patient_anonymized:
            return Skip("anonymized", "Tài khoản bệnh nhân đã xóa.")
        if not is_plain_email(notification.recipient_email):  # đúng chuỗi sẽ gửi
            # Địa chỉ lọt vào trước khi siết kiểm tra lúc đăng ký: thư viện SMTP có thể rút ra một
            # người nhận khác, ví dụ "n3<victim@y.com>" thành victim@y.com.
            return Skip("bad_recipient", "Địa chỉ email không hợp lệ.", alert=True)
        if not self._settings.is_development and notification.recipient_email.lower().endswith(
            LOCAL_DOMAIN
        ):
            return Skip(
                "local_domain", "Bỏ qua địa chỉ thuộc tên miền .local (chỉ gửi ở development)."
            )
        if notification.type is NotificationType.REMINDER:
            if (
                row.appointment.status is not AppointmentStatus.BOOKED
                or row.appointment.start_at <= now
            ):
                return Skip("not_booked", "Lịch không còn chờ khám nên không nhắc nữa.")
            return None
        if row.changed_by is Channel.ADMIN:
            return None
        since = now - RECIPIENT_WINDOW
        if await repo.sent_count(session, notification.recipient_email, since) >= RECIPIENT_LIMIT:
            reason = f"Đã gửi {RECIPIENT_LIMIT} email trong 1 giờ tới địa chỉ này."
            return Skip("recipient_limit", reason, alert=True)
        return None

    async def _drop_stale(self) -> None:
        """Email chờ quá 24 giờ đã cũ: bỏ hết bằng một câu lệnh, để sau một lần worker ngừng lâu
        thư mới không phải xếp sau cả hàng tồn (docs mục 10.5)."""
        before = self._clock.now() - STALE_AFTER
        async with self._sessions() as session, session.begin():
            dropped = await repo.drop_stale(session, before, STALE_REASON)
        if dropped:
            log.warning("notification.dropped", code="stale", count=dropped)

    def _failed(
        self, notification: Notification, now: datetime, exc: Exception, *, unexpected: bool = False
    ) -> None:
        """Hẹn gửi lại sau 1, 5, 15 phút; quá 4 lần thì FAILED và ghi log lỗi
        `notification.failed` để cảnh báo (docs mục 11.7)."""
        notification.attempts += 1
        notification.last_error = _error_summary(exc)
        fields = {
            "notification_id": notification.id,
            "type": notification.type.value,
            "attempts": notification.attempts,
            "error": type(exc).__name__,
        }
        if notification.attempts >= MAX_ATTEMPTS:
            notification.status = NotificationStatus.FAILED
            log.error("notification.failed", **fields)
            return
        notification.scheduled_at = now + RETRY_DELAYS[notification.attempts - 1]
        if unexpected:
            log.error("notification.crashed", **fields)
        else:
            log.warning("notification.retry", **fields)

    async def _check_backlog(self) -> None:
        async with self._sessions() as session:
            oldest = await repo.oldest_pending(session)
        if oldest is not None and self._clock.now() - oldest > BACKLOG_ALERT:
            age = int((self._clock.now() - oldest).total_seconds())
            log.warning("notification.backlog", oldest_pending_s=age)

    def _facts(self, row: repo.EmailRow) -> AppointmentFacts:
        appointment = row.appointment
        return AppointmentFacts(
            appointment_id=appointment.id,
            code=appointment.code,
            service_name=row.service_name,
            doctor_name=row.doctor_name,
            start_at=appointment.start_at,
            end_at=appointment.end_at,
            by_clinic=row.changed_by is Channel.ADMIN,
        )

    def _clinic(self) -> ClinicInfo:
        settings = self._settings
        return ClinicInfo(
            name=settings.clinic_name,
            address=settings.clinic_address,
            phone=settings.clinic_phone,
            base_url=settings.public_base_url,
            change_deadline_hours=settings.change_deadline_hours,
        )


def _error_summary(exc: Exception) -> str:
    """Tên lớp lỗi kèm mã SMTP nếu có. Không lưu thông điệp lỗi: lỗi SMTP hay nhắc lại địa chỉ
    người nhận, mà cột `last_error` còn nguyên cả khi tài khoản đã ẩn danh."""
    code = getattr(exc, "code", None)
    return f"{type(exc).__name__} {code}" if isinstance(code, int) else type(exc).__name__


async def enqueue_reminders(
    sessions: async_sessionmaker[AsyncSession], clock: Clock, settings: Settings
) -> int:
    """Thêm email nhắc cho lịch Đã đặt trong 24 giờ tới (FR-NTF-02). Lịch bị hủy hoặc dời trước
    giờ nhắc tự nhiên không còn khớp điều kiện quét, nên không cần sửa hàng đợi (docs mục 10.5)."""
    ahead = timedelta(hours=settings.reminder_hours_before)
    async with sessions() as session, session.begin():
        if not await repo.try_job_lock(session, REMINDER_JOB_KEY):
            return 0
        count = await repo.insert_reminders(session, clock.now(), ahead)
    if count:
        log.info("notification.reminders_enqueued", count=count)
    return count
