# syntax=docker/dockerfile:1
# Một image cho backend, worker và migrate (TD-24).
#   target dev     → compose.yaml (có thư viện dev, hot reload)
#   target runtime → staging/production (không có thư viện dev, user không phải root)
ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /usr/local/bin/uv

FROM base AS dev
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen
COPY . .
CMD ["uvicorn", "--factory", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS build
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev
COPY . .

FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid 10001 --no-create-home app
WORKDIR /app
COPY --from=build --chown=10001:10001 /app /app
USER 10001
EXPOSE 8000
CMD ["uvicorn", "--factory", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
