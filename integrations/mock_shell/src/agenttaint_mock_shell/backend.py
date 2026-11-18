"""shell.execute that requires Docker; refuses host execution when Docker is absent."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SandboxLimits:
    """Resource and privilege limits applied to every sandboxed command."""

    memory: str = "256m"
    cpus: str = "0.5"
    pids_limit: int = 64
    user: str = "65534:65534"  # nobody:nogroup
    timeout_seconds: float = 10.0
    tmpfs_size: str = "16m"


class MockShellBackend:
    def __init__(
        self,
        *,
        image: str = "python:3.12-alpine",
        require_docker: bool = True,
        limits: SandboxLimits | None = None,
    ) -> None:
        self.image = image
        self.require_docker = require_docker
        self.limits = limits or SandboxLimits()
        self.executions: list[dict[str, Any]] = []

    def docker_available(self) -> bool:
        return shutil.which("docker") is not None

    def build_docker_command(self, command: str, *, container_name: str) -> list[str]:
        """Exact `docker run` argv used for a command (exposed for tests/audit)."""
        lim = self.limits
        return [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,size={lim.tmpfs_size}",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "--user",
            lim.user,
            "--memory",
            lim.memory,
            "--memory-swap",
            lim.memory,
            "--cpus",
            lim.cpus,
            "--pids-limit",
            str(lim.pids_limit),
            "--stop-timeout",
            "1",
            self.image,
            "timeout",
            "-s",
            "KILL",
            str(max(1, int(lim.timeout_seconds))),
            "sh",
            "-c",
            command,
        ]

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
        name = f"agenttaint-sh-{uuid.uuid4().hex[:12]}"
        argv = self.build_docker_command(command, container_name=name)
        record["argv"] = argv
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                # Outer guard in case the in-container timeout or Docker hangs.
                timeout=self.limits.timeout_seconds + 15,
            )
        except subprocess.TimeoutExpired:
            subprocess.run(
                ["docker", "kill", name],
                capture_output=True,
                check=False,
                timeout=15,
            )
            record["status"] = "timeout"
            return {
                "status": "timeout",
                "command": command,
                "error": f"sandbox timeout after {self.limits.timeout_seconds}s",
                "sandbox": "docker",
            }
        timed_out = proc.returncode in {124, 137}
        record["status"] = "timeout" if timed_out else ("ok" if proc.returncode == 0 else "error")
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
                "description": (
                    "Execute a command inside a resource-limited Docker sandbox "
                    "(no network, read-only rootfs, all capabilities dropped, "
                    "unprivileged user). Never runs on the host shell."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            }
        ]
