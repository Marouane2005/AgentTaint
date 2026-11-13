"""MCP server exposing mock email tools via the official MCP Python SDK."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from agenttaint_mock_email.backend import MockEmailBackend

_backend = MockEmailBackend()


def create_mock_email_server(
    backend: MockEmailBackend | None = None,
    *,
    name: str = "agenttaint-mock-email",
) -> FastMCP:
    """Build a FastMCP server bound to a mock email backend."""
    email = backend or MockEmailBackend()
    mcp = FastMCP(name=name)

    @mcp.tool(name="email.read", description="Read messages from the local mock inbox.")
    def email_read(message_id: str | None = None) -> dict[str, Any]:
        return email.read(message_id=message_id)

    @mcp.tool(
        name="email.send",
        description="Send an email via the local mock outbox (no real network).",
    )
    def email_send(
        to: str,
        subject: str = "",
        body: str = "",
        attachment: str | None = None,
    ) -> dict[str, Any]:
        return email.send(to=to, subject=subject, body=body, attachment=attachment)

    # Keep a handle for tests.
    mcp._agenttaint_backend = email  # type: ignore[attr-defined]
    return mcp


def main() -> None:
    """Run the mock email MCP server over stdio."""
    server = create_mock_email_server(_backend)
    # Avoid printing secrets; tools only touch local fixtures.
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
