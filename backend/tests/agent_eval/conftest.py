"""Hạ tầng bộ kịch bản đánh giá Agent: database test của integration, LLM thật theo biến môi trường.

Chạy: `uv run pytest -m agent_eval` (cần LLM_API_KEY hoặc OPENAI_API_KEY trong môi trường và
`docker compose up -d db valkey`). Mỗi lần chạy gọi LLM thật cho mọi kịch bản nên tốn phí.
"""

from dataclasses import dataclass, field

import pytest

from app.core.config import get_settings
from app.modules.agent.prompts import PROMPT_VERSION
from tests.integration.conftest import (  # noqa: F401  — dùng lại fixture của integration
    app,
    app_client,
    clock,
    db,
    test_database_url,
)


@dataclass
class EvalRun:
    passed: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    safety: dict[str, str] = field(default_factory=dict)


RUN = EvalRun()


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    total = len(RUN.passed) + len(RUN.failed)
    if not total:
        return
    settings = get_settings()
    write = terminalreporter.write_line
    terminalreporter.section("Đánh giá Agent")
    write(f"Mô hình: {settings.llm_provider.value}/{settings.llm_model} · prompt {PROMPT_VERSION}")
    write(f"Đạt: {len(RUN.passed)}/{total} ({len(RUN.passed) * 100 // total}%)")
    write(f"Vi phạm an toàn: {len(RUN.safety)}")
    for name, reason in {**RUN.failed, **RUN.safety}.items():
        write(f"  ✗ {name}: {reason}")
