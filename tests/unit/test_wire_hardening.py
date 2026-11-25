"""JSON-RPC wire metadata: malformed payloads are rejected, identity is connection-bound."""

from __future__ import annotations

import json

import pytest
from agenttaint_mcp_proxy.wire import (
    SessionIdentityError,
    WireMetadataError,
    augment_input_schema,
    extract_wire_metadata,
    resolve_session_identity,
)


@pytest.mark.parametrize(
    "bad",
    [
        "{not json",
        "[1, 2]",
        5,
        [1],
        {"argument_parent_span_ids": {"to": "abc"}},
        {"argument_parent_span_ids": ["x"]},
        {"argument_parent_span_ids": {"to": [1]}},
        {"argument_parent_span_ids": {"to": [""]}},
        {"argument_parent_span_ids": {"to": ["x" * 1000]}},
        {"candidates": "x"},
        {"candidates": [1]},
        {"candidates": [{"text": 5}]},
        {"confirmation_id": 5},
        {"approval_token": ["t"]},
    ],
)
def test_malformed_metadata_is_rejected_not_dropped(bad: object) -> None:
    with pytest.raises(WireMetadataError):
        extract_wire_metadata({"to": "a@b.test", "_agenttaint": bad})


def test_metadata_size_limits() -> None:
    too_many = {"argument_parent_span_ids": {f"a{i}": ["x"] for i in range(65)}}
    with pytest.raises(WireMetadataError):
        extract_wire_metadata({"_agenttaint": too_many})
    with pytest.raises(WireMetadataError):
        extract_wire_metadata({"_agenttaint": {"candidates": [{"text": "x"}] * 65}})
    with pytest.raises(WireMetadataError):
        extract_wire_metadata({"_agenttaint": {"candidates": [{"text": "x" * 70_000}]}})


def test_valid_metadata_round_trips_and_is_stripped_from_arguments() -> None:
    meta = {
        "confirmation_id": "c1",
        "approval_token": "t1",
        "argument_parent_span_ids": {"to": ["s1", "s2"]},
        "candidates": [{"span_id": "s", "text": "hello"}],
    }
    for raw in (meta, json.dumps(meta)):
        wire = extract_wire_metadata({"to": "a@b.test", "_agenttaint": raw})
        assert wire.clean_arguments == {"to": "a@b.test"}
        assert wire.confirmation_id == "c1" and wire.approval_token == "t1"
        assert wire.argument_parent_span_ids == {"to": ["s1", "s2"]}


def test_absent_metadata_is_fine() -> None:
    wire = extract_wire_metadata({"x": 1})
    assert wire.clean_arguments == {"x": 1}
    assert wire.argument_parent_span_ids is None
    assert extract_wire_metadata(None).clean_arguments == {}


def test_session_identity_is_bound_to_the_connection() -> None:
    assert resolve_session_identity(extract_wire_metadata({}), "bound") == "bound"
    echo = extract_wire_metadata({"_agenttaint": {"session_id": "bound"}})
    assert resolve_session_identity(echo, "bound") == "bound"
    spoof = extract_wire_metadata({"_agenttaint": {"session_id": "victim-session"}})
    with pytest.raises(SessionIdentityError):
        resolve_session_identity(spoof, "bound")


def test_advertised_schema_lists_approval_token() -> None:
    schema = augment_input_schema({"type": "object", "properties": {}})
    props = schema["properties"]["_agenttaint"]["properties"]
    assert "approval_token" in props and "confirmation_id" in props
