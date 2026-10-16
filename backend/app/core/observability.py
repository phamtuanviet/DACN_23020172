"""Sentry và metrics Prometheus (docs mục 4.5, 11.7)."""

import os
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.core.config import Settings


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
        traces_sample_rate=0.1,
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
