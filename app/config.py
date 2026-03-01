"""
Configuration management using pydantic-settings.

The active environment is selected by the APP_ENV environment variable:
  - dev  → envs/.env.dev   (default)
  - qa   → envs/.env.qa
  - prod → envs/.env.prod

Usage:
  APP_ENV=prod uvicorn app.main:app ...
  or set APP_ENV before starting via the scripts in /scripts/
"""

import os
import json
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Root of the project (two levels up from this file: app/config.py → project/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Determine which .env file to load based on APP_ENV (default: dev)
_APP_ENV = os.getenv("APP_ENV", "dev").lower()
_ENV_FILE = _PROJECT_ROOT / "envs" / f".env.{_APP_ENV}"

if not _ENV_FILE.exists():
    raise FileNotFoundError(
        f"Environment file not found: {_ENV_FILE}\n"
        f"Expected one of: envs/.env.dev | envs/.env.qa | envs/.env.prod"
    )


class Settings(BaseSettings):
    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "ragflow-api"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "dev"                # dev | qa | prod
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # ── Server ────────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    RELOAD: bool = True                 # set False in prod

    # ── MySQL / Cloud-compatible DB ───────────────────────────────────────────
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "ragflow_dev"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 3600         # seconds; helps with cloud DB timeouts

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Accepts a comma-separated string OR a JSON array.
    # In .env files use: ALLOWED_ORIGINS=http://localhost:5174,http://localhost:3000
    ALLOWED_ORIGINS: str = "http://localhost:5174"

    @property
    def cors_origins(self) -> list[str]:
        """Parse ALLOWED_ORIGINS into a list, supporting both formats:
        - Comma-separated: http://a.com,http://b.com
        - JSON array:      ["http://a.com","http://b.com"]
        """
        v = self.ALLOWED_ORIGINS.strip()
        if v.startswith("["):
            return [o.strip() for o in json.loads(v)]
        return [o.strip() for o in v.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """SQLAlchemy async-compatible connection string for MySQL."""
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def sync_database_url(self) -> str:
        """Sync connection string used by Alembic migrations."""
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return upper


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings singleton loaded from envs/.env.{APP_ENV}."""
    return Settings()
