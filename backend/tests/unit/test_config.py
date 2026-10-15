import pytest

from app.core.config import Environment, Settings

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
