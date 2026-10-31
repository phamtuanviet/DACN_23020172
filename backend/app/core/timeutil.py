"""Chuyển đổi giữa giờ địa phương của phòng khám và timestamptz (docs mục 7.6)."""

from datetime import date, datetime, time
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.core.config import get_settings


@lru_cache
def clinic_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().clinic_tz)


def local_datetime(day: date, at: time) -> datetime:
    """Ghép ngày + giờ địa phương thành datetime có múi giờ của phòng khám."""
    return datetime.combine(day, at, tzinfo=clinic_tz())


def to_local(moment: datetime) -> datetime:
    return moment.astimezone(clinic_tz())


# Cách viết thứ giống giao diện (frontend/src/shared/lib/datetime.ts): "Thứ Bảy", "Chủ nhật".
WEEKDAYS = ("Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật")


def weekday_name(day: date) -> str:
    return WEEKDAYS[day.weekday()]


def format_day(day: date) -> str:
    """ "Thứ Bảy 17/10" — nhãn khung giờ cho Agent và email."""
    return f"{weekday_name(day)} {day:%d/%m}"


def format_date(day: date) -> str:
    """ "Thứ Bảy, 17/10/2026"."""
    return f"{weekday_name(day)}, {day:%d/%m/%Y}"


def format_slot(start: datetime, end: datetime) -> str:
    """ "Thứ Bảy 17/10, 08:00–08:20" (giờ phòng khám)."""
    start, end = to_local(start), to_local(end)
    return f"{format_day(start.date())}, {start:%H:%M}–{end:%H:%M}"


def format_when(start: datetime, end: datetime) -> str:
    """ "Thứ Bảy, 17/10/2026 · 08:00–08:20" — dòng thời gian trên thẻ đề xuất."""
    start, end = to_local(start), to_local(end)
    return f"{format_date(start.date())} · {start:%H:%M}–{end:%H:%M}"
