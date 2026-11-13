"""Terminal confirmation UX for local MVP (no dashboard)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TextIO

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
