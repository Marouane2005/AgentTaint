"""Origin labeling for information entering the system."""

from __future__ import annotations

from agenttaint_core.hashing import content_hash, redact_sensitive
from agenttaint_core.schemas import (
    Origin,
    ProvenanceSpan,
    ProvenanceStatus,
    SpanKind,
)

from agenttaint_provenance.trust import TrustRegistry


class SourceLabeler:
    """Assign provenance metadata at content ingress.

    Never trusts an entire tool server's output solely because the integration is trusted.
    """

    def __init__(self, trust: TrustRegistry, *, retain_redacted: bool = True) -> None:
        self.trust = trust
        self.retain_redacted = retain_redacted

    def label_tool_result(
        self,
        *,
        tool_name: str,
        content: str,
        agent_id: str | None = None,
        parent_ids: list[str] | None = None,
        path: str | None = None,
        metadata: dict | None = None,
    ) -> ProvenanceSpan:
        origin = self.trust.result_origin_for(tool_name)
        if (
            tool_name == "filesystem.read"
            and path is not None
            and self.trust.is_internal_path(path)
        ):
            origin = Origin.INTERNAL

        meta = dict(metadata or {})
        if path is not None:
            meta["path"] = path

        return ProvenanceSpan(
            origin=origin,
            kind=SpanKind.TOOL_RESULT,
            source=tool_name,
            content_hash=content_hash(content),
            content_redacted=redact_sensitive(content) if self.retain_redacted else None,
            parent_ids=list(parent_ids or []),
            agent_id=agent_id,
            provenance_status=ProvenanceStatus.KNOWN,
            metadata=meta,
        )

    def label_user_instruction(
        self,
        *,
        content: str,
        agent_id: str | None = None,
        metadata: dict | None = None,
    ) -> ProvenanceSpan:
        return ProvenanceSpan(
            origin=Origin.USER,
            kind=SpanKind.USER_INSTRUCTION,
            source="user",
            content_hash=content_hash(content),
            content_redacted=redact_sensitive(content) if self.retain_redacted else None,
            agent_id=agent_id,
            provenance_status=ProvenanceStatus.KNOWN,
            metadata=dict(metadata or {}),
        )

    def label_unknown(
        self,
        *,
        content: str,
        agent_id: str | None = None,
        reason: str = "missing_instrumentation",
    ) -> ProvenanceSpan:
        return ProvenanceSpan(
            origin=Origin.UNKNOWN,
            kind=SpanKind.GAP,
            source=None,
            content_hash=content_hash(content),
            content_redacted=redact_sensitive(content) if self.retain_redacted else None,
            agent_id=agent_id,
            provenance_status=ProvenanceStatus.UNKNOWN,
            metadata={"reason": reason},
        )
