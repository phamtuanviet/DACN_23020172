"""DTO của module catalog (FR-CAT-01..05).

Đọc công khai trả dữ liệu đang hoạt động; quản trị thấy cả mục đã ẩn (`is_active`). Danh mục
không có xóa cứng: ẩn bằng `is_active = false` (FR-CAT-05, SRS mục 6.3).
"""

from datetime import time
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field
from pydantic_core import PydanticCustomError

from app.core.validation import DbId, no_nul
from app.db.enums import Gender

MAX_PRICE_VND = 100_000_000


def _name(value: str) -> str:
    value = " ".join(no_nul(value).split())
    if len(value) < 2:
        raise PydanticCustomError("name", "Tên cần ít nhất 2 ký tự.")
    return value


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = no_nul(value).strip()
    return value or None


def _scope(value: str) -> str:
    value = no_nul(value).strip()
    if len(value) < 10:
        raise PydanticCustomError("scope", "Mô tả phạm vi khám cần ít nhất 10 ký tự.")
    return value


def _duration(value: int) -> int:
    """FR-CAT-02: 10–120 phút, bội số của 5 (khớp CHECK ck_services_duration)."""
    if not 10 <= value <= 120 or value % 5:
        raise PydanticCustomError("duration", "Thời lượng từ 10 đến 120 phút, là bội số của 5.")
    return value


def _price(value: int) -> int:
    if not 0 <= value <= MAX_PRICE_VND:
        raise PydanticCustomError("price", "Giá tham khảo từ 0 đến 100.000.000 ₫.")
    return value


SpecialtyName = Annotated[str, Field(max_length=100), AfterValidator(_name)]
ServiceName = Annotated[str, Field(max_length=150), AfterValidator(_name)]
Description = Annotated[str | None, Field(max_length=2000), AfterValidator(_optional_text)]
Scope = Annotated[str, Field(max_length=2000), AfterValidator(_scope)]
Duration = Annotated[int, AfterValidator(_duration)]
Price = Annotated[int, AfterValidator(_price)]


# ---------------------------------------------------------------------------- đọc công khai
class SpecialtyRef(BaseModel):
    id: int
    name: str


class DoctorRef(BaseModel):
    id: int
    name: str


class ServiceBrief(BaseModel):
    id: int
    name: str
    duration_min: int
    ref_price_vnd: int


class SpecialtyOut(BaseModel):
    id: int
    name: str
    description: str | None
    service_count: int = Field(description="Số dịch vụ đang hoạt động")
    doctor_count: int = Field(description="Số bác sĩ đang hoạt động")
    min_price_vnd: int | None = Field(description="Giá tham khảo thấp nhất, để hiện “từ … ₫”")


class ServiceOut(BaseModel):
    id: int
    name: str
    specialty: SpecialtyRef
    scope_description: str
    duration_min: int
    ref_price_vnd: int
    doctors: list[DoctorRef] = Field(description="Bác sĩ đang hoạt động thực hiện dịch vụ")


class DoctorOut(BaseModel):
    id: int
    name: str = Field(description="Họ tên kèm học hàm, ví dụ “ThS. BS. Trần Minh”")
    title: str
    gender: Gender
    specialty: SpecialtyRef
    services: list[ServiceBrief]


class WorkingHours(BaseModel):
    weekday: int = Field(description="1 = Thứ Hai … 7 = Chủ nhật")
    start_time: time
    end_time: time


class DoctorDetail(DoctorOut):
    bio: str | None
    working_hours: list[WorkingHours] = Field(
        description="Ca làm đang hiệu lực, theo giờ địa phương"
    )


# ---------------------------------------------------------------------------- quản trị
class SpecialtyAdminOut(SpecialtyOut):
    is_active: bool


class SpecialtyCreate(BaseModel):
    name: SpecialtyName
    description: Description = None


class SpecialtyUpdate(BaseModel):
    """Chỉ trường được gửi mới đổi; ẩn hoặc hiện lại bằng `is_active`."""

    name: SpecialtyName | None = None
    description: Description = None
    is_active: bool | None = None


class ServiceAdminOut(ServiceOut):
    is_active: bool
    appointment_count: int = Field(description="Số lịch hẹn đã có; khác 0 thì chỉ ẩn được")


class ServiceCreate(BaseModel):
    specialty_id: DbId
    name: ServiceName
    scope_description: Scope
    duration_min: Duration
    ref_price_vnd: Price


class ServiceUpdate(BaseModel):
    """Chỉ trường được gửi mới đổi. Đổi thời lượng không ảnh hưởng lịch đã đặt (giữ `end_at`)."""

    specialty_id: DbId | None = None
    name: ServiceName | None = None
    scope_description: Scope | None = None
    duration_min: Duration | None = None
    ref_price_vnd: Price | None = None
    is_active: bool | None = None
