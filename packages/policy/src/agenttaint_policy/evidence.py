"""Build PolicyContext from registry lineage + reconstruction evidence.

INFERRED reconstruction never upgrades to KNOWN and never alone authorizes.
USER authorization must be supplied as structured grants — USER free text is not scraped.
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

from agenttaint_policy.context import (
    DEFAULT_AUTHORITY_ARGUMENTS,
    DEFAULT_CONTENT_ARGUMENTS,
    PolicyContext,
)
from agenttaint_policy.grants import AuthorizationGrant, flatten_argument_values


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
    """Deprecated: returns only explicit extras.

    Free-text USER spans are intentionally NOT scraped. Callers must pass
    structured AuthorizationGrant objects instead.
    """
    _ = registry  # retained for call-site compatibility
    return {str(v).strip() for v in (extra or []) if str(v).strip()}


def grants_from_legacy_values(
    values: Iterable[str],
    *,
    tool: str = "*",
    argument: str = "*",
    agent_id: str | None = None,
    session_id: str | None = None,
) -> list[AuthorizationGrant]:
    """Compatibility helper for benchmarks that still list bare authorized values."""
    return [
        AuthorizationGrant(
            tool=tool,
            argument=argument,
            value=str(v),
            agent_id=agent_id,
            session_id=session_id,
        )
        for v in values
        if str(v).strip()
    ]


def build_policy_context(
    *,
    risk_tier: RiskTier,
    registry: ProvenanceRegistry | None,
    registry_available: bool = True,
    argument_evidence: list[ArgumentEvidence] | None = None,
    argument_parent_span_ids: dict[str, list[str]] | None = None,
    authorization_grants: Iterable[AuthorizationGrant] | None = None,
    user_authorized_values: Iterable[str] | None = None,
    authority_argument_names: set[str] | None = None,
    content_argument_names: set[str] | None = None,
    confirmation_id: str | None = None,
    confirmation_validated: bool = False,
    agent_id: str | None = None,
    session_id: str | None = None,
    tool_name: str | None = None,
    session_untrusted_seen: bool = False,
) -> PolicyContext:
    """Assemble policy inputs. Reconstruction evidence may only raise scrutiny."""
    authority = set(authority_argument_names or DEFAULT_AUTHORITY_ARGUMENTS)
    content_names = set(content_argument_names or DEFAULT_CONTENT_ARGUMENTS)
    evidence = list(argument_evidence or [])
    parents = dict(argument_parent_span_ids or {})

    grants = list(authorization_grants or [])
    # Legacy bare values become wildcard grants only when explicitly supplied —
    # never auto-mined from USER spans in the registry.
    if user_authorized_values:
        grants.extend(
            grants_from_legacy_values(
                user_authorized_values,
                agent_id=agent_id,
                session_id=session_id,
            )
        )

    has_explicit_untrusted = False
    has_inferred_untrusted = False
    statuses: list[ProvenanceStatus] = []

    if registry is not None and registry_available:
        for _arg_name, span_ids in parents.items():
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

    declared_args = {name for name, ids in parents.items() if ids}
    for ev in evidence:
        if not ev.matched_source_ids and ev.argument_name in declared_args:
            # Independent reconstruction found no untrusted source for an argument whose
            # lineage the caller declared: that is the absence of contrary evidence, not
            # a lineage gap, so it must not downgrade the declared status. (Matches below
            # still add influence: declared lineage never overrides verification.)
            continue
        statuses.append(ev.provenance_status)
        if not ev.matched_source_ids:
            continue
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
                    if src.origin == Origin.USER:
                        continue
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

    lineage_declared = any(bool(v) for v in parents.values())
    # Missing lineage is never clean: MEDIUM/HIGH calls without declared parents are
    # UNKNOWN, except that reconstruction may report INFERRED (never KNOWN).
    if (
        risk_tier in {RiskTier.HIGH, RiskTier.MEDIUM}
        and not lineage_declared
        and overall != ProvenanceStatus.INFERRED
    ):
        overall = ProvenanceStatus.UNKNOWN

    return PolicyContext(
        provenance_status=overall,
        has_untrusted_influence=has_untrusted,
        influence_inferred_only=influence_inferred_only,
        authorization_grants=grants,
        user_authorized_values={g.value for g in grants},
        authority_argument_names=authority,
        content_argument_names=content_names,
        argument_evidence=evidence,
        registry_available=registry_available,
        confirmation_id=confirmation_id,
        confirmation_validated=confirmation_validated,
        risk_tier=risk_tier,
        agent_id=agent_id,
        session_id=session_id,
        tool_name=tool_name,
        lineage_declared=lineage_declared,
        session_untrusted_seen=session_untrusted_seen,
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
    content_argument_names: set[str] | None = None,
) -> list[ArgumentEvidence]:
    """Run reconstruction on authority and content arguments."""
    evidence: list[ArgumentEvidence] = []
    names = set(authority_argument_names) | set(content_argument_names or ())
    for name in names:
        if name not in arguments:
            continue
        # Lists / nested values are reconstructed leaf by leaf; passing recipients as a
        # list must not skip reconstruction.
        for value in flatten_argument_values(arguments[name]):
            if not value.strip():
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
