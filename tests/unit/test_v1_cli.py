"""agenttaint CLI: init, config loading, approve wiring, dashboard guards."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from agenttaint_cli import config as cfgmod
from agenttaint_cli.main import main
from agenttaint_core.paths import POLICY_FILE, TRUST_REGISTRY_FILE, packaged_default

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("AGENTTAINT_") or key == "POSTGRES_PASSWORD":
            monkeypatch.delenv(key, raising=False)


def test_packaged_policy_defaults_match_repo() -> None:
    for name in (POLICY_FILE, TRUST_REGISTRY_FILE):
        assert packaged_default(name).read_bytes() == (ROOT / "policies" / name).read_bytes()


def test_init_creates_private_env_without_printing_secrets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["init", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    env_path = tmp_path / ".env"
    assert (tmp_path / "agenttaint.yaml").is_file()
    assert (tmp_path / "policies" / POLICY_FILE).is_file()
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
    values = cfgmod.read_env_file(env_path)
    for key in (
        "AGENTTAINT_CONFIRM_SECRET",
        "AGENTTAINT_DASHBOARD_TOKEN",
        "AGENTTAINT_APPROVER_TOKEN",
        "POSTGRES_PASSWORD",
    ):
        assert len(values[key]) >= 32
        assert values[key] not in out
    assert values["AGENTTAINT_DASHBOARD_TOKEN"] != values["AGENTTAINT_APPROVER_TOKEN"]


def test_init_never_overwrites_env_and_rotate_changes_only_secrets(tmp_path: Path) -> None:
    main(["init", str(tmp_path)])
    before = cfgmod.read_env_file(tmp_path / ".env")
    main(["init", str(tmp_path)])
    assert cfgmod.read_env_file(tmp_path / ".env") == before
    assert main(["init", str(tmp_path), "--rotate"]) == 0
    after = cfgmod.read_env_file(tmp_path / ".env")
    assert after["AGENTTAINT_CONFIRM_SECRET"] != before["AGENTTAINT_CONFIRM_SECRET"]
    assert after["AGENTTAINT_APPROVER_TOKEN"] != before["AGENTTAINT_APPROVER_TOKEN"]
    assert after["AGENTTAINT_DATABASE_URL"] == before["AGENTTAINT_DATABASE_URL"]
    assert stat.S_IMODE((tmp_path / ".env").stat().st_mode) == 0o600


def test_load_config_expands_env_and_resolves_paths(tmp_path: Path) -> None:
    main(["init", str(tmp_path)])
    cfg = cfgmod.load_config(tmp_path / "agenttaint.yaml")
    assert cfg.database_url.startswith("sqlite+pysqlite:///")
    assert cfg.security_database_url and cfg.security_database_url.endswith("security.db")
    assert cfg.policy_file == (tmp_path / "policies" / POLICY_FILE).resolve()
    assert cfg.backend_command[0] == "npx"
    assert cfg.dashboard_auth == "required"


def test_load_config_rejects_missing_placeholder(tmp_path: Path) -> None:
    path = tmp_path / "agenttaint.yaml"
    path.write_text("version: 1\nstorage:\n  database_url: ${NOT_SET_ANYWHERE}\n")
    with pytest.raises(cfgmod.ConfigError, match="NOT_SET_ANYWHERE"):
        cfgmod.load_config(path)


def test_load_config_rejects_bad_auth_and_version(tmp_path: Path) -> None:
    path = tmp_path / "a.yaml"
    path.write_text("version: 1\ndashboard:\n  auth: maybe\n")
    with pytest.raises(cfgmod.ConfigError):
        cfgmod.load_config(path)
    path.write_text("version: 7\n")
    with pytest.raises(cfgmod.ConfigError):
        cfgmod.load_config(path)


def test_approve_list_uses_config_security_db(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["init", str(tmp_path)])
    assert main(["approve", "--config", str(tmp_path / "agenttaint.yaml"), "list"]) == 0
    assert "No pending confirmations." in capsys.readouterr().out


def test_approve_requires_id(tmp_path: Path) -> None:
    main(["init", str(tmp_path)])
    assert main(["approve", "--config", str(tmp_path / "agenttaint.yaml"), "approve"]) == 2


def test_proxy_refuses_without_confirm_secret(tmp_path: Path) -> None:
    (tmp_path / "agenttaint.yaml").write_text("version: 1\n")
    assert main(["proxy", "--config", str(tmp_path / "agenttaint.yaml")]) == 2


def test_proxy_requires_backend_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTTAINT_CONFIRM_SECRET", "a" * 64)
    (tmp_path / "agenttaint.yaml").write_text("version: 1\nbackend:\n  command: []\n")
    assert main(["proxy", "--config", str(tmp_path / "agenttaint.yaml")]) == 2


def test_dashboard_refuses_auth_without_token(tmp_path: Path) -> None:
    (tmp_path / "agenttaint.yaml").write_text("version: 1\n")
    assert main(["dashboard", "--config", str(tmp_path / "agenttaint.yaml")]) == 2


def test_dashboard_refuses_open_auth_on_public_host(tmp_path: Path) -> None:
    (tmp_path / "agenttaint.yaml").write_text("version: 1\ndashboard:\n  auth: 'off'\n")
    rc = main(["dashboard", "--config", str(tmp_path / "agenttaint.yaml"), "--host", "0.0.0.0"])
    assert rc == 2


def test_backend_environment_strips_all_operator_tokens() -> None:
    from agenttaint_mcp_proxy.protocol_proxy import backend_environment

    env = backend_environment(
        {
            "AGENTTAINT_APPROVER_TOKEN": "x",
            "AGENTTAINT_DASHBOARD_TOKEN": "x",
            "AGENTTAINT_ADMIN_TOKEN": "x",
            "AGENTTAINT_CONFIRM_SECRET": "x",
            "PATH": "/usr/bin",
        }
    )
    assert env == {"PATH": "/usr/bin"}
