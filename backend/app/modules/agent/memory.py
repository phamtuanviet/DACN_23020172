"""Nạp và dựng lại lịch sử hội thoại từ bảng messages (docs mục 6.5, TD-22).

Mỗi dòng TOOL lưu `{"call_id", "name", "args", "result"}` và được dựng lại thành cặp "assistant gọi
tool" + "kết quả tool", nên lịch sử gửi cho LLM luôn đúng định dạng tool calling của mọi nhà cung
cấp, cắt ở đâu cũng không làm lẻ cặp.
"""

import json
from collections.abc import Sequence
from typing import Any

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from app.db.enums import MessageRole
from app.db.models.agent import Message

log = structlog.get_logger(__name__)

HISTORY_LIMIT = 20  # dòng gần nhất nạp cho mỗi lượt


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def tool_row(call_id: str, name: str, args: dict[str, Any], result: dict[str, Any]) -> str:
    return dumps({"call_id": call_id, "name": name, "args": args, "result": result})


def parse_tool_row(content: str) -> dict[str, Any] | None:
    try:
        data = json.loads(content)
    except ValueError:
        return None
    if not isinstance(data, dict) or not {"call_id", "name", "result"} <= data.keys():
        return None
    return data


def rebuild(rows: Sequence[Message]) -> list[BaseMessage]:
    """Dòng database → tin nhắn LangChain.

    - Bỏ các dòng đứng trước tin USER đầu tiên của cửa sổ (nhà cung cấp cần mở đầu bằng người
      dùng, và một cặp tool không được thiếu lời gọi).
    - Hai dòng ASSISTANT liền nhau (câu trả lời và thông báo xác nhận) gộp làm một.
    """
    messages: list[BaseMessage] = []
    started = False
    for row in rows:
        if not started and row.role is not MessageRole.USER:
            continue
        started = True
        if row.role is MessageRole.USER:
            messages.append(HumanMessage(content=row.content))
        elif row.role is MessageRole.ASSISTANT:
            previous = messages[-1] if messages else None
            if isinstance(previous, AIMessage) and not previous.tool_calls:
                messages[-1] = AIMessage(content=f"{previous.text}\n\n{row.content}")
            else:
                messages.append(AIMessage(content=row.content))
        else:
            data = parse_tool_row(row.content)
            if data is None:
                log.warning("agent.bad_tool_row", message_id=row.id)
                continue
            call_id, name = str(data["call_id"]), str(data["name"])
            args = data.get("args") if isinstance(data.get("args"), dict) else {}
            messages.append(
                AIMessage(content="", tool_calls=[{"id": call_id, "name": name, "args": args}])
            )
            messages.append(
                ToolMessage(content=dumps(data["result"]), tool_call_id=call_id, name=name)
            )
    return messages
