"""DTO của module appointments (FR-APT-01..06, docs mục 8.2, 8.3)."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, AwareDatetime, BaseModel, Field

from app.core.validation import MAX_ID, no_nul, reasonable_datetime
from app.db.enums import AppointmentStatus, Channel, HistoryAction, UserRole
from app.modules.catalog.schemas import DoctorRef


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = no_nul(value).strip()
    return value or None


Reason = Annotated[str | None, Field(max_length=500), AfterValidator(_optional_text)]
DoctorNote = Annotated[str | None, Field(max_length=1000), AfterValidator(_optional_text)]
SlotStart = Annotated[AwareDatetime, AfterValidator(reasonable_datetime)]


class Scope(StrEnum):
    """Sắp tới: lịch Đã đặt, Đã đến chưa kết thúc. Lịch sử: mọi lịch còn lại (FR-APT-04)."""

    UPCOMING = "upcoming"
    HISTORY = "history"


class BookRequest(BaseModel):
    service_id: int = Field(ge=1, le=MAX_ID)
    doctor_id: int | None = Field(
        default=None, ge=1, le=MAX_ID, description="Bỏ trống: bác sĩ bất kỳ"
    )
    start_at: SlotStart = Field(description="Giờ bắt đầu của một khung do /availability trả về")
    reason: Reason = Field(default=None, description="Lý do khám, tùy chọn, tối đa 500 ký tự")


class RescheduleRequest(BaseModel):
    """Đổi lịch giữ nguyên dịch vụ và mã lịch (UC06).

    `doctor_id` bắt buộc, kể cả khi giữ bác sĩ cũ: khung giờ người dùng chọn thuộc lưới của đúng
    bác sĩ đó, và service khóa bác sĩ này trước khi khóa lịch hẹn (docs mục 5.4).
    """

    start_at: SlotStart = Field(description="Giờ bắt đầu của một khung do /availability trả về")
    doctor_id: int = Field(
        ge=1, le=MAX_ID, description="Bác sĩ hiện tại hoặc một bác sĩ khác cùng dịch vụ"
    )


class CancelRequest(BaseModel):
    reason: Reason = Field(default=None, description="Lý do hủy, tùy chọn, tối đa 500 ký tự")


class StatusChangeRequest(BaseModel):
    """Hủy lịch đi qua `/cancel` để có lý do và email; endpoint này chỉ dành cho buổi khám."""

    status: Literal[
        AppointmentStatus.ARRIVED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW
    ]


class NoteRequest(BaseModel):
    """Ghi chú sau khám, tối đa 1.000 ký tự; gửi rỗng hoặc null để xóa (FR-DOC-03). Trường bắt
    buộc: body thiếu `note` (gõ sai tên trường) bị từ chối thay vì âm thầm xóa ghi chú."""

    note: DoctorNote = Field(description="Bệnh nhân xem được ghi chú này")


class AttentionRequest(BaseModel):
    """Gỡ cờ "cần xử lý" sau khi đã liên hệ bệnh nhân, hoặc tự gắn cờ cho lịch Đã đặt
    (FR-ADM-04)."""

    needs_attention: bool


class ServiceRef(BaseModel):
    id: int
    name: str


class AppointmentOut(BaseModel):
    id: int
    code: str = Field(description="Mã lịch hẹn LH-YYMMDD-XXXX")
    status: AppointmentStatus
    channel: Channel
    service: ServiceRef
    doctor: DoctorRef
    start_at: datetime
    end_at: datetime
    can_change: bool = Field(description="Người gọi còn đổi, hủy được không (BR-08)")
    change_until: datetime | None = Field(
        description="Hạn đổi, hủy trực tuyến của bệnh nhân (giờ khám − 2 giờ); rỗng khi không còn "
        "là lịch Đã đặt"
    )


class AppointmentPage(BaseModel):
    items: list[AppointmentOut]
    total: int
    page: int
    page_size: int


class PatientBrief(BaseModel):
    """Bác sĩ chỉ thấy họ tên và tuổi, không thấy email, số điện thoại (docs mục 4.6)."""

    id: int
    name: str
    age: int | None = Field(description="Tuổi tính từ ngày sinh")


class HistoryState(BaseModel):
    status: AppointmentStatus | None = None
    doctor: DoctorRef | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    needs_attention: bool | None = None


class HistoryEntry(BaseModel):
    """Một dòng lịch sử thay đổi: ai, khi nào, kênh nào, cũ → mới (FR-APT-05)."""

    action: HistoryAction
    channel: Channel
    actor_role: UserRole | None = Field(description="Rỗng: tác vụ hệ thống")
    by_me: bool = Field(description="Người đang xem chính là người thao tác")
    created_at: datetime
    old: HistoryState | None
    new: HistoryState | None


class PastVisit(BaseModel):
    """Lần khám trước của cùng bệnh nhân với chính bác sĩ đang xem (D-detail)."""

    id: int
    start_at: datetime
    service: ServiceRef
    status: AppointmentStatus
    doctor_note: str | None


class AppointmentDetail(AppointmentOut):
    reason: str | None
    cancel_reason: str | None
    doctor_note: str | None
    needs_attention: bool = Field(description="Bác sĩ nghỉ hoặc đổi ca: phòng khám sẽ liên hệ")
    patient: PatientBrief
    created_at: datetime
    history: list[HistoryEntry]
    previous_visits: list[PastVisit] = Field(
        description="Chỉ khi bác sĩ của lịch xem: các lần khám trước của bệnh nhân với chính bác "
        "sĩ đó, mới nhất trước; người khác nhận danh sách rỗng"
    )


# ---------------------------------------------------------------------------- lịch khám của bác sĩ
class ScheduleAppointment(BaseModel):
    """Một lịch trong lịch khám của bác sĩ: không có email, số điện thoại (docs mục 4.6)."""

    id: int
    code: str
    status: AppointmentStatus
    channel: Channel
    service: ServiceRef
    start_at: datetime
    end_at: datetime
    patient: PatientBrief
    reason: str | None
    has_note: bool


class TimeBlock(BaseModel):
    start_at: datetime
    end_at: datetime


class TimeOffBlock(TimeBlock):
    reason: str | None


class DoctorScheduleOut(BaseModel):
    """Lịch khám theo ngày hoặc tuần (FR-DOC-01, UC12): lịch ở mọi trạng thái, giờ làm theo ca,
    ngày nghỉ."""

    date_from: date
    date_to: date
    appointments: list[ScheduleAppointment]
    work: list[TimeBlock] = Field(description="Giờ làm từng ngày, trải từ ca làm lặp hằng tuần")
    time_offs: list[TimeOffBlock] = Field(description="Ngày nghỉ chồng khoảng đang xem")
    upcoming_time_offs: list[TimeOffBlock] = Field(description="Tối đa 3 ngày nghỉ sắp tới")


# ---------------------------------------------------------------------------- quản trị
class AttentionSource(StrEnum):
    """Vì sao lịch bị gắn cờ: ngày nghỉ, sửa hoặc xóa ca (BR-10), hoặc quản trị tự gắn."""

    TIME_OFF = "TIME_OFF"
    SHIFT_CHANGE = "SHIFT_CHANGE"
    SHIFT_DELETE = "SHIFT_DELETE"
    MANUAL = "MANUAL"


class PatientContact(BaseModel):
    """Quản trị thấy đủ thông tin liên hệ của bệnh nhân (docs mục 4.6)."""

    id: int
    name: str
    phone: str | None
    email: str


class AdminAppointmentOut(AppointmentOut):
    patient: PatientContact
    needs_attention: bool
    attention_source: AttentionSource | None = Field(
        description="Nguồn của lần gắn cờ gần nhất; rỗng khi chưa từng gắn cờ"
    )


class AdminAppointmentPage(BaseModel):
    items: list[AdminAppointmentOut]
    total: int
    page: int
    page_size: int
