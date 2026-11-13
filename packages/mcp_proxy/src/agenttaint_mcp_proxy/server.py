"""MCP-facing security proxy built on the official MCP Python SDK (FastMCP).

Supported (Milestone 2):
- tools/list
- tools/call (always through SecurityGateway)
- argument capture + audit
- result provenance labeling
- ALLOW / BLOCK (CONFIRM returned as denied pending approval)

Limitations (documented):
- In-process backend composition for MVP (stdio multi-process proxy later)
- Resources / prompts not proxied yet
- No Cedar backend yet
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agenttaint_audit.store import AuditStore
from agenttaint_policy.adapter import StubPolicyAdapter
from agenttaint_policy.loader import load_stub_policy
from agenttaint_provenance.registry import ProvenanceRegistry
from agenttaint_risk.classifier import RiskClassifier
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from agenttaint_mcp_proxy.backends import MappingBackend, ToolBackend, ToolSpec
from agenttaint_mcp_proxy.errors import EnforcementError
from agenttaint_mcp_proxy.gateway import SecurityGateway


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def build_gateway_from_paths(
    *,
    backend: ToolBackend,
    trust_registry_path: str | Path | None = None,
    policy_path: str | Path | None = None,
    database_url: str = "sqlite+pysqlite:///:memory:",
) -> SecurityGateway:
    root = _repo_root()
    trust_path = Path(trust_registry_path or root / "policies" / "trust_registry.yaml")
    pol_path = Path(policy_path or root / "policies" / "stub_policy.yaml")

    from agenttaint_provenance.store import ProvenanceStore
    from agenttaint_provenance.trust import load_trust_registry

    trust = load_trust_registry(trust_path)
    registry = ProvenanceRegistry(
        store=ProvenanceStore(database_url),
        trust=trust,
    )
    audit = AuditStore(database_url)
    policy = load_stub_policy(pol_path)
    return SecurityGateway(
        backend=backend,
        registry=registry,
        risk=RiskClassifier(trust),
        policy=policy,
        audit=audit,
    )


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
            "reach the backend."
        ),
    )

    # Capture gateway for tests / introspection.
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
        meta = {
            "call_id": outcome.decision.call_id,
            "decision": outcome.decision.decision.value,
            "span_id": None if outcome.result_span is None else outcome.result_span.span_id,
            "origin": None if outcome.result_span is None else outcome.result_span.origin.value,
            "risk_tier": outcome.decision.risk_tier.value,
            "policy_id": outcome.decision.policy_id,
        }
        return {**payload, "_agenttaint": meta}

    def _register(spec: ToolSpec) -> None:
        tool_name = spec.name

        if tool_name == "email.read":

            @mcp.tool(name="email.read", description=spec.description)
            def email_read(message_id: str | None = None) -> dict[str, Any]:
                args: dict[str, Any] = {}
                if message_id is not None:
                    args["message_id"] = message_id
                try:
                    outcome = gateway.invoke(
                        "email.read", args, agent_id=agent_id, raise_on_deny=True
                    )
                except EnforcementError as exc:
                    raise ToolError(_deny_payload(exc)) from exc
                return _success_payload(outcome)

            return

        if tool_name == "email.send":

            @mcp.tool(name="email.send", description=spec.description)
            def email_send(
                to: str,
                subject: str = "",
                body: str = "",
                attachment: str | None = None,
            ) -> dict[str, Any]:
                args = {
                    "to": to,
                    "subject": subject,
                    "body": body,
                    "attachment": attachment,
                }
                try:
                    outcome = gateway.invoke(
                        "email.send", args, agent_id=agent_id, raise_on_deny=True
                    )
                except EnforcementError as exc:
                    raise ToolError(_deny_payload(exc)) from exc
                return _success_payload(outcome)

            return

        @mcp.tool(name=tool_name, description=spec.description)
        def generic_tool(
            arguments_json: str = "{}",
            _name: str = tool_name,
        ) -> dict[str, Any]:
            try:
                parsed = json.loads(arguments_json) if arguments_json else {}
                if not isinstance(parsed, dict):
                    raise ValueError("arguments_json must decode to an object")
            except (json.JSONDecodeError, ValueError) as exc:
                raise ToolError(f"invalid arguments: {exc}") from exc
            try:
                outcome = gateway.invoke(
                    _name, parsed, agent_id=agent_id, raise_on_deny=True
                )
            except EnforcementError as exc:
                raise ToolError(_deny_payload(exc)) from exc
            return _success_payload(outcome)

    for spec in gateway.list_tools():
        _register(spec)

    @mcp.tool(
        name="agenttaint.preview",
        description="Preview an enforcement decision without executing a tool.",
    )
    def preview(tool_name: str, arguments_json: str = "{}") -> dict[str, Any]:
        args = json.loads(arguments_json) if arguments_json else {}
        decision = gateway.preview(tool_name, args, agent_id=agent_id)
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
    policy: StubPolicyAdapter | None = None,
    trust_registry_path: str | Path | None = None,
    policy_path: str | Path | None = None,
    agent_id: str = "agent_default",
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
        )
    else:
        root = _repo_root()
        trust_path = Path(trust_registry_path or root / "policies" / "trust_registry.yaml")
        from agenttaint_provenance.store import ProvenanceStore
        from agenttaint_provenance.trust import load_trust_registry

        trust = load_trust_registry(trust_path)
        gateway = SecurityGateway(
            backend=backend,
            registry=ProvenanceRegistry(
                store=ProvenanceStore("sqlite+pysqlite:///:memory:"),
                trust=trust,
            ),
            risk=RiskClassifier(trust),
            policy=policy,
            audit=AuditStore("sqlite+pysqlite:///:memory:"),
        )

    # Keep backend handle for assertions.
    gateway._mock_email = email  # type: ignore[attr-defined]
    proxy = create_security_proxy(gateway, agent_id=agent_id)
    return proxy, gateway


def main() -> None:
    proxy, _gateway = create_proxy_with_mock_email()
    proxy.run(transport="stdio")


if __name__ == "__main__":
    main()
