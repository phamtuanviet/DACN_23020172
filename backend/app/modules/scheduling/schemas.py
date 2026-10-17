"""DTO của module scheduling: khung trống theo ngày, ngày gần nhất, khung sớm nhất (mục 8.3)."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.modules.catalog.schemas import DoctorRef


class ServiceSummary(BaseModel):
    id: int
    name: str
    duration_min: int


class DayStatus(StrEnum):
    OPEN = "OPEN"  # còn khung trống
    FULL = "FULL"  # có giờ làm nhưng đã kín hoặc đã qua giờ
    OFF = "OFF"  # không có ca làm, hoặc nghỉ cả ngày


class SlotOut(BaseModel):
    start_at: datetime
    end_at: datetime
    doctors: list[DoctorRef] = Field(
        description="Bác sĩ còn trống ở khung này; người đầu tiên là người được chọn khi đặt "
        "với “Bác sĩ bất kỳ” (ít lịch nhất trong ngày)"
    )


class DayOut(BaseModel):
    date: date
    status: DayStatus
    slots: list[SlotOut]


class AvailabilityOut(BaseModel):
    service: ServiceSummary
    days: list[DayOut]
    nearest_dates: list[date] = Field(
        description="Tối đa 3 ngày gần nhất sau khoảng được hỏi còn khung, chỉ có khi khoảng "
        "được hỏi đã kín (FR-SCH-05)"
    )


class EarliestItem(BaseModel):
    service_id: int
    doctor: DoctorRef
    start_at: datetime
    end_at: datetime


class EarliestOut(BaseModel):
    items: list[EarliestItem]


class Alternative(BaseModel):
    """Khung thay thế kèm lỗi SLOT_TAKEN (docs mục 4.7)."""

    doctor_id: int
    start_at: datetime
    end_at: datetime
