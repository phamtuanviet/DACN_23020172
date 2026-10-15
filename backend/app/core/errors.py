"""Mô hình lỗi chung `{code, message, details}` (docs mục 4.7).

Service ném AppError; handler ở đây chuyển mọi lỗi về cùng một dạng JSON.
Bảng mã lỗi đầy đủ nằm trong tài liệu thiết kế; frontend và Agent dựa vào `code`.
"""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger(__name__)


class AppError(Exception):
    def __init__(
        self, code: str, message: str, *, status: int = 400, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


_HTTP_ERRORS: dict[int, tuple[str, str]] = {
    401: ("UNAUTHENTICATED", "Bạn cần đăng nhập để tiếp tục."),
    403: ("FORBIDDEN", "Bạn không có quyền thực hiện thao tác này."),
    404: ("NOT_FOUND", "Không tìm thấy dữ liệu yêu cầu."),
    405: ("METHOD_NOT_ALLOWED", "Phương thức không được hỗ trợ."),
    429: ("RATE_LIMITED", "Bạn thao tác quá nhanh, vui lòng thử lại sau."),
}


def _json(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    body = ErrorResponse(code=code, message=message, details=details or {})
    return JSONResponse(status_code=status, content=body.model_dump())


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _json(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [{"loc": list(e["loc"]), "message": e["msg"]} for e in exc.errors()]
        return _json(422, "VALIDATION_ERROR", "Dữ liệu gửi lên không hợp lệ.", {"fields": fields})

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _HTTP_ERRORS.get(exc.status_code, ("HTTP_ERROR", "Yêu cầu không hợp lệ."))
        return _json(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", exc_info=exc)
        request_id = structlog.contextvars.get_contextvars().get("request_id")
        return _json(
            500,
            "INTERNAL_ERROR",
            "Hệ thống đang gặp sự cố, vui lòng thử lại sau.",
            {"request_id": request_id},
        )
