"""Terminal presentation helpers: verdict colors and actionable error messages."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any, TextIO

_CODES = {"green": "32", "yellow": "33", "red": "31", "dim": "2", "bold": "1", "cyan": "36"}
VERDICT_COLORS = {"ALLOW": "green", "CONFIRM": "yellow", "BLOCK": "red"}
_force_no_color = False


def set_no_color(value: bool) -> None:
    global _force_no_color
    _force_no_color = value


def color_enabled(stream: TextIO | None = None) -> bool:
    """Color only on a real terminal, never when NO_COLOR is set or --no-color is given."""
    if _force_no_color or os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    stream = stream or sys.stdout
    return bool(getattr(stream, "isatty", lambda: False)()) and os.environ.get("TERM") != "dumb"


def paint(text: str, color: str, *, stream: TextIO | None = None) -> str:
    if not color_enabled(stream):
        return text
    return f"\x1b[{_CODES[color]}m{text}\x1b[0m"


def verdict(value: str, *, stream: TextIO | None = None) -> str:
    """ALLOW green, CONFIRM yellow, BLOCK red; padded so columns line up."""
    label = str(value).upper()
    return paint(f"{label:<7}", VERDICT_COLORS.get(label, "dim"), stream=stream)


def format_decision_row(row: Any) -> str:
    tier = getattr(getattr(row, "risk_tier", ""), "value", str(getattr(row, "risk_tier", "")))
    outcome = getattr(getattr(row, "decision", ""), "value", str(getattr(row, "decision", "")))
    return (
        f"{verdict(outcome)} {row.tool:<28} {tier:<6} {row.policy_id}  "
        f"{paint('agent=' + str(row.agent_id), 'dim')}"
    )


def error(message: str, fix: str | None = None) -> None:
    """Print ``error: <problem>`` plus a ``fix:`` line to stderr (stdout is MCP's)."""
    print(f"{paint('error:', 'red', stream=sys.stderr)} {message}", file=sys.stderr)
    if fix:
        print(f"{paint('fix:', 'cyan', stream=sys.stderr)}   {fix}", file=sys.stderr)


def launcher() -> list[str]:
    """Absolute command that starts this CLI.

    GUI clients (Claude Desktop, Cursor) do not inherit a virtualenv's PATH, so a bare
    ``agenttaint`` would not resolve; use the installed script or this interpreter.
    """
    found = shutil.which("agenttaint")
    if found:
        return [str(Path(found).resolve())]
    return [sys.executable, "-m", "agenttaint_cli.main"]


def client_snippet(client: str, config_path: Path) -> str:
    """Ready-to-paste MCP client config that wraps the server in AgentTaint."""
    cmd, *lead = launcher()
    args = [*lead, "proxy", "--config", str(config_path)]
    if client == "claude-code":
        return "claude mcp add agenttaint -- " + " ".join(shlex.quote(a) for a in [cmd, *args])
    entry = {"command": cmd, "args": args}
    body = json.dumps({"mcpServers": {"agenttaint-protected": entry}}, indent=2)
    where = {
        "claude-desktop": (
            "Add to claude_desktop_config.json (macOS: ~/Library/Application Support/Claude/, "
            "Windows: %APPDATA%\\Claude\\), then restart Claude Desktop:"
        ),
        "cursor": "Add to ~/.cursor/mcp.json (or .cursor/mcp.json in a project):",
    }[client]
    return f"{where}\n{body}"


CLIENTS = ("claude-desktop", "cursor", "claude-code")
