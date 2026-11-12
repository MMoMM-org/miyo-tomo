# review_state.py — the open-review states of /review and the listing a session start prints.
# version: 0.3.0
"""The one owner of ``/review``'s open-review states (spec 045, SDD Complex Logic; ADR-2, ADR-6).

``STATES`` is the canonical list; ``review_state`` is the only function that
classifies a review document — from its frontmatter, the stem's ``meta.json``,
the set JSON in the inbox and two probe answers — and returns a state, or
None for a review that is not listed (withdrawn); nothing else in Tomo spells
a state. ``stem_state`` is the one probe-and-classify step for a stem: it
reads ``<inbox>/<stem>_instructions.json`` through Kado when the document is
approved, probes the move's source and destination or the insert's target
only when the set waits, and calls ``review_state``; ``review-session.py
start`` (per listed document, through ``open_reviews``) and
``review-instructions.py status`` both go through it. A probe answers
"absent" only on ``KadoNotFoundError``; any other Kado failure stops the run
through ``review_vault.kado_stops``.

The order implemented (coordinator decision 2026-11-12): withdrawn
(``meta.withdrawn``, or a set whose ``actions`` list is empty) → not listed;
a begun delivery (``review_delivery.ReviewMeta.started()``) without
``doc_mark``, or an approved document without a set → ``failed-delivery``;
no set → ``open``; every action ``applied`` → ``applied``; an unapplied
``move_note`` whose source and destination both exist → ``move-refused``; an
unapplied insert or replace whose target is gone → ``target-missing``;
otherwise ``delivered`` (an unreadable set among them). ``open_reviews``
drops an ``applied`` review whose meta carries ``applied_reported`` (the
caller that reported it writes the flag), lists a document whose stem fails
``safe_stem`` under ``skipped_review_docs`` with ``stem-unsafe``, and orders
by period start under the configured week rule and name formats, inferring a
missing ``review_kind`` by parsing the period under them.

``safe_stem`` is the one guard for a stem: a plain folder name under
``tomo-tmp/review/``, never empty, ``.``, ``..`` or carrying ``/`` or ``\\``.
``read_meta`` applies it, and ``review-read.py`` / ``review-doc.py`` call it
from their ``--stem`` argparse types.

Design notes: docs/tomo/scripts/lib/review_state.md
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from lib import review_delivery as rdl
from lib.kado_client import KadoNotFoundError
from lib.note_meta import META_FILE
from lib.period import DEFAULT_FORMATS, ISO, KINDS, MONTH, WEEK, WeekRule, parse_name
from lib.review_vault import Vault, kado_stops

OPEN = "open"
FAILED_DELIVERY = "failed-delivery"
DELIVERED = "delivered"
APPLIED = "applied"
MOVE_REFUSED = "move-refused"
TARGET_MISSING = "target-missing"
STATES = (OPEN, FAILED_DELIVERY, DELIVERED, APPLIED, MOVE_REFUSED, TARGET_MISSING)

DOC_STATE_APPROVED = "approved"
STEM_SUFFIX = "_review"
APPLIED_REPORTED = "applied_reported"
STEM_UNSAFE = "stem-unsafe"
MOVE_NOTE = "move_note"
SECTION_ACTIONS = ("insert_under_marker", "replace_section")
_UNSAFE_MARKS = ("/", "\\", "..")
_NOT_A_FOLDER = ("", ".")


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


def _record(meta: Optional[dict]) -> rdl.ReviewMeta:
    """The meta as the delivery reads it; a copy, so the adapter's defaults never reach the caller's dict."""
    return rdl.ReviewMeta(dict(meta) if isinstance(meta, dict) else {})


def _actions(set_json: Optional[dict]) -> Optional[List[dict]]:
    """The set's action list; None when the set is not a readable instruction set."""
    actions = set_json.get("actions") if isinstance(set_json, dict) else None
    if not isinstance(actions, list) or not all(isinstance(a, dict) for a in actions):
        return None
    return actions


def _applied(action: dict) -> bool:
    return action.get("applied") is True


def review_state(doc: dict, meta: Optional[dict], set_json: Optional[dict] = None, *,
                 target_exists: Optional[bool] = None,
                 inbox_copy_exists: Optional[bool] = None) -> Optional[str]:
    """The state of one review, or None for one that is not listed: ``doc`` is the document's
    frontmatter, ``meta`` the stem's meta.json (None when absent), ``set_json`` the instruction
    set when it exists in the inbox (None when absent); ``target_exists`` and
    ``inbox_copy_exists`` are the probe answers for steps 5 and 6 (None: not probed)."""
    record = _record(meta)
    actions = _actions(set_json)
    # step 3, first: a withdrawn review is never listed (coordinator decision 2026-11-12)
    if record.withdrawn() or (set_json is not None and actions == []):
        return None
    # step 1: a begun delivery without its last step, or an approved document whose set is gone
    if (record.started() and rdl.DOC_MARK not in record.steps_done) or (
            doc_state(doc) == DOC_STATE_APPROVED and set_json is None):
        return FAILED_DELIVERY
    # step 2
    if set_json is None:
        return OPEN
    if actions is None:
        return DELIVERED
    # step 4
    if all(_applied(a) for a in actions):
        return APPLIED
    waiting = [a for a in actions if not _applied(a)]
    # step 5: what a refused move leaves behind — the copy still in the inbox beside the target
    if any(a.get("action") == MOVE_NOTE for a in waiting) and target_exists is True and inbox_copy_exists is True:
        return MOVE_REFUSED
    # step 6
    if any(a.get("action") in SECTION_ACTIONS for a in waiting) and target_exists is False:
        return TARGET_MISSING
    # step 7
    return DELIVERED


# ---------------------------------------------------------------- the probes

def _read_set(vault: Vault, path: str) -> Optional[dict]:
    """The set JSON at ``path``; None only when Kado says NOT_FOUND; a file that is not a JSON
    object is ``{}`` (present, unreadable). Any other Kado failure stops the run."""
    with kado_stops():
        try:
            raw = vault.client.read_file_bytes(path)
        except KadoNotFoundError:
            return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _present(vault: Vault, path) -> Optional[bool]:
    """Whether ``path`` answers through Kado: False only on NOT_FOUND, None when the set names no
    path. Any other Kado failure stops the run — a denial is never read as absent."""
    if not isinstance(path, str) or not path:
        return None
    with kado_stops():
        try:
            if path.lower().endswith(".md"):
                vault.client.read_frontmatter(path)
            else:
                vault.client.read_file(path)
        except KadoNotFoundError:
            return False
    return True


def stem_state(vault: Vault, doc: dict, meta: Optional[dict], stem: str, inbox: str) -> Optional[str]:
    """The state of ``stem`` with the probes (ADR-6): the set JSON is read for an approved document,
    the move's source (then its destination, while the source exists) or the insert's target only
    when the set waits. ``review_vault.Stopped`` on any Kado failure that is not NOT_FOUND;
    ``review_config.UnsafePath`` when ``inbox`` cannot hold a set."""
    if _record(meta).withdrawn():
        return None
    set_json = _read_set(vault, rdl.set_json_path(inbox, stem)) if doc_state(doc) == DOC_STATE_APPROVED else None
    state = review_state(doc, meta, set_json)
    if state != DELIVERED:
        return state
    action = next((a for a in _actions(set_json) or [] if not _applied(a)), None)
    target_exists = inbox_copy_exists = None
    if action is not None and action.get("action") == MOVE_NOTE:
        inbox_copy_exists = _present(vault, action.get("source"))
        if inbox_copy_exists:
            target_exists = _present(vault, action.get("destination"))
    elif action is not None and action.get("action") in SECTION_ACTIONS:
        target_exists = _present(vault, action.get("target_path"))
    return review_state(doc, meta, set_json, target_exists=target_exists, inbox_copy_exists=inbox_copy_exists)


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


def applied_reported(meta: Optional[dict]) -> bool:
    return isinstance(meta, dict) and meta.get(APPLIED_REPORTED) is True


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


def open_reviews(docs: Iterable[Tuple[str, Optional[dict]]], meta_root: Path, vault: Vault, inbox: str, *,
                 rule: WeekRule = ISO,
                 formats: Optional[Dict[str, str]] = None) -> Tuple[List[OpenReview], List[dict]]:
    """``(reviews ordered by period start, skipped)`` over ``(doc_path, frontmatter)`` pairs, each
    classified through ``stem_state`` with ``vault`` and ``inbox``; ``skipped`` names a document
    with unreadable frontmatter, no period or an unsafe stem. A withdrawn review and an applied one
    whose meta says ``applied_reported`` are not listed. ``formats`` are the configured name
    formats per kind, merged over the defaults."""
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
        stem = _str(doc.get("review_stem")) or f"{period}{STEM_SUFFIX}"
        if not safe_stem(stem):
            skipped.append({"doc_path": doc_path, "reason": STEM_UNSAFE})
            continue
        kind = doc.get("review_kind")
        if kind not in KINDS:
            kind = _infer_kind(period, rule, formats)
        meta = read_meta(meta_root, stem)
        state = stem_state(vault, doc, meta, stem, inbox)
        if state is None or (state == APPLIED and applied_reported(meta)):
            continue
        reviews.append((_period_start(period, kind, rule, formats), OpenReview(period, kind, doc_path, stem, state)))
    reviews.sort(key=lambda item: (item[0], item[1].period, item[1].doc_path))
    return [review for _, review in reviews], skipped
