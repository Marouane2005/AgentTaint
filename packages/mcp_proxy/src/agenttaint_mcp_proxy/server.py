"""MCP-facing security proxy.

Two modes:
1. Legacy FastMCP in-process composition (demo / unit helpers).
2. Preferred multi-process protocol proxy (`protocol_proxy`) that is an MCP
   client to a real downstream MCP server over stdio.

This module wires confirmation + reconstruction into the default gateway path
and accepts `_agenttaint` metadata on tool calls.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agenttaint_agent_sdk.persistence import DurableConfirmationService
from agenttaint_audit.store import AuditStore
from agenttaint_core.config import ConfigurationError, resolve_confirm_secret
from agenttaint_core.schemas import Origin
from agenttaint_policy.adapter import PolicyAdapter
from agenttaint_policy.loader import load_policy, load_stub_policy
from agenttaint_provenance.registry import ProvenanceRegistry
from agenttaint_reconstruction.engine import CandidateRecord, ReconstructionEngine
from agenttaint_reconstruction.semantic import FixtureEmbeddingBackend
from agenttaint_risk.classifier import RiskClassifier
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from agenttaint_mcp_proxy.backends import MappingBackend, ToolBackend, ToolSpec
from agenttaint_mcp_proxy.errors import EnforcementError
from agenttaint_mcp_proxy.gateway import SecurityGateway
from agenttaint_mcp_proxy.wire import (
    AGENTTAINT_META_KEY,
    AgentIdentityError,
    extract_wire_metadata,
    resolve_agent_identity,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_policy(path: Path) -> PolicyAdapter:
    if "stub" in path.name.lower():
        return load_stub_policy(path)
    return load_policy(path)


def _default_security_db_url() -> str:
    return os.environ.get(
        "AGENTTAINT_SECURITY_DB_URL",
        "sqlite+pysqlite:///:memory:",
    )


def build_gateway_from_paths(
    *,
    backend: ToolBackend,
    trust_registry_path: str | Path | None = None,
    policy_path: str | Path | None = None,
    database_url: str = "sqlite+pysqlite:///:memory:",
    security_database_url: str | None = None,
    confirmation_secret: str | None = None,
    enable_confirmation: bool = True,
    enable_reconstruction: bool = True,
) -> SecurityGateway:
    root = _repo_root()
    trust_path = Path(trust_registry_path or root / "policies" / "trust_registry.yaml")
    pol_path = Path(policy_path or root / "policies" / "provenance_policy.yaml")

    from agenttaint_provenance.store import ProvenanceStore
    from agenttaint_provenance.trust import load_trust_registry

    trust = load_trust_registry(trust_path)
    registry = ProvenanceRegistry(
        store=ProvenanceStore(database_url),
        trust=trust,
    )
    audit = AuditStore(database_url)
    policy = _load_policy(pol_path)

    confirmation = None
    if enable_confirmation:
        confirmation = DurableConfirmationService(
            # Fails closed (ConfigurationError) when no strong secret is configured.
            secret=resolve_confirm_secret(confirmation_secret),
            database_url=security_database_url or _default_security_db_url(),
        )

    reconstruction = None
    if enable_reconstruction:
        reconstruction = ReconstructionEngine(registry, embedding_backend=FixtureEmbeddingBackend())

    return SecurityGateway(
        backend=backend,
        registry=registry,
        risk=RiskClassifier(trust),
        policy=policy,
        audit=audit,
        confirmation=confirmation,  # type: ignore[arg-type]
        reconstruction=reconstruction,
        registry_available=None,
    )


def _candidate_records(raw: list[dict[str, Any]] | None) -> list[Any]:
    if not raw:
        return []
    out: list[Any] = []
    for item in raw:
        origin_raw = item.get("origin", "UNTRUSTED_TOOL")
        try:
            origin = Origin(str(origin_raw))
        except Exception:  # noqa: BLE001
            origin = Origin.UNTRUSTED_TOOL
        try:
            out.append(
                CandidateRecord(
                    span_id=str(item.get("span_id") or item.get("id") or ""),
                    text=str(item.get("text") or item.get("content") or ""),
                    origin=origin,
                )
            )
        except Exception:  # noqa: BLE001
            out.append(item)
    return out


def create_security_proxy(
    gateway: SecurityGateway,
    *,
    name: str = "agenttaint-mcp-proxy",
    agent_id: str = "agent_default",
) -> FastMCP:
    """Expose backend tools through the enforcement gateway as an MCP server."""
    mcp = FastMCP(
        name=name,
        instructions=(
            "AgentTaint MCP security proxy. All tool calls are risk-classified, "
            "policy-evaluated, audited, and provenance-labeled. Blocked calls never "
            "reach the backend. Pass confirmation_id / approval_token / "
            "argument_parent_span_ids via the _agenttaint argument object."
        ),
    )
    mcp._agenttaint_gateway = gateway  # type: ignore[attr-defined]

    def _deny_payload(exc: EnforcementError) -> str:
        return (
            f"AgentTaint {exc.decision.decision.value}: {exc.decision.explanation} "
            f"[call_id={exc.decision.call_id} policy={exc.decision.policy_id}]"
        )

    def _success_payload(outcome: Any) -> dict[str, Any]:
        payload = outcome.result
        if not isinstance(payload, dict):
            payload = {"result": payload}
        meta: dict[str, Any] = {
            "call_id": outcome.decision.call_id,
            "decision": outcome.decision.decision.value,
            "span_id": None if outcome.result_span is None else outcome.result_span.span_id,
            "origin": None if outcome.result_span is None else outcome.result_span.origin.value,
            "risk_tier": outcome.decision.risk_tier.value,
            "policy_id": outcome.decision.policy_id,
            "confirmation_id": outcome.decision.confirmation_id,
        }
        if outcome.confirmation is not None:
            meta["confirmation_id"] = outcome.confirmation.confirmation_id
            meta["confirmation_status"] = getattr(
                outcome.confirmation.status, "value", str(outcome.confirmation.status)
            )
        return {**payload, AGENTTAINT_META_KEY: meta}

    def _invoke(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        wire = extract_wire_metadata(arguments)
        clean = dict(wire.clean_arguments or {})
        try:
            effective_agent = resolve_agent_identity(wire, agent_id)
        except AgentIdentityError as exc:
            raise ToolError(f"AgentTaint BLOCK: {exc}") from exc
        try:
            outcome = gateway.invoke(
                tool_name,
                clean,
                agent_id=effective_agent,
                raise_on_deny=True,
                confirmation_id=wire.confirmation_id,
                approval_token=wire.approval_token,
                argument_parent_span_ids=wire.argument_parent_span_ids,
                candidates=_candidate_records(wire.candidates),
                session_id=wire.session_id,
            )
        except EnforcementError as exc:
            if exc.decision.decision.value == "CONFIRM" and exc.decision.confirmation_id:
                raise ToolError(
                    json.dumps(
                        {
                            "decision": "CONFIRM",
                            "confirmation_id": exc.decision.confirmation_id,
                            "explanation": exc.decision.explanation,
                            "policy_id": exc.decision.policy_id,
                            "call_id": exc.decision.call_id,
                        },
                        sort_keys=True,
                    )
                ) from exc
            raise ToolError(_deny_payload(exc)) from exc
        return _success_payload(outcome)

    tool_names = {spec.name for spec in gateway.list_tools()}

    if "email.read" in tool_names:

        @mcp.tool(name="email.read", description="Read messages from the local mock inbox.")
        def email_read(
            message_id: str | None = None,
            agenttaint: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            args: dict[str, Any] = {}
            if message_id is not None:
                args["message_id"] = message_id
            if agenttaint is not None:
                args[AGENTTAINT_META_KEY] = agenttaint
            return _invoke("email.read", args)

    if "email.send" in tool_names:

        @mcp.tool(name="email.send", description="Send an email via the local mock outbox.")
        def email_send(
            to: str,
            subject: str = "",
            body: str = "",
            attachment: str | None = None,
            agenttaint: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            args: dict[str, Any] = {
                "to": to,
                "subject": subject,
                "body": body,
                "attachment": attachment,
            }
            if agenttaint is not None:
                args[AGENTTAINT_META_KEY] = agenttaint
            return _invoke("email.send", args)

    for spec in gateway.list_tools():
        if spec.name in {"email.read", "email.send"}:
            continue
        tool_name = spec.name
        description = spec.description

        def _register(_name: str = tool_name, _description: str = description) -> None:
            @mcp.tool(name=_name, description=_description)
            def _handler(
                arguments: dict[str, Any] | None = None,
                agenttaint: dict[str, Any] | None = None,
            ) -> dict[str, Any]:
                args = dict(arguments or {})
                if agenttaint is not None:
                    args[AGENTTAINT_META_KEY] = agenttaint
                return _invoke(_name, args)

        _register()

    @mcp.tool(
        name="agenttaint.preview",
        description="Preview an enforcement decision without executing a tool.",
    )
    def preview(tool_name: str, arguments_json: str = "{}") -> dict[str, Any]:
        args = json.loads(arguments_json) if arguments_json else {}
        wire = extract_wire_metadata(args if isinstance(args, dict) else {})
        try:
            effective_agent = resolve_agent_identity(wire, agent_id)
        except AgentIdentityError as exc:
            raise ToolError(f"AgentTaint BLOCK: {exc}") from exc
        decision = gateway.preview(
            tool_name,
            wire.clean_arguments or {},
            agent_id=effective_agent,
            argument_parent_span_ids=wire.argument_parent_span_ids,
            candidates=_candidate_records(wire.candidates),
            session_id=wire.session_id,
        )
        return decision.model_dump(mode="json")

    @mcp.tool(
        name="agenttaint.audit_summary",
        description="Return counts of ALLOW/BLOCK/CONFIRM decisions recorded so far.",
    )
    def audit_summary() -> dict[str, Any]:
        return {"counts": gateway.audit.count_by_decision()}

    return mcp


def create_proxy_with_mock_email(
    *,
    policy: PolicyAdapter | None = None,
    trust_registry_path: str | Path | None = None,
    policy_path: str | Path | None = None,
    agent_id: str = "agent_default",
    enable_confirmation: bool = True,
    enable_reconstruction: bool = True,
) -> tuple[FastMCP, SecurityGateway]:
    """Convenience wiring for local demos and tests."""
    from agenttaint_mock_email.backend import MockEmailBackend

    email = MockEmailBackend()
    specs = [
        ToolSpec(
            name=item["name"],
            description=item["description"],
            input_schema=item["inputSchema"],
        )
        for item in email.list_tool_specs()
    ]
    backend = MappingBackend(
        tools={
            "email.read": lambda args: email.read(message_id=args.get("message_id")),
            "email.send": lambda args: email.send(
                to=str(args.get("to", "")),
                subject=str(args.get("subject", "")),
                body=str(args.get("body", "")),
                attachment=args.get("attachment"),
            ),
        },
        specs=specs,
    )

    if policy is None:
        gateway = build_gateway_from_paths(
            backend=backend,
            trust_registry_path=trust_registry_path,
            policy_path=policy_path,
            enable_confirmation=enable_confirmation,
            enable_reconstruction=enable_reconstruction,
        )
    else:
        root = _repo_root()
        trust_path = Path(trust_registry_path or root / "policies" / "trust_registry.yaml")
        from agenttaint_provenance.store import ProvenanceStore
        from agenttaint_provenance.trust import load_trust_registry

        trust = load_trust_registry(trust_path)
        registry = ProvenanceRegistry(
            store=ProvenanceStore("sqlite+pysqlite:///:memory:"),
            trust=trust,
        )
        confirmation = None
        if enable_confirmation:
            confirmation = DurableConfirmationService(
                secret=resolve_confirm_secret(),
                database_url=_default_security_db_url(),
            )
        reconstruction = None
        if enable_reconstruction:
            reconstruction = ReconstructionEngine(
                registry, embedding_backend=FixtureEmbeddingBackend()
            )
        gateway = SecurityGateway(
            backend=backend,
            registry=registry,
            risk=RiskClassifier(trust),
            policy=policy,
            audit=AuditStore("sqlite+pysqlite:///:memory:"),
            confirmation=confirmation,  # type: ignore[arg-type]
            reconstruction=reconstruction,
            registry_available=None,
        )

    gateway._mock_email = email  # type: ignore[attr-defined]
    proxy = create_security_proxy(gateway, agent_id=agent_id)
    return proxy, gateway


def main() -> None:
    backend_cmd = os.environ.get("AGENTTAINT_BACKEND_CMD")
    if backend_cmd:
        from agenttaint_mcp_proxy.protocol_proxy import main as protocol_main

        protocol_main()
        return
    try:
        proxy, _gateway = create_proxy_with_mock_email()
    except ConfigurationError as exc:
        raise SystemExit(f"AgentTaint proxy refusing to start: {exc}") from exc
    proxy.run(transport="stdio")


if __name__ == "__main__":
    main()
