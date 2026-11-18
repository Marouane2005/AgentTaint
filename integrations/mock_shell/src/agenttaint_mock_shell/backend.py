"""shell.execute that requires Docker; refuses host execution when Docker is absent."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any


class MockShellBackend:
    def __init__(
        self,
        *,
        image: str = "python:3.12-alpine",
        require_docker: bool = True,
    ) -> None:
        self.image = image
        self.require_docker = require_docker
        self.executions: list[dict[str, Any]] = []

    def docker_available(self) -> bool:
        return shutil.which("docker") is not None

    def execute(self, command: str) -> dict[str, Any]:
        record: dict[str, Any] = {"command": command}
        self.executions.append(record)
        if self.require_docker and not self.docker_available():
            record["status"] = "refused"
            record["error"] = "Docker sandbox required; host shell execution is disabled"
            return {
                "status": "refused",
                "command": command,
                "error": record["error"],
                "sandbox": "docker-required",
            }
        # Network disabled, read-only rootfs, no privileges.
        proc = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--security-opt",
                "no-new-privileges",
                self.image,
                "sh",
                "-c",
                command,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        record["status"] = "ok" if proc.returncode == 0 else "error"
        record["returncode"] = proc.returncode
        return {
            "status": record["status"],
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "sandbox": "docker",
        }

    def list_tool_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "shell.execute",
                "description": "Execute a command inside a Docker sandbox (never host shell).",
                "inputSchema": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            }
        ]
