"""Scheduling Engine (docs mục 5.1, 5.2): ranh giới ca, khoảng [), ngày nghỉ, lịch sát nhau,
khung đã qua, cửa sổ 30 ngày, lọc buổi (FR-SCH-01..05, AC-02)."""

from datetime import date, datetime, time, timedelta

import pytest

from app.core.timeutil import local_datetime
from app.modules.scheduling.engine import (
    Interval,
    ShiftRule,
    Slot,
    compute_slots,
    earliest_slots,
    has_working_time,
    merge_intervals,
    nearest_dates,
    within_shifts,
)
from tests.conftest import TEST_NOW

MONDAY = date(2026, 10, 12)  # TEST_NOW là Thứ Bảy 10/10/2026 09:00
WINDOW_END = TEST_NOW + timedelta(days=30)
MINUTES_20 = timedelta(minutes=20)


def shift(
    doctor_id: int = 1,
    weekday: int = 1,
    start: time = time(8, 0),
    end: time = time(11, 30),
    valid_from: date = date(2026, 10, 1),
    valid_to: date | None = None,
) -> ShiftRule:
    return ShiftRule(doctor_id, weekday, start, end, valid_from, valid_to)


def busy(day: date, start: tuple[int, int], end: tuple[int, int]) -> Interval:
    return Interval(local_datetime(day, time(*start)), local_datetime(day, time(*end)))


def hhmm(slots: list[Slot]) -> list[str]:
    return [f"{s.start.astimezone(TEST_NOW.tzinfo):%H:%M}" for s in slots]


def slots_for(
    shifts: list[ShiftRule],
    taken: dict[int, list[Interval]] | None = None,
    duration: timedelta = MINUTES_20,
    days: list[date] | None = None,
    *,
    now: datetime = TEST_NOW,
    window_end: datetime = WINDOW_END,
    time_from: time | None = None,
    time_to: time | None = None,
) -> list[Slot]:
    return compute_slots(
        shifts, taken or {}, duration, days or [MONDAY], now, window_end, time_from, time_to
    )


def test_worked_example_from_design_doc() -> None:
    """Ca 08:00–11:30, dịch vụ 20 phút, đã có lịch 08:40–09:10 (docs mục 5.1)."""
    result = slots_for([shift()], {1: [busy(MONDAY, (8, 40), (9, 10))]})
    assert hhmm(result) == [
        "08:00", "08:20", "09:10", "09:30", "09:50", "10:10", "10:30", "10:50", "11:10",
    ]  # fmt: skip
    assert result[0] == Slot(
        1, local_datetime(MONDAY, time(8, 0)), local_datetime(MONDAY, time(8, 20))
    )


def test_last_slot_ends_exactly_at_shift_end() -> None:
    result = slots_for([shift(end=time(9, 0))])
    assert hhmm(result) == ["08:00", "08:20", "08:40"]
    assert result[-1].end == local_datetime(MONDAY, time(9, 0))


def test_duration_that_does_not_divide_the_shift_leaves_a_gap_at_the_end() -> None:
    result = slots_for([shift()], duration=timedelta(minutes=45))
    assert hhmm(result) == ["08:00", "08:45", "09:30", "10:15"]


def test_half_open_intervals_allow_back_to_back_appointments() -> None:
    """Lịch 08:20–08:40 đã đặt: khung 08:00–08:20 và 08:40–09:00 vẫn hợp lệ."""
    result = slots_for([shift(end=time(9, 20))], {1: [busy(MONDAY, (8, 20), (8, 40))]})
    assert hhmm(result) == ["08:00", "08:40", "09:00"]


def test_time_off_covering_whole_day_removes_every_slot() -> None:
    result = slots_for([shift()], {1: [busy(MONDAY, (0, 0), (23, 59))]})
    assert result == []


def test_partial_time_off_moves_cursor_to_its_end() -> None:
    result = slots_for([shift()], {1: [busy(MONDAY, (7, 0), (10, 5))]})
    assert hhmm(result) == ["10:05", "10:25", "10:45", "11:05"]


def test_overlapping_busy_intervals_are_merged() -> None:
    """Ngày nghỉ 09:00–10:00 phủ lên lịch hẹn 09:30–10:20: khung kế tiếp bắt đầu 10:20."""
    taken = {1: [busy(MONDAY, (9, 30), (10, 20)), busy(MONDAY, (9, 0), (10, 0))]}
    result = slots_for([shift(end=time(11, 0))], taken)
    assert hhmm(result) == ["08:00", "08:20", "08:40", "10:20", "10:40"]


def test_busy_interval_of_another_doctor_is_ignored() -> None:
    result = slots_for([shift(end=time(9, 0))], {2: [busy(MONDAY, (8, 0), (9, 0))]})
    assert hhmm(result) == ["08:00", "08:20", "08:40"]


def test_past_slots_are_dropped_but_grid_stays_aligned_to_shift_start() -> None:
    """Bây giờ 09:05: lưới vẫn tính từ 08:00, nên khung kế tiếp là 09:20 chứ không phải 09:05."""
    now = local_datetime(MONDAY, time(9, 5))
    result = slots_for([shift(end=time(10, 0))], now=now)
    assert hhmm(result) == ["09:20", "09:40"]


def test_slot_starting_exactly_now_is_dropped() -> None:
    now = local_datetime(MONDAY, time(8, 20))
    assert hhmm(slots_for([shift(end=time(9, 0))], now=now)) == ["08:40"]


def test_booking_window_keeps_slot_at_window_end_and_drops_later_ones() -> None:
    window_end = local_datetime(MONDAY, time(8, 20))
    result = slots_for([shift(end=time(9, 0))], window_end=window_end)
    assert hhmm(result) == ["08:00", "08:20"]


def test_thirty_day_window_from_real_now() -> None:
    """Ca mỗi Thứ Hai: Thứ Hai 09/11 còn trong 30 ngày, Thứ Hai 16/11 thì không (BR-07)."""
    days = [date(2026, 11, 9), date(2026, 11, 16)]
    result = slots_for([shift(end=time(9, 0))], days=days)
    assert {s.start.date() for s in result} == {date(2026, 11, 9)}


def test_time_filter_keeps_only_slots_fully_inside_the_range() -> None:
    """Lọc 09:00–10:10: khung 10:00–10:20 vượt quá 10:10 nên bị loại (FR-SCH-04)."""
    result = slots_for([shift()], time_from=time(9, 0), time_to=time(10, 10))
    assert hhmm(result) == ["09:00", "09:20", "09:40"]


def test_shift_applies_only_on_its_weekday_and_validity_range() -> None:
    rules = [
        shift(weekday=1, valid_from=date(2026, 10, 13)),  # Thứ Hai, hiệu lực từ 13/10
        shift(weekday=2, valid_to=date(2026, 10, 13)),  # Thứ Ba, hiệu lực tới 13/10
    ]
    days = [MONDAY, date(2026, 10, 13), date(2026, 10, 19), date(2026, 10, 20)]
    result = slots_for(rules, days=days)
    assert {s.start.date() for s in result} == {date(2026, 10, 13), date(2026, 10, 19)}


def test_sunday_uses_weekday_seven() -> None:
    sunday = date(2026, 10, 18)
    assert hhmm(slots_for([shift(weekday=7, end=time(8, 40))], days=[sunday])) == ["08:00", "08:20"]


def test_slots_are_sorted_by_time_then_doctor() -> None:
    rules = [shift(doctor_id=2, end=time(8, 40)), shift(doctor_id=1, end=time(8, 40))]
    result = slots_for(rules, {2: [busy(MONDAY, (8, 0), (8, 10))]})
    assert [(s.doctor_id, f"{s.start:%H:%M}") for s in result] == [
        (1, "08:00"),
        (2, "08:10"),
        (1, "08:20"),
    ]


def test_duplicate_shifts_do_not_create_duplicate_slots() -> None:
    result = slots_for([shift(end=time(8, 40)), shift(end=time(8, 40))])
    assert hhmm(result) == ["08:00", "08:20"]


def test_non_positive_duration_is_rejected() -> None:
    with pytest.raises(ValueError):
        slots_for([shift()], duration=timedelta(0))


def test_nearest_dates_returns_first_three_days_with_slots() -> None:
    rules = [shift(weekday=w, end=time(8, 20)) for w in (1, 3, 5)]
    days = [MONDAY + timedelta(days=i) for i in range(14)]
    taken = {1: [busy(MONDAY, (8, 0), (8, 20))]}  # Thứ Hai 12/10 đã kín
    assert nearest_dates(rules, taken, MINUTES_20, days, TEST_NOW, WINDOW_END) == [
        date(2026, 10, 14),
        date(2026, 10, 16),
        date(2026, 10, 19),
    ]


def test_nearest_dates_can_return_fewer_than_limit() -> None:
    days = [MONDAY + timedelta(days=i) for i in range(3)]
    assert nearest_dates([shift()], {}, MINUTES_20, days, TEST_NOW, WINDOW_END) == [MONDAY]


def test_has_working_time_distinguishes_day_off_from_fully_booked() -> None:
    rules = [shift()]
    whole_day_off = {1: [busy(MONDAY, (0, 0), (23, 59))]}
    assert not has_working_time(rules, whole_day_off, MONDAY)
    assert has_working_time(rules, {1: [busy(MONDAY, (8, 0), (9, 0))]}, MONDAY)
    assert not has_working_time(rules, {}, date(2026, 10, 13))  # không có ca Thứ Ba


def test_within_shifts_checks_appointment_is_fully_inside_a_shift() -> None:
    rules = [shift()]
    assert within_shifts(rules, 1, busy(MONDAY, (11, 10), (11, 30)))
    assert not within_shifts(rules, 1, busy(MONDAY, (11, 20), (11, 40)))
    assert not within_shifts(rules, 2, busy(MONDAY, (8, 0), (8, 20)))


def test_merge_intervals_joins_touching_ranges() -> None:
    merged = merge_intervals(
        [
            busy(MONDAY, (9, 0), (9, 20)),
            busy(MONDAY, (8, 40), (9, 0)),
            busy(MONDAY, (10, 0), (11, 0)),
        ]
    )
    assert merged == [busy(MONDAY, (8, 40), (9, 20)), busy(MONDAY, (10, 0), (11, 0))]


def test_earliest_slots_finds_first_free_slot_of_each_doctor() -> None:
    rules = [shift(doctor_id=1, end=time(8, 40)), shift(doctor_id=2, weekday=2, end=time(8, 40))]
    days = [MONDAY + timedelta(days=i) for i in range(7)]
    taken = {1: [busy(MONDAY, (8, 0), (8, 20))]}
    found = earliest_slots(rules, taken, MINUTES_20, days, TEST_NOW, WINDOW_END)
    assert found[1].start == local_datetime(MONDAY, time(8, 20))
    assert found[2].start == local_datetime(date(2026, 10, 13), time(8, 0))
