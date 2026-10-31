"""6 tool của Agent — lớp mỏng gọi service, lấy danh tính từ AgentContext (docs mục 6.3).

Không tool nào nhận `patient_id`: danh tính lấy từ `AgentContext` mà server đặt vào config của
LangGraph, phần LLM không nhìn thấy. Mọi tool đi qua `@agent_tool`: kiểm tra tham số bằng
Pydantic, đo thời gian, đổi `AppError` thành kết quả lỗi có cấu trúc cho LLM, ghi một dòng
`tool_call_logs` (FR-AGT-08) và một dòng TOOL vào `messages` để lượt sau dùng lại kết quả.
"""

import time as perf
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import date, time
from typing import Any, Literal

import structlog
from langchain_core.messages import ToolCall
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.actor import Actor
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import AppError
from app.core.timeutil import format_day
from app.core.validation import MAX_ID, ReasonableDate
from app.db.enums import Channel, MessageRole, ProposalType, UserRole
from app.modules.agent import repository as repo
from app.modules.agent.guard import Usage
from app.modules.agent.memory import tool_row
from app.modules.agent.proposals import TYPE_LABELS, ProposalService, ProposeArgs
from app.modules.agent.schemas import ProposalOut, ServiceOption
from app.modules.appointments.schemas import Scope
from app.modules.appointments.service import AppointmentService
from app.modules.catalog.schemas import ServiceOut
from app.modules.catalog.service import CatalogService
from app.modules.scheduling.schemas import SlotOption
from app.modules.scheduling.service import SchedulingService, SlotSearch
from app.modules.support.service import SupportService

log = structlog.get_logger(__name__)

SERVICE_LIMIT = 5
DOCTOR_LIMIT = 10
APPOINTMENT_LIMIT = 10
MAX_SLOT_RANGE_DAYS = 14
# Buổi do LLM chọn được đổi thành khoảng giờ ở backend; LLM không tự đặt giờ (docs mục 6.3).
PARTS_OF_DAY = {
    "morning": (time(7, 0), time(12, 0)),
    "afternoon": (time(12, 0), time(17, 0)),
    "evening": (time(17, 0), time(21, 0)),
}
PART_LABELS = {"morning": "sáng", "afternoon": "chiều", "evening": "tối"}


@dataclass
class AgentContext:
    """Ngữ cảnh phía server của một lượt chat; LLM không thấy và không sửa được."""

    patient_id: int
    conversation_id: uuid.UUID
    clock: Clock
    settings: Settings
    sessions: async_sessionmaker[AsyncSession]
    usage: Usage = field(default_factory=Usage)
    tool_calls: int = 0

    @property
    def actor(self) -> Actor:
        return Actor(user_id=self.patient_id, role=UserRole.PATIENT, channel=Channel.AGENT)


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    data: dict[str, Any]  # trả cho LLM, lưu vào messages và tool_call_logs
    services: list[ServiceOption] | None = None  # để giao diện vẽ thẻ dịch vụ
    slots: list[SlotOption] | None = None  # nút chọn khung giờ
    proposal: ProposalOut | None = None  # thẻ xác nhận


Handler = Callable[[AgentContext, Any], Awaitable[ToolResult]]
Describe = Callable[[dict[str, Any], dict[str, Any]], str]


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    args: type[BaseModel]
    running: str  # nhãn "Đang tìm khung giờ trống…"
    failed: str  # nhãn khi tool trả lỗi
    describe: Describe  # nhãn khi xong, tính từ tham số và kết quả (cả khi tải lại hội thoại)
    handler: Handler

    def spec(self) -> dict[str, Any]:
        """Định nghĩa tool dạng OpenAI; LangChain đổi sang định dạng của nhà cung cấp khác."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": _without_titles(self.args.model_json_schema()),
            },
        }


TOOLS: dict[str, AgentTool] = {}


def agent_tool(
    name: str, *, args: type[BaseModel], running: str, failed: str, describe: Describe
) -> Callable[[Handler], Handler]:
    """Đăng ký tool; docstring của hàm là mô tả gửi cho LLM."""

    def register(handler: Handler) -> Handler:
        description = " ".join((handler.__doc__ or "").split())
        TOOLS[name] = AgentTool(name, description, args, running, failed, describe, handler)
        return handler

    return register


def _without_titles(schema: Any) -> Any:
    """Bỏ "title" Pydantic tự sinh: thừa token, không giúp mô hình chọn tham số."""
    if isinstance(schema, dict):
        return {k: _without_titles(v) for k, v in schema.items() if k != "title"}
    if isinstance(schema, list):
        return [_without_titles(v) for v in schema]
    return schema


def tool_specs() -> list[dict[str, Any]]:
    return [tool.spec() for tool in TOOLS.values()]


def end_label(name: str, args: dict[str, Any], data: dict[str, Any]) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return "Chưa thực hiện được"
    if "error" in data:
        return tool.failed
    return tool.describe(args, data)


def running_label(name: str) -> str:
    tool = TOOLS.get(name)
    return tool.running if tool else "Đang xử lý…"


async def run_tool(ctx: AgentContext, call: ToolCall) -> ToolResult:
    """Chạy một lời gọi tool của LLM; mọi lỗi đều thành kết quả có cấu trúc, không ném ra ngoài."""
    name = call["name"]
    raw_args = jsonb_safe(call.get("args") or {})
    tool = TOOLS.get(name)
    # Tên tool do LLM sinh: tên lạ có thể là chữ người dùng ép mô hình viết, không ghi vào log.
    known = name if tool else "unknown"
    started = perf.perf_counter()
    if tool is None:
        result = ToolResult(False, {"error": "UNKNOWN_TOOL", "message": "Không có tool này."})
    else:
        try:
            result = await tool.handler(ctx, tool.args.model_validate(raw_args))
        except ValidationError as exc:
            result = ToolResult(False, _validation_data(exc))
        except AppError as err:
            result = ToolResult(False, {"error": err.code, "message": err.message, **err.details})
        except Exception as exc:  # lỗi ngoài dự kiến không được làm hỏng cả lượt chat
            log.warning("agent.tool_crashed", tool=known, error=type(exc).__name__)
            result = ToolResult(
                False,
                {"error": "INTERNAL_ERROR", "message": "Hệ thống đang gặp sự cố khi tra cứu."},
            )
    result = replace(result, data=jsonb_safe(result.data))
    latency_ms = round((perf.perf_counter() - started) * 1000)
    ctx.tool_calls += 1
    now = ctx.clock.now()
    try:
        async with ctx.sessions() as session, session.begin():
            repo.add_tool_log(
                session,
                ctx.conversation_id,
                tool_name=known if tool is None else name,
                args=raw_args,
                result=result.data,
                success=result.ok,
                latency_ms=latency_ms,
                now=now,
            )
            repo.add_message(
                session,
                ctx.conversation_id,
                MessageRole.TOOL,
                tool_row(str(call.get("id") or uuid.uuid4().hex), name, raw_args, result.data),
                now,
            )
    except SQLAlchemyError as exc:
        # Không lưu được log (database lỗi): lượt chat vẫn tiếp tục, ghi lại để điều tra.
        log.error("agent.tool_log_failed", tool=known, error=type(exc).__name__)
    log.info("agent.tool", tool=known, success=result.ok, latency_ms=latency_ms)
    return result


def jsonb_safe(value: Any) -> Any:
    """PostgreSQL jsonb không nhận ký tự NUL và surrogate lẻ: bỏ chúng khỏi chuỗi do LLM sinh."""
    if isinstance(value, str):
        cleaned = value.replace("\x00", "")
        if _has_surrogate(cleaned):
            cleaned = cleaned.encode("utf-8", "ignore").decode("utf-8")
        return cleaned
    if isinstance(value, dict):
        return {str(jsonb_safe(k)): jsonb_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonb_safe(v) for v in value]
    return value


def _has_surrogate(text: str) -> bool:
    return any("\ud800" <= ch <= "\udfff" for ch in text)


def _validation_data(exc: ValidationError) -> dict[str, Any]:
    return {
        "error": "VALIDATION_ERROR",
        "message": "Tham số không hợp lệ, hãy sửa rồi gọi lại.",
        "fields": [
            {"field": ".".join(str(part) for part in e["loc"]) or "(chung)", "message": e["msg"]}
            for e in exc.errors()
        ],
    }


def _json(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


# ---------------------------------------------------------------------------- tham số
class SearchServicesArgs(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=100,
        description="Từ khóa ngắn: tên dịch vụ, chuyên khoa hoặc từ trong phạm vi khám, ví dụ "
        "'da liễu', 'nhổ răng'. Nhiều triệu chứng thì ngăn cách bằng dấu phẩy: 'đau họng, sốt'",
    )
    specialty_id: int | None = Field(default=None, ge=1, le=MAX_ID)


class SearchDoctorsArgs(BaseModel):
    query: str | None = Field(default=None, max_length=100, description="Tên bác sĩ")
    specialty_id: int | None = Field(default=None, ge=1, le=MAX_ID)
    service_id: int | None = Field(default=None, ge=1, le=MAX_ID)


class FindSlotsArgs(BaseModel):
    service_id: int = Field(ge=1, le=MAX_ID, description="id dịch vụ từ search_services")
    date_from: ReasonableDate = Field(description="Ngày đầu, dạng YYYY-MM-DD")
    date_to: ReasonableDate = Field(description="Ngày cuối, dạng YYYY-MM-DD, cách ngày đầu ≤ 14")
    doctor_id: int | None = Field(
        default=None, ge=1, le=MAX_ID, description="Chỉ khi người dùng muốn một bác sĩ cụ thể"
    )
    part_of_day: Literal["morning", "afternoon", "evening"] | None = Field(
        default=None, description="Buổi: morning 07–12h, afternoon 12–17h, evening 17–21h"
    )
    limit: int = Field(default=5, ge=1, le=10, description="Số khung tối đa")

    @model_validator(mode="after")
    def _range(self) -> "FindSlotsArgs":
        if self.date_to < self.date_from:
            raise ValueError("date_to phải bằng hoặc sau date_from.")
        if (self.date_to - self.date_from).days >= MAX_SLOT_RANGE_DAYS:
            raise ValueError("Mỗi lần chỉ tìm trong tối đa 14 ngày.")
        return self


class MyAppointmentsArgs(BaseModel):
    scope: Literal["upcoming", "history"] = Field(
        default="upcoming", description="upcoming: lịch sắp tới; history: lịch đã qua, đã hủy"
    )


class HandoffArgs(BaseModel):
    summary: str = Field(
        min_length=1,
        max_length=1000,
        description="Tóm tắt ngắn yêu cầu của người dùng cho nhân viên, không chép email, "
        "số điện thoại",
    )


# ---------------------------------------------------------------------------- nhãn trạng thái
def _describe_services(_: dict[str, Any], data: dict[str, Any]) -> str:
    services = data.get("services") or []
    if not services:
        return "Không tìm thấy dịch vụ phù hợp"
    if len(services) == 1:
        return f"Đã tìm dịch vụ: {services[0]['name']}"
    return f"Đã tìm {len(services)} dịch vụ phù hợp"


def _describe_doctors(_: dict[str, Any], data: dict[str, Any]) -> str:
    doctors = data.get("doctors") or []
    return f"Đã tìm {len(doctors)} bác sĩ" if doctors else "Không tìm thấy bác sĩ phù hợp"


def _span(date_from: Any, date_to: Any) -> str:
    try:
        first, last = date.fromisoformat(str(date_from)), date.fromisoformat(str(date_to))
    except ValueError:
        return ""
    return format_day(first) if first == last else f"{first:%d/%m}–{last:%d/%m}"


def _describe_slots(args: dict[str, Any], data: dict[str, Any]) -> str:
    where = " ".join(
        part
        for part in (
            PART_LABELS.get(str(args.get("part_of_day"))),
            _span(args.get("date_from"), args.get("date_to")),
        )
        if part
    )
    found = "Đã tìm khung trống" if data.get("slots") else "Không còn khung trống"
    return f"{found} {where}".strip()


def _describe_appointments(_: dict[str, Any], __: dict[str, Any]) -> str:
    return "Đã xem lịch hẹn của bạn"


def _describe_proposal(_: dict[str, Any], data: dict[str, Any]) -> str:
    kind = str(data.get("type"))
    label = TYPE_LABELS.get(ProposalType(kind)) if kind in ProposalType else None
    return f"Đã tạo đề xuất {label}" if label else "Đã tạo đề xuất"


def _describe_handoff(_: dict[str, Any], __: dict[str, Any]) -> str:
    return "Đã gửi yêu cầu cho nhân viên"


# ---------------------------------------------------------------------------- 6 tool
def _service_option(service: ServiceOut) -> ServiceOption:
    return ServiceOption(
        id=service.id,
        name=service.name,
        specialty=service.specialty.name,
        duration_min=service.duration_min,
        ref_price_vnd=service.ref_price_vnd,
        scope_description=service.scope_description,
    )


@agent_tool(
    "search_services",
    args=SearchServicesArgs,
    running="Đang tìm dịch vụ…",
    failed="Chưa tìm được dịch vụ",
    describe=_describe_services,
)
async def search_services(ctx: AgentContext, args: SearchServicesArgs) -> ToolResult:
    """Tìm dịch vụ khám theo từ khóa trong tên dịch vụ, chuyên khoa hoặc phạm vi khám. Trả tối
    đa 5 dịch vụ kèm chuyên khoa, phạm vi khám, thời lượng, giá tham khảo. Chỉ khớp từ khóa, không
    suy luận bệnh hay chuyên khoa từ triệu chứng."""
    phrases = [p.strip() for p in args.query.split(",") if p.strip()][:SERVICE_LIMIT]
    found: dict[int, ServiceOut] = {}
    async with ctx.sessions() as session:
        catalog = CatalogService(session, ctx.clock)
        for phrase in phrases or [args.query]:
            for service in await catalog.search_services(phrase, args.specialty_id):
                found.setdefault(service.id, service)
    services = [_service_option(s) for s in list(found.values())[:SERVICE_LIMIT]]
    data = {"services": [_json(s) for s in services], "more": len(found) > SERVICE_LIMIT}
    return ToolResult(True, data, services=services)


@agent_tool(
    "search_doctors",
    args=SearchDoctorsArgs,
    running="Đang tìm bác sĩ…",
    failed="Chưa tìm được bác sĩ",
    describe=_describe_doctors,
)
async def search_doctors(ctx: AgentContext, args: SearchDoctorsArgs) -> ToolResult:
    """Tìm bác sĩ theo tên, chuyên khoa hoặc dịch vụ. Trả tối đa 10 bác sĩ: id, họ tên kèm học
    hàm, chuyên khoa, các dịch vụ bác sĩ thực hiện."""
    async with ctx.sessions() as session:
        doctors = await CatalogService(session, ctx.clock).search_doctors(
            args.query, args.specialty_id, args.service_id
        )
    data = {
        "doctors": [
            {
                "id": d.id,
                "name": d.name,
                "specialty": d.specialty.name,
                "services": [s.name for s in d.services],
            }
            for d in doctors[:DOCTOR_LIMIT]
        ]
    }
    return ToolResult(True, data)


@agent_tool(
    "find_available_slots",
    args=FindSlotsArgs,
    running="Đang tìm khung giờ trống…",
    failed="Chưa tìm được khung giờ",
    describe=_describe_slots,
)
async def find_available_slots(ctx: AgentContext, args: FindSlotsArgs) -> ToolResult:
    """Tìm khung giờ trống thật của một dịch vụ trong khoảng ngày (tối đa 14 ngày), lọc theo bác
    sĩ và buổi nếu cần. Mỗi khung có doctor_id, tên bác sĩ, start_at, end_at (giờ Việt Nam) và nhãn
    đọc sẵn. Không còn khung thì có nearest_dates (ngày gần nhất còn khung) và alternatives (tối đa
    3 khung gần nhất, kể cả buổi khác, bác sĩ khác). Chỉ dùng các khung trong kết quả."""
    time_from, time_to = PARTS_OF_DAY.get(args.part_of_day or "", (None, None))
    async with ctx.sessions() as session:
        out = await SchedulingService(session, ctx.clock, ctx.settings).find_slots(
            SlotSearch(
                service_id=args.service_id,
                date_from=args.date_from,
                date_to=args.date_to,
                doctor_id=args.doctor_id,
                time_from=time_from,
                time_to=time_to,
                limit=args.limit,
            )
        )
    data = {
        "service": _json(out.service),
        "slots": [_json(s) for s in out.slots],
        "more": out.more,
        "nearest_dates": [
            {"date": d.isoformat(), "label": format_day(d)} for d in out.nearest_dates
        ],
        "alternatives": [_json(s) for s in out.alternatives],
    }
    return ToolResult(True, data, slots=out.slots or out.alternatives or None)


@agent_tool(
    "get_my_appointments",
    args=MyAppointmentsArgs,
    running="Đang xem lịch hẹn của bạn…",
    failed="Chưa xem được lịch hẹn",
    describe=_describe_appointments,
)
async def get_my_appointments(ctx: AgentContext, args: MyAppointmentsArgs) -> ToolResult:
    """Xem lịch hẹn của chính người đang trò chuyện: sắp tới hoặc lịch sử. Mỗi lịch có id, mã,
    dịch vụ, bác sĩ, thời gian, trạng thái và can_change (còn đổi, hủy trực tuyến được không)."""
    async with ctx.sessions() as session:
        page = await AppointmentService(session, ctx.clock, ctx.settings).list_mine(
            ctx.actor, scope=Scope(args.scope), page_size=APPOINTMENT_LIMIT
        )
    data = {
        "appointments": [
            {
                "id": a.id,
                "code": a.code,
                "service_id": a.service.id,
                "service": a.service.name,
                "doctor_id": a.doctor.id,
                "doctor": a.doctor.name,
                "start_at": a.start_at.isoformat(),
                "end_at": a.end_at.isoformat(),
                "label": f"{format_day(a.start_at.date())}, {a.start_at:%H:%M}–{a.end_at:%H:%M}",
                "status": a.status.value,
                "can_change": a.can_change,
            }
            for a in page.items
        ],
        "total": page.total,
    }
    return ToolResult(True, data)


@agent_tool(
    "propose_booking",
    args=ProposeArgs,
    running="Đang chuẩn bị đề xuất…",
    failed="Chưa tạo được đề xuất",
    describe=_describe_proposal,
)
async def propose_booking(ctx: AgentContext, args: ProposeArgs) -> ToolResult:
    """Tạo đề xuất đặt (BOOK), đổi (RESCHEDULE) hoặc hủy (CANCEL) lịch; giao diện hiện thẻ để
    người dùng bấm Xác nhận. Tool này KHÔNG ghi lịch: lịch chỉ thay đổi khi người dùng xác nhận
    trên thẻ. Đề xuất mới thay thế đề xuất cũ đang chờ. Backend kiểm tra trước khung còn trống và
    quy định; không đạt thì trả lỗi kèm lý do."""
    async with ctx.sessions() as session:
        proposal = await ProposalService(session, ctx.clock, ctx.settings).create(
            ctx.actor, ctx.conversation_id, args
        )
    data = {
        "proposal_id": str(proposal.id),
        "type": proposal.type.value,
        "expires_at": proposal.expires_at.isoformat(),
        "card": _json(proposal.display),
        "note": "Đang chờ người dùng bấm Xác nhận trên thẻ; chưa có lịch nào thay đổi.",
    }
    return ToolResult(True, data, proposal=proposal)


@agent_tool(
    "handoff_to_staff",
    args=HandoffArgs,
    running="Đang chuyển cho nhân viên…",
    failed="Chưa gửi được yêu cầu",
    describe=_describe_handoff,
)
async def handoff_to_staff(ctx: AgentContext, args: HandoffArgs) -> ToolResult:
    """Chuyển yêu cầu cho nhân viên phòng khám kèm tóm tắt hội thoại; yêu cầu vào hàng chờ của
    quản trị và nhân viên sẽ liên hệ lại người dùng."""
    async with ctx.sessions() as session:
        request = await SupportService(session, ctx.clock).create(
            ctx.actor, summary=args.summary, conversation_id=ctx.conversation_id
        )
    data = {
        "support_request_id": request.id,
        "note": "Đã chuyển cho nhân viên; nhân viên sẽ liên hệ lại người dùng.",
    }
    return ToolResult(True, data)
