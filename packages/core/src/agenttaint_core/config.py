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
    trust_registry_path: Path = Field(
        default=Path("policies/trust_registry.yaml"),
    )
    retain_redacted_content: bool = True
    shared_secret: str = "dev-only-change-me"
    api_host: str = "0.0.0.0"
    api_port: int = 8080


def get_settings() -> Settings:
    return Settings()
