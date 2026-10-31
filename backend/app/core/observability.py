"""Sentry và metrics Prometheus (docs mục 4.5, 11.7)."""

import os
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations import Integration
from sentry_sdk.integrations.anthropic import AnthropicIntegration
from sentry_sdk.integrations.langchain import LangchainIntegration
from sentry_sdk.integrations.openai import OpenAIIntegration
from sentry_sdk.types import Event, Hint

from app.core.config import Settings


def scrub_event(event: Event, _hint: Hint) -> Event:
    """Bỏ body, query string, cookie của request khỏi event trước khi gửi Sentry.

    Body chứa lý do khám, email, số điện thoại; query string chứa từ khóa người dùng gõ (có thể là
    triệu chứng). Sentry chỉ cần đường dẫn, phương thức, request id để tìm log tương ứng.
    """
    request = event.get("request")
    if isinstance(request, dict):
        for key in ("data", "query_string", "cookies"):
            request.pop(key, None)
    return event


def llm_integrations() -> list[Integration]:
    """Sentry tự bật các integration này khi có thư viện LLM. Không bao giờ gửi prompt, câu trả lời
    (nội dung chat là dữ liệu cá nhân, docs mục 6.8, 11.8), kể cả khi sau này bật send_default_pii;
    chỉ giữ số liệu như thời gian, số token."""
    return [
        OpenAIIntegration(include_prompts=False),
        LangchainIntegration(include_prompts=False),
        AnthropicIntegration(include_prompts=False),
    ]


def init_sentry(settings: Settings) -> None:
    if settings.sentry_dsn is None:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=settings.app_env.value,
        release=settings.release,
        send_default_pii=False,  # không gửi dữ liệu cá nhân của bệnh nhân
        # Biến cục bộ trong stack trace có thể chứa họ tên, email, lý do khám (AGENTS.md).
        include_local_variables=False,
        max_request_body_size="never",
        before_send=scrub_event,
        traces_sample_rate=0.1,
        integrations=llm_integrations(),
    )


def setup_metrics(app: FastAPI) -> None:
    """Expose /metrics (ngoài tiền tố /api nên Caddy không chuyển ra Internet).

    Khi Uvicorn chạy nhiều worker, đặt PROMETHEUS_MULTIPROC_DIR để gộp metrics của các tiến trình.
    """
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if multiproc_dir:
        Path(multiproc_dir).mkdir(parents=True, exist_ok=True)
    Instrumentator(excluded_handlers=["/metrics", "/api/v1/health/.*"]).instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )
