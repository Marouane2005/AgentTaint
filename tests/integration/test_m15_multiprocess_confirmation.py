"""M15: confirmation hardening across real processes (client ↔ proxy ↔ backend)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]


def _params(db_dir: Path, env: dict[str, str]) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "agenttaint_mcp_proxy.protocol_proxy",
            "--backend-cmd",
            f"{sys.executable} -m agenttaint_mock_email",
            "--database-url",
            f"sqlite+pysqlite:///{db_dir / 'prov.db'}",
            "--security-database-url",
            f"sqlite+pysqlite:///{db_dir / 'sec.db'}",
            "--agent-id",
            "agent_mp",
        ],
        cwd=str(ROOT),
        env=env,
    )


def _text(result: Any) -> str:
    return " ".join(getattr(b, "text", "") for b in result.content if getattr(b, "text", None))


def test_proxy_refuses_to_start_without_secret(tmp_path: Path) -> None:
    env = {k: v for k, v in os.environ.items() if k != "AGENTTAINT_CONFIRM_SECRET"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "agenttaint_mcp_proxy.protocol_proxy",
            "--backend-cmd",
            f"{sys.executable} -m agenttaint_mock_email",
        ],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
    )
    assert proc.returncode != 0
    assert "AGENTTAINT_CONFIRM_SECRET" in (proc.stderr + proc.stdout)


@pytest.mark.asyncio
async def test_self_approval_blocked_and_out_of_band_cli_approval_works(tmp_path: Path) -> None:
    env = dict(os.environ)
    args = {"to": "partner@corp.example", "subject": "q3", "body": "report"}
    async with stdio_client(_params(tmp_path, env)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {t.name for t in (await session.list_tools()).tools}
            assert not any("approve" in n for n in names)

            first = await session.call_tool("email.send", args)
            assert first.isError is True
            payload = json.loads(_text(first))
            assert payload["decision"] == "CONFIRM"
            cid = payload["confirmation_id"]

            # Agent tries to approve itself: no such tool.
            selfie = await session.call_tool(
                "agenttaint.approve_confirmation", {"confirmation_id": cid}
            )
            assert selfie.isError is True
            # Agent tries to impersonate another identity.
            spoof = await session.call_tool(
                "email.send", {**args, "_agenttaint": {"agent_id": "agent_root"}}
            )
            # Rejected by schema validation (agent_id is not an accepted field) and,
            # behind that, by the proxy's identity check.
            assert spoof.isError is True and "agent_id" in _text(spoof)
            # Retry without human approval → BLOCK.
            early = await session.call_tool(
                "email.send", {**args, "_agenttaint": {"confirmation_id": cid}}
            )
            assert early.isError is True and "BLOCK" in _text(early)

            # A second confirmation, approved by a human through the CLI process.
            second = await session.call_tool("email.send", args)
            cid2 = json.loads(_text(second))["confirmation_id"]
            cli = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agenttaint_agent_sdk.confirm_cli",
                    "--database-url",
                    f"sqlite+pysqlite:///{tmp_path / 'sec.db'}",
                    "approve",
                    cid2,
                    "--yes",
                ],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert cli.returncode == 0, cli.stdout + cli.stderr
            # The approver reads the token from the CLI output and relays it.
            token_line = next(
                line for line in cli.stdout.splitlines() if line.startswith("approval_token:")
            )
            meta = {"confirmation_id": cid2, "approval_token": token_line.split(":", 1)[1].strip()}
            id_only = await session.call_tool(
                "email.send", {**args, "_agenttaint": {"confirmation_id": cid2}}
            )
            assert id_only.isError is True
            ok = await session.call_tool("email.send", {**args, "_agenttaint": meta})
            assert ok.isError is False, _text(ok)
            replay = await session.call_tool("email.send", {**args, "_agenttaint": meta})
            assert replay.isError is True
