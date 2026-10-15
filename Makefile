# Lệnh thường dùng. Gõ `make` để xem danh sách.
.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help dev down logs ps migrate migration seed test lint fmt api-types \
	secrets secrets-status secret deploy rollback

help: ## Liệt kê các lệnh
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

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

lint: ## Lint + kiểm tra kiểu cả hai phía, kiểm tra cấu hình deploy
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd frontend && npm run lint && npm run typecheck
	deploy/secrets.sh lint

fmt: ## Tự định dạng mã
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd frontend && npm run format

api-types: ## Xuất OpenAPI từ backend và sinh kiểu TypeScript cho frontend
	cd backend && uv run python -m app.cli export-openapi ../frontend/src/shared/api/openapi.json
	cd frontend && npm run gen:api

# ---- Staging/production trên GitHub (cần gh đã đăng nhập) — xem deploy/README.md ----
# SHA đầy đủ của release=<sha|nhánh> (tag image là SHA đầy đủ); mặc định commit mới nhất của main trên GitHub.
RELEASE_SHA = $$(gh api 'repos/{owner}/{repo}/commits/$(or $(release),main)' --jq .sha)

secrets: ## Tạo environment, nhập secret/variable còn thiếu: make secrets env=staging
	@deploy/secrets.sh setup $(env)

secrets-status: ## Xem secret/variable của một môi trường, không đổi gì: make secrets-status env=staging
	@deploy/secrets.sh status $(env)

secret: ## Đổi một secret/variable: make secret env=staging name=LLM_API_KEY
	@deploy/secrets.sh set $(env) $(name)

deploy: ## Deploy (lại) một bản đã build: make deploy env=staging [release=<sha>], mặc định main
	@[ -n "$(env)" ] || { echo "Cách dùng: make deploy env=staging|production [release=<sha>]"; exit 1; }
	gh workflow run deploy.yml -f environment=$(env) -f release=$(RELEASE_SHA) -f skip_migrate=false
	@echo "Đã gửi. Theo dõi: gh run watch (hoặc tab Actions trên GitHub)"

rollback: ## Quay về bản cũ, bỏ qua migration: make rollback env=production release=<sha>
	@[ -n "$(env)" ] && [ -n "$(release)" ] || { echo "Cách dùng: make rollback env=staging|production release=<sha>"; exit 1; }
	gh workflow run deploy.yml -f environment=$(env) -f release=$(RELEASE_SHA) -f skip_migrate=true
	@echo "Đã gửi. Theo dõi: gh run watch (hoặc tab Actions trên GitHub)"
