"""Temp-dir backed filesystem.read / filesystem.write."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class MockFilesystemBackend:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or os.environ.get("AGENTTAINT_FS_ROOT", "/tmp/agenttaint-fs"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.writes: list[dict[str, Any]] = []

    def _resolve(self, path: str) -> Path:
        # Absolute paths are remapped under the sandbox root by basename chain.
        # This keeps the mock local while still exercising path-policy on the
        # original path string at the AgentTaint gateway.
        raw = Path(path)
        if raw.is_absolute():
            target = self.root / raw.relative_to(raw.anchor)
        else:
            target = self.root / raw
        target = target.resolve()
        if not str(target).startswith(str(self.root.resolve())):
            raise PermissionError(f"path escapes sandbox: {path}")
        return target

    def read(self, path: str) -> dict[str, Any]:
        target = self._resolve(path)
        if not target.exists():
            return {"path": path, "exists": False, "content": ""}
        return {
            "path": path,
            "exists": True,
            "content": target.read_text(encoding="utf-8"),
        }

    def write(self, path: str, content: str = "") -> dict[str, Any]:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        record = {"path": path, "bytes": len(content.encode("utf-8"))}
        self.writes.append(record)
        return {"status": "ok", **record}

    def list_tool_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "filesystem.read",
                "description": "Read a file from the local mock workspace.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
            {
                "name": "filesystem.write",
                "description": "Write a file in the local mock workspace.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path"],
                },
            },
        ]
