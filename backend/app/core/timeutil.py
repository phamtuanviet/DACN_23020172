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
