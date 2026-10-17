"""Lõi tính khung trống — hàm THUẦN: không I/O, không đọc đồng hồ hệ thống (docs mục 5.1).

Mọi dữ liệu (ca làm, khoảng bận, "bây giờ") được truyền vào, nên test được bằng unit test thuần.
Ngày giờ địa phương đổi sang timestamptz qua `core.timeutil` (múi giờ phòng khám).
"""

from bisect import bisect_right
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.core.timeutil import local_datetime, to_local


@dataclass(frozen=True, slots=True)
class Interval:
    start: datetime
    end: datetime  # khoảng nửa mở [start, end)

    def overlaps(self, other: "Interval") -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, other: "Interval") -> bool:
        return self.start <= other.start and other.end <= self.end


@dataclass(frozen=True, slots=True)
class ShiftRule:
    doctor_id: int
    weekday: int  # 1 = thứ Hai … 7 = Chủ nhật (date.isoweekday())
    start_time: time
    end_time: time
    valid_from: date
    valid_to: date | None

    def applies_on(self, day: date) -> bool:
        return (
            day.isoweekday() == self.weekday
            and self.valid_from <= day
            and (self.valid_to is None or day <= self.valid_to)
        )

    def interval_on(self, day: date) -> Interval:
        return Interval(local_datetime(day, self.start_time), local_datetime(day, self.end_time))


@dataclass(frozen=True, slots=True)
class Slot:
    doctor_id: int
    start: datetime
    end: datetime


def merge_intervals(intervals: Iterable[Interval]) -> list[Interval]:
    """Gộp các khoảng chồng hoặc sát nhau (ngày nghỉ phủ lên lịch hẹn…).

    Kết quả rời nhau và tăng dần theo cả giờ bắt đầu lẫn giờ kết thúc, nên con trỏ chỉ cần đi tới.
    """
    merged: list[Interval] = []
    for item in sorted(intervals, key=lambda i: i.start):
        if merged and item.start <= merged[-1].end:
            if item.end > merged[-1].end:
                merged[-1] = Interval(merged[-1].start, item.end)
        else:
            merged.append(item)
    return merged


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
    """Thuật toán con trỏ ở docs mục 5.1 (FR-SCH-01, 02, 03).

    `busy` theo doctor_id: ngày nghỉ và lịch BOOKED/ARRIVED. Lọc khung đã qua, khung ngoài cửa sổ
    đặt lịch và khung không nằm trọn trong [time_from, time_to); sắp theo giờ rồi theo bác sĩ.
    """
    calendar = _Calendar(shifts, busy, duration)
    slots: list[Slot] = []
    for day in days:
        slots.extend(calendar.slots_on(day, now, window_end, time_from, time_to))
    slots.sort(key=lambda s: (s.start, s.doctor_id))
    return slots


def nearest_dates(
    shifts: list[ShiftRule],
    busy: dict[int, list[Interval]],
    duration: timedelta,
    days: Iterable[date],
    now: datetime,
    window_end: datetime,
    time_from: time | None = None,
    time_to: time | None = None,
    limit: int = 3,
) -> list[date]:
    """Các ngày đầu tiên theo thứ tự `days` còn khung trống; đủ `limit` thì dừng (FR-SCH-05)."""
    calendar = _Calendar(shifts, busy, duration)
    found: list[date] = []
    for day in days:
        if len(found) >= limit:
            break
        if calendar.slots_on(day, now, window_end, time_from, time_to):
            found.append(day)
    return found


def earliest_slots(
    shifts: list[ShiftRule],
    busy: dict[int, list[Interval]],
    duration: timedelta,
    days: Iterable[date],
    now: datetime,
    window_end: datetime,
) -> dict[int, Slot]:
    """Khung trống sớm nhất của từng bác sĩ; đi lần lượt từng ngày, dừng khi mọi bác sĩ đã có."""
    calendar = _Calendar(shifts, busy, duration)
    doctors = {rule.doctor_id for rule in shifts}
    found: dict[int, Slot] = {}
    for day in days:
        if len(found) == len(doctors):
            break
        day_slots = calendar.slots_on(day, now, window_end, None, None)
        for slot in sorted(day_slots, key=lambda s: (s.start, s.doctor_id)):
            found.setdefault(slot.doctor_id, slot)
    return found


def has_working_time(
    shifts: list[ShiftRule], time_offs: dict[int, list[Interval]], day: date
) -> bool:
    """Ngày có giờ làm (ca không bị ngày nghỉ phủ kín), dù còn khung trống hay đã kín lịch."""
    merged = {doctor_id: merge_intervals(items) for doctor_id, items in time_offs.items()}
    for rule in shifts:
        if not rule.applies_on(day):
            continue
        shift = rule.interval_on(day)
        if not any(off.contains(shift) for off in merged.get(rule.doctor_id, [])):
            return True
    return False


def within_shifts(shifts: list[ShiftRule], doctor_id: int, interval: Interval) -> bool:
    """Lịch hẹn còn nằm trọn trong một ca của bác sĩ không (dùng khi sửa, xóa ca làm, BR-10)."""
    day = to_local(interval.start).date()
    return any(
        rule.doctor_id == doctor_id
        and rule.applies_on(day)
        and rule.interval_on(day).contains(interval)
        for rule in shifts
    )


class _Calendar:
    """Ca làm theo thứ trong tuần và khoảng bận đã gộp, dựng một lần cho nhiều ngày."""

    def __init__(
        self, shifts: list[ShiftRule], busy: dict[int, list[Interval]], duration: timedelta
    ) -> None:
        if duration <= timedelta(0):
            raise ValueError("Thời lượng dịch vụ phải lớn hơn 0")
        self._duration = duration
        self._shifts_by_weekday: dict[int, list[ShiftRule]] = {}
        for rule in shifts:
            self._shifts_by_weekday.setdefault(rule.weekday, []).append(rule)
        self._busy = {doctor_id: merge_intervals(items) for doctor_id, items in busy.items()}

    def slots_on(
        self,
        day: date,
        now: datetime,
        window_end: datetime,
        time_from: time | None,
        time_to: time | None,
    ) -> list[Slot]:
        lower = local_datetime(day, time_from) if time_from is not None else None
        upper = local_datetime(day, time_to) if time_to is not None else None
        seen: set[tuple[int, datetime]] = set()  # hai ca chồng nhau (dữ liệu lỗi) không sinh trùng
        slots: list[Slot] = []
        for rule in self._shifts_by_weekday.get(day.isoweekday(), []):
            if not rule.applies_on(day):
                continue
            busy = self._busy.get(rule.doctor_id, [])
            for start in _cursor(rule.interval_on(day), busy, self._duration):
                end = start + self._duration
                if start <= now or start > window_end:
                    continue
                if (lower is not None and start < lower) or (upper is not None and end > upper):
                    continue
                if (rule.doctor_id, start) not in seen:
                    seen.add((rule.doctor_id, start))
                    slots.append(Slot(rule.doctor_id, start, end))
        return slots


def _cursor(shift: Interval, busy: list[Interval], duration: timedelta) -> Iterator[datetime]:
    """Khung đầu tiên bắt đầu từ đầu ca, các khung cách nhau đúng thời lượng; gặp khoảng bận thì
    khung kế tiếp bắt đầu ngay sau khoảng đó (FR-SCH-02). `busy` đã gộp, rời nhau và tăng dần.

    Lưới giờ luôn tính từ đầu ca chứ không từ "bây giờ", nên khung đã qua chỉ bị lọc bỏ ở bước sau
    và giờ hiển thị không bị xô lệch theo thời điểm xem.
    """
    index = bisect_right(busy, shift.start, key=lambda b: b.end)  # bỏ khoảng kết thúc trước ca
    t = shift.start
    while t + duration <= shift.end:
        while index < len(busy) and busy[index].end <= t:
            index += 1
        if index < len(busy) and busy[index].start < t + duration:
            t = busy[index].end
        else:
            yield t
            t += duration
