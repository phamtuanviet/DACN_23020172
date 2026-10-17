"""Phân quyền theo bản ghi (BR-05, docs mục 4.6) — lớp 2, bắt buộc vì Agent gọi thẳng service.

Danh tính luôn lấy từ `Actor` do server dựng (token, ngữ cảnh của Agent), không bao giờ từ tham số
do người dùng hay LLM gửi lên.
"""

from datetime import datetime, timedelta

from app.core.actor import Actor
from app.core.errors import forbidden
from app.db.enums import AppointmentStatus, Channel, UserRole
from app.db.models.appointments import Appointment


def ensure_can_book(actor: Actor) -> int:
    """Chỉ bệnh nhân đặt lịch, và chỉ cho chính mình; quản trị không đặt hộ (docs mục 4.6)."""
    if actor.role is not UserRole.PATIENT or actor.user_id is None:
        raise forbidden()
    return actor.user_id


def ensure_can_manage_schedule(actor: Actor) -> None:
    """Xem lịch hẹn theo bác sĩ (kèm họ tên bệnh nhân) và gắn cờ "cần xử lý" (BR-10): chỉ quản trị
    hoặc tác vụ hệ thống."""
    if actor.role is UserRole.ADMIN:
        return
    if actor.role is None and actor.channel is Channel.SYSTEM:
        return
    raise forbidden()


def can_change(
    appointment: Appointment, actor: Actor, now: datetime, change_deadline: timedelta
) -> bool:
    """Lịch BOOKED; bệnh nhân là chủ lịch và còn ít nhất 2 giờ (BR-08); quản trị không bị giới hạn
    2 giờ (FR-ADM-03)."""
    if appointment.status is not AppointmentStatus.BOOKED:
        return False
    if actor.role is UserRole.ADMIN:
        return True
    is_owner = actor.role is UserRole.PATIENT and actor.user_id == appointment.patient_id
    return is_owner and appointment.start_at - now >= change_deadline
