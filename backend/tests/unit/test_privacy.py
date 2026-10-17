"""Dữ liệu bệnh nhân không lọt vào log và Sentry khi có lỗi (AGENTS.md, docs mục 6.8, 11.8)."""

import json
from typing import cast

import pytest
import structlog
from sentry_sdk.types import Event

from app.core.config import Environment, Settings
from app.core.db import get_engine
from app.core.logging import configure_logging
from app.core.observability import scrub_event

SECRET = "Ho ra máu kéo dài (CA-BỆNH-GIẢ)"


def test_json_logs_render_tracebacks_without_local_variables(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(Settings(_env_file=None, app_env=Environment.STAGING))
    try:
        payload = {"reason": SECRET}  # biến cục bộ giống body request của POST /appointments
        try:
            if payload:
                raise RuntimeError("lỗi giả lập")
        except RuntimeError:
            structlog.get_logger("test").exception("unhandled_error")
        record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        # So trên nội dung đã giải mã: JSONRenderer ghi chữ có dấu dạng \uXXXX.
        text = json.dumps(record, ensure_ascii=False)
        assert record["exception"], "vẫn phải có traceback để điều tra lỗi"
        assert "lỗi giả lập" in text
        assert SECRET not in text
    finally:
        configure_logging(Settings(_env_file=None, app_env=Environment.DEVELOPMENT))


def test_sentry_events_drop_request_body_query_and_cookies() -> None:
    event = cast(
        Event,
        {
            "request": {
                "url": "https://example.com/api/v1/appointments",
                "method": "POST",
                "data": {"reason": SECRET},
                "query_string": "q=ho+ra+mau",
                "cookies": {"refresh_token": "bi-mat"},
                "headers": {"X-Request-Id": "abc123"},
            }
        },
    )
    scrubbed = scrub_event(event, {})
    assert scrubbed["request"] == {
        "url": "https://example.com/api/v1/appointments",
        "method": "POST",
        "headers": {"X-Request-Id": "abc123"},
    }


def test_sql_errors_do_not_carry_parameter_values() -> None:
    assert get_engine().sync_engine.hide_parameters
