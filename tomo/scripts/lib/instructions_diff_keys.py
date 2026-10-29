# version: 0.1.0
"""instructions_diff_keys.py — identity and parsing helpers for the coverage audit.

Extracted from instructions-diff.py (#216). Every other instructions_diff_*
module joins expected entries to rendered actions through these helpers, so
they live in one leaf module that imports only lib.item_key: one copy of the
join rules (ADR-1) keeps the expected side and the actual side keyed alike.
"""
from __future__ import annotations

import re

from lib.item_key import derive as _item_key

# Wikilink bullet in a link_to_moc line_to_add, e.g. "- [[Note]]" or
# "- [[safe-stem|Original Title]]". Used to credit each note in a #70-batched
# link_to_moc (which merges several notes under one (target_moc, new_section)).
_BULLET_RE = re.compile(r"^\s*-\s*\[\[(.+?)\]\]", re.MULTILINE)


def _bullet_titles(line_to_add: str | None) -> list[str]:
    """Note titles referenced by the bullets in a link_to_add block. For an
    aliased link [[stem|Title]] the display Title is returned (it matches the
    suggestion item title the coverage check keys on)."""
    titles: list[str] = []
    for m in _BULLET_RE.finditer(line_to_add or ""):
        ref = m.group(1)
        titles.append(ref.split("|", 1)[1] if "|" in ref else ref)
    return titles


def _stem(path: str | None) -> str:
    if not path:
        return ""
    p = path.rsplit("/", 1)[-1]
    if p.endswith(".md"):
        p = p[:-3]
    return p


def _moc_stem(name: str | None) -> str:
    return _stem(name)


def _key_segments(key: str) -> list[str]:
    """Split an item_key into path segments, extension-stripped on the last
    one only. The parser's current source_path is the bare wikilink stem
    (no extension, e.g. "Dresden") while a rendered action's traceability
    field carries the real filename (e.g. "100 Inbox/Dresden.md") — the two
    conventions must still agree on the *last* segment. Directory segments
    are left untouched: they carry the disambiguating information this
    module needs (ADR-1), and a plain stem compare is exactly what
    collapses two same-named items in different subfolders."""
    parts = key.split("/")
    last = parts[-1]
    if last.endswith(".md"):
        last = last[:-3]
    parts[-1] = last
    return parts


def _keys_match(expected_key: str, actual_key: str) -> bool:
    """True when `expected_key` (an item_key drawn straight from
    confirmed_items, never inbox-prefixed) and `actual_key` (an item_key
    drawn from a rendered action's traceability field) name the same item.

    `render_actions._build_move_note_actions` only inbox-joins a bare
    (single-segment) origin — a subfolder-qualified one is carried through
    verbatim — so `actual_key` may carry one extra leading path segment that
    `expected_key` does not. Comparing the trailing path segments lets the
    two conventions agree without this module knowing the inbox path,
    while still keeping two same-named items in different subfolders apart
    (ADR-1) — the exact identity a bare-stem compare collapses."""
    if not expected_key or not actual_key:
        return False
    if expected_key == actual_key:
        return True
    e_parts = _key_segments(expected_key)
    a_parts = _key_segments(actual_key)
    return len(e_parts) <= len(a_parts) and a_parts[-len(e_parts):] == e_parts


def _confirmed_key(item: dict) -> str:
    """Identity of a confirmed item for the coverage join (ADR-1).

    Prefers the dedicated `item_key` — the item's vault-relative path,
    verbatim — which both parser paths now mint: `build_from_wire` threads it
    through from the wire, and the markdown path joins the suggestions doc on
    the suggestion id. Falls back to `source_path`, the bare display stem, for
    a document that carries no key — one produced before spec 034, or one whose
    edited `Source:` line no longer matches its id, where the markdown join
    refuses to guess. `_keys_match` tolerates both conventions, so the two paths
    can converge independently; without the preference, two confirmed items
    sharing a bare stem are indistinguishable here and a missing action for one
    hides behind the other's presence.
    """
    return _item_key(item.get("item_key") or item.get("source_path") or "")


def _daily_key(entry: dict) -> str:
    """Identity of a daily-update entry for the delete-coverage join (ADR-1).

    `_confirmed_key`'s counterpart on the daily side. `source_item_key` is the
    entry's vault-relative path: on the wire path it travels on the wire
    itself (spec 035 F9), on the markdown path it is restored by
    `suggestion-parser.enrich_daily_updates_with_item_keys`; `source_stem` is
    display text (ADR-2) and is the fallback when no key is available — on
    the markdown path specifically, when the recovery found the discriminator
    ambiguous and declined to guess.
    """
    return _item_key(entry.get("source_item_key") or entry.get("source_stem") or "")


def _same_note_as_any(key: str, keys: list[str]) -> bool:
    """True when `key` names the same inbox note as any member of `keys`.

    SYMMETRIC — neither side is assumed to be the qualified one. Read it as
    "same note as", not as a membership test, before adding a call site.

    A plain `in` test against a set is wrong here even though both sides are
    drawn from one document: a confirmed item may carry its full path while a
    daily entry for that same note carries only the bare stem (or the reverse),
    and the emitter resolves the bare one against the inbox root before
    comparing — so the two DO name one note and it must not expect a deletion
    for both. `_keys_match` is exactly that tolerance; it is applied in both
    directions because either side may be the unqualified one, which the
    move_note join it was written for never has to consider.

    It stays tolerant only where the emitter's fallback could have produced the
    difference: two qualified keys in different inbox subfolders share no path
    suffix and remain distinct (ADR-1), which is the collapse this replaces.
    """
    return any(_keys_match(key, other) or _keys_match(other, key) for other in keys)


def _unique_members(members: list[str]) -> list[str]:
    """Drop repeats (case-insensitive), keeping the first spelling and order."""
    seen: set[str] = set()
    out: list[str] = []
    for m in members:
        if m.casefold() not in seen:
            seen.add(m.casefold())
            out.append(m)
    return out


def _parse_supporting_items(raw: str | list | None) -> list[str]:
    """Parse supporting_items — list (moc-proposal-parser) or str (SNN IDs)."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [s.strip() for s in raw if isinstance(s, str) and s.strip()]
    s = raw.strip().strip("[](){}")
    return [tok.strip().strip("[]()").lstrip("#") for tok in s.split(",") if tok.strip()]
