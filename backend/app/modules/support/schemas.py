"""DTO Pydantic vào/ra của module support: kiểu, độ dài, định dạng."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.db.enums import SupportStatus

MAX_SUMMARY_LENGTH = 1000


class SupportRequestOut(BaseModel):
    id: int
    status: SupportStatus
    created_at: datetime


class SupportPatient(BaseModel):
    """Quản trị cần đủ thông tin để gọi lại bệnh nhân (docs mục 4.6)."""

    id: int
    name: str
    phone: str | None
    email: str


class SupportRequestAdminOut(SupportRequestOut):
    """Một yêu cầu trong hàng chờ của quản trị (FR-ADM-04)."""

    patient: SupportPatient
    summary: str = Field(description="Tóm tắt hội thoại do trợ lý viết")
    handled_by: str | None = Field(description="Quản trị đã xử lý")
    handled_at: datetime | None


class SupportRequestUpdate(BaseModel):
    """Đánh dấu đã xử lý; gửi OPEN để mở lại nếu đánh dấu nhầm."""

    status: Literal[SupportStatus.DONE, SupportStatus.OPEN]
