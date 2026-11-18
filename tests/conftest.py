"""Shared pytest fixtures."""

from __future__ import annotations

import secrets
from collections.abc import Iterator

import pytest

# A per-run random secret: the proxy has no default and fails closed without one.
TEST_CONFIRM_SECRET = secrets.token_hex(32)


@pytest.fixture(autouse=True)
def _confirm_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("AGENTTAINT_CONFIRM_SECRET", TEST_CONFIRM_SECRET)
    yield TEST_CONFIRM_SECRET
