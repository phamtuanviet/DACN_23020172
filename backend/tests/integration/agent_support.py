"""Hạ tầng test Agent: LLM giả theo kịch bản, đọc luồng SSE, cấu hình riêng cho từng test.

Test hằng ngày không gọi LLM thật (docs mục 12): mô hình giả trả lần lượt các câu trả lời viết sẵn
(gọi tool hoặc chữ), nên kiểm được đường ống tool, SSE, đề xuất mà không tốn phí.
"""

import asyncio
import json
import re
import uuid
from collections.abc import AsyncIterator, Callable, Sequence
from typing import Any

import httpx
import openai
from fastapi import FastAPI
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolCall
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import Field, SecretStr

from app.core.config import Environment, Settings, get_settings
from app.core.security import get_app_settings
from app.modules.agent.llm import get_chat_model


class ScriptedModel(BaseChatModel):
    """Trả lần lượt các AIMessage trong `script`; ghi lại tin nhắn mỗi lần được gọi."""

    script: list[AIMessage] = Field(default_factory=list)
    received: list[list[BaseMessage]] = Field(default_factory=list)
    error: str | None = None  # gọi là ném lỗi kết nối, như nhà cung cấp LLM gặp sự cố
    crash: bool = False  # lỗi của chính hệ thống, không phải của nhà cung cấp
    delay_s: float = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        return self

    def _next(self, messages: list[BaseMessage]) -> AIMessage:
        self.received.append(list(messages))
        if self.error:
            request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            raise openai.APIConnectionError(message=self.error, request=request)
        if self.crash:
            raise RuntimeError("lỗi nội bộ")
        assert self.script, "kịch bản của LLM giả đã hết"
        return self.script.pop(0)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next(messages))])

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        message = self._next(messages)
        for token in re.split(r"(\s+)", message.text):
            if token:
                yield ChatGenerationChunk(message=AIMessageChunk(content=token))
        for index, call in enumerate(message.tool_calls):
            yield ChatGenerationChunk(
                message=AIMessageChunk(
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
            )
        yield ChatGenerationChunk(
            message=AIMessageChunk(
                content="",
                usage_metadata={"input_tokens": 1000, "output_tokens": 50, "total_tokens": 1050},
            )
        )


def call(name: str, **args: Any) -> AIMessage:
    """Lượt LLM gọi một tool."""
    tool_call: ToolCall = {"name": name, "args": args, "id": f"call_{uuid.uuid4().hex[:8]}"}
    return AIMessage(content="", tool_calls=[tool_call])


def say(text: str) -> AIMessage:
    return AIMessage(content=text)


def parse_sse(body: str) -> list[tuple[str, Any]]:
    """`event: x` + `data: {...}` → [(x, dữ liệu)]; bỏ dòng chú thích `: ping`."""
    events: list[tuple[str, Any]] = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        name, data = "message", []
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
        if data:
            events.append((name, json.loads("\n".join(data))))
    return events


def agent_settings(**overrides: Any) -> Settings:
    """Valkey database 15 riêng cho test: ngắt mạch, bộ đếm chi phí không đụng tới máy dev."""
    base = get_settings().valkey_url.get_secret_value().rsplit("/", 1)[0]
    values: dict[str, Any] = {
        "app_env": Environment.DEVELOPMENT,
        "valkey_url": SecretStr(f"{base}/15"),
        "clinic_phone": "028 3822 0000",
        **overrides,
    }
    return Settings(_env_file=None, **values)


def use_agent(app: FastAPI, model: BaseChatModel | None, settings: Settings) -> None:
    app.dependency_overrides[get_chat_model] = lambda: model
    app.dependency_overrides[get_app_settings] = lambda: settings
