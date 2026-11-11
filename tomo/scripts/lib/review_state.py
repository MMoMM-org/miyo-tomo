# review_state.py — the open-review states of /review and the listing a session start prints.
# version: 0.2.1
"""The one owner of ``/review``'s open-review states (spec 045, SDD Complex Logic).

``STATES`` is the canonical list; ``review_state`` is the only function that
classifies a review document; nothing else in Tomo spells a state. The inbox
document (``tomo.doc_type: review``) is the source of truth (ADR-2): its
top-level ``review_period``, ``review_kind`` and ``review_stem`` keys name the
review, ``tomo.state`` says whether the user approved it. ``meta.json`` under
``tomo-tmp/review/<stem>/`` is content-free and only adds ``failed_step``; a
missing or broken meta counts as absent.

``safe_stem`` is the one guard for a stem: a plain folder name under
``tomo-tmp/review/``, never empty, ``.``, ``..`` or carrying ``/`` or ``\\``.
``read_meta`` applies it, and ``review-read.py`` / ``review-doc.py`` call it
from their ``--stem`` argparse types (T3.8: three private copies had drifted).

``open_reviews`` orders the listing by period start under the configured
week rule and name formats (the default ISO week format would override a
configured rule) and infers a missing ``review_kind`` by parsing the period
under those formats.

T2.3 implements steps 1 and 2 of the algorithm (``failed-delivery``, ``open``).
Steps 3–7 (``delivered``, ``applied``, ``move-refused``, ``target-missing``)
need the set JSON and the probes and arrive in T4.3; until then a set JSON
handed to ``review_state`` raises ``StateNotClassified``.

Stdlib only. Design notes: docs/tomo/scripts/lib/review_state.md
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from lib.period import DEFAULT_FORMATS, ISO, KINDS, MONTH, WEEK, WeekRule, parse_name

OPEN = "open"
FAILED_DELIVERY = "failed-delivery"
DELIVERED = "delivered"
APPLIED = "applied"
MOVE_REFUSED = "move-refused"
TARGET_MISSING = "target-missing"
STATES = (OPEN, FAILED_DELIVERY, DELIVERED, APPLIED, MOVE_REFUSED, TARGET_MISSING)

DOC_STATE_APPROVED = "approved"
META_FILE = "meta.json"
STEM_SUFFIX = "_review"
_UNSAFE_MARKS = ("/", "\\", "..")
_NOT_A_FOLDER = ("", ".")


class StateNotClassified(NotImplementedError):
    """A set JSON was handed in: steps 3–7 of the algorithm arrive in spec 045 T4.3."""


# ---------------------------------------------------------------- the stem

def safe_stem(stem: str) -> bool:
    """Whether ``stem`` names a plain folder under the stage root: not empty or whitespace,
    not ``.`` or ``..``, and without ``/``, ``\\`` or ``..`` anywhere."""
    if not isinstance(stem, str) or stem.strip() in _NOT_A_FOLDER:
        return False
    return not any(mark in stem for mark in _UNSAFE_MARKS)


# ---------------------------------------------------------------- the state

def doc_state(doc: dict) -> Optional[str]:
    tomo = doc.get("tomo") if isinstance(doc, dict) else None
    state = tomo.get("state") if isinstance(tomo, dict) else None
    return state if isinstance(state, str) else None


def review_state(doc: dict, meta: Optional[dict], set_json: Optional[dict] = None, *,
                 target_exists: Optional[bool] = None,
                 inbox_copy_exists: Optional[bool] = None) -> str:
    """The state of one review: ``doc`` is the document's frontmatter, ``meta`` the
    stem's meta.json (None when absent), ``set_json`` the instruction set when it
    exists in the inbox (None when absent); the probes are for steps 5 and 6."""
    failed_step = meta.get("failed_step") if isinstance(meta, dict) else None
    if failed_step or (doc_state(doc) == DOC_STATE_APPROVED and set_json is None):
        return FAILED_DELIVERY
    if set_json is None:
        return OPEN
    raise StateNotClassified("set JSON states (steps 3-7) arrive in spec 045 T4.3")


# ---------------------------------------------------------------- meta.json

def read_meta(root: Path, stem: str) -> Optional[dict]:
    """``<root>/<stem>/meta.json`` as a dict; None when missing, unparsable, not an object or the stem is unsafe."""
    if not safe_stem(stem):
        return None
    path = Path(root) / stem / META_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------- the listing

@dataclass(frozen=True)
class OpenReview:
    period: str
    kind: str
    doc_path: str
    stem: str
    state: str

    def to_dict(self) -> Dict[str, str]:
        return {"period": self.period, "kind": self.kind, "doc_path": self.doc_path,
                "stem": self.stem, "state": self.state}


def _str(value) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() else None


def _period_start(period: str, kind: str, rule: WeekRule, formats: Dict[str, str]) -> date:
    """The period's first day under ``formats[kind]`` for ordering; ``date.max`` when it does not parse."""
    fmt = formats.get(kind)
    parsed = parse_name(period, fmt, rule) if fmt else None
    return parsed.start if parsed is not None else date.max


def _infer_kind(period: str, rule: WeekRule, formats: Dict[str, str]) -> str:
    """The first kind (week before month) whose format parses the name; a name no
    format parses keeps the letter guess so the listing still shows a kind."""
    for kind in KINDS:
        if _period_start(period, kind, rule, formats) != date.max:
            return kind
    return WEEK if "W" in period.upper() else MONTH


def open_reviews(docs: Iterable[Tuple[str, Optional[dict]]], meta_root: Path, *,
                 rule: WeekRule = ISO,
                 formats: Optional[Dict[str, str]] = None) -> Tuple[List[OpenReview], List[dict]]:
    """``(reviews ordered by period start, skipped)`` over ``(doc_path, frontmatter)``
    pairs; ``skipped`` names a document with unreadable frontmatter or no period.
    ``formats`` are the configured name formats per kind, merged over the defaults."""
    formats = dict(DEFAULT_FORMATS, **(formats or {}))
    reviews: List[Tuple[date, OpenReview]] = []
    skipped: List[dict] = []
    for doc_path, doc in docs:
        if not isinstance(doc, dict):
            skipped.append({"doc_path": doc_path, "reason": "frontmatter-unreadable"})
            continue
        period = _str(doc.get("review_period"))
        if period is None:
            skipped.append({"doc_path": doc_path, "reason": "period-missing"})
            continue
        kind = doc.get("review_kind")
        if kind not in KINDS:
            kind = _infer_kind(period, rule, formats)
        stem = _str(doc.get("review_stem")) or f"{period}{STEM_SUFFIX}"
        # No set_json here until T4.3 classifies it: StateNotClassified would abort the listing.
        state = review_state(doc, read_meta(meta_root, stem))
        reviews.append((_period_start(period, kind, rule, formats), OpenReview(period, kind, doc_path, stem, state)))
    reviews.sort(key=lambda item: (item[0], item[1].period, item[1].doc_path))
    return [review for _, review in reviews], skipped
