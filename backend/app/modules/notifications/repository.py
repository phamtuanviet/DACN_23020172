"""Truy vấn database của module notifications (SQLAlchemy). Không ra quyết định nghiệp vụ.

Module chỉ ghi bảng notifications; lịch hẹn, người dùng, dịch vụ chỉ đọc để dựng nội dung email.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, literal, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.enums import (
    AppointmentStatus,
    Channel,
    HistoryAction,
    NotificationStatus,
    NotificationType,
)
from app.db.models.appointments import Appointment, AppointmentHistory, Notification
from app.db.models.catalog import Service
from app.db.models.users import User

# Khóa advisory của job quét (agent dùng 4217): nhiều replica worker thì mỗi lượt chỉ một chạy.
_JOB_LOCK = 4_218


@dataclass(frozen=True, slots=True)
class EmailRow:
    appointment: Appointment
    patient_anonymized: bool
    service_name: str
    doctor_name: str
    changed_by: Channel | None  # kênh của lần đổi, hủy gần nhất


async def try_job_lock(session: AsyncSession, key: int) -> bool:
    """Khóa theo transaction; replica khác đang giữ thì bỏ lượt này (docs mục 10.5)."""
    result = await session.execute(
        text("SELECT pg_try_advisory_xact_lock(:ns, :key)"), {"ns": _JOB_LOCK, "key": key}
    )
    return bool(result.scalar_one())


async def claim_due(session: AsyncSession, now: datetime) -> Notification | None:
    """Một email PENDING đến hạn, khóa `FOR UPDATE SKIP LOCKED`: các replica chia nhau hàng đợi;
    dùng chỉ mục một phần `ix_notifications_pending`."""
    stmt = (
        select(Notification)
        .where(Notification.status == NotificationStatus.PENDING, Notification.scheduled_at <= now)
        .order_by(Notification.scheduled_at, Notification.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


_CHANGE_ACTIONS = {
    NotificationType.RESCHEDULED: HistoryAction.RESCHEDULE,
    NotificationType.CANCELLED: HistoryAction.CANCEL,
}


async def email_row(session: AsyncSession, notification: Notification) -> EmailRow | None:
    doctor = aliased(User, name="doctor_user")
    stmt = (
        select(
            Appointment,
            User.anonymized_at.is_not(None),
            Service.name,
            doctor.full_name,
        )
        .join(User, User.id == Appointment.patient_id)
        .join(Service, Service.id == Appointment.service_id)
        .join(doctor, doctor.id == Appointment.doctor_id)
        .where(Appointment.id == notification.appointment_id)
    )
    row = (await session.execute(stmt)).one_or_none()
    if row is None:
        return None
    changed_by: Channel | None = None
    action = _CHANGE_ACTIONS.get(notification.type)
    if action is not None:
        channel_stmt = (
            select(AppointmentHistory.channel)
            .where(
                AppointmentHistory.appointment_id == notification.appointment_id,
                AppointmentHistory.action == action,
            )
            .order_by(AppointmentHistory.created_at.desc(), AppointmentHistory.id.desc())
            .limit(1)
        )
        changed_by = (await session.execute(channel_stmt)).scalar_one_or_none()
    return EmailRow(row[0], bool(row[1]), row[2], row[3], changed_by)


async def insert_reminders(session: AsyncSession, now: datetime, ahead: timedelta) -> int:
    """Email nhắc cho lịch Đã đặt bắt đầu trong `ahead` tới và được tạo sớm hơn `ahead` trước
    giờ khám (FR-NTF-02). Unique index một-nhắc-mỗi-lịch + ON CONFLICT DO NOTHING nên chạy lại bao
    nhiêu lần cũng không tạo trùng."""
    rows = (
        select(
            Appointment.id,
            literal(NotificationType.REMINDER, Notification.__table__.c.type.type),
            User.email,
            literal(NotificationStatus.PENDING, Notification.__table__.c.status.type),
            literal(0),
            literal(now),
        )
        .join(User, User.id == Appointment.patient_id)
        .where(
            Appointment.status == AppointmentStatus.BOOKED,
            Appointment.start_at > now,
            Appointment.start_at <= now + ahead,
            Appointment.created_at <= Appointment.start_at - ahead,
            User.is_active.is_(True),
            User.anonymized_at.is_(None),
        )
        # Khóa ngoại lấy khóa trên lịch hẹn theo thứ tự chèn: tăng dần theo id như
        # `lock_appointments` của quản trị, để hai bên không khóa chéo nhau.
        .order_by(Appointment.id)
    )
    stmt = (
        insert(Notification)
        .from_select(
            ["appointment_id", "type", "recipient_email", "status", "attempts", "scheduled_at"],
            rows,
        )
        .on_conflict_do_nothing(
            index_elements=["appointment_id", "type"],
            index_where=Notification.type == NotificationType.REMINDER,
        )
        .returning(Notification.id)
    )
    return len((await session.execute(stmt)).all())


async def drop_stale(session: AsyncSession, before: datetime, reason: str) -> int:
    """Đánh FAILED mọi email PENDING đến hạn từ trước `before`; trả số email bị bỏ. Dòng đang bị
    worker khác giữ thì bỏ qua (`SKIP LOCKED`), để một worker treo không chặn mọi replica; lượt
    sau sẽ dọn tiếp."""
    stale = (
        select(Notification.id)
        .where(
            Notification.status == NotificationStatus.PENDING, Notification.scheduled_at < before
        )
        .with_for_update(skip_locked=True)
    )
    stmt = (
        update(Notification)
        .where(Notification.id.in_(stale.scalar_subquery()))
        .values(status=NotificationStatus.FAILED, last_error=reason)
        .returning(Notification.id)
    )
    return len((await session.execute(stmt)).all())


async def sent_count(session: AsyncSession, recipient: str, since: datetime) -> int:
    """Số email đã gửi tới một địa chỉ từ `since`, cho giới hạn theo người nhận."""
    stmt = select(func.count()).where(
        Notification.recipient_email == recipient,
        Notification.status == NotificationStatus.SENT,
        Notification.sent_at >= since,
    )
    return int((await session.execute(stmt)).scalar_one())


async def oldest_pending(session: AsyncSession) -> datetime | None:
    """Email chờ gửi lâu nhất, cho log theo dõi (docs mục 11.7)."""
    stmt = select(func.min(Notification.scheduled_at)).where(
        Notification.status == NotificationStatus.PENDING
    )
    return (await session.execute(stmt)).scalar_one_or_none()
