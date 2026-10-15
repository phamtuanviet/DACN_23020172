"""Cấu hình theo môi trường (docs mục 4.5, 11.4).

Một image chạy cho cả ba môi trường; khác nhau chỉ ở biến môi trường và file secret:
- development: giá trị mặc định chạy được ngay với compose.yaml.
- staging:     giống production, nhưng được bật /docs và nạp dữ liệu giả.
- production:  tắt /docs, chặn seed, bắt buộc đủ secret thật khi khởi động.

Secret đọc từ biến môi trường hoặc file trong /run/secrets (Docker secrets);
tên file trùng tên trường, ví dụ /run/secrets/database_url.
"""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SECRETS_DIR = Path("/run/secrets")
DEV_JWT_KEY = "dev:dev-only-insecure-signing-key-change-me"


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Môi trường ---
    app_env: Environment = Environment.DEVELOPMENT
    release: str = "local"  # git SHA của bản phát hành, deploy.sh truyền vào
    public_base_url: str = "http://localhost:3000"

    # --- Database, Valkey ---
    database_url: SecretStr = SecretStr("postgresql+psycopg://dacn:dacn@localhost:5432/dacn")
    database_migrator_url: SecretStr | None = None  # role app_migrator, chỉ bước migrate dùng
    db_pool_size: int = 4
    db_max_overflow: int = 2
    valkey_url: SecretStr = SecretStr("redis://localhost:6379/0")

    # --- Xác thực (TD-07) ---
    jwt_keys: SecretStr = SecretStr(DEV_JWT_KEY)  # "kid:secret[,kid_cũ:secret_cũ]"
    access_token_ttl_min: int = 30
    refresh_token_ttl_days: int = 7

    # --- Quy tắc nghiệp vụ (PRD mục 7, các giá trị "đề xuất") ---
    clinic_tz: str = "Asia/Ho_Chi_Minh"
    clinic_phone: str = ""
    booking_window_days: int = 30
    change_deadline_hours: int = 2
    max_active_appointments: int = 3
    proposal_ttl_min: int = 10
    agent_daily_message_limit: int = 50
    reminder_hours_before: int = 24
    chat_retention_days: int = 365

    # --- LLM (TD-21, docs mục 6.8) ---
    llm_provider: str = "anthropic"
    llm_model: str = "claude-haiku-5-5"
    llm_fallback_model: str | None = None
    llm_api_key: SecretStr | None = None
    llm_timeout_s: int = 30
    llm_daily_budget_usd: float = 5.0

    # --- Email (TD-28) ---
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = False
    mail_from: str = "no-reply@dacn.local"

    # --- Quan sát ---
    sentry_dsn: SecretStr | None = None
    log_level: str = "INFO"

    @field_validator(
        "database_migrator_url",
        "llm_fallback_model",
        "llm_api_key",
        "smtp_user",
        "smtp_password",
        "sentry_dsn",
        mode="before",
    )
    @classmethod
    def _blank_means_unset(cls, value: object) -> object:
        """File secret rỗng hoặc dòng `X=` trong env file được hiểu là chưa cấu hình."""
        return None if isinstance(value, str) and not value.strip() else value

    # ---------------------------------------------------------------- suy ra từ môi trường
    @property
    def is_development(self) -> bool:
        return self.app_env is Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        return self.app_env is Environment.PRODUCTION

    @property
    def docs_enabled(self) -> bool:
        return not self.is_production

    @property
    def seed_allowed(self) -> bool:
        return not self.is_production

    @property
    def migration_database_url(self) -> str:
        url = self.database_migrator_url or self.database_url
        return url.get_secret_value()

    def validate_for_runtime(self) -> None:
        """Gọi khi backend/worker khởi động. Staging và production từ chối chạy với cấu hình dev."""
        if self.is_development:
            return
        problems: list[str] = []
        if self.jwt_keys.get_secret_value() == DEV_JWT_KEY:
            problems.append("jwt_keys đang là khóa dev")
        if "localhost" in self.database_url.get_secret_value():
            problems.append("database_url trỏ tới localhost")
        if not self.public_base_url.startswith("https://"):
            problems.append("public_base_url phải dùng https")
        if not self.smtp_starttls:
            problems.append("smtp_starttls phải bật")
        if self.is_production and self.sentry_dsn is None:
            problems.append("thiếu sentry_dsn")
        if problems:
            raise RuntimeError(f"Cấu hình {self.app_env} không hợp lệ: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    if SECRETS_DIR.is_dir():
        return Settings(_secrets_dir=SECRETS_DIR)
    return Settings()
