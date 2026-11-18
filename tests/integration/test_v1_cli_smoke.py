"""`agenttaint init` -> `proxy` -> CONFIRM -> `approve` -> retry allowed -> BLOCK."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "smoke_cli_proxy.py"


@pytest.mark.asyncio
async def test_cli_end_to_end(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("smoke_cli_proxy", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    await module.run(tmp_path)
