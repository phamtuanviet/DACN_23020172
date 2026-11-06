"""Gửi email qua SMTP (aiosmtplib): Mailpit khi dev, Amazon SES ở staging/production (TD-28)."""

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from functools import lru_cache
from typing import Protocol

import aiosmtplib
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from app.core.config import Settings
from app.modules.notifications.content import EmailContent

# Lỗi mạng, lỗi SMTP: tính là một lần gửi thất bại để thử lại (FR-NTF-03).
SEND_ERRORS: tuple[type[Exception], ...] = (aiosmtplib.SMTPException, OSError, TimeoutError)


@dataclass(frozen=True, slots=True)
class OutgoingEmail:
    to: str
    subject: str
    html: str
    text: str


class Mailer(Protocol):
    async def send(self, email: OutgoingEmail) -> None: ...


@lru_cache
def _templates() -> Environment:
    return Environment(
        loader=PackageLoader("app.modules.notifications", "templates"),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render(content: EmailContent, to: str) -> OutgoingEmail:
    """Dựng email HTML và bản chữ thuần từ cùng một nội dung."""
    env = _templates()
    return OutgoingEmail(
        to=to,
        subject=content.subject,
        html=env.get_template("email.html").render(c=content),
        text=env.get_template("email.txt").render(c=content),
    )


class SmtpMailer:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, email: OutgoingEmail) -> None:
        settings = self._settings
        message = EmailMessage()
        message["From"] = formataddr((settings.clinic_name, settings.mail_from))
        message["To"] = email.to
        message["Subject"] = email.subject
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid(domain=settings.mail_from.rpartition("@")[2] or None)
        message.set_content(email.text)
        message.add_alternative(email.html, subtype="html")
        password = settings.smtp_password.get_secret_value() if settings.smtp_password else None
        # Phong bì ghi rõ người gửi, người nhận, không để aiosmtplib rút từ header To.
        await aiosmtplib.send(
            message,
            sender=settings.mail_from,
            recipients=[email.to],
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=password,
            start_tls=settings.smtp_starttls,
            timeout=settings.smtp_timeout_s,
        )
