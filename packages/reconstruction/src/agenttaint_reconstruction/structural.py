"""Structural value extraction and matching (emails, URLs, IPs, paths, commands)."""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
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
    # Spelled-out addresses ("alice at evil dot com"): a MODERATE-support structural hit
    # (never STRONG on its own), found only when BOTH the local part and the spelled-out
    # domain appear in the "local at domain" order.
    for qv in q_vals:
        key = (qv.kind.value, qv.normalized)
        if qv.kind != StructuralKind.EMAIL or key in seen or "@" not in qv.normalized:
            continue
        local, _, domain = qv.normalized.rpartition("@")
        found = _spelled_out_address_re(local, domain).search(
            unicodedata.normalize("NFKC", candidate)
        )
        if found:
            seen.add(key)
            hits.append(
                StructuralHit(
                    kind=StructuralKind.EMAIL,
                    query_value=qv.raw,
                    candidate_value=found.group(0),
                    normalized=qv.normalized,
                )
            )
    return hits


# --------------------------------------------------------------------------------------
# Semantic-promotion gate: high-precision arguments need corroboration
# --------------------------------------------------------------------------------------

_EMAIL_ARG_NAMES = frozenset({"to", "cc", "bcc", "recipient", "recipients", "email", "from"})
_URL_ARG_NAMES = frozenset({"url", "uri", "endpoint"})
_PATH_ARG_NAMES = frozenset({"path", "cwd", "file", "filename"})
_SHELL_ARG_NAMES = frozenset({"command", "args", "cmd"})
_FULL_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def classify_structured_argument(argument_name: str, value: str) -> StructuralKind | None:
    """Return the high-precision kind of an argument, or None for free text.

    Emails, URLs, file paths and shell commands are *exact* values: a paraphrase
    similarity score says almost nothing about whether the model copied one from
    an untrusted source, so semantic evidence alone must not promote them.
    """
    name = argument_name.casefold()
    text = value.strip()
    if not text:
        return None
    if _FULL_EMAIL_RE.match(text):
        return StructuralKind.EMAIL
    lowered = text.lower()
    if lowered.startswith(("http://", "https://")):
        return StructuralKind.URL
    if name in _SHELL_ARG_NAMES:
        return StructuralKind.SHELL_TOKEN
    if name in _EMAIL_ARG_NAMES and "@" in text and " " not in text:
        return StructuralKind.EMAIL
    if name in _URL_ARG_NAMES:
        return StructuralKind.URL
    if name in _PATH_ARG_NAMES or (
        " " not in text and (text.startswith("/") or re.match(r"^[A-Za-z]:\\", text))
    ):
        return StructuralKind.PATH
    return None


def _words(text: str) -> set[str]:
    return {w for w in _SPLIT_RE.split(unicodedata.normalize("NFKC", text).casefold()) if w}


def _domain_of_email(normalized_email: str) -> str:
    return normalized_email.rpartition("@")[2]


def _host_of_url(normalized_url: str) -> str:
    return urlsplit(normalized_url).hostname or ""


def _name_overlap(domain: str, candidate: str, candidate_domains: set[str]) -> bool:
    """Exact-domain match, or a spelled-out domain with no conflicting real address."""
    if not domain:
        return False
    if domain in candidate_domains:
        return True
    if candidate_domains:
        # The candidate states a *different* concrete address/host. Shared label
        # fragments (corp-team vs corp-team-mail) are a near miss, not a copy.
        return False
    return (
        _spelled_out_domain_re(domain).search(unicodedata.normalize("NFKC", candidate)) is not None
    )


_DOT_WORDS = r"(?:\s*\[?\(?\s*(?:dot|period)\s*\)?\]?\s*|\s*\[\.\]\s*|\s*\.\s*)"
_HYPHEN_WORDS = r"(?:\s*(?:-|_|dash|hyphen)\s*|\s+)"


@lru_cache(maxsize=512)
def _spelled_out_domain_re(domain: str) -> re.Pattern[str]:
    """Narrow matcher for a domain spelled out in prose ("evil dot com", "evil[.]com").

    Every label must appear in order and consecutive labels must be joined by a dot
    word or a dot (hyphenated labels may be spelled with spaces or "dash"). Loose
    bag-of-words overlap ("an example of a .com site") deliberately does not match.
    """
    groups = [g for g in domain.casefold().split(".") if g]
    if len(groups) < 2:
        return re.compile(r"(?!x)x")  # never matches
    parts = []
    for g in groups:
        tokens = [t for t in re.split(r"[^0-9a-z]+", g) if t]
        if not tokens:
            return re.compile(r"(?!x)x")
        parts.append(_HYPHEN_WORDS.join(re.escape(t) for t in tokens))
    return re.compile(r"(?<![0-9a-z])" + _DOT_WORDS.join(parts) + r"(?![0-9a-z])", re.IGNORECASE)


@lru_cache(maxsize=512)
def _spelled_out_address_re(local: str, domain: str) -> re.Pattern[str]:
    """``local`` + an "at" marker + a spelled-out ``domain`` (see _spelled_out_domain_re)."""
    domain_re = _spelled_out_domain_re(domain)
    tokens = [t for t in re.split(r"[^0-9a-z]+", local.casefold()) if t]
    if not tokens or domain_re.pattern == r"(?!x)x":
        return re.compile(r"(?!x)x")
    local_re = r"[\s._\-]*".join(re.escape(t) for t in tokens)
    at_re = r"\s*(?:@|\[at\]|\(at\)|\bat\b)\s*"
    return re.compile(
        r"(?<![0-9a-z])" + local_re + at_re + domain_re.pattern.replace("(?<![0-9a-z])", "", 1),
        re.IGNORECASE,
    )


def has_structural_overlap(kind: StructuralKind, query: str, candidate: str) -> bool:
    """Weak structural/domain overlap between an argument and a candidate text.

    Deliberately weaker than ``structural_matches`` (which needs the *whole*
    value to recur) but strict enough that unrelated or near-miss text fails.
    """
    q = query.strip()
    if not q:
        return False
    cand_values = extract_structural_values(candidate)
    if kind == StructuralKind.EMAIL:
        emails = [v.normalized for v in extract_structural_values(q) if v.kind == kind]
        if not emails and "@" in q:
            emails = [normalize_email(q)]
        cand_domains = {
            _domain_of_email(v.normalized) for v in cand_values if v.kind == StructuralKind.EMAIL
        }
        cand_domains |= {
            _host_of_url(v.normalized) for v in cand_values if v.kind == StructuralKind.URL
        }
        cand_domains.discard("")
        return any(
            _name_overlap(_domain_of_email(e), candidate, cand_domains) for e in emails if "@" in e
        )
    if kind == StructuralKind.URL:
        host = _host_of_url(normalize_url(q))
        cand_hosts = {
            _host_of_url(v.normalized) for v in cand_values if v.kind == StructuralKind.URL
        }
        cand_hosts |= {
            _domain_of_email(v.normalized) for v in cand_values if v.kind == StructuralKind.EMAIL
        }
        cand_hosts.discard("")
        return _name_overlap(host, candidate, cand_hosts)
    if kind == StructuralKind.PATH:
        norm = normalize_path(q)
        parts = [p for p in norm.split("/") if p]
        if not parts:
            return False
        cand_paths = [v.normalized for v in cand_values if v.kind == StructuralKind.PATH]
        parent = "/".join(parts[:-1])
        for cp in cand_paths:
            if parent and (cp.startswith(parent + "/") or cp == parent):
                return True
            cparts = [p for p in cp.split("/") if p]
            if len(parts) >= 2 and len(cparts) >= 2 and parts[:2] == cparts[:2]:
                return True
        # Distinctive file name recurring verbatim in the candidate.
        base = parts[-1]
        return len(base) >= 4 and base in _words(candidate) | set(cand_paths) | {
            p for cp in cand_paths for p in cp.split("/")
        }
    if kind == StructuralKind.SHELL_TOKEN:
        tokens = [t for t in q.split() if t]
        if not tokens:
            return False
        words = _words(candidate)
        if tokens[0].casefold() not in words:
            return False
        rest = [t for t in tokens[1:] if not t.startswith("-") and len(t) >= 3]
        if not rest:
            return True
        return any(t.casefold() in candidate.casefold() for t in rest)
    return False
