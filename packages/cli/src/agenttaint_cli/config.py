"""Load ``agenttaint.yaml`` and its sibling ``.env`` without leaking secrets."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_PLACEHOLDER = re.compile(r"\$\{([A-Z0-9_]+)\}")


class ConfigError(RuntimeError):
    """Raised for an unreadable or invalid configuration file."""


def read_env_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env file (comments and blank lines ignored)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_env_defaults(config_path: Path) -> list[str]:
    """Export values from ``.env`` next to the config unless already set.

    Returns the variable names loaded (never their values).
    """
    loaded: list[str] = []
    for key, value in read_env_file(config_path.parent / ".env").items():
        if key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def _expand(value: Any) -> Any:
    if isinstance(value, str):

        def repl(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in os.environ:
                raise ConfigError(f"config references ${{{name}}} but it is not set")
            return os.environ[name]

        return _PLACEHOLDER.sub(repl, value)
    if isinstance(value, list):
        return [_expand(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    return value


@dataclass
class AgentTaintConfig:
    path: Path
    agent_id: str = "agent_default"
    policy_file: Path | None = None
    trust_registry: Path | None = None
    database_url: str = "sqlite+pysqlite:///:memory:"
    security_database_url: str | None = None
    backend_command: list[str] = field(default_factory=list)
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8080
    dashboard_auth: str = "required"


def _resolve_path(base: Path, value: Any) -> Path | None:
    if value in (None, ""):
        return None
    p = Path(str(value)).expanduser()
    return p if p.is_absolute() else (base / p).resolve()


def load_config(path: str | Path, *, load_dotenv: bool = True) -> AgentTaintConfig:
    cfg_path = Path(path).expanduser().resolve()
    if not cfg_path.is_file():
        raise ConfigError(f"config file not found: {cfg_path}")
    if load_dotenv:
        load_env_defaults(cfg_path)
    try:
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {cfg_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("config root must be a mapping")
    if raw.get("version", 1) != 1:
        raise ConfigError(f"unsupported config version: {raw.get('version')!r}")
    data = _expand(raw)
    base = cfg_path.parent
    policy = data.get("policy") or {}
    storage = data.get("storage") or {}
    backend = data.get("backend") or {}
    dashboard = data.get("dashboard") or {}

    command = backend.get("command") or []
    if isinstance(command, str):
        import shlex

        command = shlex.split(command)
    if not isinstance(command, list) or not all(isinstance(c, str) for c in command):
        raise ConfigError("backend.command must be a list of strings")

    auth = str(dashboard.get("auth", "required")).lower()
    if auth not in {"off", "mutations", "required"}:
        raise ConfigError("dashboard.auth must be off, mutations or required")

    return AgentTaintConfig(
        path=cfg_path,
        agent_id=str(data.get("agent_id") or "agent_default"),
        policy_file=_resolve_path(base, policy.get("file")),
        trust_registry=_resolve_path(base, policy.get("trust_registry")),
        database_url=str(storage.get("database_url") or "sqlite+pysqlite:///:memory:"),
        security_database_url=(
            str(storage["security_database_url"]) if storage.get("security_database_url") else None
        ),
        backend_command=list(command),
        dashboard_host=str(dashboard.get("host", "127.0.0.1")),
        dashboard_port=int(dashboard.get("port", 8080)),
        dashboard_auth=auth,
    )
