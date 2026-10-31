"""DTO Pydantic vào/ra của module agent: chat SSE, hội thoại, đề xuất (docs mục 6, 8.4)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field

from app.core.validation import no_nul
from app.db.enums import ProposalStatus, ProposalType
from app.modules.appointments.schemas import AppointmentOut
from app.modules.scheduling.schemas import SlotOption

MAX_MESSAGE_LENGTH = 1000  # docs mục 6.6


def _message_text(value: str) -> str:
    value = no_nul(value).strip()
    if not value:
        raise ValueError("Tin nhắn không được để trống.")
    return value


MessageText = Annotated[str, Field(max_length=MAX_MESSAGE_LENGTH), AfterValidator(_message_text)]


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID | None = Field(
        default=None, description="Bỏ trống ở tin nhắn đầu tiên: backend tạo hội thoại mới"
    )
    message: MessageText
    trigger: Literal["proposal_failed"] | None = Field(
        default=None,
        description="Lượt giao diện tự gửi sau khi xác nhận đề xuất thất bại vì khung vừa bị đặt "
        "(docs mục 6.4); backend thay nội dung tin nhắn bằng câu dựng sẵn",
    )


# ---------------------------------------------------------------------------- phần tử hội thoại
class ToolStatus(BaseModel):
    """Dòng trạng thái của một lần gọi tool; chỉ có tên và nhãn, không có tham số (docs mục 8.4)."""

    name: str
    status: Literal["start", "end"]
    label: str
    ok: bool | None = None


class ServiceOption(BaseModel):
    """Dịch vụ khớp từ khóa, hiện thành thẻ có nút "Tìm giờ khám"."""

    id: int
    name: str
    specialty: str
    duration_min: int
    ref_price_vnd: int
    scope_description: str


class ProposalDisplay(BaseModel):
    """Chữ trên thẻ xác nhận, do backend dựng từ dữ liệu đã kiểm tra (không phải chữ của LLM)."""

    service: str
    doctor: str
    when: str = Field(description="Ví dụ “Thứ Bảy, 17/10/2026 · 08:00–08:20”")
    reason: str | None = None
    code: str | None = Field(default=None, description="Mã lịch đang đổi hoặc hủy")
    old_when: str | None = Field(default=None, description="Đổi lịch: giờ cũ")
    old_doctor: str | None = Field(default=None, description="Đổi lịch sang bác sĩ khác")


class ProposalOut(BaseModel):
    id: uuid.UUID
    type: ProposalType
    status: ProposalStatus
    expires_at: datetime
    display: ProposalDisplay
    appointment_id: int | None
    appointment_code: str | None = Field(default=None, description="Mã lịch sau khi xác nhận")
    error: str | None = Field(default=None, description="Lý do khi status = FAILED")


class ChatItem(BaseModel):
    """Một dòng trong khung chat khi tải lại hội thoại (docs mục 9.5)."""

    id: int
    kind: Literal["user", "assistant", "tool"]
    created_at: datetime
    text: str | None = None
    hidden: bool = Field(default=False, description="Lượt tự gửi sau đề xuất thất bại")
    tool: ToolStatus | None = None
    services: list[ServiceOption] | None = None
    slots: list[SlotOption] | None = None
    proposal: ProposalOut | None = None


class ConversationOut(BaseModel):
    id: uuid.UUID
    items: list[ChatItem]
    remaining_quota: int


class AgentStatus(BaseModel):
    available: bool = Field(description="Trợ lý đang nhận tin nhắn (có mô hình, chưa ngắt mạch)")
    daily_limit: int
    remaining_quota: int


class ConfirmOut(BaseModel):
    """Kết quả xác nhận: cùng cấu trúc lịch hẹn của web, kèm trạng thái đề xuất (docs mục 6.4)."""

    proposal: ProposalOut
    appointment: AppointmentOut


# ---------------------------------------------------------------------------- sự kiện SSE
class MetaEvent(BaseModel):
    conversation_id: uuid.UUID
    user_message_id: int


class TokenEvent(BaseModel):
    text: str


class ServicesEvent(BaseModel):
    services: list[ServiceOption]


class SlotsEvent(BaseModel):
    slots: list[SlotOption]


class DoneEvent(BaseModel):
    assistant_message_id: int | None
    remaining_quota: int


class ErrorEvent(BaseModel):
    code: str
    message: str
