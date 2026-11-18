"""Runtime configuration (local-first, no paid APIs required)."""

from __future__ import annotations

import os
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
    # Secrets have no defaults: they must be configured explicitly (fail closed).
    shared_secret: str = ""
    api_host: str = "127.0.0.1"
    api_port: int = 8080
    api_auth: str = "off"
    dashboard_token: str = ""
    confirm_secret: str = ""


def get_settings() -> Settings:
    return Settings()


CONFIRM_SECRET_ENV = "AGENTTAINT_CONFIRM_SECRET"
MIN_SECRET_LENGTH = 32

# Placeholder values that shipped in earlier examples; never accept them.
_KNOWN_PLACEHOLDER_SECRETS = frozenset(
    {
        "agenttaint-local-confirm-secret-change-me",
        "dev-only-change-me",
        "change-me",
        "changeme",
    }
)


class ConfigurationError(RuntimeError):
    """Raised when required security configuration is missing or unsafe."""


def resolve_confirm_secret(explicit: str | None = None) -> str:
    """Return the confirmation HMAC secret or raise ConfigurationError.

    There is deliberately no default. Generate one with::

        python3 -c "import secrets; print(secrets.token_hex(32))"

    and export it as ``AGENTTAINT_CONFIRM_SECRET``.
    """
    value = (explicit if explicit is not None else os.environ.get(CONFIRM_SECRET_ENV, "")).strip()
    if not value:
        raise ConfigurationError(
            f"{CONFIRM_SECRET_ENV} is not set. Generate one with "
            '`python3 -c "import secrets; print(secrets.token_hex(32))"`.'
        )
    if value.casefold() in _KNOWN_PLACEHOLDER_SECRETS or "change-me" in value.casefold():
        raise ConfigurationError(f"{CONFIRM_SECRET_ENV} is a placeholder value; set a random one.")
    if len(value) < MIN_SECRET_LENGTH:
        raise ConfigurationError(
            f"{CONFIRM_SECRET_ENV} must be at least {MIN_SECRET_LENGTH} characters."
        )
    return value
