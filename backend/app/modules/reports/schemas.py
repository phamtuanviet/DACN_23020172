"""DTO Pydantic vào/ra của module reports: đánh giá bác sĩ (FR-RPT-02) và số liệu dashboard
(FR-RPT-01). Kết quả gửi đánh giá dùng `ReviewOut` của module appointments, nơi chi tiết lịch
cũng hiện đánh giá."""

from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.core.validation import no_nul


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = no_nul(value).strip()
    return value or None


ReviewComment = Annotated[str | None, Field(max_length=500), AfterValidator(_optional_text)]


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5, description="Số sao, từ 1 đến 5")
    comment: ReviewComment = Field(default=None, description="Nhận xét, tùy chọn, tối đa 500 ký tự")


# ---------------------------------------------------------------------------- dashboard
class StatusCounts(BaseModel):
    """Số lịch hẹn theo trạng thái hiện tại. `total` là mọi lịch trừ Đã hủy."""

    total: int
    booked: int
    arrived: int
    completed: int
    cancelled: int
    no_show: int


class DayStats(StatusCounts):
    day: date


class DoctorStats(StatusCounts):
    id: int
    name: str


class Rates(BaseModel):
    cancel_rate: float | None = Field(
        description="Đã hủy / mọi lịch có giờ khám trong khoảng (kể cả đã hủy); rỗng khi không có "
        "lịch nào"
    )
    no_show_rate: float | None = Field(
        description="Vắng mặt / (Đã đến + Đã khám + Vắng mặt), tức trên các lịch đã biết kết quả; "
        "rỗng khi chưa có lịch nào như vậy"
    )


class ChannelSplit(BaseModel):
    """Lịch được đặt trong khoảng (theo thời điểm đặt, kể cả lịch sau đó bị hủy), theo kênh."""

    web: int
    agent: int


class StatsOut(BaseModel):
    """Số liệu dashboard (FR-RPT-01, AC-18). Ngày theo giờ Việt Nam; lịch tính theo ngày khám."""

    date_from: date
    date_to: date
    totals: StatusCounts
    rates: Rates
    previous_rates: Rates = Field(description="Cùng số ngày, liền trước khoảng đang xem")
    days: list[DayStats] = Field(description="Đủ mọi ngày trong khoảng, ngày không có lịch là 0")
    doctors: list[DoctorStats] = Field(
        description="Bác sĩ đang hoạt động và bác sĩ có lịch trong khoảng; nhiều lịch nhất trước"
    )
    channels: ChannelSplit
