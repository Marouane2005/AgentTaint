"""MCP wire helpers for AgentTaint metadata and schema augmentation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

AGENTTAINT_META_KEY = "_agenttaint"

_AGENTTAINT_SCHEMA_PROPS: dict[str, Any] = {
    "confirmation_id": {"type": "string"},
    "approval_token": {"type": "string"},
    "argument_parent_span_ids": {
        "type": "object",
        "additionalProperties": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "candidates": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "span_id": {"type": "string"},
                "text": {"type": "string"},
                "origin": {"type": "string"},
            },
        },
    },
    "agent_id": {"type": "string"},
    "session_id": {"type": "string"},
    "provenance_context_hash": {"type": "string"},
}


@dataclass(frozen=True)
class WireMetadata:
    confirmation_id: str | None = None
    approval_token: str | None = None
    argument_parent_span_ids: dict[str, list[str]] | None = None
    candidates: list[dict[str, Any]] | None = None
    agent_id: str | None = None
    session_id: str | None = None
    provenance_context_hash: str | None = None
    clean_arguments: dict[str, Any] | None = None


def extract_wire_metadata(arguments: dict[str, Any] | None) -> WireMetadata:
    """Split `_agenttaint` metadata from backend tool arguments."""
    args = dict(arguments or {})
    meta_raw = args.pop(AGENTTAINT_META_KEY, None)
    meta: dict[str, Any] = {}
    if isinstance(meta_raw, str):
        try:
            parsed = json.loads(meta_raw)
            if isinstance(parsed, dict):
                meta = parsed
        except json.JSONDecodeError:
            meta = {}
    elif isinstance(meta_raw, dict):
        meta = dict(meta_raw)

    parents = meta.get("argument_parent_span_ids")
    parent_map: dict[str, list[str]] | None = None
    if isinstance(parents, dict):
        parent_map = {
            str(k): [str(x) for x in (v or [])] for k, v in parents.items() if isinstance(v, list)
        }

    candidates = meta.get("candidates")
    cand_list: list[dict[str, Any]] | None = None
    if isinstance(candidates, list):
        cand_list = [c for c in candidates if isinstance(c, dict)]

    return WireMetadata(
        confirmation_id=_as_opt_str(meta.get("confirmation_id")),
        approval_token=_as_opt_str(meta.get("approval_token")),
        argument_parent_span_ids=parent_map,
        candidates=cand_list,
        agent_id=_as_opt_str(meta.get("agent_id")),
        session_id=_as_opt_str(meta.get("session_id")),
        provenance_context_hash=_as_opt_str(meta.get("provenance_context_hash")),
        clean_arguments=args,
    )


def augment_input_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    """Forward the real backend schema and document `_agenttaint` metadata."""
    base = dict(schema or {"type": "object", "properties": {}})
    if base.get("type") is None:
        base["type"] = "object"
    props = dict(base.get("properties") or {})
    props[AGENTTAINT_META_KEY] = {
        "type": "object",
        "description": (
            "AgentTaint enforcement metadata: confirmation_id, approval_token, "
            "argument_parent_span_ids, candidates, agent_id, session_id."
        ),
        "properties": dict(_AGENTTAINT_SCHEMA_PROPS),
        "additionalProperties": False,
    }
    base["properties"] = props
    return base


def _as_opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
