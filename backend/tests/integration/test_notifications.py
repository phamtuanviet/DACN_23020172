"""Email qua hàng đợi và worker (UC17, FR-NTF-01..03, AC-16, docs mục 10.5) trên PostgreSQL thật.

Không gửi email thật: `FakeMailer` thay cho SMTP, còn hàng đợi, khóa dòng, thử lại chạy thật.
"""

import asyncio
from datetime import date, time, timedelta

import aiosmtplib
import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Environment, Settings
from app.core.db import get_sessionmaker
from app.core.timeutil import local_datetime
from app.db.enums import AppointmentStatus, NotificationStatus, NotificationType, UserRole
from app.db.models.appointments import Appointment, Notification
from app.db.models.users import User
from app.modules.notifications.mailer import OutgoingEmail
from app.modules.notifications.service import NotificationSender, enqueue_reminders
from tests.integration.conftest import MutableClock
from tests.integration.factories import (
    APP_SETTINGS,
    MONDAY,
    Clinic,
    add_appointment,
    at,
    bearer,
    build_clinic,
)

pytestmark = pytest.mark.integration

SUNDAY = date(2026, 10, 11)


class FakeMailer:
    """Ghi lại email thay vì gửi; `failures` lần gửi đầu tiên ném lỗi SMTP."""

    def __init__(self, failures: int = 0) -> None:
        self.sent: list[OutgoingEmail] = []
        self.failures = failures

    async def send(self, email: OutgoingEmail) -> None:
        if self.failures:
            self.failures -= 1
            raise aiosmtplib.SMTPServerDisconnected("Máy chủ SMTP đóng kết nối")
        self.sent.append(email)


@pytest.fixture
async def clinic(db: AsyncSession) -> Clinic:
    return await build_clinic(db)


def sender(
    clock: MutableClock, mailer: FakeMailer, settings: Settings = APP_SETTINGS
) -> NotificationSender:
    return NotificationSender(get_sessionmaker(), clock, settings, mailer)


async def notifications(db: AsyncSession) -> list[Notification]:
    stmt = select(Notification).order_by(Notification.id).execution_options(populate_existing=True)
    rows = list((await db.execute(stmt)).scalars())
    await db.commit()
    return rows


async def book(client: AsyncClient, clinic: Clinic, hour: int = 9, **fields: object) -> int:
    response = await client.post(
        "/api/v1/appointments",
        json={
            "service_id": clinic.service_id,
            "doctor_id": clinic.doctor_ids[0],
            "start_at": at(MONDAY, hour),
            **fields,
        },
        headers=bearer(clinic.patient_ids[0], UserRole.PATIENT),
    )
    assert response.status_code == 201
    return int(response.json()["id"])


async def test_ac16_booking_reschedule_and_cancel_each_send_an_email(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    appointment_id = await book(app_client, clinic, reason="Nổi mẩn đỏ ở tay")
    mailer = FakeMailer()

    assert await sender(clock, mailer).send_due() == 1

    email = mailer.sent[0]
    assert email.to == clinic.emails[clinic.patient_ids[0]]
    assert email.subject.startswith("Đã đặt lịch khám Thứ Hai 12/10 lúc 09:00 · LH-")
    assert "Chào bạn," in email.text
    assert "Bệnh Nhân 0" not in email.html + email.text  # email đăng ký chưa xác minh
    assert "Nổi mẩn đỏ" not in email.html + email.text  # lý do khám không ra khỏi hệ thống
    [row] = await notifications(db)
    assert (row.status, row.attempts, row.sent_at) == (NotificationStatus.SENT, 1, clock.at)

    rescheduled = await app_client.patch(
        f"/api/v1/appointments/{appointment_id}/reschedule",
        json={"start_at": at(MONDAY, 10), "doctor_id": clinic.doctor_ids[0]},
        headers=bearer(clinic.patient_ids[0], UserRole.PATIENT),
    )
    cancelled = await app_client.post(
        f"/api/v1/appointments/{appointment_id}/cancel",
        json={"reason": "Phòng khám báo bác sĩ nghỉ"},
        headers=bearer(clinic.admin_id, UserRole.ADMIN),
    )
    assert rescheduled.status_code == cancelled.status_code == 200

    assert await sender(clock, mailer).send_due() == 2
    subjects = [e.subject for e in mailer.sent[1:]]
    assert subjects[0].startswith("Đã đổi lịch khám sang Thứ Hai 12/10 lúc 10:00")
    assert subjects[1].startswith("Đã hủy lịch khám Thứ Hai 12/10 lúc 10:00")
    assert "Lịch hẹn của bạn đã đổi sang thời gian mới" in mailer.sent[1].text
    assert "Phòng khám đã hủy lịch hẹn sau của bạn" in mailer.sent[2].text  # FR-NTF-01
    assert "Phòng khám báo bác sĩ nghỉ" not in mailer.sent[2].text
    assert [r.type for r in await notifications(db)] == [
        NotificationType.BOOKED,
        NotificationType.RESCHEDULED,
        NotificationType.CANCELLED,
    ]


async def test_failed_sends_are_retried_three_times_then_marked_failed(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    """FR-NTF-03: lỗi SMTP không ảnh hưởng lịch đã đặt; thử lại sau 1, 5, 15 phút rồi FAILED."""
    appointment_id = await book(app_client, clinic)
    mailer = FakeMailer(failures=10)
    started = clock.at

    assert await sender(clock, mailer).send_due() == 0
    [row] = await notifications(db)
    assert (row.status, row.attempts) == (NotificationStatus.PENDING, 1)
    assert row.scheduled_at == started + timedelta(minutes=1)
    assert row.last_error == "SMTPServerDisconnected"  # thông điệp SMTP có thể chứa địa chỉ
    assert await sender(clock, mailer).send_due() == 0  # chưa tới hạn thử lại
    assert (await notifications(db))[0].attempts == 1

    for minutes, attempts in ((1, 2), (5, 3), (15, 4)):
        clock.advance(minutes=minutes)
        await sender(clock, mailer).send_due()
        assert (await notifications(db))[0].attempts == attempts
    [row] = await notifications(db)
    assert row.status is NotificationStatus.FAILED
    assert mailer.sent == []
    booked = await db.execute(select(Appointment.status).where(Appointment.id == appointment_id))
    assert booked.scalar_one() is AppointmentStatus.BOOKED


async def test_a_retry_that_succeeds_marks_the_email_sent(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    await book(app_client, clinic)
    mailer = FakeMailer(failures=1)
    await sender(clock, mailer).send_due()
    clock.advance(minutes=1)
    assert await sender(clock, mailer).send_due() == 1
    [row] = await notifications(db)
    assert (row.status, row.attempts, row.last_error) == (NotificationStatus.SENT, 2, None)


async def test_local_addresses_are_only_sent_in_development(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    async with db.begin():
        await db.execute(
            update(User).where(User.id == clinic.patient_ids[0]).values(email="lan@demo.local")
        )
    await book(app_client, clinic, hour=9)
    await book(app_client, clinic, hour=10)
    staging = Settings(_env_file=None, app_env=Environment.STAGING)
    mailer = FakeMailer()

    assert await sender(clock, mailer, staging).send_due(limit=1) == 0
    skipped = (await notifications(db))[0]
    assert (skipped.status, skipped.attempts) == (NotificationStatus.FAILED, 0)
    assert skipped.last_error is not None and ".local" in skipped.last_error

    assert await sender(clock, mailer).send_due() == 1  # development: Mailpit hứng mọi email
    assert [e.to for e in mailer.sent] == ["lan@demo.local"]


async def test_emails_waiting_over_a_day_are_dropped(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    """Hàng đợi tồn từ trước khi bật worker: thư chờ quá 24 giờ đã cũ nên bỏ, không gửi dồn."""
    await book(app_client, clinic)
    clock.advance(hours=25)
    mailer = FakeMailer()

    assert await sender(clock, mailer).send_due() == 0
    [row] = await notifications(db)
    assert (row.status, row.attempts) == (NotificationStatus.FAILED, 0)
    assert row.last_error is not None and "24 giờ" in row.last_error
    assert mailer.sent == []


async def test_one_address_gets_at_most_five_emails_an_hour(
    app_client: AsyncClient,
    db: AsyncSession,
    clinic: Clinic,
    clock: MutableClock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Email đăng ký chưa xác minh: một tài khoản đặt, hủy liên tục không biến phòng khám thành
    nguồn gửi thư hàng loạt tới hộp thư của người khác. Thư phòng khám đổi, hủy vẫn đi."""
    appointment_id = await add_appointment(db, clinic, start=time(9, 0))
    recipient = clinic.emails[clinic.patient_ids[0]]

    def email(status: NotificationStatus, minutes_ago: int) -> Notification:
        at = clock.at - timedelta(minutes=minutes_ago)
        sent = status is NotificationStatus.SENT
        return Notification(
            appointment_id=appointment_id,
            type=NotificationType.BOOKED,
            recipient_email=recipient,
            status=status,
            attempts=int(sent),
            scheduled_at=at,
            sent_at=at if sent else None,
        )

    async with db.begin():
        db.add_all([email(NotificationStatus.SENT, m) for m in (5, 20, 40, 59, 61)])
        db.add_all([email(NotificationStatus.PENDING, 0) for _ in range(2)])
    mailer = FakeMailer()
    capsys.readouterr()

    assert await sender(clock, mailer).send_due() == 1  # 4 thư trong giờ qua: thư thứ 5 vẫn gửi
    assert "recipient_limit" in capsys.readouterr().out  # mã lý do không bị bộ lọc log che
    *_, fifth, sixth = await notifications(db)
    assert fifth.status is NotificationStatus.SENT
    assert (sixth.status, sixth.attempts) == (NotificationStatus.FAILED, 0)
    assert sixth.last_error is not None and "1 giờ" in sixth.last_error

    cancelled = await app_client.post(
        f"/api/v1/appointments/{appointment_id}/cancel",
        json={"reason": "Bác sĩ nghỉ đột xuất"},
        headers=bearer(clinic.admin_id, UserRole.ADMIN),
    )
    assert cancelled.status_code == 200
    assert await sender(clock, mailer).send_due() == 1
    assert mailer.sent[-1].subject.startswith("Đã hủy lịch khám")


async def test_legacy_address_that_is_not_plain_is_never_sent(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    """Địa chỉ lọt vào trước khi siết kiểm tra lúc đăng ký không được gửi: thư viện SMTP sẽ rút
    "n3<victim@y.com>" thành một người nhận khác."""
    async with db.begin():
        await db.execute(
            update(User).where(User.id == clinic.patient_ids[0]).values(email="n3<victim@y.com>")
        )
    await book(app_client, clinic)
    mailer = FakeMailer()

    assert await sender(clock, mailer).send_due() == 0
    [row] = await notifications(db)
    assert (row.status, row.attempts) == (NotificationStatus.FAILED, 0)
    assert mailer.sent == []


async def mark_created(db: AsyncSession, appointment_id: int, days_before: int) -> None:
    async with db.begin():
        appointment = await db.get(Appointment, appointment_id)
        assert appointment is not None
        appointment.created_at = appointment.start_at - timedelta(days=days_before)


async def test_reminders_are_enqueued_once_24_hours_ahead(
    db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    """FR-NTF-02: lịch Đã đặt trong 24 giờ tới, tạo sớm hơn 24 giờ trước giờ khám, nhắc một lần."""
    due = await add_appointment(db, clinic, start=time(9, 0))
    late_booking = await add_appointment(
        db, clinic, patient_index=1, start=time(9, 0), doctor_index=1
    )
    cancelled = await add_appointment(
        db, clinic, start=time(10, 0), status=AppointmentStatus.CANCELLED
    )
    next_week = await add_appointment(db, clinic, day=date(2026, 10, 19), start=time(9, 0))
    for appointment_id, days in ((due, 3), (late_booking, 0), (cancelled, 3), (next_week, 3)):
        await mark_created(db, appointment_id, days)
    clock.at = local_datetime(SUNDAY, time(10, 0))

    first = await enqueue_reminders(get_sessionmaker(), clock, APP_SETTINGS)
    again = await enqueue_reminders(get_sessionmaker(), clock, APP_SETTINGS)

    assert (first, again) == (1, 0)
    [reminder] = await notifications(db)
    assert (reminder.appointment_id, reminder.type) == (due, NotificationType.REMINDER)
    mailer = FakeMailer()
    assert await sender(clock, mailer).send_due() == 1
    assert mailer.sent[0].subject == "Nhắc lịch: ngày mai 09:00 khám với BS. Bác Sĩ 0"


async def test_reminder_for_an_appointment_cancelled_meanwhile_is_skipped(
    db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    appointment_id = await add_appointment(db, clinic, start=time(9, 0))
    await mark_created(db, appointment_id, 3)
    clock.at = local_datetime(SUNDAY, time(10, 0))
    await enqueue_reminders(get_sessionmaker(), clock, APP_SETTINGS)
    async with db.begin():
        await db.execute(
            update(Appointment)
            .where(Appointment.id == appointment_id)
            .values(status=AppointmentStatus.CANCELLED)
        )

    mailer = FakeMailer()
    assert await sender(clock, mailer).send_due() == 0
    [row] = await notifications(db)
    assert (row.status, row.attempts) == (NotificationStatus.FAILED, 0)
    assert mailer.sent == []


async def test_two_workers_share_the_queue_without_sending_twice(
    app_client: AsyncClient, db: AsyncSession, clinic: Clinic, clock: MutableClock
) -> None:
    """`FOR UPDATE SKIP LOCKED`: hai replica worker chạy cùng lúc không gửi trùng email."""
    for hour in (8, 9, 10):
        await book(app_client, clinic, hour=hour)
    mailer = FakeMailer()

    results = await asyncio.gather(
        sender(clock, mailer).send_due(), sender(clock, mailer).send_due()
    )

    assert sum(results) == 3
    assert len(mailer.sent) == 3
    assert {r.status for r in await notifications(db)} == {NotificationStatus.SENT}
