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
    "session_id": {"type": "string"},
}


class AgentIdentityError(PermissionError):
    """Caller tried to assert an agent identity different from the proxy's own."""


def resolve_agent_identity(wire: WireMetadata, configured_agent_id: str) -> str:
    """Agent identity comes from proxy configuration, never from the caller.

    A caller-supplied ``agent_id`` is accepted only if it equals the configured
    identity (harmless echo); any other value is rejected so it can never be used
    to impersonate another agent or satisfy a confirmation bound to one.
    """
    claimed = wire.agent_id
    if claimed is not None and claimed != configured_agent_id:
        raise AgentIdentityError(
            "agent_id is derived from proxy configuration; caller-supplied identity "
            f"{claimed!r} rejected"
        )
    return configured_agent_id


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


class WireMetadataError(ValueError):
    """The ``_agenttaint`` metadata object is malformed; the call must be rejected."""


class SessionIdentityError(PermissionError):
    """Caller tried to assert a session different from the one bound to this connection."""


MAX_PARENT_ARGUMENTS = 64
MAX_PARENT_IDS_PER_ARGUMENT = 128
MAX_CANDIDATES = 64
MAX_CANDIDATE_TEXT_CHARS = 65_536
MAX_ID_CHARS = 256
MAX_META_JSON_CHARS = 1_000_000


def resolve_session_identity(wire: WireMetadata, bound_session_id: str) -> str:
    """Session identity is bound to the connection, never chosen by the caller.

    Session-scoped authorization grants and the reconstruction corpus are keyed by
    session, so a caller-asserted ``session_id`` would let one session borrow another
    session's grants. A caller may echo the bound id; anything else is rejected.
    """
    claimed = wire.session_id
    if claimed is not None and claimed != bound_session_id:
        raise SessionIdentityError(
            "session_id is bound to this proxy connection; caller-supplied session "
            f"{claimed!r} rejected"
        )
    return bound_session_id


def _require_str_id(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WireMetadataError(f"{where} must be a non-empty string")
    if len(value) > MAX_ID_CHARS:
        raise WireMetadataError(f"{where} longer than {MAX_ID_CHARS} characters")
    return value


def _parse_meta(meta_raw: Any) -> dict[str, Any]:
    if meta_raw is None:
        return {}
    if isinstance(meta_raw, str):
        if len(meta_raw) > MAX_META_JSON_CHARS:
            raise WireMetadataError("_agenttaint metadata too large")
        try:
            parsed = json.loads(meta_raw)
        except json.JSONDecodeError as exc:
            raise WireMetadataError(f"_agenttaint is not valid JSON: {exc.msg}") from exc
        if not isinstance(parsed, dict):
            raise WireMetadataError("_agenttaint JSON must be an object")
        return parsed
    if isinstance(meta_raw, dict):
        return dict(meta_raw)
    raise WireMetadataError(
        f"_agenttaint must be an object or a JSON object string, got {type(meta_raw).__name__}"
    )


def extract_wire_metadata(arguments: dict[str, Any] | None) -> WireMetadata:
    """Split `_agenttaint` metadata from backend tool arguments.

    Malformed metadata raises :class:`WireMetadataError` instead of being silently
    dropped: dropping it would quietly turn a declared lineage into an undeclared one.
    """
    args = dict(arguments or {})
    meta = _parse_meta(args.pop(AGENTTAINT_META_KEY, None))

    parent_map: dict[str, list[str]] | None = None
    parents = meta.get("argument_parent_span_ids")
    if parents is not None:
        if not isinstance(parents, dict):
            raise WireMetadataError("argument_parent_span_ids must be an object")
        if len(parents) > MAX_PARENT_ARGUMENTS:
            raise WireMetadataError("argument_parent_span_ids has too many arguments")
        parent_map = {}
        for key, ids in parents.items():
            if not isinstance(ids, list):
                raise WireMetadataError(f"argument_parent_span_ids[{key!r}] must be a list")
            if len(ids) > MAX_PARENT_IDS_PER_ARGUMENT:
                raise WireMetadataError(f"argument_parent_span_ids[{key!r}] has too many ids")
            parent_map[str(key)] = [
                _require_str_id(x, f"argument_parent_span_ids[{key!r}] entry") for x in ids
            ]

    cand_list: list[dict[str, Any]] | None = None
    candidates = meta.get("candidates")
    if candidates is not None:
        if not isinstance(candidates, list):
            raise WireMetadataError("candidates must be a list")
        if len(candidates) > MAX_CANDIDATES:
            raise WireMetadataError("too many candidates")
        cand_list = []
        for item in candidates:
            if not isinstance(item, dict):
                raise WireMetadataError("each candidate must be an object")
            text = item.get("text", item.get("content", ""))
            if text is not None and (
                not isinstance(text, str) or len(text) > MAX_CANDIDATE_TEXT_CHARS
            ):
                raise WireMetadataError("candidate text must be a string of bounded size")
            cand_list.append(item)

    for key in ("confirmation_id", "approval_token", "agent_id", "session_id"):
        value = meta.get(key)
        if value is not None and not isinstance(value, str):
            raise WireMetadataError(f"{key} must be a string")

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
            "AgentTaint enforcement metadata: confirmation_id, approval_token (issued to "
            "the human approver), argument_parent_span_ids, candidates. Agent and session "
            "identity are fixed by the proxy; approvals happen out-of-band."
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
