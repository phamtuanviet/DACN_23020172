"""Đồ thị LangGraph hai node agent ↔ tools (docs mục 6.1).

State chỉ gồm danh sách `messages`; đồ thị chạy không trạng thái mỗi lượt, lịch sử nạp từ bảng
`messages` (TD-22). Node `tools` tự viết để tiêm danh tính bệnh nhân, ghi `tool_call_logs` và đổi
`AppError` thành kết quả lỗi cho LLM. Hai node phát sự kiện tùy biến (stream_mode="custom") mà
service đổi thành SSE: token, trạng thái tool, thẻ dịch vụ, nút khung giờ, thẻ đề xuất (mục 8.4).
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal, cast

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    BaseMessageChunk,
    ToolMessage,
    message_chunk_to_message,
)
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from app.modules.agent.llm import ChatModel
from app.modules.agent.memory import dumps
from app.modules.agent.schemas import ServicesEvent, SlotsEvent, TokenEvent, ToolStatus
from app.modules.agent.tools import TOOLS, AgentContext, end_label, run_tool, running_label

RECURSION_LIMIT = 10  # khoảng 4 vòng gọi tool trong một lượt (docs mục 6.6)
MAX_TOOL_CALLS_PER_STEP = 3  # một câu trả lời của LLM gọi quá số này thì phần thừa bị từ chối
# Ước lượng token của prompt khi lần gọi bị hủy trước khi nhà cung cấp báo số thật: ~3 ký tự tiếng
# Việt một token, cộng phần định nghĩa 6 tool.
CHARS_PER_TOKEN = 3
TOOL_SPEC_TOKENS = 1500

Event = tuple[str, BaseModel]  # tên sự kiện SSE, dữ liệu


@dataclass(frozen=True)
class Runtime:
    """Đặt trong config["configurable"]: phần LLM không nhìn thấy (docs mục 6.3)."""

    ctx: AgentContext
    model: ChatModel


def _runtime(config: RunnableConfig) -> Runtime:
    return cast(Runtime, config.get("configurable", {})["runtime"])


async def _agent(state: MessagesState, config: RunnableConfig) -> dict[str, list[BaseMessage]]:
    """Gọi LLM đã gắn 6 tool, phát từng đoạn chữ ngay khi nhận được (NFR-03)."""
    runtime = _runtime(config)
    write = get_stream_writer()
    full: BaseMessage | None = None
    runtime.ctx.usage.begin_call(estimate_input_tokens(state["messages"]))
    async for chunk in runtime.model.astream(state["messages"]):
        if chunk.text:
            write(("token", TokenEvent(text=chunk.text)))
        if isinstance(full, BaseMessageChunk) and isinstance(chunk, BaseMessageChunk):
            full = full + chunk
        else:
            full = chunk
    message = message_chunk_to_message(full) if full is not None else AIMessage(content="")
    runtime.ctx.usage.add(message.usage_metadata if isinstance(message, AIMessage) else None)
    return {"messages": [message]}


async def _tools(state: MessagesState, config: RunnableConfig) -> dict[str, list[BaseMessage]]:
    """Chạy lần lượt các lời gọi tool của lượt LLM vừa rồi."""
    runtime = _runtime(config)
    write = get_stream_writer()
    last = state["messages"][-1]
    calls = last.tool_calls if isinstance(last, AIMessage) else []
    results: list[BaseMessage] = [
        # Nhà cung cấp cần đủ kết quả cho mọi lời gọi; phần vượt trần không được chạy.
        ToolMessage(content=dumps(TOO_MANY_CALLS), tool_call_id=call.get("id") or "", name="")
        for call in calls[MAX_TOOL_CALLS_PER_STEP:]
    ]
    for call in calls[:MAX_TOOL_CALLS_PER_STEP]:
        name = call["name"]
        shown = name if name in TOOLS else "unknown"  # tên lạ do LLM bịa không ra giao diện
        write(("tool", ToolStatus(name=shown, status="start", label=running_label(name))))
        result = await run_tool(runtime.ctx, call)
        label = end_label(name, call.get("args") or {}, result.data)
        write(("tool", ToolStatus(name=shown, status="end", label=label, ok=result.ok)))
        if result.services:
            write(("services", ServicesEvent(services=result.services)))
        if result.slots:
            write(("slots", SlotsEvent(slots=result.slots)))
        if result.proposal:
            write(("proposal", result.proposal))
        results.append(
            ToolMessage(content=dumps(result.data), tool_call_id=call.get("id") or "", name=name)
        )
    return {"messages": results}


TOO_MANY_CALLS = {
    "error": "TOO_MANY_TOOL_CALLS",
    "message": f"Mỗi lượt chỉ gọi tối đa {MAX_TOOL_CALLS_PER_STEP} tool; gọi lần lượt.",
}


def estimate_input_tokens(messages: Sequence[BaseMessage]) -> int:
    return sum(len(m.text) for m in messages) // CHARS_PER_TOKEN + TOOL_SPEC_TOKENS


def _route(state: MessagesState) -> Literal["tools", "__end__"]:
    last = state["messages"][-1]
    return "tools" if isinstance(last, AIMessage) and last.tool_calls else "__end__"


@lru_cache(maxsize=1)
def agent_graph() -> CompiledStateGraph[Any, Any, Any, Any]:
    builder = StateGraph(MessagesState)
    builder.add_node("agent", _agent)
    builder.add_node("tools", _tools)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", _route, ["tools", END])
    builder.add_edge("tools", "agent")
    return builder.compile()


async def run_graph(
    model: ChatModel, ctx: AgentContext, messages: list[BaseMessage]
) -> AsyncIterator[Event]:
    """Sự kiện của một lượt chat, theo đúng thứ tự phát sinh."""
    config: RunnableConfig = {
        "recursion_limit": RECURSION_LIMIT,
        "configurable": {"runtime": Runtime(ctx, model)},
    }
    async for part in agent_graph().astream(
        {"messages": messages}, config, stream_mode="custom", version="v2"
    ):
        if part["type"] == "custom":
            yield cast(Event, part["data"])
