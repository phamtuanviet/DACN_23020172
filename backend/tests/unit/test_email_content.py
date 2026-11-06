"""Nội dung 4 loại email (SRS mục 7.4, thiết kế S-email): tiêu đề, mốc đổi/hủy, chữ thoát HTML."""

from dataclasses import replace
from datetime import datetime, time
from email.message import EmailMessage
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import SecretStr

from app.core.config import Environment, Settings
from app.db.enums import NotificationType
from app.modules.notifications import mailer as mailer_module
from app.modules.notifications.content import AppointmentFacts, ClinicInfo, build_email
from app.modules.notifications.mailer import render

VN = ZoneInfo("Asia/Ho_Chi_Minh")
NOW = datetime(2026, 10, 16, 8, 15, tzinfo=VN)  # Thứ Sáu
FACTS = AppointmentFacts(
    appointment_id=42,
    code="LH-261010-7KQ2",
    service_name="Khám da liễu tổng quát",
    doctor_name="ThS. BS. Trần Minh",
    start_at=datetime.combine(datetime(2026, 10, 17).date(), time(8, 0), tzinfo=VN),
    end_at=datetime.combine(datetime(2026, 10, 17).date(), time(8, 20), tzinfo=VN),
)
CLINIC = ClinicInfo(
    name="Phòng khám DACN",
    address="1 Đường Mẫu, Hà Nội",
    phone="024 0000 0000",
    base_url="https://app.example.com/",
    change_deadline_hours=2,
)


def test_booked_email_matches_the_design() -> None:
    content = build_email(NotificationType.BOOKED, FACTS, CLINIC, NOW)

    assert content.subject == "Đã đặt lịch khám Thứ Bảy 17/10 lúc 08:00 · LH-261010-7KQ2"
    assert content.heading == "Lịch khám của bạn đã được đặt"
    assert content.day == "Thứ Bảy, 17/10/2026"
    assert content.time == "08:00 – 08:20"
    assert content.what == "Khám da liễu tổng quát · ThS. BS. Trần Minh"
    assert content.links[0].url == "https://app.example.com/me/appointments?id=42"
    assert content.notes == [
        "Cần đổi hoặc hủy? Làm trực tuyến trước 06:00 Thứ Bảy 17/10. "
        "Sau mốc đó, vui lòng gọi 024 0000 0000."
    ]
    assert content.footer == "Phòng khám DACN · 1 Đường Mẫu, Hà Nội · 024 0000 0000"


def test_reminder_says_tomorrow_and_lists_tips() -> None:
    content = build_email(NotificationType.REMINDER, FACTS, CLINIC, NOW)

    assert content.subject == "Nhắc lịch: ngày mai 08:00 khám với ThS. BS. Trần Minh"
    assert content.heading == "Ngày mai bạn có lịch khám"
    assert content.day == "Ngày mai · Thứ Bảy, 17/10/2026"
    assert content.as_list is True
    assert [link.label for link in content.links] == ["Xem lịch hẹn", "Đổi hoặc hủy"]
    same_day = build_email(
        NotificationType.REMINDER, FACTS, CLINIC, NOW.replace(day=17, hour=6, minute=0)
    )
    assert same_day.subject.startswith("Nhắc lịch: hôm nay 08:00")


@pytest.mark.parametrize(
    ("by_clinic", "intro"),
    [(False, "Bạn đã hủy lịch hẹn sau:"), (True, "Phòng khám đã hủy lịch hẹn sau của bạn:")],
)
def test_cancel_email_tells_who_cancelled(by_clinic: bool, intro: str) -> None:
    facts = replace(FACTS, by_clinic=by_clinic)
    content = build_email(NotificationType.CANCELLED, facts, CLINIC, NOW)
    assert content.subject == "Đã hủy lịch khám Thứ Bảy 17/10 lúc 08:00 · LH-261010-7KQ2"
    assert content.intro == intro
    assert content.struck is True
    assert content.links[0].url == "https://app.example.com/booking"


def test_reschedule_email_without_clinic_phone() -> None:
    clinic = ClinicInfo("Phòng khám DACN", "", "", "http://localhost:3000", 2)
    content = build_email(NotificationType.RESCHEDULED, FACTS, clinic, NOW)
    assert content.subject == "Đã đổi lịch khám sang Thứ Bảy 17/10 lúc 08:00 · LH-261010-7KQ2"
    assert content.notes[0] == "Mã lịch hẹn giữ nguyên."
    assert content.notes[1].endswith("vui lòng gọi phòng khám.")
    assert content.footer == "Phòng khám DACN"


def test_rendered_email_escapes_catalog_text_in_html() -> None:
    facts = replace(FACTS, service_name="<b>Khám</b> & tư vấn")
    email = render(build_email(NotificationType.BOOKED, facts, CLINIC, NOW), "lan@example.com")

    assert email.to == "lan@example.com"
    assert "&lt;b&gt;Khám&lt;/b&gt; &amp; tư vấn" in email.html
    assert "<b>Khám</b>" not in email.html
    assert "<b>Khám</b> & tư vấn" in email.text  # bản chữ thuần không thoát HTML
    assert "Chào bạn," in email.text  # không có họ tên do người đăng ký tự đặt
    assert "LH-261010-7KQ2" in email.html and "LH-261010-7KQ2" in email.text
    assert "https://app.example.com/me/appointments?id=42" in email.text


async def test_smtp_mailer_builds_a_multipart_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Thư gồm bản chữ thuần và HTML, người gửi mang tên phòng khám; cấu hình SMTP lấy từ
    Settings."""
    calls: list[tuple[EmailMessage, dict[str, Any]]] = []

    async def fake_send(message: EmailMessage, **kwargs: Any) -> None:
        calls.append((message, kwargs))

    monkeypatch.setattr(mailer_module.aiosmtplib, "send", fake_send)
    settings = Settings(
        _env_file=None,
        app_env=Environment.DEVELOPMENT,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user",
        smtp_password=SecretStr("pw"),
        smtp_starttls=True,
        mail_from="no-reply@example.com",
    )
    email = render(build_email(NotificationType.BOOKED, FACTS, CLINIC, NOW), "lan@example.com")

    await mailer_module.SmtpMailer(settings).send(email)

    [(message, kwargs)] = calls
    assert message["To"] == "lan@example.com"
    assert message["Subject"] == email.subject
    assert "no-reply@example.com" in message["From"] and "DACN" in message["From"]
    assert message["Message-ID"].endswith("@example.com>")
    assert [part.get_content_type() for part in message.iter_parts()] == [
        "text/plain",
        "text/html",
    ]
    assert kwargs == {
        "sender": "no-reply@example.com",
        "recipients": ["lan@example.com"],
        "hostname": "smtp.example.com",
        "port": 587,
        "username": "user",
        "password": "pw",
        "start_tls": True,
        "timeout": 15,
    }
