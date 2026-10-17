"""Ghi email vào bảng notifications trong cùng transaction với lịch hẹn (docs mục 10.5).

Lịch hẹn và email cùng commit hoặc cùng rollback: không có lịch mà thiếu email, cũng không có
email cho lịch không tồn tại. Worker gửi sau (FR-NTF-01).
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import NotificationStatus, NotificationType
from app.db.models.appointments import Notification


async def enqueue(
    session: AsyncSession,
    *,
    appointment_id: int,
    type: NotificationType,
    recipient_email: str,
    scheduled_at: datetime,
) -> None:
    session.add(
        Notification(
            appointment_id=appointment_id,
            type=type,
            recipient_email=recipient_email,
            status=NotificationStatus.PENDING,
            attempts=0,
            scheduled_at=scheduled_at,
        )
    )
