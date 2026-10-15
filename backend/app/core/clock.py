"""Nguồn thời gian duy nhất của ứng dụng (docs mục 2.4, nguyên tắc 6).

Không gọi datetime.now() rải rác: lấy "bây giờ" qua Clock để test cố định được thời gian.
"""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """Dùng trong test và trong seed (lùi đồng hồ về quá khứ)."""

    def __init__(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("FixedClock cần datetime có múi giờ")
        self._at = at

    def now(self) -> datetime:
        return self._at


_system_clock = SystemClock()


def get_clock() -> Clock:
    """Dependency của FastAPI; test ghi đè bằng app.dependency_overrides[get_clock]."""
    return _system_clock
