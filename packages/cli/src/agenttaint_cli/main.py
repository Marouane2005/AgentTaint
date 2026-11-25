"""``agenttaint`` command: init, connect, doctor, proxy, approve, log, dashboard, version."""

from __future__ import annotations

import argparse
import os
import re
import secrets
import shlex
import shutil
from importlib import resources
from pathlib import Path

from agenttaint_cli import __version__, ui
from agenttaint_cli.config import AgentTaintConfig, ConfigError, load_config

DEFAULT_CONFIG = "agenttaint.yaml"
SECRET_KEYS = (
    "AGENTTAINT_CONFIRM_SECRET",
    "AGENTTAINT_DASHBOARD_TOKEN",
    "AGENTTAINT_APPROVER_TOKEN",
    "POSTGRES_PASSWORD",
)
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def _err(message: str, fix: str | None = None) -> None:
    # stdout belongs to the MCP stdio protocol when running the proxy.
    text = message[7:] if message.startswith("error: ") else message
    ui.error(text, fix)


def _config_fix(exc: ConfigError) -> str | None:
    text = str(exc)
    if "not found" in text:
        return "run `agenttaint init` in this directory, or pass --config <path-to-agenttaint.yaml>"
    return None


# --- init -----------------------------------------------------------------------


def _env_file_body(target: Path) -> str:
    db = target / "agenttaint.db"
    sec = target / "agenttaint-security.db"
    lines = [
        "# AgentTaint secrets and storage. Written by `agenttaint init`.",
        "# Keep this file private (mode 600). Rotate with `agenttaint init --rotate`.",
        f"AGENTTAINT_CONFIRM_SECRET={secrets.token_hex(32)}",
        f"AGENTTAINT_DASHBOARD_TOKEN={secrets.token_urlsafe(32)}",
        f"AGENTTAINT_APPROVER_TOKEN={secrets.token_urlsafe(32)}",
        f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}",
        f"AGENTTAINT_DATABASE_URL=sqlite+pysqlite:///{db}",
        f"AGENTTAINT_SECURITY_DB_URL=sqlite+pysqlite:///{sec}",
        "",
    ]
    return "\n".join(lines)


def _write_private(path: Path, body: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(body)
    os.chmod(path, 0o600)


def _rotate_secrets(env_path: Path) -> list[str]:
    """Replace secret values in an existing .env, keep everything else."""
    from agenttaint_cli.config import read_env_file

    current = read_env_file(env_path)
    fresh = {
        "AGENTTAINT_CONFIRM_SECRET": secrets.token_hex(32),
        "AGENTTAINT_DASHBOARD_TOKEN": secrets.token_urlsafe(32),
        "AGENTTAINT_APPROVER_TOKEN": secrets.token_urlsafe(32),
    }
    out: list[str] = []
    seen: set[str] = set()
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        key = raw.partition("=")[0].strip()
        if key in fresh and not raw.lstrip().startswith("#"):
            out.append(f"{key}={fresh[key]}")
            seen.add(key)
        else:
            out.append(raw)
    for key, value in fresh.items():
        if key not in seen and key not in current:
            out.append(f"{key}={value}")
    _write_private(env_path, "\n".join(out) + "\n")
    return sorted(fresh)


def cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.directory).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    config_path = target / DEFAULT_CONFIG
    env_path = target / ".env"
    policy_dir = target / "policies"

    if args.rotate:
        if not env_path.is_file():
            _err(f"error: {env_path} does not exist; run `agenttaint init` first")
            return 1
        rotated = _rotate_secrets(env_path)
        print(f"Rotated {', '.join(rotated)} in {env_path} (values not shown).")
        print("Restart the proxy and dashboard. Pending confirmations become invalid.")
        return 0

    created: list[str] = []
    templates = resources.files("agenttaint_cli") / "templates"
    if not config_path.exists() or args.force:
        body = (templates / "agenttaint.yaml").read_text(encoding="utf-8")
        if args.backend:
            try:
                command = shlex.split(args.backend)
            except ValueError as exc:
                _err(
                    f"--backend is not a valid command line ({exc})",
                    'quote it: --backend "npx -y my-server"',
                )
                return 2
            if not command:
                _err(
                    "--backend is empty",
                    'pass the MCP server command, e.g. --backend "npx -y my-server"',
                )
                return 2
            line = "  command: [" + ", ".join(_yaml_str(c) for c in command) + "]"
            body = re.sub(r"(?m)^  command: \[.*\]$", lambda _m: line, body, count=1)
        if not args.backend:
            # MCP clients start the proxy from an arbitrary cwd, so root the default
            # filesystem backend at an absolute path next to the config.
            sandbox = target / "sandbox"
            body = body.replace('"./sandbox"', _yaml_str(str(sandbox)))
        config_path.write_text(body, encoding="utf-8")
        created.append(str(config_path))
        if not args.backend:
            if not sandbox.exists():
                sandbox.mkdir()
                created.append(f"{sandbox}/ (sandbox directory for the default filesystem backend)")

    from agenttaint_core.paths import POLICY_FILE, TRUST_REGISTRY_FILE, packaged_default

    policy_dir.mkdir(exist_ok=True)
    for name in (POLICY_FILE, TRUST_REGISTRY_FILE):
        dest = policy_dir / name
        if not dest.exists() or args.force:
            shutil.copyfile(packaged_default(name), dest)
            created.append(str(dest))

    if env_path.exists():
        print(f"Kept existing {env_path} (secrets are never overwritten; use --rotate).")
    else:
        _write_private(env_path, _env_file_body(target))
        created.append(f"{env_path} (mode 600, secrets not shown)")

    for item in created:
        print(f"created {item}")
    print()
    print("Next steps:")
    if args.backend:
        print(f"  1. Backend set to: {args.backend}")
    else:
        print(f"  1. Edit {config_path}: set backend.command to the MCP server to protect")
        print("     (the default is the reference filesystem server on ./sandbox).")
    print(f"  2. Check everything:  agenttaint doctor --config {config_path}")
    print("  3. Connect your client (prints a ready-to-paste snippet):")
    print(f"       agenttaint connect claude-desktop --config {config_path}")
    print("       (also: cursor, claude-code)")
    print(f"  4. Optional dashboard: agenttaint dashboard --config {config_path}")
    print(f"     Tools not listed in {policy_dir / TRUST_REGISTRY_FILE} get the default risk tier.")
    if args.client:
        print()
        print(ui.client_snippet(args.client, config_path))
    return 0


def _yaml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


# --- connect ----------------------------------------------------------------------


def cmd_connect(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser().resolve()
    if not config_path.is_file():
        _err(f"config file not found: {config_path}", "run `agenttaint init` first")
        return 1
    print(ui.client_snippet(args.client, config_path))
    return 0


# --- doctor -----------------------------------------------------------------------


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check the setup and say how to fix whatever is wrong."""
    checks: list[tuple[bool, str, str | None]] = []

    def check(ok: bool, label: str, fix: str | None = None) -> None:
        checks.append((ok, label, fix))

    try:
        cfg = _load(args)
    except ConfigError as exc:
        _err(str(exc), _config_fix(exc))
        return 1
    check(True, f"config loads: {cfg.path}")
    for label, path in (("policy file", cfg.policy_file), ("trust registry", cfg.trust_registry)):
        check(
            path is not None and path.is_file(),
            f"{label} present: {path}",
            "run `agenttaint init --force` to restore the default policies",
        )
    secret = os.environ.get("AGENTTAINT_CONFIRM_SECRET", "")
    check(
        len(secret) >= 32,
        "AGENTTAINT_CONFIRM_SECRET set (32+ chars)",
        "set it in .env (`agenttaint init` generates one) or export it",
    )
    check(
        bool(cfg.security_database_url),
        "storage.security_database_url set (needed for approvals)",
        "set AGENTTAINT_SECURITY_DB_URL in .env",
    )
    if cfg.backend_command:
        exe = cfg.backend_command[0]
        found = shutil.which(exe) is not None or Path(exe).expanduser().is_file()
        check(found, f"backend executable found: {exe}", f"install `{exe}` or fix backend.command")
    else:
        check(False, "backend.command is set", "set backend.command (or use --demo-backend)")
    for module, why in (("mcp", "the MCP SDK"), ("uvicorn", "the dashboard server")):
        try:
            __import__(module)
            check(True, f"python module `{module}` importable")
        except ImportError:
            check(False, f"python module `{module}` importable", f"pip install {module} ({why})")
    failed = 0
    for ok, label, fix in checks:
        mark = ui.paint("OK  ", "green") if ok else ui.paint("FAIL", "red")
        print(f"[{mark}] {label}")
        if not ok:
            failed += 1
            if fix:
                print(f"       fix: {fix}")
    print()
    print("All checks passed." if not failed else f"{failed} check(s) failed.")
    return 0 if not failed else 1


# --- log --------------------------------------------------------------------------


def cmd_log(args: argparse.Namespace) -> int:
    """Show recent decisions with color-coded ALLOW / CONFIRM / BLOCK verdicts."""
    try:
        cfg = _load(args)
    except ConfigError as exc:
        _err(str(exc), _config_fix(exc))
        return 2
    from agenttaint_audit.store import AuditStore

    try:
        rows = AuditStore(cfg.database_url).list_decisions(limit=args.limit)
    except Exception as exc:  # noqa: BLE001 - surface DB problems with a hint
        _err(f"could not read the audit log ({exc})", "check storage.database_url in your config")
        return 1
    if not rows:
        print("No decisions recorded yet. Make a tool call through `agenttaint proxy` first.")
        return 0
    for row in rows:
        print(ui.format_decision_row(row))
    return 0


# --- proxy ------------------------------------------------------------------------


def _load(args: argparse.Namespace) -> AgentTaintConfig:
    return load_config(args.config)


def cmd_proxy(args: argparse.Namespace) -> int:
    from agenttaint_core.config import ConfigurationError, resolve_confirm_secret

    try:
        cfg = _load(args)
    except ConfigError as exc:
        _err(str(exc), _config_fix(exc))
        return 2
    try:
        resolve_confirm_secret()
    except ConfigurationError as exc:
        _err(
            f"AgentTaint proxy refusing to start: {exc}",
            "run `agenttaint init` (writes a .env with a generated secret) or export "
            "AGENTTAINT_CONFIRM_SECRET",
        )
        return 2
    if cfg.security_database_url:
        os.environ["AGENTTAINT_SECURITY_DB_URL"] = cfg.security_database_url

    if args.demo_backend:
        from agenttaint_mcp_proxy.server import create_proxy_with_mock_email

        proxy, _ = create_proxy_with_mock_email(
            trust_registry_path=cfg.trust_registry,
            policy_path=cfg.policy_file,
            agent_id=cfg.agent_id,
        )
        proxy.run(transport="stdio")
        return 0

    if not cfg.backend_command:
        _err(
            "backend.command is empty in the config",
            'set it to the MCP server to protect, e.g. ["npx", "-y", "my-server"], or pass '
            "--demo-backend to try the built-in mock email server",
        )
        return 2

    import asyncio

    from agenttaint_mcp_proxy.protocol_proxy import run_protocol_proxy

    asyncio.run(
        run_protocol_proxy(
            cfg.backend_command,
            trust_registry_path=cfg.trust_registry,
            policy_path=cfg.policy_file,
            database_url=cfg.database_url,
            security_database_url=cfg.security_database_url,
            agent_id=cfg.agent_id,
        )
    )
    return 0


# --- approve ----------------------------------------------------------------------


def cmd_approve(args: argparse.Namespace) -> int:
    from agenttaint_agent_sdk.confirm_cli import main as confirm_main

    try:
        cfg = _load(args)
    except ConfigError as exc:
        _err(str(exc), _config_fix(exc))
        return 2
    if not cfg.security_database_url:
        _err(
            "storage.security_database_url must be set to approve confirmations",
            "set AGENTTAINT_SECURITY_DB_URL in .env (`agenttaint init` writes it)",
        )
        return 2
    argv = ["--database-url", cfg.security_database_url, args.action]
    if args.confirmation_id:
        argv.append(args.confirmation_id)
    elif args.action != "list":
        _err(
            f"`agenttaint approve {args.action}` needs a confirmation id",
            "run `agenttaint approve list` to see pending ids",
        )
        return 2
    if args.yes and args.action == "approve":
        argv.append("--yes")
    return int(confirm_main(argv) or 0)


# --- dashboard --------------------------------------------------------------------


def cmd_dashboard(args: argparse.Namespace) -> int:
    try:
        cfg = _load(args)
    except ConfigError as exc:
        _err(str(exc), _config_fix(exc))
        return 2
    host = args.host or cfg.dashboard_host
    port = args.port or cfg.dashboard_port
    auth = cfg.dashboard_auth
    if auth != "off" and not os.environ.get("AGENTTAINT_DASHBOARD_TOKEN", "").strip():
        _err(
            "dashboard.auth is enabled but AGENTTAINT_DASHBOARD_TOKEN is not set",
            "add AGENTTAINT_DASHBOARD_TOKEN to .env (`agenttaint init` generates one), or set "
            "dashboard.auth: off for loopback-only use",
        )
        return 2
    if auth == "off" and host not in LOOPBACK:
        _err(
            "refusing to serve an unauthenticated dashboard on a non-loopback host",
            "bind to 127.0.0.1, or set dashboard.auth: required",
        )
        return 2
    os.environ["AGENTTAINT_API_AUTH"] = auth
    os.environ["AGENTTAINT_DATABASE_URL"] = cfg.database_url
    if cfg.security_database_url:
        os.environ["AGENTTAINT_SECURITY_DB_URL"] = cfg.security_database_url
    if cfg.trust_registry is not None:
        os.environ.setdefault("AGENTTAINT_POLICY_DIR", str(cfg.trust_registry.parent))

    import uvicorn
    from agenttaint_api.app import ui_directory  # type: ignore[import-untyped]

    ui = ui_directory()
    print(f"AgentTaint dashboard on http://{host}:{port}  (auth: {auth})")
    if ui is None:
        print("Note: no bundled UI found; serving the API only (set AGENTTAINT_UI_DIR).")
    uvicorn.run("agenttaint_api.app:app", host=host, port=port, reload=False)
    return 0


# --- entry point ------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agenttaint",
        description="Provenance-based tool-call firewall for MCP agents.",
    )
    parser.add_argument("--version", action="version", version=f"agenttaint {__version__}")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create agenttaint.yaml, policies/ and a private .env")
    p_init.add_argument("directory", nargs="?", default=".")
    p_init.add_argument("--force", action="store_true", help="Overwrite config and policies")
    p_init.add_argument("--rotate", action="store_true", help="Rotate secrets in .env")
    p_init.add_argument(
        "--backend",
        metavar="CMD",
        help='MCP server command to protect, e.g. --backend "npx -y @scope/server /path"',
    )
    p_init.add_argument(
        "--client",
        choices=ui.CLIENTS,
        help="Also print the config snippet for this MCP client",
    )
    p_init.set_defaults(func=cmd_init)

    p_proxy = sub.add_parser("proxy", help="Run the MCP proxy on stdio in front of a server")
    p_proxy.add_argument("--config", default=DEFAULT_CONFIG)
    p_proxy.add_argument(
        "--demo-backend",
        action="store_true",
        help="Protect the built-in mock email server instead of backend.command",
    )
    p_proxy.set_defaults(func=cmd_proxy)

    p_approve = sub.add_parser("approve", help="List, show, approve or deny confirmations")
    p_approve.add_argument("--config", default=DEFAULT_CONFIG)
    p_approve.add_argument("action", choices=["list", "show", "approve", "deny"])
    p_approve.add_argument("confirmation_id", nargs="?")
    p_approve.add_argument("--yes", action="store_true", help="Skip the interactive prompt")
    p_approve.set_defaults(func=cmd_approve)

    p_dash = sub.add_parser("dashboard", help="Serve the dashboard and control-plane API")
    p_dash.add_argument("--config", default=DEFAULT_CONFIG)
    p_dash.add_argument("--host", default=None)
    p_dash.add_argument("--port", type=int, default=None)
    p_dash.set_defaults(func=cmd_dashboard)

    p_conn = sub.add_parser("connect", help="Print the MCP client config that runs the proxy")
    p_conn.add_argument("client", choices=ui.CLIENTS)
    p_conn.add_argument("--config", default=DEFAULT_CONFIG)
    p_conn.set_defaults(func=cmd_connect)

    p_doc = sub.add_parser("doctor", help="Check config, secrets, backend and dependencies")
    p_doc.add_argument("--config", default=DEFAULT_CONFIG)
    p_doc.set_defaults(func=cmd_doctor)

    p_log = sub.add_parser("log", help="Show recent ALLOW / CONFIRM / BLOCK decisions")
    p_log.add_argument("--config", default=DEFAULT_CONFIG)
    p_log.add_argument("--limit", type=int, default=20)
    p_log.set_defaults(func=cmd_log)

    p_ver = sub.add_parser("version", help="Print the version")
    p_ver.set_defaults(func=lambda _a: print(f"agenttaint {__version__}") or 0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ui.set_no_color(bool(args.no_color))
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
