"""Các phần thuần của Agent: prompt, dựng lịch sử, tham số tool, nhãn trạng thái, mô hình giả."""

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import ValidationError

from app.core.config import Environment, Settings
from app.db.enums import MessageRole
from app.db.models.agent import Message
from app.modules.agent.fake_llm import RuleBasedChatModel, _days, fold
from app.modules.agent.memory import rebuild, tool_row
from app.modules.agent.prompts import PROMPT_VERSION, static_prompt, time_context
from app.modules.agent.proposals import ProposeArgs
from app.modules.agent.tools import TOOLS, FindSlotsArgs, end_label, tool_specs

SAIGON = ZoneInfo("Asia/Ho_Chi_Minh")


def _row(role: MessageRole, content: str, row_id: int = 1) -> Message:
    return Message(id=row_id, role=role, content=content)


# ---------------------------------------------------------------------------- prompt
def test_time_context_turns_next_week_into_dates() -> None:
    """Docs mục 6.2: bảng 14 ngày để "thứ Bảy tuần sau" (từ Thứ Bảy 10/10) thành 17/10."""
    text = time_context(datetime(2026, 10, 10, 9, 15, tzinfo=SAIGON))
    assert "Bây giờ: Thứ Bảy 10/10/2026 09:15" in text
    assert "- Thứ Bảy 10/10/2026 = 2026-10-10 (tuần này, hôm nay)" in text
    assert "- Chủ nhật 11/10/2026 = 2026-10-11 (tuần này, ngày mai)" in text
    assert "- Thứ Bảy 17/10/2026 = 2026-10-17 (tuần sau)" in text
    assert text.count("\n- ") == 14


def test_time_context_from_monday_still_covers_next_week() -> None:
    text = time_context(datetime(2026, 10, 12, 8, 0, tzinfo=SAIGON))
    assert "- Chủ nhật 25/10/2026 = 2026-10-25 (tuần sau)" in text


def test_static_prompt_carries_clinic_rules_without_patient_data() -> None:
    settings = Settings(_env_file=None, app_env=Environment.DEVELOPMENT, clinic_phone="028 1")
    prompt = static_prompt(settings)
    assert "30 ngày" in prompt and "2 giờ" in prompt and "3 lịch" in prompt
    assert "10 phút" in prompt and "028 1" in prompt
    assert "Không chẩn đoán" in prompt and "115" in prompt
    assert PROMPT_VERSION


# ---------------------------------------------------------------------------- lịch sử
def test_rebuild_pairs_tool_rows_and_starts_with_the_user() -> None:
    args = {"service_id": 3}
    rows = [
        _row(MessageRole.ASSISTANT, "câu trả lời bị cắt khỏi cửa sổ", 1),
        _row(MessageRole.USER, "Khám da liễu", 2),
        _row(MessageRole.TOOL, tool_row("call_1", "search_services", args, {"services": []}), 3),
        _row(MessageRole.ASSISTANT, "Bạn muốn khám ngày nào?", 4),
        _row(MessageRole.ASSISTANT, "Đã đặt lịch LH-261010-AB12.", 5),
    ]
    messages = rebuild(rows)
    assert [type(m) for m in messages] == [HumanMessage, AIMessage, ToolMessage, AIMessage]
    call = messages[1]
    assert isinstance(call, AIMessage) and call.tool_calls[0]["args"] == args
    tool = messages[2]
    assert isinstance(tool, ToolMessage) and tool.tool_call_id == "call_1"
    assert messages[3].text == "Bạn muốn khám ngày nào?\n\nĐã đặt lịch LH-261010-AB12."


def test_rebuild_skips_broken_tool_rows() -> None:
    rows = [_row(MessageRole.USER, "Xin chào"), _row(MessageRole.TOOL, "không phải JSON", 2)]
    assert [type(m) for m in rebuild(rows)] == [HumanMessage]


# ---------------------------------------------------------------------------- tool
def test_tools_never_take_a_patient_id() -> None:
    """Docs mục 6.3: đúng 6 tool, không tool nào nhận patient_id từ LLM."""
    specs = tool_specs()
    assert sorted(s["function"]["name"] for s in specs) == sorted(
        [
            "search_services",
            "search_doctors",
            "find_available_slots",
            "get_my_appointments",
            "propose_booking",
            "handoff_to_staff",
        ]
    )
    for spec in specs:
        assert "patient" not in json.dumps(spec["function"]["parameters"])
        assert spec["function"]["description"]


def test_slot_search_is_limited_to_fourteen_days() -> None:
    FindSlotsArgs(service_id=1, date_from=date(2026, 10, 10), date_to=date(2026, 10, 23))
    with pytest.raises(ValidationError):
        FindSlotsArgs(service_id=1, date_from=date(2026, 10, 10), date_to=date(2026, 10, 24))
    with pytest.raises(ValidationError):
        FindSlotsArgs(service_id=1, date_from=date(2026, 10, 12), date_to=date(2026, 10, 11))


@pytest.mark.parametrize(
    ("args", "valid"),
    [
        (
            {
                "action": "BOOK",
                "service_id": 1,
                "doctor_id": 2,
                "start_at": "2026-10-17T08:00+07:00",
            },
            True,
        ),
        ({"action": "BOOK", "service_id": 1, "start_at": "2026-10-17T08:00+07:00"}, False),
        (
            {"action": "BOOK", "service_id": 1, "doctor_id": 2, "start_at": "2026-10-17T08:00"},
            False,
        ),
        (
            {
                "action": "RESCHEDULE",
                "appointment_id": 5,
                "doctor_id": 2,
                "start_at": "2026-10-17T08:00+07:00",
            },
            True,
        ),
        ({"action": "CANCEL", "appointment_id": 5}, True),
        ({"action": "CANCEL"}, False),
    ],
)
def test_propose_args_follow_the_action(args: dict[str, object], valid: bool) -> None:
    if valid:
        ProposeArgs.model_validate(args)
    else:
        with pytest.raises(ValidationError):
            ProposeArgs.model_validate(args)


def test_status_labels_read_like_the_design() -> None:
    """Thiết kế AI-desktop: "Đã tìm dịch vụ: …", "Đã tìm khung trống sáng Thứ Bảy 17/10"."""
    one = {"services": [{"name": "Khám da liễu tổng quát"}]}
    assert end_label("search_services", {}, one) == "Đã tìm dịch vụ: Khám da liễu tổng quát"
    slots_args = {"date_from": "2026-10-17", "date_to": "2026-10-17", "part_of_day": "morning"}
    found = end_label("find_available_slots", slots_args, {"slots": [{}]})
    assert found == "Đã tìm khung trống sáng Thứ Bảy 17/10"
    none = end_label("find_available_slots", {**slots_args, "part_of_day": None}, {"slots": []})
    assert none == "Không còn khung trống Thứ Bảy 17/10"
    assert end_label("propose_booking", {}, {"type": "CANCEL"}) == "Đã tạo đề xuất hủy lịch"
    assert end_label("propose_booking", {}, {"error": "SLOT_TAKEN"}) == "Chưa tạo được đề xuất"
    assert set(TOOLS) == {s["function"]["name"] for s in tool_specs()}


# ---------------------------------------------------------------------------- mô hình giả
def test_fake_model_understands_relative_days() -> None:
    saturday = date(2026, 10, 10)
    assert fold("Thứ Bảy tuần sau") == "thu bay tuan sau"
    assert _days("thu bay tuan sau", saturday) == (date(2026, 10, 17), date(2026, 10, 17))
    assert _days("chieu mai", saturday) == (date(2026, 10, 11), date(2026, 10, 11))
    assert _days("thu hai", saturday) == (date(2026, 10, 12), date(2026, 10, 12))


def test_fake_model_walks_the_booking_flow() -> None:
    model = RuleBasedChatModel()
    system = SystemMessage(content="Bây giờ: Thứ Bảy 10/10/2026 09:15 (giờ Việt Nam).")
    ask = HumanMessage(content="Tôi muốn khám da liễu sáng thứ Bảy tuần sau")

    first = model.invoke([system, ask])
    assert isinstance(first, AIMessage)
    assert first.tool_calls[0]["name"] == "search_services"
    services = {"services": [{"id": 3, "name": "Khám da liễu tổng quát"}]}
    second = model.invoke(
        [
            system,
            ask,
            first,
            ToolMessage(json.dumps(services), tool_call_id="c1", name="search_services"),
        ]
    )
    assert isinstance(second, AIMessage)
    assert second.tool_calls[0]["args"] == {
        "service_id": 3,
        "date_from": "2026-10-17",
        "date_to": "2026-10-17",
        "part_of_day": "morning",
    }


# ---------------------------------------------------------------------------- chọn mô hình
def test_model_comes_from_settings_without_network() -> None:
    """TD-21: đổi nhà cung cấp, mô hình chỉ bằng biến môi trường; không có khóa thì Agent tạm
    ngưng (503) thay vì lỗi lúc chạy."""
    from pydantic import SecretStr

    from app.core.config import LlmProvider
    from app.modules.agent.llm import build_chat_model, system_message

    base = {"_env_file": None, "app_env": Environment.DEVELOPMENT}
    assert build_chat_model(Settings(**base, llm_api_key=None)) is None
    assert isinstance(
        build_chat_model(Settings(**base, llm_provider=LlmProvider.FAKE)), RuleBasedChatModel
    )
    openai = Settings(**base, llm_api_key=SecretStr("sk-test"))
    first = build_chat_model(openai)
    assert first is not None and build_chat_model(openai) is first  # giữ client giữa các lượt
    assert first.kwargs["parallel_tool_calls"] is False  # type: ignore[attr-defined]
    anthropic = Settings(
        **base,
        llm_provider=LlmProvider.ANTHROPIC,
        llm_model="claude-haiku-5-5",
        llm_api_key=SecretStr("sk-test"),
    )
    assert build_chat_model(anthropic) is not None
    now = datetime(2026, 10, 10, 9, 0, tzinfo=SAIGON)
    cached = system_message(now, anthropic).content
    assert isinstance(cached, list) and cached[0]["cache_control"] == {"type": "ephemeral"}
    assert isinstance(system_message(now, openai).content, str)
