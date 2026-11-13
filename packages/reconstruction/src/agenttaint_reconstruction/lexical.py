"""Lexical evidence: exact, normalized, token overlap, and n-gram similarity.

Scores are in [0, 1] and are NOT probabilities of causation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[a-z0-9@._/-]+", re.IGNORECASE)


def normalize_text(text: str) -> str:
    """NFKC normalize, casefold, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text)
    text = text.casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(normalize_text(text))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _ngrams(tokens: list[str], n: int) -> set[str]:
    if len(tokens) < n:
        return set(tokens)
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


@dataclass(frozen=True)
class LexicalScore:
    exact_substring: bool
    normalized_equal: bool
    token_jaccard: float
    bigram_jaccard: float
    score: float
    """Transparent aggregate in [0, 1] — not a causation probability."""


def lexical_similarity(query: str, candidate: str) -> LexicalScore:
    q_norm = normalize_text(query)
    c_norm = normalize_text(candidate)
    exact = bool(q_norm) and (q_norm in c_norm or c_norm in q_norm)
    equal = q_norm == c_norm and bool(q_norm)
    q_toks = tokenize(query)
    c_toks = tokenize(candidate)
    token_j = _jaccard(set(q_toks), set(c_toks))
    bigram_j = _jaccard(_ngrams(q_toks, 2), _ngrams(c_toks, 2))

    # Transparent weighted blend; documented as heuristic evidence only.
    score = 0.0
    if equal:
        score = 1.0
    elif exact:
        score = max(0.85, 0.5 * token_j + 0.5 * bigram_j)
    else:
        score = 0.55 * token_j + 0.45 * bigram_j

    return LexicalScore(
        exact_substring=exact,
        normalized_equal=equal,
        token_jaccard=token_j,
        bigram_jaccard=bigram_j,
        score=min(1.0, max(0.0, score)),
    )
