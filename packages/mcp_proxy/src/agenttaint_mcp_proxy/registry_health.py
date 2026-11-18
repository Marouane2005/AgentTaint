"""Real provenance-registry availability probes (replaces manual flags)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text


def probe_registry_available(registry: Any) -> bool:
    """Return True only when the registry store answers a trivial health query."""
    try:
        store = getattr(registry, "store", None)
        if store is None:
            return False
        session_factory = getattr(store, "session", None)
        if session_factory is None:
            return False
        with session_factory() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - probe must fail closed
        return False
