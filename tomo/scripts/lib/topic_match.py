# topic_match.py — Standalone weighted-overlap scorer for MOC topic matching.
# version: 0.1.0
"""Ruzicka-style weighted topic overlap used by both MOC match sites.

Weights a topic W_TITLE (2) when it appears as a substring of the note's
title, W_BASE (1) otherwise.  Missing-side weight is 0 in both the numerator
(Σmin over ∩) and the denominator (Σmax over ∪), so a topic that is
exclusive to one side cannot inflate the score beyond what the shared mass
supports.

Stdlib only — no new dependencies.

See docs/XDD/specs/029-topic-weighting-moc-matching/ for the full design.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

W_TITLE: int = 2
W_BASE: int = 1


def _normalize(text: str) -> str:
    """Lowercase, strip, and collapse internal whitespace."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def title_tokens(title: str) -> str:
    """Return the normalized form of *title* used for substring matching."""
    return _normalize(title)


def _weight(topic: str, norm_title: str) -> int:
    """Return W_TITLE if *topic* (normalized) is a substring of *norm_title*."""
    t = _normalize(topic)
    return W_TITLE if t and norm_title and t in norm_title else W_BASE


def weighted_overlap(
    topics_a: Iterable[str],
    title_a: str,
    topics_b: Iterable[str],
    title_b: str,
) -> float:
    """Return the weighted Ruzicka overlap score in [0.0, 1.0].

    Empty topic set on either side returns 0.0.  Pure and total — no I/O.
    """
    a = {_normalize(t) for t in topics_a if _normalize(t)}
    b = {_normalize(t) for t in topics_b if _normalize(t)}
    if not a or not b:
        return 0.0

    nt_a = title_tokens(title_a)
    nt_b = title_tokens(title_b)

    wa = {t: _weight(t, nt_a) for t in a}
    wb = {t: _weight(t, nt_b) for t in b}

    inter = a & b
    union = a | b

    numer = sum(min(wa.get(t, 0), wb.get(t, 0)) for t in inter)
    denom = sum(max(wa.get(t, 0), wb.get(t, 0)) for t in union)

    return (numer / denom) if denom else 0.0
