"""Hạ tầng bộ kịch bản đánh giá Agent: database test của integration, LLM thật theo biến môi trường.

Chạy: `uv run pytest -m agent_eval` (cần LLM_API_KEY trong môi trường và
`docker compose up -d db valkey`). Mỗi lần chạy gọi LLM thật cho mọi kịch bản nên tốn phí.

Cuối lần chạy in mục "Đánh giá Agent" (tỷ lệ đạt theo nhóm, thời gian, token, chi phí ước tính) và
ghi kết quả ra file JSON (`report.py`) để so sánh các mô hình bằng `compare.py`.
"""

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.core.config import LlmProvider, get_settings
from app.modules.agent.prompts import PROMPT_VERSION
from tests.agent_eval.report import build_report, format_summary, write_report
from tests.integration.conftest import (  # noqa: F401  — dùng lại fixture của integration
    app,
    app_client,
    clock,
    db,
    test_database_url,
)


@dataclass
class ScenarioResult:
    name: str
    category: str
    outcome: str = "passed"  # passed, failed, safety
    reason: str | None = None
    turns: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EvalRun:
    results: list[ScenarioResult] = field(default_factory=list)


RUN = EvalRun()


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    if not RUN.results:
        return
    settings = get_settings()
    report = build_report(
        [vars(result) for result in RUN.results],
        model=f"{settings.llm_provider.value}/{settings.llm_model}",
        prompt_version=PROMPT_VERSION,
        fake=settings.llm_provider is LlmProvider.FAKE,
        input_usd_per_mtok=settings.llm_input_usd_per_mtok,
        output_usd_per_mtok=settings.llm_output_usd_per_mtok,
    )
    terminalreporter.section("Đánh giá Agent")
    for line in format_summary(report):
        terminalreporter.write_line(line)
    path = write_report(report)
    terminalreporter.write_line(f"Kết quả chi tiết: {path}")
