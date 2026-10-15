"""Lõi tính khung trống — hàm THUẦN: không I/O, không đọc đồng hồ hệ thống (docs mục 5.1).

Mọi dữ liệu (ca làm, khoảng bận, "bây giờ") được truyền vào, nên test được bằng unit test thuần.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True, slots=True)
class Interval:
    start: datetime
    end: datetime  # khoảng nửa mở [start, end)


@dataclass(frozen=True, slots=True)
class ShiftRule:
    doctor_id: int
    weekday: int  # 1 = thứ Hai … 7 = Chủ nhật (date.isoweekday())
    start_time: time
    end_time: time
    valid_from: date
    valid_to: date | None


@dataclass(frozen=True, slots=True)
class Slot:
    doctor_id: int
    start: datetime
    end: datetime


def compute_slots(
    shifts: list[ShiftRule],
    busy: dict[int, list[Interval]],
    duration: timedelta,
    days: list[date],
    now: datetime,
    window_end: datetime,
    time_from: time | None = None,
    time_to: time | None = None,
) -> list[Slot]:
    """Thuật toán con trỏ ở docs mục 5.1 (FR-SCH-01, 02, 03)."""
    raise NotImplementedError
