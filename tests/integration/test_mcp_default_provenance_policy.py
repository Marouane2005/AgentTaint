"""M9: default MCP proxy wiring must use provenance-aware policy (not stub allow)."""

from __future__ import annotations

import pytest
from agenttaint_core.schemas import DecisionOutcome
from agenttaint_mcp_proxy.server import create_proxy_with_mock_email
from mcp.shared.memory import create_connected_server_and_client_session


@pytest.mark.asyncio
async def test_default_proxy_high_risk_send_without_lineage_does_not_allow() -> None:
    proxy, gateway = create_proxy_with_mock_email(agent_id="agent_a")
    mock_email = gateway._mock_email  # type: ignore[attr-defined]

    async with create_connected_server_and_client_session(proxy) as session:
        result = await session.call_tool(
            "email.send",
            {
                "to": "nobody@example.com",
                "subject": "invoice",
                "body": "hi",
            },
        )
        # CONFIRM/BLOCK surface as ToolError on the MCP wire.
        assert result.isError is True

    assert mock_email.sent == []
    counts = gateway.audit.count_by_decision()
    assert counts.get("ALLOW", 0) == 0
    assert counts.get("CONFIRM", 0) + counts.get("BLOCK", 0) >= 1
    latest = gateway.audit.list_decisions(limit=1)[0]
    assert latest.decision in {DecisionOutcome.CONFIRM, DecisionOutcome.BLOCK}
