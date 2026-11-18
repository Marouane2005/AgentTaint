"""MCP server exposing mock HTTP tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from agenttaint_mock_http.backend import MockHttpBackend


def create_mock_http_server(
    backend: MockHttpBackend | None = None,
    *,
    name: str = "agenttaint-mock-http",
) -> FastMCP:
    http = backend or MockHttpBackend()
    mcp = FastMCP(name=name)

    @mcp.tool(
        name="http.get",
        description="Fetch a URL via the local mock HTTP layer (no network).",
    )
    def http_get(url: str) -> dict[str, Any]:
        return http.get(url)

    @mcp.tool(
        name="http.post",
        description="POST to a URL via the local mock HTTP layer (no network).",
    )
    def http_post(url: str, body: str = "", content: str = "") -> dict[str, Any]:
        return http.post(url, body=body, content=content)

    mcp._agenttaint_backend = http  # type: ignore[attr-defined]
    return mcp


def main() -> None:
    create_mock_http_server().run(transport="stdio")


if __name__ == "__main__":
    main()
