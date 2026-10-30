from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "双门店外卖点餐系统 API"
    app_env: str = "development"
    debug: bool = False
    enable_commerce: bool = False
    enable_test_commerce: bool = False
    database_url: str = "postgresql+asyncpg://takeaway:takeaway@localhost:5432/takeaway"
    jwt_secret: str = Field(default="development-only-change-me-please-32-chars")
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 480
    admin_domain: str = "admin.localhost"

    seed_super_admin_password: str | None = None
    seed_store_a_password: str | None = None
    seed_store_b_password: str | None = None

    @property
    def commerce_enabled(self) -> bool:
        return self.enable_commerce or (self.app_env == "testing" and self.enable_test_commerce)

    @field_validator("admin_domain")
    @classmethod
    def normalize_admin_domain(cls, value: str) -> str:
        return value.strip().lower().rstrip(".")

    @model_validator(mode="after")
    def reject_insecure_production_defaults(self):
        if self.enable_test_commerce and self.app_env != "testing":
            raise ValueError("ENABLE_TEST_COMMERCE 仅用于 APP_ENV=testing；正式营业请使用 ENABLE_COMMERCE")
        if self.app_env == "production":
            if len(self.jwt_secret) < 32 or "change-me" in self.jwt_secret:
                raise ValueError("生产环境 JWT_SECRET 必须是至少 32 位的随机密钥")
            if "takeaway:takeaway@" in self.database_url:
                raise ValueError("生产环境禁止使用默认数据库凭据")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
