"""Điểm vào FastAPI. Chạy: uvicorn --factory app.main:create_app"""

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.observability import init_sentry, setup_metrics


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.validate_for_runtime()
    configure_logging(settings)
    init_sentry(settings)

    app = FastAPI(
        title="DACN — Đặt lịch khám bệnh",
        version=settings.release,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(api_router)
    setup_metrics(app)
    return app
