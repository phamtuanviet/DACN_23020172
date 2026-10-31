"""Mô hình giả theo luật (LLM_PROVIDER=fake): không gọi mạng, không tốn phí, chỉ cho development
và e2e; cấu hình staging, production từ chối giá trị này.

Hiểu vài mẫu câu, đủ để chạy hết đường ống của Agent trên giao diện: tìm dịch vụ → tìm khung →
đề xuất → xác nhận; hủy lịch; gặp nhân viên. Không dùng để đánh giá chất lượng Agent: bộ kịch bản
ở tests/agent_eval chạy với mô hình thật (docs mục 6.7, 12).
"""

import json
import re
import unicodedata
import uuid
from collections.abc import Callable, Iterator, Sequence
from datetime import date, datetime, timedelta
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolCall,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

# Từ khóa (đã bỏ dấu) → từ khóa gửi search_services.
KEYWORDS = {
    "da lieu": "da liễu",
    "tai mui hong": "tai mũi họng",
    "rang": "răng",
    "nhi": "nhi",
    "mat": "mắt",
    "noi tong quat": "nội tổng quát",
    "dinh ky": "định kỳ",
}
WEEKDAYS = {
    "thu hai": 0,
    "thu 2": 0,
    "thu ba": 1,
    "thu 3": 1,
    "thu tu": 2,
    "thu 4": 2,
    "thu nam": 3,
    "thu 5": 3,
    "thu sau": 4,
    "thu 6": 4,
    "thu bay": 5,
    "thu 7": 5,
    "chu nhat": 6,
}
# Buổi so trên chữ có dấu: bỏ dấu thì "tối" trùng "tôi".
PARTS = {"sáng": "morning", "chiều": "afternoon", "tối": "evening"}
HELP = (
    "Mình có thể tìm dịch vụ, tìm giờ trống và giúp bạn đặt, đổi, hủy lịch. "
    "Bạn muốn khám dịch vụ gì, vào ngày nào?"
)


def fold(text: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt: "Thứ Bảy" → "thu bay"."""
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _has(text: str, word: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", text) is not None


def _now(messages: Sequence[BaseMessage]) -> datetime:
    """Đọc "Bây giờ: Thứ Bảy 10/10/2026 09:15" trong prompt hệ thống."""
    for message in messages:
        if isinstance(message, SystemMessage):
            match = re.search(r"(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2})", message.text)
            if match:
                d, m, y, hh, mm = (int(g) for g in match.groups())
                return datetime(y, m, d, hh, mm)
    return datetime(2026, 1, 1)


def _days(text: str, today: date) -> tuple[date, date]:
    if _has(text, "hom nay"):
        return today, today
    if _has(text, "mai"):
        tomorrow = today + timedelta(days=1)
        return tomorrow, tomorrow
    for name, weekday in WEEKDAYS.items():
        if _has(text, name):
            if _has(text, "tuan sau"):
                day = today - timedelta(days=today.weekday()) + timedelta(days=7 + weekday)
            else:
                day = today + timedelta(days=(weekday - today.weekday()) % 7 or 7)
            return day, day
    return today + timedelta(days=1), today + timedelta(days=7)


def _hhmm(text: str) -> str | None:
    match = re.search(r"(?<!\d)(\d{1,2})\s*(?::|h|gio)\s*(\d{2})?(?!\d)", text)
    if not match or int(match.group(1)) > 23:
        return None
    return f"{int(match.group(1)):02d}:{int(match.group(2) or 0):02d}"


def _call(name: str, args: dict[str, Any]) -> AIMessage:
    tool_call: ToolCall = {"name": name, "args": args, "id": f"call_{uuid.uuid4().hex[:12]}"}
    return AIMessage(content="", tool_calls=[tool_call])


def _tool_results(messages: Sequence[BaseMessage], name: str) -> list[dict[str, Any]]:
    """Kết quả (mới nhất trước) của một tool trong cả hội thoại."""
    found: list[dict[str, Any]] = []
    for message in reversed(messages):
        if isinstance(message, ToolMessage) and message.name == name:
            try:
                found.append(json.loads(message.text))
            except ValueError:
                continue
    return found


def _tool_args(messages: Sequence[BaseMessage], name: str) -> dict[str, Any] | None:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                if call["name"] == name:
                    return dict(call["args"])
    return None


class RuleBasedChatModel(BaseChatModel):
    """Mô hình giả: quyết định tool hoặc câu trả lời từ tin nhắn cuối và kết quả tool trước đó."""

    @property
    def _llm_type(self) -> str:
        return "rule-based-fake"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._decide(messages))])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        message = self._decide(messages)
        for index, call in enumerate(message.tool_calls):
            chunk = AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {
                        "name": call["name"],
                        "args": json.dumps(call["args"], ensure_ascii=False),
                        "id": call["id"],
                        "index": index,
                    }
                ],
            )
            yield ChatGenerationChunk(message=chunk)
        for token in re.split(r"(\s+)", message.text):
            if token:
                yield ChatGenerationChunk(message=AIMessageChunk(content=token))

    # ------------------------------------------------------------ luật
    @staticmethod
    def _last_human(messages: Sequence[BaseMessage]) -> str:
        human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        return human.text if human else ""

    def _decide(self, messages: Sequence[BaseMessage]) -> AIMessage:
        text = fold(self._last_human(messages))
        last = messages[-1] if messages else None
        if isinstance(last, ToolMessage):
            try:
                result = json.loads(last.text)
            except ValueError:
                result = {}
            return self._after_tool(str(last.name), result, text, messages)
        return self._first_step(text, messages)

    def _first_step(self, text: str, messages: Sequence[BaseMessage]) -> AIMessage:
        if _has(text, "nhan vien"):
            return _call("handoff_to_staff", {"summary": "Bệnh nhân muốn gặp nhân viên."})
        if _has(text, "huy"):
            return _call("get_my_appointments", {"scope": "upcoming"})
        if "nguoi khac dat" in text:
            args = _tool_args(messages, "find_available_slots")
            if args:
                return _call("find_available_slots", args)
        wanted = _hhmm(text)
        searches = _tool_results(messages, "find_available_slots")
        if wanted and searches:
            for result in searches:
                for slot in [*result.get("slots", []), *result.get("alternatives", [])]:
                    if str(slot.get("start_at", ""))[11:16] == wanted:
                        return _call(
                            "propose_booking",
                            {
                                "action": "BOOK",
                                "service_id": result["service"]["id"],
                                "doctor_id": slot["doctor_id"],
                                "start_at": slot["start_at"],
                            },
                        )
            return AIMessage(content=f"Mình không thấy khung {wanted} trong các khung vừa tìm.")
        for key, keyword in KEYWORDS.items():
            if _has(text, key):
                return _call("search_services", {"query": keyword})
        return AIMessage(content=HELP)

    def _after_tool(
        self, name: str, result: dict[str, Any], text: str, messages: Sequence[BaseMessage]
    ) -> AIMessage:
        if "error" in result:
            return AIMessage(content=f"Mình chưa làm được: {result.get('message', '')}")
        if name == "search_services":
            services = result.get("services") or []
            if not services:
                return AIMessage(content="Mình chưa tìm thấy dịch vụ phù hợp với từ khóa này.")
            first, last = _days(text, _now(messages).date())
            args: dict[str, Any] = {
                "service_id": services[0]["id"],
                "date_from": first.isoformat(),
                "date_to": last.isoformat(),
            }
            asked = unicodedata.normalize("NFC", self._last_human(messages).lower())
            part = next((p for key, p in PARTS.items() if key in asked.split()), None)
            if part:
                args["part_of_day"] = part
            return _call("find_available_slots", args)
        if name == "find_available_slots":
            slots = result.get("slots") or []
            if slots:
                day = str(slots[0]["label"]).split(",")[0]
                listed = ", ".join(f"{s['start_at'][11:16]} ({s['doctor_name']})" for s in slots)
                return AIMessage(
                    content=f"{day} còn các khung: {listed}. Bạn bấm một khung bên dưới để chọn."
                )
            alternatives = [s["label"] for s in result.get("alternatives") or []]
            hint = f" Khung gần nhất: {'; '.join(alternatives)}." if alternatives else ""
            return AIMessage(content=f"Không còn khung trống đúng yêu cầu.{hint}")
        if name == "propose_booking":
            card = result.get("card") or {}
            return AIMessage(
                content=f"Mình đã tạo đề xuất: {card.get('service')}, {card.get('doctor')}, "
                f"{card.get('when')}. Bạn kiểm tra rồi bấm Xác nhận trên thẻ nhé."
            )
        if name == "get_my_appointments":
            changeable = [a for a in result.get("appointments") or [] if a.get("can_change")]
            if _has(text, "huy") and changeable:
                return _call(
                    "propose_booking", {"action": "CANCEL", "appointment_id": changeable[0]["id"]}
                )
            return AIMessage(content="Bạn chưa có lịch nào hủy trực tuyến được.")
        if name == "handoff_to_staff":
            return AIMessage(
                content="Mình đã chuyển yêu cầu, nhân viên phòng khám sẽ liên hệ lại bạn."
            )
        return AIMessage(content=HELP)
