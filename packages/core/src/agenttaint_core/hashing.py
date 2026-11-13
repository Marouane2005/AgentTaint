"""Content hashing and redaction helpers.

Audit records prefer hashes over plaintext sensitive values.
"""

from __future__ import annotations

import hashlib
import re
from typing import Final

_EMAIL_RE: Final = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_URL_RE: Final = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_IPV4_RE: Final = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def content_hash(content: str | bytes, *, encoding: str = "utf-8") -> str:
    """Return a stable SHA-256 hex digest of content."""
    if isinstance(content, str):
        payload = content.encode(encoding)
    else:
        payload = content
    return hashlib.sha256(payload).hexdigest()


def redact_sensitive(
    text: str,
    *,
    redact_emails: bool = True,
    redact_urls: bool = True,
    redact_ips: bool = False,
) -> str:
    """Replace common sensitive tokens with placeholders for safe storage/display."""
    out = text
    if redact_emails:
        out = _EMAIL_RE.sub("[REDACTED_EMAIL]", out)
    if redact_urls:
        out = _URL_RE.sub("[REDACTED_URL]", out)
    if redact_ips:
        out = _IPV4_RE.sub("[REDACTED_IP]", out)
    return out
