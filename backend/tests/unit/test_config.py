from pathlib import Path

import pytest

from app.core.config import Environment, LlmProvider, Settings

VALID_STAGING = {
    "app_env": Environment.STAGING,
    "jwt_keys": "k1:a-real-secret-from-github-environments",
    "database_url": "postgresql+psycopg://app_runtime:x@db.internal:5432/dacn",
    "public_base_url": "https://staging.datlich.example.vn",
    "smtp_starttls": True,
}


def test_development_runs_with_defaults() -> None:
    Settings(_env_file=None).validate_for_runtime()


def test_production_rejects_development_defaults() -> None:
    settings = Settings(_env_file=None, app_env=Environment.PRODUCTION)
    with pytest.raises(RuntimeError, match="jwt_keys"):
        settings.validate_for_runtime()


def test_staging_accepts_real_config() -> None:
    Settings(_env_file=None, **VALID_STAGING).validate_for_runtime()


def test_production_requires_sentry() -> None:
    settings = Settings(_env_file=None, **{**VALID_STAGING, "app_env": Environment.PRODUCTION})
    with pytest.raises(RuntimeError, match="sentry_dsn"):
        settings.validate_for_runtime()


@pytest.mark.parametrize(
    ("env", "docs", "seed"),
    [
        (Environment.DEVELOPMENT, True, True),
        (Environment.STAGING, True, True),
        (Environment.PRODUCTION, False, False),
    ],
)
def test_environment_switches(env: Environment, docs: bool, seed: bool) -> None:
    settings = Settings(_env_file=None, app_env=env)
    assert settings.docs_enabled is docs
    assert settings.seed_allowed is seed


def test_blank_optional_values_are_unset() -> None:
    settings = Settings(_env_file=None, llm_api_key="", sentry_dsn="  ", llm_fallback_model="")
    assert settings.llm_api_key is None
    assert settings.sentry_dsn is None
    assert settings.llm_fallback_model is None


@pytest.mark.parametrize("env_value", ["postgresql+psycopg://tu-app-env@db/dacn", ""])
def test_secret_file_wins_over_env(
    env_value: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "database_url").write_text("postgresql+psycopg://tu-github@db/dacn")
    monkeypatch.setenv("DATABASE_URL", env_value)
    settings = Settings(_env_file=None, _secrets_dir=tmp_path)
    assert settings.database_url.get_secret_value() == "postgresql+psycopg://tu-github@db/dacn"


@pytest.mark.parametrize("field", ["database_url", "valkey_url", "jwt_keys"])
def test_staging_rejects_empty_secret(field: str) -> None:
    settings = Settings(_env_file=None, **{**VALID_STAGING, field: ""})
    with pytest.raises(RuntimeError, match=f"thiếu {field}"):
        settings.validate_for_runtime()


@pytest.mark.parametrize("env", [Environment.STAGING, Environment.PRODUCTION])
def test_fake_llm_is_development_only(env: Environment) -> None:
    """Mô hình giả theo luật chỉ cho e2e trên máy dev; staging, production từ chối khởi động."""
    values = {**VALID_STAGING, "app_env": env, "sentry_dsn": "https://key@sentry.example/1"}
    Settings(_env_file=None, **values).validate_for_runtime()
    fake = Settings(_env_file=None, **values, llm_provider=LlmProvider.FAKE)
    with pytest.raises(RuntimeError, match="llm_provider=fake"):
        fake.validate_for_runtime()


def test_llm_key_is_read_only_from_llm_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Không đọc OPENAI_API_KEY: khóa của nhà cung cấp này không được gửi sang nhà cung cấp khác
    (compose ánh xạ OPENAI_API_KEY sang LLM_API_KEY cho máy dev)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-khac")
    assert Settings(_env_file=None).llm_api_key is None
