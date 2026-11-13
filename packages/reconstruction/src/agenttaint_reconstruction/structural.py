"""Structural value extraction and matching (emails, URLs, IPs, paths, commands)."""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit, urlunsplit


class StructuralKind(StrEnum):
    EMAIL = "EMAIL"
    URL = "URL"
    IPV4 = "IPV4"
    PATH = "PATH"
    SHELL_TOKEN = "SHELL_TOKEN"


_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![A-Za-z0-9._%+-])"
)
# Common obfuscations used by adaptive attackers (still INFERRED evidence only).
_OBFUSCATED_EMAIL_RE = re.compile(
    r"([A-Za-z0-9._%+-]+)\s*(?:\[at\]|\(at\)|@)\s*([A-Za-z0-9.-]+)\s*"
    r"(?:\[dot\]|\(dot\)|\.)\s*([A-Za-z]{2,})",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PATH_RE = re.compile(r"(?:(?:/[A-Za-z0-9._\-]+)+|[A-Za-z]:\\(?:[A-Za-z0-9._\\-]+)+)")
_SHELL_RE = re.compile(r"\b(?:curl|wget|rm|chmod|scp|ssh|bash|sh|powershell)\b", re.I)


@dataclass(frozen=True)
class StructuralValue:
    kind: StructuralKind
    raw: str
    normalized: str


@dataclass(frozen=True)
class StructuralHit:
    kind: StructuralKind
    query_value: str
    candidate_value: str
    normalized: str


def normalize_email(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip().casefold()
    # Strip common obfuscations used in adversarial tests.
    value = value.replace(" [@] ", "@").replace("[at]", "@").replace("(at)", "@")
    value = value.replace(" [.] ", ".").replace("[dot]", ".")
    return value


def normalize_url(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip()
    parts = urlsplit(value)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.casefold()
    # Drop default ports and trailing slash on path for comparison.
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]
    path = parts.path.rstrip("/") or ""
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def normalize_path(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip()
    value = value.replace("\\", "/")
    while "//" in value:
        value = value.replace("//", "/")
    return value.rstrip("/").casefold()


def normalize_ip(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def extract_structural_values(text: str) -> list[StructuralValue]:
    found: list[StructuralValue] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: StructuralKind, raw: str, normalized: str) -> None:
        key = (kind.value, normalized)
        if key in seen or not normalized:
            return
        seen.add(key)
        found.append(StructuralValue(kind=kind, raw=raw, normalized=normalized))

    for match in _EMAIL_RE.finditer(text):
        raw = match.group(1)
        add(StructuralKind.EMAIL, raw, normalize_email(raw))
    for match in _OBFUSCATED_EMAIL_RE.finditer(text):
        raw = match.group(0)
        rebuilt = f"{match.group(1)}@{match.group(2)}.{match.group(3)}"
        add(StructuralKind.EMAIL, raw, normalize_email(rebuilt))
    for match in _URL_RE.finditer(text):
        raw = match.group(0).rstrip(").,;")
        add(StructuralKind.URL, raw, normalize_url(raw))
    for match in _IPV4_RE.finditer(text):
        raw = match.group(0)
        norm = normalize_ip(raw)
        if norm:
            add(StructuralKind.IPV4, raw, norm)
    for match in _PATH_RE.finditer(text):
        raw = match.group(0)
        add(StructuralKind.PATH, raw, normalize_path(raw))
    for match in _SHELL_RE.finditer(text):
        raw = match.group(0)
        add(StructuralKind.SHELL_TOKEN, raw, raw.casefold())
    return found


def structural_matches(query: str, candidate: str) -> list[StructuralHit]:
    """Return structural values that appear (normalized) in both texts."""
    q_vals = extract_structural_values(query)
    # Also treat the whole query as a possible email/url/path if it parses alone.
    q_alone = query.strip()
    if "@" in q_alone and " " not in q_alone:
        q_vals.append(
            StructuralValue(
                kind=StructuralKind.EMAIL,
                raw=q_alone,
                normalized=normalize_email(q_alone),
            )
        )
    if q_alone.lower().startswith("http"):
        q_vals.append(
            StructuralValue(
                kind=StructuralKind.URL,
                raw=q_alone,
                normalized=normalize_url(q_alone),
            )
        )

    c_by_norm: dict[tuple[str, str], StructuralValue] = {
        (v.kind.value, v.normalized): v for v in extract_structural_values(candidate)
    }
    hits: list[StructuralHit] = []
    seen: set[tuple[str, str]] = set()
    for qv in q_vals:
        key = (qv.kind.value, qv.normalized)
        if key in seen:
            continue
        cv = c_by_norm.get(key)
        if cv is None:
            continue
        seen.add(key)
        hits.append(
            StructuralHit(
                kind=qv.kind,
                query_value=qv.raw,
                candidate_value=cv.raw,
                normalized=qv.normalized,
            )
        )
    return hits
