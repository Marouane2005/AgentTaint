"""MCP server exposing mock filesystem tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from agenttaint_mock_filesystem.backend import MockFilesystemBackend


def create_mock_filesystem_server(
    backend: MockFilesystemBackend | None = None,
    *,
    name: str = "agenttaint-mock-filesystem",
) -> FastMCP:
    fs = backend or MockFilesystemBackend()
    mcp = FastMCP(name=name)

    @mcp.tool(name="filesystem.read", description="Read a file from the local mock workspace.")
    def filesystem_read(path: str) -> dict[str, Any]:
        return fs.read(path)

    @mcp.tool(name="filesystem.write", description="Write a file in the local mock workspace.")
    def filesystem_write(path: str, content: str = "") -> dict[str, Any]:
        return fs.write(path, content=content)

    mcp._agenttaint_backend = fs  # type: ignore[attr-defined]
    return mcp


def main() -> None:
    create_mock_filesystem_server().run(transport="stdio")


if __name__ == "__main__":
    main()
