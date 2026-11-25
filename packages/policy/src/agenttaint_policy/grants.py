"""Structured, scoped USER authorization grants.

Free-text USER spans must never be scraped into a global allow-list of tokens.
A grant authorizes one (tool, argument, value) tuple for an optional agent/session.
"""

from __future__ import annotations

from dataclasses import dataclass

from agenttaint_core.hashing import redact_sensitive


def normalize_grant_value(value: str) -> str:
    """Kind-aware normalisation.

    Only values that are case-insensitive by definition are casefolded: email
    addresses and URL scheme/host. Paths, shell commands and other values are
    compared case-sensitively so ``/tmp/X`` can never authorize ``/tmp/x``.
    """
    text = value.strip()
    if "://" in text:
        scheme, _, rest = text.partition("://")
        host, slash, tail = rest.partition("/")
        return f"{scheme.casefold()}://{host.casefold()}{slash}{tail}"
    if "@" in text and not any(ch in text for ch in " /\\"):
        return text.casefold()
    return text


def flatten_argument_values(value: object) -> list[str]:
    """Leaf string values of an argument (lists/dicts are flattened, never str()-ed)."""
    if isinstance(value, dict):
        return [leaf for v in value.values() for leaf in flatten_argument_values(v)]
    if isinstance(value, list | tuple | set | frozenset):
        return [leaf for v in value for leaf in flatten_argument_values(v)]
    if value is None:
        return []
    return [str(value)]


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
        redact_sensitive("user@example.com").casefold(),
        redact_sensitive("https://example.com/x").casefold(),
        "[redacted_email]",
        "[redacted_url]",
        "[redacted_ip]",
    }
    if g.casefold() in placeholders or a.casefold() in placeholders:
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
    present = {
        name: [leaf for leaf in flatten_argument_values(arguments[name]) if leaf.strip()]
        for name in sorted(authority_argument_names)
        if name in arguments
    }
    present = {name: leaves for name, leaves in present.items() if leaves}
    if not present:
        return False
    # Every leaf of every present authority argument (each recipient in a list, each
    # element of ``args``) must be covered by its own grant.
    for name, leaves in present.items():
        for value in leaves:
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
