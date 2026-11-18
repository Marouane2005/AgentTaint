"""End-to-end smoke for an installed `agenttaint` CLI (no repo checkout needed).

init -> proxy in front of the mock email MCP server -> list/read/send ->
the send is held (CONFIRM) or BLOCKed -> `agenttaint approve list` sees the queue.
Exit code 0 on success. Prints no secrets.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Run with only the generated .env: ambient AGENTTAINT_* settings must not leak in.
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("AGENTTAINT_")}


def agenttaint(*args: str) -> list[str]:
    return [sys.executable, "-m", "agenttaint_cli", *args]


async def run(workdir: Path) -> None:
    subprocess.run(
        agenttaint("init", str(workdir)), check=True, stdout=subprocess.DEVNULL, env=CLEAN_ENV
    )
    cfg_path = workdir / "agenttaint.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    cfg["backend"]["command"] = [sys.executable, "-m", "agenttaint_mock_email"]
    cfg_path.write_text(yaml.safe_dump(cfg))

    cmd = agenttaint("proxy", "--config", str(cfg_path))
    params = StdioServerParameters(command=cmd[0], args=cmd[1:], cwd=str(workdir), env=CLEAN_ENV)
    send_args = {"to": "ops@example.com", "subject": "status", "body": "weekly status"}
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {t.name for t in (await session.list_tools()).tools}
            assert {"email.read", "email.send"} <= names, names
            assert not any("approve" in n for n in names)

            # 1. High-risk send with no untrusted influence: held for a human.
            held = json.loads(_text(await session.call_tool("email.send", send_args)))
            assert held["decision"] == "CONFIRM", held
            confirmation_id = held["confirmation_id"]
            print("send #1:", held["decision"], held["policy_id"])

            # 2. Approve out of band with the CLI (the agent has no approve tool).
            subprocess.run(
                agenttaint(
                    "approve", "--config", str(cfg_path), "approve", confirmation_id, "--yes"
                ),
                check=True,
                stdout=subprocess.DEVNULL,
                env=CLEAN_ENV,
            )

            # 3. The exact same call with the confirmation id now goes through.
            retry = await session.call_tool(
                "email.send", {**send_args, "_agenttaint": {"confirmation_id": confirmation_id}}
            )
            assert retry.isError is False, _text(retry)
            print("send #1 retry after approval: allowed")

            # 4. After reading untrusted email, a send is blocked outright.
            assert (await session.call_tool("email.read", {})).isError is False
            blocked = await session.call_tool(
                "email.send", {"to": "nobody@example.com", "subject": "x", "body": "y"}
            )
            decision = json.loads(_text(blocked))
            assert blocked.isError is True and decision["decision"] == "BLOCK", decision
            print("send #2 after untrusted read:", decision["decision"], decision["policy_id"])

    listed = subprocess.run(
        agenttaint("approve", "--config", str(cfg_path), "list"),
        check=True,
        capture_output=True,
        text=True,
        env=CLEAN_ENV,
    )
    print("approve list:", listed.stdout.strip().splitlines()[:2])
    print("smoke ok:", sorted(names))


def _text(result: object) -> str:
    content = getattr(result, "content", [])
    return " ".join(getattr(b, "text", "") or "" for b in content)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        asyncio.run(run(Path(tmp)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
