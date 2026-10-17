"""DTO của module appointments (FR-APT-01, docs mục 8.3)."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, Field

from app.core.validation import MAX_ID, no_nul
from app.db.enums import AppointmentStatus, Channel
from app.modules.catalog.schemas import DoctorRef


def _reason(value: str | None) -> str | None:
    if value is None:
        return None
    value = no_nul(value).strip()
    return value or None


Reason = Annotated[str | None, Field(max_length=500), AfterValidator(_reason)]


class BookRequest(BaseModel):
    service_id: int = Field(ge=1, le=MAX_ID)
    doctor_id: int | None = Field(
        default=None, ge=1, le=MAX_ID, description="Bỏ trống: bác sĩ bất kỳ"
    )
    start_at: AwareDatetime = Field(description="Giờ bắt đầu của một khung do /availability trả về")
    reason: Reason = Field(default=None, description="Lý do khám, tùy chọn, tối đa 500 ký tự")


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
    can_change: bool = Field(description="Bệnh nhân còn đổi, hủy được không (BR-08)")
