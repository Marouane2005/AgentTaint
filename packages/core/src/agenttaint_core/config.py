"""Runtime configuration (local-first, no paid APIs required)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENTTAINT_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = "sqlite+pysqlite:///:memory:"
    security_db_url: str = "sqlite+pysqlite:///:memory:"
    trust_registry_path: Path = Field(
        default=Path("policies/trust_registry.yaml"),
    )
    retain_redacted_content: bool = True
    shared_secret: str = "dev-only-change-me"
    api_host: str = "127.0.0.1"
    api_port: int = 8080
    api_auth: str = "off"
    dashboard_token: str = ""
    confirm_secret: str = "agenttaint-local-confirm-secret-change-me"


def get_settings() -> Settings:
    return Settings()
