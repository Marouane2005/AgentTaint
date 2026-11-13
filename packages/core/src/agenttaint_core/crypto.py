"""Local HMAC helpers for envelope and confirmation authenticity.

Uses only the Python standard library. Shared secrets are for cooperating
AgentTaint components — not a substitute for mutual TLS in production.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_nonce(nbytes: int = 16) -> str:
    return secrets.token_hex(nbytes)


def hmac_sign(secret: str, payload: bytes | str) -> str:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def hmac_verify(secret: str, payload: bytes | str, signature: str) -> bool:
    expected = hmac_sign(secret, payload)
    return hmac.compare_digest(expected, signature)
