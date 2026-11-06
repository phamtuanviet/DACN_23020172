"""Nội dung 4 loại email (SRS mục 7.4, thiết kế S-email): hàm thuần, không I/O, để test được.

Không chứa lý do khám hay ghi chú của bác sĩ (dữ liệu sức khỏe), vì hộp thư nằm ngoài tầm kiểm soát
của phòng khám. Cũng không chứa họ tên: email đăng ký chưa được xác minh, nên không đưa chữ do người
đăng ký tự đặt vào thư mang tên phòng khám gửi tới một địa chỉ có thể là của người khác.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from app.core.timeutil import format_date, format_day, to_local
from app.db.enums import NotificationType


@dataclass(frozen=True, slots=True)
class AppointmentFacts:
    appointment_id: int
    code: str
    service_name: str
    doctor_name: str
    start_at: datetime
    end_at: datetime
    by_clinic: bool = False  # đổi, hủy do phòng khám (quản trị) thực hiện


@dataclass(frozen=True, slots=True)
class ClinicInfo:
    name: str
    address: str
    phone: str
    base_url: str
    change_deadline_hours: int


@dataclass(frozen=True, slots=True)
class Link:
    label: str
    url: str


@dataclass(frozen=True, slots=True)
class EmailContent:
    greeting: str
    day: str
    time: str
    what: str
    code: str
    clinic: str
    address: str
    footer: str
    subject: str = ""
    heading: str = ""
    intro: str = ""
    struck: bool = False  # lịch đã hủy: gạch giờ khám
    links: list[Link] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    as_list: bool = False  # ghi chú dạng gạch đầu dòng (email nhắc)


def _relative_day(start: datetime, now: datetime) -> str | None:
    days = (to_local(start).date() - to_local(now).date()).days
    return {0: "hôm nay", 1: "ngày mai"}.get(days)


def build_email(
    kind: NotificationType, facts: AppointmentFacts, clinic: ClinicInfo, now: datetime
) -> EmailContent:
    start, end = to_local(facts.start_at), to_local(facts.end_at)
    day_short = format_day(start.date())
    deadline_at = start - timedelta(hours=clinic.change_deadline_hours)
    deadline = f"{deadline_at:%H:%M} {format_day(deadline_at.date())}"
    call = f"gọi {clinic.phone}" if clinic.phone else "gọi phòng khám"
    base_url = clinic.base_url.rstrip("/")
    view = Link("Xem lịch hẹn", f"{base_url}/me/appointments?id={facts.appointment_id}")
    change_note = f"Cần đổi hoặc hủy? Làm trực tuyến trước {deadline}. Sau mốc đó, vui lòng {call}."
    base = EmailContent(
        greeting="Chào bạn,",
        day=format_date(start.date()),
        time=f"{start:%H:%M} – {end:%H:%M}",
        what=f"{facts.service_name} · {facts.doctor_name}",
        code=facts.code,
        clinic=clinic.name,
        address=clinic.address,
        footer=" · ".join(part for part in (clinic.name, clinic.address, clinic.phone) if part),
    )

    if kind is NotificationType.BOOKED:
        return replace(
            base,
            subject=f"Đã đặt lịch khám {day_short} lúc {start:%H:%M} · {facts.code}",
            heading="Lịch khám của bạn đã được đặt",
            intro="Phòng khám đã nhận lịch hẹn của bạn:",
            links=[view],
            notes=[change_note],
        )
    if kind is NotificationType.RESCHEDULED:
        return replace(
            base,
            subject=f"Đã đổi lịch khám sang {day_short} lúc {start:%H:%M} · {facts.code}",
            heading="Lịch khám của bạn đã được đổi",
            intro=(
                "Phòng khám đã đổi lịch hẹn của bạn sang thời gian mới:"
                if facts.by_clinic
                else "Lịch hẹn của bạn đã đổi sang thời gian mới:"
            ),
            links=[view],
            notes=["Mã lịch hẹn giữ nguyên.", change_note],
        )
    if kind is NotificationType.CANCELLED:
        return replace(
            base,
            subject=f"Đã hủy lịch khám {day_short} lúc {start:%H:%M} · {facts.code}",
            heading="Lịch khám của bạn đã được hủy",
            intro=(
                "Phòng khám đã hủy lịch hẹn sau của bạn:"
                if facts.by_clinic
                else "Bạn đã hủy lịch hẹn sau:"
            ),
            struck=True,
            links=[Link("Đặt lịch mới", f"{base_url}/booking")],
            notes=[
                f"Phòng khám sẽ liên hệ để sắp xếp lại. Bạn cần hỗ trợ ngay, vui lòng {call}."
                if facts.by_clinic
                else "Muốn khám vào thời gian khác? Bạn đặt lịch mới bất cứ lúc nào."
            ],
        )

    relative = _relative_day(facts.start_at, now)
    return replace(
        base,
        subject=f"Nhắc lịch: {relative or day_short} {start:%H:%M} khám với {facts.doctor_name}",
        heading=f"{relative.capitalize()} bạn có lịch khám" if relative else "Bạn sắp có lịch khám",
        intro="Phòng khám nhắc bạn lịch hẹn sắp tới:",
        day=f"{relative.capitalize()} · {base.day}" if relative else base.day,
        links=[view, Link("Đổi hoặc hủy", view.url)],
        notes=[
            "Đến trước 10 phút và đọc mã lịch hẹn cho lễ tân.",
            f"Không đến được? Đổi hoặc hủy trước {deadline} để nhường khung cho người khác.",
        ],
        as_list=True,
    )
