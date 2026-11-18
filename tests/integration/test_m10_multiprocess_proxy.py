"""M10: multi-process MCP client ↔ proxy ↔ backend over stdio."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError

ROOT = Path(__file__).resolve().parents[2]


def _proxy_params(*, backend_module: str, db_path: Path) -> StdioServerParameters:
    backend = f"{sys.executable} -m {backend_module}"
    args = [
        "-m",
        "agenttaint_mcp_proxy.protocol_proxy",
        "--backend-cmd",
        backend,
        "--trust-registry",
        str(ROOT / "policies" / "trust_registry.yaml"),
        "--policy",
        str(ROOT / "policies" / "provenance_policy.yaml"),
        "--database-url",
        f"sqlite+pysqlite:///{db_path / 'prov.db'}",
        "--security-database-url",
        f"sqlite+pysqlite:///{db_path / 'sec.db'}",
        "--agent-id",
        "agent_mp",
    ]
    env = {**os.environ, "AGENTTAINT_CONFIRM_SECRET": os.environ["AGENTTAINT_CONFIRM_SECRET"]}
    return StdioServerParameters(command=sys.executable, args=args, cwd=str(ROOT), env=env)


@pytest.mark.asyncio
async def test_multiprocess_email_list_and_block(tmp_path: Path) -> None:
    params = _proxy_params(backend_module="agenttaint_mock_email", db_path=tmp_path)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert "email.read" in names
            assert "email.send" in names
            # Approval is out-of-band only: the agent-facing surface has no approve tool.
            assert not any("approve" in n for n in names)

            # Real schema forwarded (not arguments_json-only).
            send = next(t for t in tools.tools if t.name == "email.send")
            props = (send.inputSchema or {}).get("properties") or {}
            assert "to" in props
            assert "_agenttaint" in props

            read_result = await session.call_tool("email.read", {})
            assert read_result.isError is False

            blocked = await session.call_tool(
                "email.send",
                {
                    "to": "nobody@example.com",
                    "subject": "x",
                    "body": "y",
                },
            )
            assert blocked.isError is True
            text = " ".join(
                getattr(b, "text", "") for b in blocked.content if getattr(b, "text", None)
            )
            assert "CONFIRM" in text or "BLOCK" in text or "AgentTaint" in text


@pytest.mark.asyncio
async def test_multiprocess_http_and_filesystem_servers(tmp_path: Path) -> None:
    params = _proxy_params(backend_module="agenttaint_mock_http", db_path=tmp_path)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert "http.get" in names
            assert "http.post" in names

    params_fs = _proxy_params(backend_module="agenttaint_mock_filesystem", db_path=tmp_path / "fs")
    (tmp_path / "fs").mkdir(exist_ok=True)
    async with stdio_client(params_fs) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert "filesystem.read" in names
            assert "filesystem.write" in names


@pytest.mark.asyncio
async def test_multiprocess_shell_refuses_without_docker(tmp_path: Path) -> None:
    params = _proxy_params(backend_module="agenttaint_mock_shell", db_path=tmp_path)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # shell.execute is HIGH → CONFIRM/BLOCK before backend when no grant.
            result = await session.call_tool(
                "shell.execute",
                {"command": "echo hi"},
            )
            assert result.isError is True


@pytest.mark.asyncio
async def test_multiprocess_backend_error_surfaces(tmp_path: Path) -> None:
    # Point backend at a module that exits immediately → client init / call error path.
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "agenttaint_mcp_proxy.protocol_proxy",
            "--backend-cmd",
            f"{sys.executable} -c 'raise SystemExit(1)'",
            "--trust-registry",
            str(ROOT / "policies" / "trust_registry.yaml"),
            "--database-url",
            f"sqlite+pysqlite:///{tmp_path / 'e.db'}",
        ],
        cwd=str(ROOT),
        env=dict(os.environ),
    )
    with pytest.raises((McpError, OSError, RuntimeError, BaseExceptionGroup)):
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
