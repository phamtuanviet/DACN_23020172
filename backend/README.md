# Backend

FastAPI, modular monolith (docs mục 4). Python 3.12, quản lý gói bằng `uv`.

## Code đặt ở đâu

```text
app/
├── main.py          create_app(): điểm vào duy nhất của HTTP
├── worker.py        tiến trình tác vụ nền (APScheduler)
├── cli.py           lệnh quản trị: export-openapi, seed, seed-appointments, create-admin, import-catalog
├── api/             router gốc /api/v1 và health check — chỉ ghép router, không có nghiệp vụ
├── core/            dùng chung: config, db, errors, logging, clock, security…
├── db/              Base, enum, model ORM (models/), seed
└── modules/<tên>/   một module nghiệp vụ = một thư mục
    ├── router.py      HTTP: nhận DTO, tạo Actor, gọi service
    ├── schemas.py     DTO Pydantic
    ├── service.py     nghiệp vụ + transaction (không biết HTTP)
    └── repository.py  truy vấn SQLAlchemy
```

## Quy tắc

- **Phân tầng.** router → service → repository. Router không truy vấn database; service không biết HTTP; repository không ra quyết định nghiệp vụ.
- **Mỗi bảng chỉ một module được ghi** (docs mục 4.3). Module khác cần ghi thì gọi service của module sở hữu.
- **Phụ thuộc một chiều** (docs mục 4.4): không vòng, không module nào import `agent`, `core` không import `modules`.
- **Service nhận `Actor`** (`core/actor.py`) thay vì request, để web và tool của Agent dùng chung.
- **Không gọi `datetime.now()`**: lấy thời gian qua `core/clock.py` để test cố định được.
- **Lỗi nghiệp vụ** ném `AppError(code, message, status=…)`; mã lỗi theo docs mục 4.7.
- **Cấu hình mới** thêm vào `core/config.py`; giá trị khác nhau giữa môi trường đặt ở `deploy/env/<môi trường>/app.env`, secret ở GitHub Environments.

## Lệnh

```bash
uv sync                                   # cài thư viện (kể cả nhóm dev)
uv run pytest                             # unit + API test (bỏ qua integration, agent_eval)
uv run pytest -m integration              # cần PostgreSQL: docker compose up -d db valkey
uv run ruff check . && uv run mypy app    # lint, kiểm tra kiểu
uv run alembic revision --autogenerate -m "mo ta"   # đọc lại file sinh ra trước khi commit
uv run python -m app.cli --help
```
