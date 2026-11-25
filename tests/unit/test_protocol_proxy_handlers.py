"""Protocol-proxy request handlers, driven without a real MCP transport.

``Server`` and the ``mcp.types`` models are replaced with tiny shims so the handler
logic (identity binding, malformed metadata, write-ahead audit, off-loop evaluation) is
exercised independently of the installed ``mcp`` version.
"""

from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from agenttaint_mcp_proxy import protocol_proxy as pp
from agenttaint_policy.grants import AuthorizationGrant
from test_gateway_strict_lineage import GOOD, UpsertAudit, make_gateway


class _Result:
    def __init__(self, content: list[Any], isError: bool = False) -> None:  # noqa: N803
        self.content, self.isError = content, isError


class _Text:
    def __init__(self, type: str, text: str) -> None:  # noqa: A002
        self.type, self.text = type, text


class _Tool:
    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


class _FakeServer:
    def __init__(self, *_: Any, **__: Any) -> None:
        self.handlers: dict[str, Any] = {}

    def _register(self, fn: Any) -> Any:
        self.handlers[fn.__name__] = fn
        return fn

    def list_tools(self) -> Any:
        return self._register

    def call_tool(self) -> Any:
        return self._register


class _Backend:
    def __init__(self, audit: Any | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.audit_rows_at_call: list[int] = []
        self._audit = audit

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        if self._audit is not None:
            self.audit_rows_at_call.append(len(self._audit.decisions))
        return SimpleNamespace(content=[_Text("text", json.dumps({"sent": True}))], isError=False)


@pytest.fixture(autouse=True)
def _shim(monkeypatch: pytest.MonkeyPatch) -> None:
    shim = SimpleNamespace(CallToolResult=_Result, TextContent=_Text, Tool=_Tool)
    monkeypatch.setattr(pp, "types", shim)
    monkeypatch.setattr(pp, "Server", _FakeServer)


def _build(grant: bool = True, audit: Any | None = None) -> tuple[Any, Any, _Backend, Any]:
    grants = [AuthorizationGrant(tool="email.send", argument="to", value=GOOD)] if grant else []
    gw, _reg, fake_audit, _calls = make_gateway(strict=False, grants=grants)
    if audit is not None:
        gw.audit = audit
        fake_audit = audit
    backend = _Backend(fake_audit)
    server = pp.build_protocol_server(
        gateway=gw, backend_session=backend, agent_id="agent_a", session_id="sess-1"
    )
    return server.handlers["call_tool"], gw, backend, fake_audit


def _run(handler: Any, name: str, args: dict[str, Any]) -> dict[str, Any]:
    async def go() -> Any:
        return await handler(name, args)

    result = anyio.run(go)
    return {"is_error": result.isError, **json.loads(result.content[0].text)}


def test_build_marks_gateway_strict_and_hides_reserved_backend_tools() -> None:
    _, gw, _, _ = _build()
    assert gw.strict_lineage is True


def test_allowed_call_is_audited_before_forwarding_and_labelled_after() -> None:
    audit = UpsertAudit()
    handler, _gw, backend, _ = _build(audit=audit)
    out = _run(handler, "email.send", {"to": GOOD, "body": "hi"})
    assert out["is_error"] is False and out["sent"] is True
    assert backend.audit_rows_at_call == [1]  # write-ahead: ALLOW already on record
    assert len(audit.decisions) == 1 and "Provenance span=" in audit.decisions[0].explanation


@pytest.mark.parametrize(
    ("meta", "policy"),
    [
        ({"session_id": "someone-else"}, "session-identity-mismatch"),
        ({"agent_id": "agent_root"}, "agent-identity-mismatch"),
        ({"approval_token": 123}, "malformed-agenttaint-metadata"),
        ({"argument_parent_span_ids": "not-a-map"}, "malformed-agenttaint-metadata"),
    ],
)
def test_bad_identity_or_metadata_is_blocked_without_touching_the_backend(
    meta: dict[str, Any], policy: str
) -> None:
    handler, _gw, backend, _ = _build()
    out = _run(handler, "email.send", {"to": GOOD, "_agenttaint": meta})
    assert out["is_error"] is True and out["decision"] == "BLOCK"
    assert out["policy_id"] == policy
    assert backend.calls == []


def test_reserved_tool_names_cannot_be_called_through_the_proxy() -> None:
    handler, _gw, backend, _ = _build()
    out = _run(handler, "agenttaint.approve_confirmation", {"confirmation_id": "x"})
    assert out["policy_id"] == "reserved-tool-name" and backend.calls == []


def test_blocked_call_is_not_forwarded() -> None:
    handler, _gw, backend, _ = _build(grant=False)
    out = _run(handler, "email.send", {"to": GOOD, "body": "hi"})
    assert out["is_error"] is True and out["decision"] in {"CONFIRM", "BLOCK"}
    assert backend.calls == []


def test_slow_policy_evaluation_does_not_block_the_event_loop() -> None:
    handler, gw, _backend, _ = _build()
    real_invoke = gw._invoke
    threads: list[str] = []

    def slow_invoke(*args: Any, **kwargs: Any) -> Any:
        threads.append(threading.current_thread().name)
        time.sleep(0.4)  # stands in for BGE embedding / SQLite latency
        return real_invoke(*args, **kwargs)

    gw._invoke = slow_invoke  # type: ignore[method-assign]
    ticks = 0

    async def main() -> None:
        nonlocal ticks
        done = anyio.Event()

        async def ticker() -> None:
            nonlocal ticks
            while not done.is_set():
                await anyio.sleep(0.02)
                ticks += 1

        async with anyio.create_task_group() as tg:
            tg.start_soon(ticker)
            await handler("email.send", {"to": GOOD, "body": "hi"})
            done.set()

    anyio.run(main)
    assert threads and threads[0] != threading.main_thread().name
    assert ticks >= 10, f"event loop stalled during evaluation (ticks={ticks})"
