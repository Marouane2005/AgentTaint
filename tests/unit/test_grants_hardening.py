"""Grant matching: case sensitivity by kind, list arguments, expanded authority names."""

from __future__ import annotations

from agenttaint_policy.context import DEFAULT_AUTHORITY_ARGUMENTS
from agenttaint_policy.grants import (
    AuthorizationGrant,
    flatten_argument_values,
    grants_cover_authority_arguments,
    values_equivalent,
)


def _covered(grants: list[AuthorizationGrant], args: dict[str, object]) -> bool:
    return grants_cover_authority_arguments(
        grants=grants,
        tool_name="email.send",
        arguments=args,
        authority_argument_names=set(DEFAULT_AUTHORITY_ARGUMENTS),
    )


def test_email_and_url_host_are_case_insensitive() -> None:
    assert values_equivalent("Bob@Corp.Test", "bob@corp.test")
    assert values_equivalent("HTTPS://Example.COM/a", "https://example.com/a")


def test_paths_and_commands_are_case_sensitive() -> None:
    assert not values_equivalent("/tmp/X", "/tmp/x")
    assert not values_equivalent("rm -rf /tmp/A", "rm -rf /tmp/a")
    assert not values_equivalent("https://example.com/Secret", "https://example.com/secret")
    assert values_equivalent(" /tmp/x ", "/tmp/x")


def test_redaction_placeholders_never_authorize_in_any_case() -> None:
    assert not values_equivalent("[REDACTED_EMAIL]", "[REDACTED_EMAIL]")
    assert not values_equivalent("[redacted_email]", "[REDACTED_EMAIL]")


def test_grant_on_to_does_not_cover_bcc_cc_or_cwd() -> None:
    g = [AuthorizationGrant(tool="email.send", argument="to", value="bob@corp.test")]
    assert _covered(g, {"to": "bob@corp.test"})
    assert not _covered(g, {"to": "bob@corp.test", "bcc": "evil@x.test"})
    assert not _covered(g, {"to": "bob@corp.test", "cc": "evil@x.test"})
    assert not _covered(g, {"to": "bob@corp.test", "cwd": "/"})
    assert not _covered(g, {"to": "bob@corp.test", "args": ["-rf", "/"]})
    assert not _covered(g, {"to": "bob@corp.test", "uri": "https://evil.test"})
    assert not _covered(g, {"to": "bob@corp.test", "target": "x"})


def test_list_valued_arguments_need_a_grant_per_element() -> None:
    g = [AuthorizationGrant(tool="email.send", argument="recipients", value="a@corp.test")]
    assert _covered(g, {"recipients": ["a@corp.test"]})
    assert not _covered(g, {"recipients": ["a@corp.test", "evil@x.test"]})
    assert not _covered(g, {"recipients": ["evil@x.test"]})


def test_flatten_argument_values() -> None:
    assert flatten_argument_values(["a", ["b", {"k": "c"}], None, 3]) == ["a", "b", "c", "3"]
    assert flatten_argument_values("x") == ["x"]
    assert flatten_argument_values(None) == []


def test_expanded_authority_names_present() -> None:
    for name in ("cc", "bcc", "cwd", "args", "uri", "target", "recipient", "recipients"):
        assert name in DEFAULT_AUTHORITY_ARGUMENTS
