"""Small in-process sliding-window rate limiter for the public demo.

One process serves the demo, so an in-memory limiter is enough. Keys are
client addresses; a global bucket per rule caps total load even when clients
rotate addresses.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from starlette.requests import Request


@dataclass(frozen=True)
class Rule:
    name: str
    per_client: int
    global_limit: int
    window_s: float


class SlidingWindowLimiter:
    def __init__(self, max_keys: int = 20_000) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()
        self._max_keys = max_keys

    def _allow(self, key: tuple[str, str], limit: int, window: float, now: float) -> float:
        q = self._hits.setdefault(key, deque())
        while q and now - q[0] >= window:
            q.popleft()
        if len(q) >= limit:
            return window - (now - q[0])
        return 0.0

    def check(self, rule: Rule, client: str, now: float | None = None) -> float:
        """Record a hit; return 0 when allowed, else seconds until retry."""
        now = time.monotonic() if now is None else now
        with self._lock:
            if len(self._hits) > self._max_keys:
                self._hits.clear()
            for key, limit in (
                ((rule.name, "*"), rule.global_limit),
                ((rule.name, client), rule.per_client),
            ):
                wait = self._allow(key, limit, rule.window_s, now)
                if wait > 0:
                    return wait
            self._hits[(rule.name, "*")].append(now)
            self._hits[(rule.name, client)].append(now)
            return 0.0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_address(request: Request) -> str:
    """Best-effort client address behind the hosting proxy."""
    for header in ("cf-connecting-ip", "true-client-ip"):
        value = request.headers.get(header, "").strip()
        if value:
            return value[:64]
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


# Rules for the public demo, matched in order (method, path prefix).
DEMO_RULES: list[tuple[str, str, Rule]] = [
    ("POST", "/api/v1/waitlist", Rule("waitlist", 5, 200, 3600)),
    ("GET", "/api/v1/admin/", Rule("admin", 10, 60, 60)),
    ("POST", "/api/v1/demo/run", Rule("demo_run", 12, 240, 60)),
    ("POST", "/api/v1/demo/custom", Rule("demo_custom", 8, 160, 60)),
    ("DELETE", "/api/v1/admin/", Rule("admin_write", 10, 30, 60)),
    ("POST", "/api/v1/demo/seed", Rule("demo_seed", 2, 10, 60)),
    ("GET", "/api/v1/", Rule("api_read", 240, 6000, 60)),
]


def rule_for(method: str, path: str) -> Rule | None:
    for rule_method, prefix, rule in DEMO_RULES:
        if method == rule_method and path.startswith(prefix):
            return rule
    return None
