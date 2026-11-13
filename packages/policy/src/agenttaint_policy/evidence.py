"""Build PolicyContext from registry lineage + reconstruction evidence.

INFERRED reconstruction never upgrades to KNOWN and never alone authorizes.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from agenttaint_core.hashing import content_hash
from agenttaint_core.schemas import (
    ArgumentEvidence,
    EvidenceType,
    Origin,
    ProvenanceStatus,
    RiskTier,
)
from agenttaint_provenance.registry import ProvenanceRegistry

from agenttaint_policy.context import PolicyContext


def _origins_untrusted(origins: Iterable[Origin]) -> bool:
    return any(o in {Origin.UNTRUSTED_TOOL, Origin.UNKNOWN} for o in origins)


def explicit_argument_origins(
    registry: ProvenanceRegistry,
    parent_span_ids: list[str],
) -> set[Origin]:
    origins: set[Origin] = set()
    for span_id in parent_span_ids:
        span = registry.store.get_span(span_id)
        if span is None:
            origins.add(Origin.UNKNOWN)
            continue
        origins.add(span.origin)
        for anc in registry.ancestors(span_id):
            origins.add(anc.origin)
    return origins


def collect_user_authorized_values(
    registry: ProvenanceRegistry,
    *,
    extra: Iterable[str] | None = None,
) -> set[str]:
    """Values grounded in USER instruction spans (redacted text when available)."""
    values: set[str] = {str(v).strip() for v in (extra or []) if str(v).strip()}
    for span in registry.store.list_spans():
        if span.origin != Origin.USER:
            continue
        text = (span.content_redacted or "").strip()
        if text:
            values.add(text)
            # Also split common separators so a multi-line instruction can authorize
            # a single recipient token.
            for token in text.replace(",", " ").replace("\n", " ").split():
                token = token.strip().strip(".;:")
                if "@" in token or token.startswith("http") or "/" in token:
                    values.add(token)
    return values


def build_policy_context(
    *,
    risk_tier: RiskTier,
    registry: ProvenanceRegistry | None,
    registry_available: bool = True,
    argument_evidence: list[ArgumentEvidence] | None = None,
    argument_parent_span_ids: dict[str, list[str]] | None = None,
    user_authorized_values: Iterable[str] | None = None,
    authority_argument_names: set[str] | None = None,
    confirmation_id: str | None = None,
    confirmation_validated: bool = False,
) -> PolicyContext:
    """Assemble policy inputs. Reconstruction evidence may only raise scrutiny."""
    authority = authority_argument_names or {
        "to",
        "recipient",
        "url",
        "path",
        "command",
    }
    evidence = list(argument_evidence or [])
    parents = dict(argument_parent_span_ids or {})

    has_explicit_untrusted = False
    has_inferred_untrusted = False
    statuses: list[ProvenanceStatus] = []

    if registry is not None and registry_available:
        for _arg, span_ids in parents.items():
            if not span_ids:
                continue
            origins = explicit_argument_origins(registry, span_ids)
            if _origins_untrusted(origins):
                has_explicit_untrusted = True
            for sid in span_ids:
                report = registry.lineage_completeness(sid)
                statuses.append(report.effective_status)
                if report.untrusted_source_ids:
                    has_explicit_untrusted = True
                if report.inferred_ancestor_ids or report.inferred_edge_count:
                    has_inferred_untrusted = True

        authorized = collect_user_authorized_values(
            registry, extra=user_authorized_values
        )
    else:
        authorized = {str(v).strip() for v in (user_authorized_values or []) if str(v).strip()}

    for ev in evidence:
        statuses.append(ev.provenance_status)
        if not ev.matched_source_ids:
            continue
        # Reconstruction / INFERRED evidence can flag influence but never authorize.
        if ev.evidence_type == EvidenceType.INFERRED or (
            ev.provenance_status == ProvenanceStatus.INFERRED
        ):
            if registry is not None and registry_available:
                for sid in ev.matched_source_ids:
                    src = registry.store.get_span(sid)
                    if src is None or src.origin in {
                        Origin.UNTRUSTED_TOOL,
                        Origin.UNKNOWN,
                    }:
                        has_inferred_untrusted = True
                        break
                    # Matched USER-only sources do not count as untrusted influence.
                    if src.origin == Origin.USER:
                        continue
                    # Walk ancestors of matched candidate
                    if any(
                        a.origin in {Origin.UNTRUSTED_TOOL, Origin.UNKNOWN}
                        for a in registry.ancestors(sid)
                    ):
                        has_inferred_untrusted = True
                        break
            else:
                has_inferred_untrusted = True
        elif ev.explicit_lineage:
            has_explicit_untrusted = True

    has_untrusted = has_explicit_untrusted or has_inferred_untrusted
    influence_inferred_only = has_inferred_untrusted and not has_explicit_untrusted

    if not statuses:
        overall = ProvenanceStatus.UNKNOWN
    elif any(s == ProvenanceStatus.UNKNOWN for s in statuses):
        overall = ProvenanceStatus.UNKNOWN
    elif any(s == ProvenanceStatus.PARTIAL for s in statuses):
        overall = ProvenanceStatus.PARTIAL
    elif any(s == ProvenanceStatus.INFERRED for s in statuses):
        overall = ProvenanceStatus.INFERRED
    else:
        overall = ProvenanceStatus.KNOWN

    # No argument lineage at all on HIGH-risk → UNKNOWN (fail-closed path).
    if risk_tier == RiskTier.HIGH and not parents and not evidence:
        overall = ProvenanceStatus.UNKNOWN

    return PolicyContext(
        provenance_status=overall,
        has_untrusted_influence=has_untrusted,
        influence_inferred_only=influence_inferred_only,
        user_authorized_values=authorized,
        authority_argument_names=authority,
        argument_evidence=evidence,
        registry_available=registry_available,
        confirmation_id=confirmation_id,
        confirmation_validated=confirmation_validated,
        risk_tier=risk_tier,
    )


def reconstruct_authority_evidence(
    *,
    engine: Any,
    arguments: dict[str, Any],
    candidates: list[Any],
    authority_argument_names: set[str],
    agent_id: str | None,
    attach: bool = True,
    ablation: Any | None = None,
) -> list[ArgumentEvidence]:
    """Run reconstruction on authority arguments; return ArgumentEvidence list."""
    evidence: list[ArgumentEvidence] = []
    for name in authority_argument_names:
        if name not in arguments:
            continue
        value = arguments[name]
        if not isinstance(value, str) or not value.strip():
            continue
        kwargs: dict[str, Any] = {
            "argument_name": name,
            "argument_value": value,
            "candidates": candidates,
            "agent_id": agent_id,
            "attach": attach,
        }
        if ablation is not None:
            kwargs["ablation"] = ablation
        result = engine.reconstruct_argument(**kwargs)
        if result.matches:
            for match in result.matches:
                evidence.append(match.evidence)
        else:
            evidence.append(
                ArgumentEvidence(
                    argument_name=name,
                    value_hash=content_hash(value),
                    provenance_status=ProvenanceStatus.UNKNOWN,
                    evidence_type=EvidenceType.INFERRED,
                )
            )
    return evidence
