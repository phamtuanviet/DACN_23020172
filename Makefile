# Lệnh thường dùng. Gõ `make` để xem danh sách.
.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help dev down logs ps migrate migration seed test lint fmt api-types

help: ## Liệt kê các lệnh
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

dev: ## Dựng môi trường development (backend :8000, frontend :3000, mailpit :8025)
	$(COMPOSE) up --build

down: ## Dừng môi trường development
	$(COMPOSE) down

logs: ## Xem log các container
	$(COMPOSE) logs -f

ps: ## Trạng thái các container
	$(COMPOSE) ps

migrate: ## Chạy migration tới bản mới nhất
	$(COMPOSE) exec backend alembic upgrade head

migration: ## Tạo migration mới: make migration m="mo ta thay doi"
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

seed: ## Nạp dữ liệu giả (bị chặn ở production)
	$(COMPOSE) exec backend python -m app.cli seed

test: ## Chạy test backend và frontend
	cd backend && uv run pytest
	cd frontend && npm test

lint: ## Lint + kiểm tra kiểu cả hai phía
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd frontend && npm run lint && npm run typecheck

fmt: ## Tự định dạng mã
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd frontend && npm run format

api-types: ## Xuất OpenAPI từ backend và sinh kiểu TypeScript cho frontend
	cd backend && uv run python -m app.cli export-openapi ../frontend/src/shared/api/openapi.json
	cd frontend && npm run gen:api
