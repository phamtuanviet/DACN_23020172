"""Lỗi dữ liệu từ database trả 422, không phải 500 (docs mục 4.7)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DataError

from app.core.errors import register_error_handlers


def test_database_data_error_becomes_validation_error() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/loi-du-lieu")
    async def broken() -> None:
        raise DataError("SELECT 1", {"reason": "dữ liệu giả"}, Exception("value out of range"))

    with TestClient(app) as client:
        response = client.get("/loi-du-lieu")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "dữ liệu giả" not in response.text
