from fastapi.testclient import TestClient


def test_live_returns_ok_with_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


def test_unknown_route_uses_common_error_format(client: TestClient) -> None:
    response = client.get("/api/v1/khong-ton-tai")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
