"""Executes shell.execute inside the real Docker sandbox and checks its limits.

Runs in the CI `docker-sandbox` job. Locally it is skipped unless
AGENTTAINT_TEST_DOCKER=1 and a working Docker daemon is available.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any

import pytest
from agenttaint_mock_shell.backend import MockShellBackend, SandboxLimits

pytestmark = pytest.mark.docker


@pytest.fixture(scope="module")
def backend() -> MockShellBackend:
    if os.environ.get("AGENTTAINT_TEST_DOCKER") != "1":
        pytest.skip("set AGENTTAINT_TEST_DOCKER=1 to run Docker sandbox tests")
    if shutil.which("docker") is None:
        pytest.skip("docker not installed")
    probe = subprocess.run(["docker", "info"], capture_output=True, check=False, timeout=30)
    if probe.returncode != 0:
        pytest.skip("docker daemon not reachable")
    return MockShellBackend()


def _run(backend: MockShellBackend, command: str) -> dict[str, Any]:
    out = backend.execute(command)
    assert out["sandbox"] == "docker", out
    return out


def test_command_runs_in_sandbox(backend: MockShellBackend) -> None:
    out = _run(backend, "echo sandbox-ok")
    assert out["status"] == "ok", out
    assert out["stdout"].strip() == "sandbox-ok"


def test_runs_as_nobody(backend: MockShellBackend) -> None:
    out = _run(backend, "id -u; id -g")
    assert out["stdout"].split() == ["65534", "65534"], out


def test_all_capabilities_dropped(backend: MockShellBackend) -> None:
    out = _run(backend, "grep -E '^Cap(Eff|Prm|Bnd):' /proc/self/status")
    caps = dict(line.split(":\t") for line in out["stdout"].strip().splitlines())
    assert caps["CapEff"].strip("0") == "", caps
    assert caps["CapPrm"].strip("0") == "", caps
    assert caps["CapBnd"].strip("0") == "", caps


def test_no_new_privileges(backend: MockShellBackend) -> None:
    out = _run(backend, "grep NoNewPrivs /proc/self/status")
    assert out["stdout"].split()[-1] == "1", out


def test_network_is_blocked(backend: MockShellBackend) -> None:
    out = _run(backend, "ls /sys/class/net")
    assert out["stdout"].split() == ["lo"], out
    out = _run(
        backend,
        "wget -q -T 3 -O- http://1.1.1.1 >/dev/null 2>&1 && echo NET_OPEN || echo NET_BLOCKED",
    )
    assert out["stdout"].strip() == "NET_BLOCKED", out
    out = _run(
        backend,
        "wget -q -T 3 -O- https://example.com >/dev/null 2>&1 && echo DNS_OPEN || echo DNS_BLOCKED",
    )
    assert out["stdout"].strip() == "DNS_BLOCKED", out


def test_root_filesystem_is_read_only(backend: MockShellBackend) -> None:
    out = _run(backend, "touch /usr/agenttaint 2>/dev/null && echo WROTE || echo RO")
    assert out["stdout"].strip() == "RO", out


def test_tmp_is_writable_but_noexec(backend: MockShellBackend) -> None:
    out = _run(
        backend,
        "echo data > /tmp/f && cat /tmp/f && cp /bin/busybox /tmp/bb && "
        "(/tmp/bb true 2>/dev/null && echo EXEC_ALLOWED || echo NOEXEC)",
    )
    assert out["stdout"].split() == ["data", "NOEXEC"], out


def _cgroup_value(backend: MockShellBackend, v2: str, v1: str) -> str:
    out = _run(backend, f"cat /sys/fs/cgroup/{v2} 2>/dev/null || cat /sys/fs/cgroup/{v1}")
    assert out["status"] == "ok", out
    return out["stdout"].strip()


def test_memory_limit_applied(backend: MockShellBackend) -> None:
    value = _cgroup_value(backend, "memory.max", "memory/memory.limit_in_bytes")
    assert int(value) == 256 * 1024 * 1024


def test_cpu_limit_applied(backend: MockShellBackend) -> None:
    out = _run(
        backend,
        "cat /sys/fs/cgroup/cpu.max 2>/dev/null || "
        "echo $(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us) "
        "$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us)",
    )
    quota, period = out["stdout"].split()
    assert int(quota) / int(period) == pytest.approx(0.5)


def test_pids_limit_applied_and_enforced(backend: MockShellBackend) -> None:
    value = _cgroup_value(backend, "pids.max", "pids/pids.max")
    assert int(value) == 64
    out = _run(
        backend,
        "i=0; fail=0; while [ $i -lt 120 ]; do (sleep 2) 2>/dev/null & "
        "[ $? -ne 0 ] && fail=1; i=$((i+1)); done 2>/tmp/err; "
        "grep -qi fork /tmp/err && echo LIMITED || echo UNLIMITED",
    )
    assert "LIMITED" in out["stdout"].split(), out


def test_timeout_kills_long_command() -> None:
    if os.environ.get("AGENTTAINT_TEST_DOCKER") != "1" or shutil.which("docker") is None:
        pytest.skip("set AGENTTAINT_TEST_DOCKER=1 to run Docker sandbox tests")
    short = MockShellBackend(limits=SandboxLimits(timeout_seconds=2))
    start = time.monotonic()
    out = short.execute("sleep 60; echo finished")
    elapsed = time.monotonic() - start
    assert out["status"] == "timeout", out
    assert "finished" not in out.get("stdout", "")
    assert elapsed < 30
