# Hệ thống đặt lịch khám bệnh tích hợp AI Agent

Bệnh nhân đặt, đổi, hủy lịch khám qua website hoặc trò chuyện với AI Agent; bác sĩ xem lịch khám; quản trị viên quản lý danh mục, ca làm và lịch hẹn. Thiết kế chi tiết nằm trong [docs/](docs/README.md).

## Cấu trúc repository

```text
.
├── backend/            FastAPI + SQLAlchemy + LangGraph — xem backend/README.md
├── frontend/           Next.js (App Router) — xem frontend/README.md
├── deploy/             Cấu hình staging/production: compose, Caddy, script deploy — xem deploy/README.md
├── docs/               PRD, SRS, ERD, System Design
├── .github/workflows/  CI (mỗi pull request) và Deploy (staging → duyệt → production)
├── compose.yaml        Môi trường development (một lệnh)
└── Makefile            Lệnh thường dùng
```

## Ba môi trường

| | development | staging | production |
| --- | --- | --- | --- |
| Chạy ở | Máy lập trình, `compose.yaml` | VM staging, `deploy/compose.prod.yaml` | VM production, `deploy/compose.prod.yaml` |
| Cấu hình (không bí mật) | Mặc định trong `compose.yaml`, ghi đè bằng `.env` | `deploy/env/staging/*.env` | `deploy/env/production/*.env` |
| Secret | Không cần (giá trị dev) | GitHub Environment `staging` | GitHub Environment `production` |
| Database | PostgreSQL container | PostgreSQL managed (gói nhỏ) | PostgreSQL managed có PITR |
| Dữ liệu | Dữ liệu giả (seed) | Dữ liệu giả (seed) | Dữ liệu thật, chặn seed |
| Email | Mailpit — xem tại http://localhost:8025 | Amazon SES | Amazon SES |
| Swagger `/docs` | Bật | Bật | Tắt |
| Công cụ tìm kiếm | Chặn | Chặn | Cho phép trang công khai |
| Deploy | — | Tự động khi CI trên `main` xanh | Sau staging, cần người duyệt |

Cùng một image chạy ở cả ba môi trường; khác nhau chỉ ở biến môi trường và secret (backend: `app/core/config.py`, frontend: `src/shared/config/server-env.ts`). Staging và production không bao giờ khởi động nếu còn dùng secret mặc định của development.

## Bắt đầu

Cần Docker. Chạy toàn bộ môi trường development:

```bash
make dev        # hoặc: docker compose up --build
```

| Địa chỉ | Dịch vụ |
| --- | --- |
| http://localhost:3000 | Frontend |
| http://localhost:8000/docs | API (Swagger) |
| http://localhost:8025 | Mailpit — hộp thư giả |

Muốn dùng AI Agent khi phát triển: chép `.env.example` thành `.env` và điền `LLM_API_KEY`.

Chạy ngoài Docker (cần [uv](https://docs.astral.sh/uv/) và Node 24.15 trở lên), vẫn dùng database của compose:

```bash
docker compose up -d db valkey mailpit
cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn --factory app.main:create_app --reload
cd frontend && npm ci && npm run dev
```

## Lệnh thường dùng

| Lệnh | Việc |
| --- | --- |
| `make dev` / `make down` | Bật / tắt môi trường development |
| `make test` | Test backend (pytest) và frontend (Vitest) |
| `make lint` | ruff + mypy, ESLint + TypeScript |
| `make fmt` | Tự định dạng mã |
| `make migration m="..."` / `make migrate` | Tạo / chạy migration |
| `make seed` | Nạp dữ liệu giả (bị chặn ở production) |
| `make api-types` | Xuất OpenAPI từ backend và sinh kiểu TypeScript cho frontend |
