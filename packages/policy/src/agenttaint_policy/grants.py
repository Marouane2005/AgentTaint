"""Structured, scoped USER authorization grants.

Free-text USER spans must never be scraped into a global allow-list of tokens.
A grant authorizes one (tool, argument, value) tuple for an optional agent/session.
"""

from __future__ import annotations

from dataclasses import dataclass

from agenttaint_core.hashing import redact_sensitive


def normalize_grant_value(value: str) -> str:
    return value.strip().casefold()


def values_equivalent(granted: str, actual: str) -> bool:
    """Match grant values to live call arguments.

    Matching uses cleartext equality (casefold/strip). Redacted placeholders such as
    ``[REDACTED_EMAIL]`` never authorize, because every email redacts to the same
    token. Callers must compare grants against live tool arguments (not audit
    redactions) so redaction of stored USER text cannot break or widen matching.
    """
    g = normalize_grant_value(granted)
    a = normalize_grant_value(actual)
    if not g or not a:
        return False
    # Fail closed on redaction placeholders — they are not unique capabilities.
    placeholders = {
        normalize_grant_value(redact_sensitive("user@example.com")),
        normalize_grant_value(redact_sensitive("https://example.com/x")),
        "[redacted_email]",
        "[redacted_url]",
        "[redacted_ip]",
    }
    if g in placeholders or a in placeholders:
        return False
    return g == a


@dataclass(frozen=True)
class AuthorizationGrant:
    """Explicit authorization for one authority argument value."""

    tool: str
    argument: str
    value: str
    agent_id: str | None = None
    session_id: str | None = None

    def matches(
        self,
        *,
        tool: str,
        argument: str,
        value: str,
        agent_id: str | None = None,
        session_id: str | None = None,
    ) -> bool:
        if self.tool not in {"*", tool}:
            return False
        if self.argument not in {"*", argument}:
            return False
        if self.agent_id is not None and self.agent_id != agent_id:
            return False
        if self.session_id is not None and self.session_id != session_id:
            return False
        return values_equivalent(self.value, value)


def grants_cover_authority_arguments(
    *,
    grants: list[AuthorizationGrant],
    tool_name: str,
    arguments: dict[str, object],
    authority_argument_names: set[str],
    agent_id: str | None = None,
    session_id: str | None = None,
) -> bool:
    """True only when every present authority argument has a matching grant."""
    present = [
        name
        for name in authority_argument_names
        if name in arguments and str(arguments.get(name, "")).strip()
    ]
    if not present:
        return False
    for name in present:
        value = str(arguments[name])
        if not any(
            g.matches(
                tool=tool_name,
                argument=name,
                value=value,
                agent_id=agent_id,
                session_id=session_id,
            )
            for g in grants
        ):
            return False
    return True
