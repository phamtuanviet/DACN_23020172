"""Phân quyền theo bản ghi (BR-05, docs mục 4.6) — lớp 2, bắt buộc vì Agent gọi thẳng service.

Danh tính luôn lấy từ `Actor` do server dựng (token, ngữ cảnh của Agent), không bao giờ từ tham số
do người dùng hay LLM gửi lên.
"""

from datetime import datetime, timedelta

from app.core.actor import Actor
from app.core.errors import AppError, forbidden
from app.core.timeutil import to_local
from app.db.enums import AppointmentStatus, Channel, UserRole
from app.db.models.appointments import Appointment
from app.modules.appointments.state_machine import can_transition

STATUS_LABELS = {
    AppointmentStatus.BOOKED: "Đã đặt",
    AppointmentStatus.ARRIVED: "Đã đến",
    AppointmentStatus.COMPLETED: "Đã khám",
    AppointmentStatus.CANCELLED: "Đã hủy",
    AppointmentStatus.NO_SHOW: "Vắng mặt",
}


# ---------------------------------------------------------------------------- lỗi
def invalid_transition(message: str, current: AppointmentStatus) -> AppError:
    return AppError("INVALID_TRANSITION", message, status=409, details={"status": current.value})


def change_deadline_passed(hours: int, clinic_phone: str) -> AppError:
    contact = f" theo số {clinic_phone}" if clinic_phone else ""
    return AppError(
        "CHANGE_DEADLINE_PASSED",
        f"Chỉ đổi, hủy trực tuyến trước giờ khám ít nhất {hours} giờ. "
        f"Vui lòng gọi phòng khám{contact} để được hỗ trợ.",
        status=409,
        details={"clinic_phone": clinic_phone or None},
    )


# ---------------------------------------------------------------------------- quyền
def ensure_can_book(actor: Actor) -> int:
    """Chỉ bệnh nhân đặt lịch, và chỉ cho chính mình; quản trị không đặt hộ (docs mục 4.6)."""
    if actor.role is not UserRole.PATIENT or actor.user_id is None:
        raise forbidden()
    return actor.user_id


def ensure_can_list_own(actor: Actor) -> int:
    """`/appointments/me`: chỉ bệnh nhân, và chỉ lịch của chính mình."""
    return ensure_can_book(actor)


def ensure_is_doctor(actor: Actor) -> int:
    """Lịch khám của bác sĩ: chỉ bác sĩ, và chỉ lịch của chính mình (AC-09)."""
    if actor.role is not UserRole.DOCTOR or actor.user_id is None:
        raise forbidden()
    return actor.user_id


def ensure_admin(actor: Actor) -> None:
    """Danh sách mọi lịch hẹn, gắn hoặc gỡ cờ thủ công: chỉ quản trị (FR-ADM-03, 04)."""
    if actor.role is not UserRole.ADMIN:
        raise forbidden()


def ensure_can_manage_schedule(actor: Actor) -> None:
    """Xem lịch hẹn theo bác sĩ (kèm họ tên bệnh nhân) và gắn cờ "cần xử lý" (BR-10): chỉ quản trị
    hoặc tác vụ hệ thống."""
    if actor.role is UserRole.ADMIN:
        return
    if actor.role is None and actor.channel is Channel.SYSTEM:
        return
    raise forbidden()


def _is_owner(appointment: Appointment, actor: Actor) -> bool:
    return actor.role is UserRole.PATIENT and actor.user_id == appointment.patient_id


def _is_doctor_of(appointment: Appointment, actor: Actor) -> bool:
    return actor.role is UserRole.DOCTOR and actor.user_id == appointment.doctor_id


def ensure_can_view(appointment: Appointment, actor: Actor) -> None:
    """Chủ lịch, bác sĩ của lịch, quản trị (AC-05)."""
    if actor.role is UserRole.ADMIN or _is_owner(appointment, actor):
        return
    if _is_doctor_of(appointment, actor):
        return
    raise forbidden()


def ensure_can_change(
    appointment: Appointment,
    actor: Actor,
    now: datetime,
    *,
    deadline_hours: int,
    clinic_phone: str,
) -> None:
    """Đổi, hủy: chủ lịch hoặc quản trị (403); lịch còn BOOKED (409 INVALID_TRANSITION); bệnh nhân
    còn ít nhất 2 giờ trước giờ khám (409 CHANGE_DEADLINE_PASSED, BR-08). Quản trị không bị giới
    hạn 2 giờ (FR-ADM-03)."""
    if actor.role is not UserRole.ADMIN and not _is_owner(appointment, actor):
        raise forbidden()
    if appointment.status is not AppointmentStatus.BOOKED:
        label = STATUS_LABELS[appointment.status].lower()
        raise invalid_transition(
            f"Lịch hẹn {label} nên không đổi, hủy được nữa.", appointment.status
        )
    if actor.role is UserRole.PATIENT and appointment.start_at - now < timedelta(
        hours=deadline_hours
    ):
        raise change_deadline_passed(deadline_hours, clinic_phone)


def can_change(
    appointment: Appointment, actor: Actor, now: datetime, change_deadline: timedelta
) -> bool:
    """Lịch BOOKED; bệnh nhân là chủ lịch và còn ít nhất 2 giờ (BR-08); quản trị không bị giới hạn
    2 giờ (FR-ADM-03)."""
    if appointment.status is not AppointmentStatus.BOOKED:
        return False
    if actor.role is UserRole.ADMIN:
        return True
    return _is_owner(appointment, actor) and appointment.start_at - now >= change_deadline


def ensure_can_set_status_owner(appointment: Appointment, actor: Actor) -> None:
    """Đổi trạng thái: bác sĩ của lịch hoặc quản trị (docs mục 4.6)."""
    if actor.role is UserRole.ADMIN or _is_doctor_of(appointment, actor):
        return
    raise forbidden()


NOTE_STATUSES = (AppointmentStatus.ARRIVED, AppointmentStatus.COMPLETED)


def ensure_can_write_note(appointment: Appointment, actor: Actor) -> None:
    """Ghi chú sau khám: chỉ bác sĩ của lịch; quản trị chỉ xem (docs mục 4.6, FR-DOC-03).

    Chỉ ghi khi bệnh nhân đã đến hoặc đã khám; không giới hạn ngày để bác sĩ ghi nốt sau buổi khám.
    """
    if not _is_doctor_of(appointment, actor):
        raise forbidden()
    if appointment.status not in NOTE_STATUSES:
        raise invalid_transition(
            "Chỉ ghi chú cho lịch hẹn bệnh nhân đã đến hoặc đã khám.", appointment.status
        )


def ensure_valid_status_change(
    appointment: Appointment, actor: Actor, target: AppointmentStatus, now: datetime
) -> None:
    """Sơ đồ ở docs mục 5.5 (409 INVALID_TRANSITION, FR-APT-06), cộng giới hạn thời điểm:

    - bác sĩ chỉ cập nhật lịch trong ngày hôm nay (FR-DOC-02); quản trị sửa được cả ngày đã qua;
    - không ai cập nhật lịch của ngày chưa tới; chỉ đánh Vắng mặt khi đã tới giờ khám.
    """
    current = appointment.status
    if not can_transition(current, target):
        raise invalid_transition(
            f"Không thể chuyển lịch hẹn từ “{STATUS_LABELS[current]}” "
            f"sang “{STATUS_LABELS[target]}”.",
            current,
        )
    day, today = to_local(appointment.start_at).date(), to_local(now).date()
    if day > today:
        raise invalid_transition("Lịch hẹn chưa tới ngày khám.", current)
    if actor.role is UserRole.DOCTOR and day != today:
        raise invalid_transition("Bác sĩ chỉ cập nhật trạng thái lịch trong ngày hôm nay.", current)
    if target is AppointmentStatus.NO_SHOW and appointment.start_at > now:
        raise invalid_transition("Chưa tới giờ khám nên chưa thể đánh dấu vắng mặt.", current)
