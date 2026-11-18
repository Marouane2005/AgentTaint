"""MCP server exposing Docker-sandboxed shell.execute."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from agenttaint_mock_shell.backend import MockShellBackend


def create_mock_shell_server(
    backend: MockShellBackend | None = None,
    *,
    name: str = "agenttaint-mock-shell",
) -> FastMCP:
    shell = backend or MockShellBackend()
    mcp = FastMCP(name=name)

    @mcp.tool(
        name="shell.execute",
        description="Execute a command inside a Docker sandbox (never host shell).",
    )
    def shell_execute(command: str) -> dict[str, Any]:
        return shell.execute(command)

    mcp._agenttaint_backend = shell  # type: ignore[attr-defined]
    return mcp


def main() -> None:
    create_mock_shell_server().run(transport="stdio")


if __name__ == "__main__":
    main()
