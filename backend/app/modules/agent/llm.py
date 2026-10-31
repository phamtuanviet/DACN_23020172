"""Mô hình ngôn ngữ của Agent: chọn nhà cung cấp bằng biến môi trường, gắn 6 tool (TD-20, TD-21).

Mặc định OpenAI gpt-4o-mini; đổi sang Anthropic chỉ cần LLM_PROVIDER, LLM_MODEL. Đổi mô hình hoặc
prompt thì chạy lại bộ kịch bản đánh giá trước khi lên production (docs mục 6.8).
"""

from datetime import datetime
from typing import Annotated

from fastapi import Depends
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from app.core.config import LlmProvider, Settings
from app.core.security import SettingsDep
from app.modules.agent.fake_llm import RuleBasedChatModel
from app.modules.agent.prompts import static_prompt, time_context
from app.modules.agent.tools import tool_specs

ChatModel = Runnable[LanguageModelInput, BaseMessage]

MAX_OUTPUT_TOKENS = 800  # một câu trả lời của trợ lý đặt lịch không cần dài hơn
TEMPERATURE = 0.2  # gọi tool ổn định, ít bịa
_cache: dict[tuple[object, ...], ChatModel] = {}


def build_chat_model(settings: Settings) -> ChatModel | None:
    """Mô hình đã gắn tool; None khi chưa có khóa API (Agent trả 503, phần còn lại vẫn chạy)."""
    if settings.llm_provider is LlmProvider.FAKE:
        return RuleBasedChatModel()
    if settings.llm_api_key is None:
        return None
    key = (
        settings.llm_provider,
        settings.llm_model,
        settings.llm_fallback_model,
        settings.llm_api_key.get_secret_value(),
        settings.llm_timeout_s,
    )
    if key not in _cache:  # giữ client HTTP giữa các lượt chat, khỏi bắt tay TLS lại
        model = _bound(settings, settings.llm_model)
        if settings.llm_fallback_model:
            model = model.with_fallbacks([_bound(settings, settings.llm_fallback_model)])
        _cache[key] = model
    return _cache[key]


def _bound(settings: Settings, model_name: str) -> ChatModel:
    assert settings.llm_api_key is not None
    specs = tool_specs()
    if settings.llm_provider is LlmProvider.ANTHROPIC:
        anthropic: BaseChatModel = ChatAnthropic(
            model=model_name,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_s,
            max_retries=1,  # lỗi mạng thử lại 1 lần (SRS 7.3)
            temperature=TEMPERATURE,
            max_tokens=MAX_OUTPUT_TOKENS,
        )
        return anthropic.bind_tools(specs, parallel_tool_calls=False)
    openai = ChatOpenAI(
        model=model_name,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout_s,
        max_retries=1,
        temperature=TEMPERATURE,
        max_tokens=MAX_OUTPUT_TOKENS,
        stream_usage=True,  # số token nằm ở chunk cuối, dùng cho trần chi phí
    )
    # Mỗi câu trả lời một tool (cả hai nhà cung cấp): tránh hai đề xuất song song.
    return openai.bind_tools(specs, parallel_tool_calls=False)


def system_message(now: datetime, settings: Settings) -> SystemMessage:
    """Phần tĩnh trước, ngữ cảnh thời gian sau (docs mục 6.2). Anthropic cần đánh dấu chỗ lưu đệm;
    OpenAI tự lưu đệm phần đầu giống nhau của prompt."""
    static, dynamic = static_prompt(settings), time_context(now)
    if settings.llm_provider is LlmProvider.ANTHROPIC:
        return SystemMessage(
            content=[
                {"type": "text", "text": static, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": dynamic},
            ]
        )
    return SystemMessage(content=f"{static}\n{dynamic}")


def get_chat_model(settings: SettingsDep) -> ChatModel | None:
    """Dependency; test thay bằng mô hình viết sẵn kịch bản (app.dependency_overrides)."""
    return build_chat_model(settings)


ChatModelDep = Annotated[ChatModel | None, Depends(get_chat_model)]
