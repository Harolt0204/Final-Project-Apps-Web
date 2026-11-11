"""Application settings, read from environment variables or the project `.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# `.env` lives in the project root, one level above `backend/`.
PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEV_JWT_SECRET = "dev-only-insecure-secret-change-me-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "production"] = "development"
    database_url: str = Field(
        default="mysql+pymysql://thesis_app:thesis_dev_password@127.0.0.1:3307/thesis_management"
    )
    jwt_secret: str = Field(default=DEV_JWT_SECRET)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60, ge=5, le=24 * 60)
    # Comma-separated list, e.g. "http://localhost:5173,http://127.0.0.1:5173".
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Failed logins allowed per e-mail and client IP within the window (OWASP API4:2023).
    login_max_failures: int = Field(default=5, ge=1)
    login_window_seconds: int = Field(default=15 * 60, ge=60)
    # Folder with the built frontend (index.html + assets). When set, the API also serves
    # the single-page app, so production runs as one service on one origin.
    static_dir: Path | None = None

    @model_validator(mode="after")
    def production_needs_real_secret(self) -> "Settings":
        if self.environment == "production" and (
            self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32
        ):
            raise ValueError(
                "In production JWT_SECRET must be set to a random value of at least 32 characters"
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
