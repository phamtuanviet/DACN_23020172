"""Danh tính của người/tiến trình thực hiện thao tác, truyền vào mọi service (docs mục 4.2)."""

from dataclasses import dataclass

from app.db.enums import Channel, UserRole


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: int | None  # None khi là tiến trình hệ thống (worker)
    role: UserRole | None
    channel: Channel
