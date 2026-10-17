"""DTO của module schedule: ca làm lặp hằng tuần, ngày nghỉ, lịch bị ảnh hưởng (FR-ADM-02, BR-10).

Ca làm lưu giờ địa phương của phòng khám (docs mục 7.6), chính xác đến phút.
"""

from datetime import date, datetime, time
from typing import Annotated

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    Field,
    ValidationInfo,
    field_validator,
)
from pydantic_core import PydanticCustomError

from app.core.validation import no_nul, reasonable_datetime


def _weekday(value: int) -> int:
    if not 1 <= value <= 7:
        raise PydanticCustomError("weekday", "Thứ trong tuần từ 1 (Thứ Hai) đến 7 (Chủ nhật).")
    return value


def _clock_time(value: time) -> time:
    if value.tzinfo is not None:
        raise PydanticCustomError("time_tz", "Giờ ca làm là giờ địa phương, không kèm múi giờ.")
    if value.second or value.microsecond:
        raise PydanticCustomError("time_minute", "Giờ ca làm chỉ tính đến phút.")
    return value


def _reason(value: str | None) -> str | None:
    if value is None:
        return None
    value = no_nul(value).strip()
    return value or None


Weekday = Annotated[int, AfterValidator(_weekday)]
ClockTime = Annotated[time, AfterValidator(_clock_time)]


class ShiftIn(BaseModel):
    weekday: Weekday = Field(description="1 = Thứ Hai … 7 = Chủ nhật")
    start_time: ClockTime
    end_time: ClockTime
    valid_from: date
    valid_to: date | None = Field(default=None, description="Bỏ trống: không hết hạn")

    @field_validator("end_time")
    @classmethod
    def _end_after_start(cls, value: time, info: ValidationInfo) -> time:
        start = info.data.get("start_time")
        if start is not None and value <= start:
            raise PydanticCustomError("time_order", "Giờ kết thúc phải sau giờ bắt đầu.")
        return value

    @field_validator("valid_to")
    @classmethod
    def _valid_range(cls, value: date | None, info: ValidationInfo) -> date | None:
        valid_from = info.data.get("valid_from")
        if value is not None and valid_from is not None and value < valid_from:
            raise PydanticCustomError(
                "valid_range", "Ngày hết hiệu lực không được trước ngày bắt đầu."
            )
        return value


class ShiftUpdate(BaseModel):
    """Chỉ trường được gửi mới đổi; sau khi gộp với ca hiện tại được kiểm lại như ShiftIn."""

    weekday: Weekday | None = None
    start_time: ClockTime | None = None
    end_time: ClockTime | None = None
    valid_from: date | None = None
    valid_to: date | None = None


class ShiftOut(BaseModel):
    id: int
    doctor_id: int
    weekday: int
    start_time: time
    end_time: time
    valid_from: date
    valid_to: date | None


class TimeOffIn(BaseModel):
    start_at: Annotated[AwareDatetime, AfterValidator(reasonable_datetime)]
    end_at: Annotated[AwareDatetime, AfterValidator(reasonable_datetime)]
    reason: Annotated[str | None, Field(max_length=255), AfterValidator(_reason)] = None

    @field_validator("end_at")
    @classmethod
    def _end_after_start(cls, value: datetime, info: ValidationInfo) -> datetime:
        start = info.data.get("start_at")
        if start is not None and value <= start:
            raise PydanticCustomError(
                "time_order", "Thời điểm kết thúc phải sau thời điểm bắt đầu."
            )
        return value


class TimeOffOut(BaseModel):
    id: int
    doctor_id: int
    start_at: datetime
    end_at: datetime
    reason: str | None


class AffectedOut(BaseModel):
    """Lịch BOOKED sắp tới bị ảnh hưởng: nằm trong ngày nghỉ hoặc không còn nằm trong ca nào."""

    id: int
    code: str
    start_at: datetime
    end_at: datetime
    service_name: str
    patient_name: str
    needs_attention: bool


class ShiftChangeOut(BaseModel):
    dry_run: bool
    shift: ShiftOut | None = Field(description="Ca sau khi sửa; rỗng khi xóa")
    affected: list[AffectedOut]


class TimeOffChangeOut(BaseModel):
    dry_run: bool
    time_off: TimeOffOut | None = Field(description="Rỗng khi dry_run")
    affected: list[AffectedOut]
