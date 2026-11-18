"""Terminal confirmation UX and out-of-band approval CLI."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TextIO

from agenttaint_agent_sdk.confirmation import ConfirmationRecord, ConfirmationService


def format_confirmation_prompt(record: ConfirmationRecord) -> str:
    lines = [
        "=== AgentTaint confirmation required ===",
        f"confirmation_id: {record.confirmation_id}",
        f"tool:            {record.tool}",
        f"agent_id:        {record.agent_id}",
        f"risk_tier:       {record.risk_tier.value}",
        f"policy_id:       {record.policy_id or '(none)'}",
        f"args_hash:       {record.arguments_hash}",
        f"expires_at:      {record.expires_at.isoformat()}",
        f"explanation:     {record.explanation}",
        "arguments (redacted):",
    ]
    for key, value in sorted(record.arguments_redacted.items()):
        lines.append(f"  {key}: {value}")
    lines.append("Approve only if these exact arguments match intent.")
    lines.append("Approve? [y/N]")
    return "\n".join(lines)


def interactive_confirm(
    service: ConfirmationService,
    record: ConfirmationRecord,
    *,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
    stream: TextIO | None = None,
) -> ConfirmationRecord:
    """Prompt a human; approval is bound and single-use via ConfirmationService."""
    prompt = format_confirmation_prompt(record)
    if stream is not None:
        stream.write(prompt + "\n")
        stream.flush()
    else:
        print_fn(prompt)
    answer = input_fn("> ").strip().casefold()
    if answer in {"y", "yes"}:
        return service.approve(record.confirmation_id)
    return service.deny(record.confirmation_id)


# --- Out-of-band approval CLI ------------------------------------------------
#
# Approvals must come from a channel the agent cannot reach. The MCP proxy no
# longer exposes any approval tool; a human operator runs this CLI against the
# proxy's security database instead:
#
#   export AGENTTAINT_CONFIRM_SECRET=...      # same secret as the proxy
#   export AGENTTAINT_SECURITY_DB_URL=sqlite+pysqlite:////path/to/security.db
#   python3 -m agenttaint_agent_sdk.confirm_cli list
#   python3 -m agenttaint_agent_sdk.confirm_cli approve <confirmation_id>
#
# The approval token stays in the security database; the agent retries the exact
# call with only ``_agenttaint.confirmation_id`` and the proxy validates it.


def _build_service(database_url: str | None) -> Any:
    import os

    from agenttaint_core.config import resolve_confirm_secret

    from agenttaint_agent_sdk.persistence import DurableConfirmationService

    url = (database_url or os.environ.get("AGENTTAINT_SECURITY_DB_URL", "")).strip()
    if not url:
        raise SystemExit(
            "Set AGENTTAINT_SECURITY_DB_URL (or --database-url) to the proxy's security DB."
        )
    return DurableConfirmationService(secret=resolve_confirm_secret(), database_url=url)


def main(argv: list[str] | None = None) -> int:
    import argparse

    from agenttaint_core.config import ConfigurationError

    parser = argparse.ArgumentParser(
        prog="agenttaint-confirm",
        description="Review and approve AgentTaint confirmations out-of-band.",
    )
    parser.add_argument("--database-url", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List pending confirmations")
    for name in ("show", "approve", "deny"):
        cmd = sub.add_parser(name)
        cmd.add_argument("confirmation_id")
        if name == "approve":
            cmd.add_argument(
                "--yes", action="store_true", help="Approve without the interactive prompt"
            )
    args = parser.parse_args(argv)

    try:
        service = _build_service(args.database_url)
    except ConfigurationError as exc:
        print(f"error: {exc}")
        return 2

    if args.command == "list":
        pending = service.list_by_status()
        if not pending:
            print("No pending confirmations.")
        for rec in pending:
            print(
                f"{rec.confirmation_id}  {rec.tool}  agent={rec.agent_id}  "
                f"risk={rec.risk_tier.value}  expires={rec.expires_at.isoformat()}"
            )
        return 0

    record = service.get(args.confirmation_id)
    if record is None:
        print("error: unknown confirmation_id")
        return 1
    if args.command == "show":
        print(format_confirmation_prompt(record).rsplit("\n", 1)[0])
        print(f"status:          {record.status.value}")
        return 0
    try:
        if args.command == "deny":
            service.deny(args.confirmation_id)
            print(f"DENIED {args.confirmation_id}")
            return 0
        if not args.yes:
            print(format_confirmation_prompt(record))
            if input("> ").strip().casefold() not in {"y", "yes"}:
                service.deny(args.confirmation_id)
                print(f"DENIED {args.confirmation_id}")
                return 0
        service.approve(args.confirmation_id)
    except Exception as exc:  # noqa: BLE001 - surface binder errors to the operator
        print(f"error: {exc}")
        return 1
    print(f"APPROVED {args.confirmation_id} (single use, bound to tool/arguments/agent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
