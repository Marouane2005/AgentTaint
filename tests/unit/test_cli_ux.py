"""CLI usability: colored verdicts, actionable errors, init defaults, connect/doctor."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from agenttaint_cli import config as cfgmod
from agenttaint_cli import ui
from agenttaint_cli.main import main


@pytest.fixture(autouse=True)
def _restore_environ() -> Iterator[None]:
    """CLI commands export .env values into os.environ; undo that after each test."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture(autouse=True)
def _reset_color(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    ui.set_no_color(False)


def test_verdicts_are_color_coded_when_color_is_forced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert "\x1b[32m" in ui.verdict("ALLOW")
    assert "\x1b[33m" in ui.verdict("CONFIRM")
    assert "\x1b[31m" in ui.verdict("BLOCK")


def test_no_color_and_non_tty_produce_plain_text(monkeypatch: pytest.MonkeyPatch) -> None:
    assert ui.verdict("BLOCK").strip() == "BLOCK"  # pytest stdout is not a TTY
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("NO_COLOR", "1")
    assert "\x1b[" not in ui.verdict("BLOCK")
    monkeypatch.delenv("NO_COLOR")
    ui.set_no_color(True)
    assert "\x1b[" not in ui.verdict("ALLOW")


def test_error_prints_problem_and_fix_on_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    ui.error("something broke", "do this")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error: something broke" in captured.err and "fix:" in captured.err
    assert "do this" in captured.err


def test_missing_config_error_explains_the_fix(tmp_path: Path) -> None:
    with pytest.raises(cfgmod.ConfigError, match="agenttaint init"):
        cfgmod.load_config(tmp_path / "nope.yaml")


def test_missing_placeholder_error_names_the_env_file(tmp_path: Path) -> None:
    path = tmp_path / "agenttaint.yaml"
    path.write_text("version: 1\nstorage:\n  database_url: ${NOPE_NOT_SET}\n")
    with pytest.raises(cfgmod.ConfigError, match=r"\.env"):
        cfgmod.load_config(path)


def test_cli_missing_config_exits_with_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["proxy", "--config", str(tmp_path / "agenttaint.yaml")])
    err = capsys.readouterr().err
    assert rc == 2 and "agenttaint init" in err and "fix:" in err


def test_init_default_backend_is_absolute_and_sandbox_created(tmp_path: Path) -> None:
    assert main(["init", str(tmp_path)]) == 0
    cfg = cfgmod.load_config(tmp_path / "agenttaint.yaml")
    assert cfg.backend_command[-1] == str((tmp_path / "sandbox").resolve())
    assert (tmp_path / "sandbox").is_dir()


def test_init_backend_flag_sets_command(tmp_path: Path) -> None:
    assert main(["init", str(tmp_path), "--backend", 'npx -y my-server "/a b"']) == 0
    cfg = cfgmod.load_config(tmp_path / "agenttaint.yaml")
    assert cfg.backend_command == ["npx", "-y", "my-server", "/a b"]
    assert not (tmp_path / "sandbox").exists()


def test_init_rejects_bad_backend(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["init", str(tmp_path), "--backend", 'npx "unterminated']) == 2
    assert "fix:" in capsys.readouterr().err


@pytest.mark.parametrize("client", ["claude-desktop", "cursor"])
def test_connect_prints_valid_json_snippet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], client: str
) -> None:
    main(["init", str(tmp_path)])
    capsys.readouterr()
    assert main(["connect", client, "--config", str(tmp_path / "agenttaint.yaml")]) == 0
    out = capsys.readouterr().out
    entry = json.loads(out[out.index("{") :])["mcpServers"]["agenttaint-protected"]
    assert Path(entry["command"]).is_absolute()  # GUI clients do not inherit venv PATH
    assert entry["args"][-3:-1] == ["proxy", "--config"]
    assert entry["args"][-1] == str((tmp_path / "agenttaint.yaml").resolve())


def test_connect_claude_code_prints_add_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["init", str(tmp_path)])
    capsys.readouterr()
    assert main(["connect", "claude-code", "--config", str(tmp_path / "agenttaint.yaml")]) == 0
    out = capsys.readouterr().out
    assert out.startswith("claude mcp add agenttaint -- /")
    assert " proxy --config " in out


def test_connect_without_config_fails_with_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["connect", "cursor", "--config", str(tmp_path / "missing.yaml")]) == 1
    assert "agenttaint init" in capsys.readouterr().err


def test_doctor_reports_failures_with_fixes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AGENTTAINT_CONFIRM_SECRET", raising=False)
    (tmp_path / "agenttaint.yaml").write_text(
        'version: 1\nbackend:\n  command: ["definitely-not-a-real-binary-xyz"]\n'
    )
    assert main(["doctor", "--config", str(tmp_path / "agenttaint.yaml")]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "fix:" in out and "definitely-not-a-real-binary-xyz" in out


def test_init_flow_then_doctor_passes_core_checks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in cfgmod.read_env_file(tmp_path / ".env"):
        monkeypatch.delenv(key, raising=False)
    main(["init", str(tmp_path), "--backend", "python3 -m http.server"])
    capsys.readouterr()
    main(["doctor", "--config", str(tmp_path / "agenttaint.yaml")])
    out = capsys.readouterr().out
    assert "config loads" in out
    assert "[FAIL] AGENTTAINT_CONFIRM_SECRET" not in out
    assert "[FAIL] backend executable" not in out
