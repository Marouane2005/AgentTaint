"""Multi-process MCP protocol proxy.

Architecture:
  MCP client  --stdio-->  AgentTaint proxy (this module)  --stdio-->  backend MCP server

The proxy is a real MCP *server* to upstream clients and a real MCP *client* to the
downstream tool server. Enforcement always runs in SecurityGateway before any
backend tools/call is issued.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
from pathlib import Path
from typing import Any

import anyio
import mcp.types as types
from agenttaint_core.config import ConfigurationError, resolve_confirm_secret
from agenttaint_core.schemas import DecisionOutcome
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.lowlevel.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server

from agenttaint_mcp_proxy.backends import ToolSpec
from agenttaint_mcp_proxy.errors import EnforcementError
from agenttaint_mcp_proxy.gateway import SecurityGateway
from agenttaint_mcp_proxy.server import build_gateway_from_paths
from agenttaint_mcp_proxy.wire import (
    AGENTTAINT_META_KEY,
    AgentIdentityError,
    augment_input_schema,
    extract_wire_metadata,
    resolve_agent_identity,
)

# Proxy-side secrets must never be handed to downstream tool servers.
_SECRET_ENV_VARS = frozenset(
    {
        "AGENTTAINT_CONFIRM_SECRET",
        "AGENTTAINT_DASHBOARD_TOKEN",
        "AGENTTAINT_APPROVER_TOKEN",
        "AGENTTAINT_ADMIN_TOKEN",
        "AGENTTAINT_SHARED_SECRET",
        "AGENTTAINT_SECURITY_DB_URL",
        "AGENTTAINT_DATABASE_URL",
    }
)


def backend_environment(environ: dict[str, str] | None = None) -> dict[str, str]:
    """Environment for the downstream MCP server, minus proxy secrets/keyrings."""
    src = dict(os.environ if environ is None else environ)
    return {
        k: v
        for k, v in src.items()
        if k not in _SECRET_ENV_VARS and not k.startswith("AGENTTAINT_ENVELOPE_KEY")
    }


class _ListingBackend:
    """Placeholder backend used only for gateway construction / list_tools cache."""

    def __init__(self) -> None:
        self._specs: list[ToolSpec] = []

    def set_specs(self, specs: list[ToolSpec]) -> None:
        self._specs = list(specs)

    def list_tools(self) -> list[ToolSpec]:
        return list(self._specs)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        raise RuntimeError(
            f"protocol proxy must forward {name!r} via MCP client, not ListingBackend"
        )


def _candidate_records(raw: list[dict[str, Any]] | None) -> list[Any]:
    if not raw:
        return []
    from agenttaint_core.schemas import Origin
    from agenttaint_reconstruction.engine import CandidateRecord

    out: list[Any] = []
    for item in raw:
        origin_raw = item.get("origin", "UNTRUSTED_TOOL")
        try:
            origin = Origin(str(origin_raw))
        except Exception:  # noqa: BLE001
            origin = Origin.UNTRUSTED_TOOL
        out.append(
            CandidateRecord(
                span_id=str(item.get("span_id") or item.get("id") or ""),
                text=str(item.get("text") or item.get("content") or ""),
                origin=origin,
            )
        )
    return out


def _text_result(payload: Any, *, is_error: bool = False) -> types.CallToolResult:
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, sort_keys=True, default=str)
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        isError=is_error,
    )


async def _list_backend_tools(session: ClientSession) -> list[ToolSpec]:
    listed = await session.list_tools()
    specs: list[ToolSpec] = []
    for tool in listed.tools:
        specs.append(
            ToolSpec(
                name=tool.name,
                description=tool.description or tool.name,
                input_schema=dict(tool.inputSchema or {"type": "object"}),
            )
        )
    return specs


def build_protocol_server(
    *,
    gateway: SecurityGateway,
    backend_session: ClientSession,
    agent_id: str = "agent_default",
) -> Server:
    """Create a low-level MCP Server that enforces then forwards."""
    server = Server("agenttaint-mcp-protocol-proxy")
    cancelled: set[str | int] = set()

    @server.list_tools()  # type: ignore[untyped-decorator, no-untyped-call]
    async def list_tools() -> list[types.Tool]:
        specs = gateway.list_tools()
        tools: list[types.Tool] = []
        for spec in specs:
            tools.append(
                types.Tool(
                    name=spec.name,
                    description=spec.description,
                    inputSchema=augment_input_schema(spec.input_schema),
                )
            )
        tools.append(
            types.Tool(
                name="agenttaint.preview",
                description="Preview enforcement without executing the backend tool.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string"},
                        "arguments": {"type": "object"},
                    },
                    "required": ["tool_name"],
                },
            )
        )
        tools.append(
            types.Tool(
                name="agenttaint.audit_summary",
                description="Return ALLOW/BLOCK/CONFIRM decision counts.",
                inputSchema={"type": "object", "properties": {}},
            )
        )
        return tools

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(name: str, arguments: dict[str, Any]) -> types.CallToolResult:
        # Cooperative cancellation: if a cancel notification arrived for this request,
        # refuse to forward. Mid-flight backend calls may still complete (documented).
        req_id = None
        try:
            req_id = server.request_context.request_id
        except Exception:  # noqa: BLE001
            req_id = None
        if req_id is not None and req_id in cancelled:
            return _text_result(
                {"error": "cancelled", "request_id": req_id},
                is_error=True,
            )

        if name == "agenttaint.audit_summary":
            return _text_result({"counts": gateway.audit.count_by_decision()})

        if name == "agenttaint.preview":
            tool_name = str((arguments or {}).get("tool_name", ""))
            raw_args = (arguments or {}).get("arguments") or {}
            if not isinstance(raw_args, dict):
                raw_args = {}
            wire = extract_wire_metadata(raw_args)
            try:
                preview_agent = resolve_agent_identity(wire, agent_id)
            except AgentIdentityError as exc:
                return _text_result({"decision": "BLOCK", "error": str(exc)}, is_error=True)
            decision = gateway.preview(
                tool_name,
                wire.clean_arguments or {},
                agent_id=preview_agent,
                argument_parent_span_ids=wire.argument_parent_span_ids,
                candidates=_candidate_records(wire.candidates),
                session_id=wire.session_id,
            )
            return _text_result(decision.model_dump(mode="json"))

        wire = extract_wire_metadata(arguments or {})
        clean = dict(wire.clean_arguments or {})
        try:
            effective_agent = resolve_agent_identity(wire, agent_id)
        except AgentIdentityError as exc:
            return _text_result(
                {"decision": "BLOCK", "policy_id": "agent-identity-mismatch", "error": str(exc)},
                is_error=True,
            )
        try:
            outcome = gateway.invoke(
                name,
                clean,
                agent_id=effective_agent,
                raise_on_deny=False,
                confirmation_id=wire.confirmation_id,
                approval_token=wire.approval_token,
                argument_parent_span_ids=wire.argument_parent_span_ids,
                candidates=_candidate_records(wire.candidates),
                session_id=wire.session_id,
                execute=False,
            )
        except EnforcementError as exc:
            return _text_result(
                {
                    "decision": exc.decision.decision.value,
                    "explanation": exc.decision.explanation,
                    "policy_id": exc.decision.policy_id,
                    "call_id": exc.decision.call_id,
                    "confirmation_id": exc.decision.confirmation_id,
                },
                is_error=True,
            )

        if outcome.decision.decision != DecisionOutcome.ALLOW:
            payload: dict[str, Any] = {
                "decision": outcome.decision.decision.value,
                "explanation": outcome.decision.explanation,
                "policy_id": outcome.decision.policy_id,
                "call_id": outcome.decision.call_id,
                "confirmation_id": outcome.decision.confirmation_id,
            }
            if outcome.confirmation is not None:
                payload["confirmation_id"] = outcome.confirmation.confirmation_id
            return _text_result(payload, is_error=True)

        if req_id is not None and req_id in cancelled:
            return _text_result(
                {"error": "cancelled_before_forward", "request_id": req_id},
                is_error=True,
            )

        try:
            with anyio.CancelScope() as scope:
                if req_id is not None and req_id in cancelled:
                    scope.cancel()
                backend_result = await backend_session.call_tool(name, clean)
        except anyio.get_cancelled_exc_class():
            return _text_result({"error": "cancelled"}, is_error=True)
        except Exception as exc:  # noqa: BLE001
            outcome.decision.decision = DecisionOutcome.BLOCK
            outcome.decision.policy_id = "backend-error"
            outcome.decision.explanation = f"Backend failure after ALLOW: {exc}"
            gateway.audit.record(outcome.decision)
            return _text_result({"error": str(exc)}, is_error=True)

        # Label + audit success path (mirrors SecurityGateway.invoke post-forward).
        text_bits = []
        for block in backend_result.content:
            text = getattr(block, "text", None)
            if text:
                text_bits.append(text)
        result_text = (
            "\n".join(text_bits)
            if text_bits
            else json.dumps({"isError": backend_result.isError}, sort_keys=True)
        )
        span = gateway.label_tool_result(
            tool_name=name,
            content=result_text,
            agent_id=effective_agent,
        )
        outcome.decision.explanation = (
            f"{outcome.decision.explanation} Provenance span={span.span_id} "
            f"origin={span.origin.value}."
        )
        gateway.audit.record(outcome.decision)

        meta = {
            "call_id": outcome.decision.call_id,
            "decision": outcome.decision.decision.value,
            "span_id": span.span_id,
            "origin": span.origin.value,
            "risk_tier": outcome.decision.risk_tier.value,
            "policy_id": outcome.decision.policy_id,
        }
        if backend_result.isError:
            return types.CallToolResult(
                content=list(backend_result.content)
                + [
                    types.TextContent(
                        type="text",
                        text=json.dumps({AGENTTAINT_META_KEY: meta}, sort_keys=True),
                    )
                ],
                isError=True,
            )
        # Prefer structured JSON when backend returned parseable JSON text.
        body: Any
        try:
            body = json.loads(result_text) if result_text else {}
        except json.JSONDecodeError:
            body = {"result": result_text}
        if not isinstance(body, dict):
            body = {"result": body}
        body[AGENTTAINT_META_KEY] = meta
        return _text_result(body, is_error=False)

    return server


async def run_protocol_proxy(
    backend_command: list[str],
    *,
    trust_registry_path: str | Path | None = None,
    policy_path: str | Path | None = None,
    database_url: str = "sqlite+pysqlite:///:memory:",
    security_database_url: str | None = None,
    agent_id: str = "agent_default",
) -> None:
    """Connect to a downstream MCP server over stdio and serve the proxy on stdio."""
    if not backend_command:
        raise ValueError("backend_command required")
    params = StdioServerParameters(
        command=backend_command[0],
        args=list(backend_command[1:]),
        env=backend_environment(),
    )
    listing = _ListingBackend()
    gateway = build_gateway_from_paths(
        backend=listing,
        trust_registry_path=trust_registry_path,
        policy_path=policy_path,
        database_url=database_url,
        security_database_url=security_database_url,
    )

    async with stdio_client(params) as (bread, bwrite):
        async with ClientSession(bread, bwrite) as backend_session:
            await backend_session.initialize()
            specs = await _list_backend_tools(backend_session)
            listing.set_specs(specs)
            server = build_protocol_server(
                gateway=gateway,
                backend_session=backend_session,
                agent_id=agent_id,
            )
            init = server.create_initialization_options(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            )
            async with stdio_server() as (sread, swrite):
                await server.run(sread, swrite, init)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="AgentTaint multi-process MCP proxy")
    parser.add_argument(
        "--backend-cmd",
        default=os.environ.get("AGENTTAINT_BACKEND_CMD", ""),
        help="Shell command that launches the downstream MCP server on stdio",
    )
    parser.add_argument("--trust-registry", default=None)
    parser.add_argument("--policy", default=None)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("AGENTTAINT_DATABASE_URL", "sqlite+pysqlite:///:memory:"),
    )
    parser.add_argument(
        "--security-database-url",
        default=os.environ.get("AGENTTAINT_SECURITY_DB_URL"),
    )
    parser.add_argument("--agent-id", default="agent_default")
    args = parser.parse_args(argv)
    cmd = shlex.split(args.backend_cmd)
    if not cmd:
        raise SystemExit("AGENTTAINT_BACKEND_CMD / --backend-cmd is required")
    try:
        resolve_confirm_secret()
    except ConfigurationError as exc:
        raise SystemExit(f"AgentTaint proxy refusing to start: {exc}") from exc
    asyncio.run(
        run_protocol_proxy(
            cmd,
            trust_registry_path=args.trust_registry,
            policy_path=args.policy,
            database_url=args.database_url,
            security_database_url=args.security_database_url,
            agent_id=args.agent_id,
        )
    )


if __name__ == "__main__":
    main()
