#!/usr/bin/env python3
# version: 0.2.0
"""test_034_t5_0b_delete_bookkeeping_item_key.py — the delete bookkeeping
joins on item_key, not on the bare filename stem.

Covers T5.0b (XDD 034 Phase 5). `_build_delete_source_actions` joined three
inputs — confirmed items, move_note origins and daily entries — on a bare
filename stem across six collections (`confirmed_stems`, `expected_by_stem`,
`keep_source_stems`, `seen`, `daily_stems`, `moves_by_origin`). Recursive
discovery (Phase 3) lets two notes in different inbox subfolders share a
filename, so each collection collapsed two distinct notes into one bucket:
one delete emitted for two origins, one note's `keep_source` suppressing the
other's delete, one namesake's daily entry crediting the other in the reason
string the user approves under CON-2.

Reachability (plan/phase-5.md, T5.0b): the two-confirmed-namesake cases are
wire-path-only today — the #116 filter drops such items on the markdown path
before `build_actions` ever runs — so they are driven by calling
`_build_delete_source_actions` directly, the established pattern in
`test_instruction_render_delete_source_completion_gate.py`. The daily-entry
cases are live on BOTH parser paths (T5.0 threads `source_item_key` through
markdown and wire alike), so they are asserted on both.

Spec: docs/XDD/specs/034-recursive-inbox-discovery/
SDD:  ADR-1 (the item key IS the vault-relative path), ADR-2 (`stem` stays
      display text), CON-2 (the user approves on the rendered reason strings),
      CON-4 (emitted action shape unchanged)
AC:   OQ6 (source-deletion completion gate)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


ir = _load("instruction_render_034_t50b", "instruction-render.py")
sp = _load("suggestion_parser_034_t50b", "suggestion-parser.py")

INBOX = "100 Inbox"
# Two notes, same filename, different inbox subfolders — the collision this
# spec exists to handle.
KEY_A = f"{INBOX}/Projects/Dresden.md"
KEY_B = f"{INBOX}/Travel/Dresden.md"
DISPLAY = "Dresden.md"
DAY = "2026-06-10"
CONTENT_A = "Sprint retro moved to the Dresden office."
CONTENT_B = "Zwinger courtyard, gallery closed on Mondays."


# ──────────────────────────────────────────────────────────────────────
# Fixture helpers
# ──────────────────────────────────────────────────────────────────────

def _confirmed(item_key: str, item_id: str, keep_source: bool = False) -> dict:
    """A confirmed item: display stem in `source_path` (ADR-2), path in
    `item_key` (ADR-1) — exactly what both parser paths emit."""
    return {
        "id": item_id,
        "action": "create_note",
        "source_path": DISPLAY,
        "item_key": item_key,
        "keep_source": keep_source,
    }


def _move_note(item_key: str, note_id: str) -> dict:
    """A move_note as `_build_move_note_actions` emits it: `source_inbox_item`
    is already the resolved vault-relative origin path."""
    return {
        "id": note_id,
        "action": "move_note",
        "source_inbox_item": item_key,
        "source": f"{INBOX}/rendered-{note_id}.md",
        "destination": f"200 Notes/{note_id}.md",
        "title": note_id,
        "rendered_file": f"rendered-{note_id}.md",
        "parent_mocs": [],
        "tags": [],
    }


def _daily_day(entries: list[dict]) -> dict:
    """One parsed daily-updates day carrying accepted log entries."""
    return {
        "date": DAY,
        "daily_note_path": None,
        "trackers": [],
        "log_entries": entries,
        "log_links": [],
    }


def _doc(entries: list[tuple[str, str, str]]) -> dict:
    """The Tomo-owned suggestions doc both parser paths recover keys from.

    `entries` is [(content, source_item_key, section_id)].
    """
    return {
        "daily_notes_updates": [{
            "daily_note_stem": DAY,
            "exists": True,
            "trackers": [],
            "log_links": [],
            "log_entries": [
                {
                    "content": content,
                    "reason": "worthiness 0.2",
                    "source_stem": "Dresden",
                    "source_item_key": key,
                    "source_section": section,
                }
                for content, key, section in entries
            ],
        }],
    }


def _markdown(entries: list[str]) -> str:
    """The rendered review document — it carries only the bare display stem."""
    lines = [
        "## Daily Notes Updates",
        "",
        f"### [[{DAY}]]",
        "",
        "**Possible Log Entries (inline text):**",
    ]
    for content in entries:
        lines += [
            f"- after_last_line — {content}",
            "  - Reason: worthiness 0.2",
            "  - Source: [[Dresden]]",
            "  - [x] Accept",
        ]
    lines += ["", "## Suggestions", ""]
    return "\n".join(lines)


def _wire(entries: list[tuple[str, str, str]]) -> dict:
    """An edited wire (ADR-026). F9 (spec 035): daily entries now carry
    `source_item_key` directly — populated by construction at render time,
    exactly like the real wire suggestions-render.py emits."""
    return {
        "suggestions": [],
        "daily_updates": [_daily_day([
            {
                "time": None,
                "position": "after_last_line",
                "content": content,
                "reason": "worthiness 0.2",
                "source_stem": "Dresden",
                "source_item_key": key,
                "accepted": True,
                "force_atomic_note": False,
            }
            for content, key, _section in entries
        ])],
    }


def _daily_updates_via_path(path: str, entries: list[tuple[str, str, str]],
                            tmp_path: Path) -> list[dict]:
    """Produce the `daily_updates` the renderer receives, on either parser path.

    F9 (spec 035): the two paths now diverge in MECHANISM. Markdown still
    recovers identity from the Tomo-owned suggestions doc via
    `enrich_daily_updates_with_item_keys` (discriminator match — markdown text
    itself cannot carry the key). Wire carries `source_item_key` directly;
    `build_from_wire`'s verbatim passthrough reproduces it with no restore
    step (`_restore_daily_item_keys` was retired).
    """
    if path == "markdown":
        doc = _doc(entries)
        contents = [content for content, _key, _section in entries]
        parsed = sp.parse_daily_updates(_markdown(contents))
        sp.enrich_daily_updates_with_item_keys(parsed, doc)
        return parsed
    built = sp.build_from_wire(_wire(entries), "")
    return built["daily_updates"]


def _deletes(actions: list[dict]) -> list[dict]:
    return [a for a in actions if a.get("action") == "delete_source"]


def _paths(actions: list[dict]) -> set[str]:
    return {a["source_path"] for a in _deletes(actions)}


def _reason_for(actions: list[dict], source_path: str) -> str:
    matches = [a for a in _deletes(actions) if a["source_path"] == source_path]
    assert len(matches) == 1, f"expected 1 delete for {source_path}, got {matches}"
    return matches[0]["reason"]


# ──────────────────────────────────────────────────────────────────────
# Case 1 — two confirmed namesakes (wire path only)
# ──────────────────────────────────────────────────────────────────────

def test_two_confirmed_namesakes_each_get_their_own_delete():
    """`moves_by_origin` / `expected_by_stem`: two namesakes, one atomic each.

    Stem-keyed, both move_notes land in one bucket, the gate passes
    coincidentally (2 >= 2) and `moves[0]` emits a single delete — B's source
    survives in the inbox.
    """
    confirmed = [_confirmed(KEY_A, "S01"), _confirmed(KEY_B, "S02")]
    move_notes = [_move_note(KEY_A, "A01"), _move_note(KEY_B, "A02")]

    out = ir._build_delete_source_actions(
        confirmed, move_notes, [], [], INBOX, [0]
    )

    assert _paths(out) == {KEY_A, KEY_B}, (
        f"each namesake needs its own delete, got {_deletes(out)}"
    )
    assert _reason_for(out, KEY_A) == "Origin consumed by 1 atomic."
    assert _reason_for(out, KEY_B) == "Origin consumed by 1 atomic."


def test_oq6_denominator_counts_this_notes_atomics_only():
    """The OQ6 gate denominator is per ORIGIN NOTE, not per filename.

    A carries two atomics, both rendered; B carries one whose move_note never
    arrived. A is fully captured and must be deleted; only B defers. Keyed by
    stem the two shared a denominator (3) against a shared bucket of 2 moves,
    so B's missing atomic held back A's delete as well — the under-count the
    plan names.
    """
    confirmed = [
        _confirmed(KEY_A, "S01"),
        _confirmed(KEY_A, "S02"),
        _confirmed(KEY_B, "S03"),
    ]
    move_notes = [
        _move_note(KEY_A, "A01"),
        _move_note(KEY_A, "A02"),
        # B's atomic was dropped before rendering — no move_note for it.
    ]

    out = ir._build_delete_source_actions(
        confirmed, move_notes, [], [], INBOX, [0]
    )

    assert _paths(out) == {KEY_A}, (
        f"A is fully captured (2 of 2) and B is not; got {_deletes(out)}"
    )
    assert _reason_for(out, KEY_A) == "Origin consumed by 2 atomics."


# ──────────────────────────────────────────────────────────────────────
# Case 2 — keep_source on one namesake only (wire path only)
# ──────────────────────────────────────────────────────────────────────

def test_keep_source_on_one_namesake_does_not_suppress_the_other():
    """`keep_source_stems`: A opts out of deletion, B does not.

    Stem-keyed, A's opt-out lands in the same bucket as B and suppresses both —
    zero deletes. B's user never asked to keep their note.
    """
    confirmed = [
        _confirmed(KEY_A, "S01", keep_source=True),
        _confirmed(KEY_B, "S02", keep_source=False),
    ]
    move_notes = [_move_note(KEY_A, "A01"), _move_note(KEY_B, "A02")]

    out = ir._build_delete_source_actions(
        confirmed, move_notes, [], [], INBOX, [0]
    )

    assert _paths(out) == {KEY_B}, (
        f"only the namesake that opted out may be kept, got {_deletes(out)}"
    )


# ──────────────────────────────────────────────────────────────────────
# Case 3 — two daily-only namesakes (both parser paths)
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("parser_path", ["markdown", "wire"])
def test_two_daily_only_namesakes_each_get_their_own_delete(parser_path, tmp_path):
    """`seen`: two namesakes whose content is fully captured in the daily note.

    Stem-keyed, the second one is skipped as already-seen and its source
    survives. Live on both parser paths — T5.0 recovers `source_item_key` for
    daily entries from the suggestions doc on each.
    """
    daily_updates = _daily_updates_via_path(
        parser_path,
        [(CONTENT_A, KEY_A, "S01"), (CONTENT_B, KEY_B, "S02")],
        tmp_path,
    )
    # Reachability: a fixture whose keys never arrived would exercise the
    # inbox-root fallback, not the collision.
    keys = {
        e.get("source_item_key")
        for day in daily_updates for e in day["log_entries"]
    }
    assert keys == {KEY_A, KEY_B}, f"{parser_path} path lost the keys: {keys}"

    out = ir._build_delete_source_actions([], [], daily_updates, [], INBOX, [0])

    assert _paths(out) == {KEY_A, KEY_B}, (
        f"each daily-only namesake needs its own delete, got {_deletes(out)}"
    )
    for key in (KEY_A, KEY_B):
        assert _reason_for(out, key) == "Content fully captured in daily note."


# ──────────────────────────────────────────────────────────────────────
# Case 4 — one confirmed namesake plus one daily-only (both parser paths)
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("parser_path", ["markdown", "wire"])
def test_confirmed_namesake_does_not_swallow_the_daily_only_one(
    parser_path, tmp_path
):
    """`confirmed_stems` + `daily_stems`: A is confirmed, B is daily-only.

    Stem-keyed, two things go wrong at once and both reach the document the
    user approves under CON-2: B's daily-only delete is suppressed because A
    is confirmed, and A's reason reads "+ daily" for a daily capture that was
    B's.
    """
    daily_updates = _daily_updates_via_path(
        parser_path, [(CONTENT_B, KEY_B, "S02")], tmp_path
    )
    confirmed = [_confirmed(KEY_A, "S01")]
    move_notes = [_move_note(KEY_A, "A01")]

    out = ir._build_delete_source_actions(
        confirmed, move_notes, daily_updates, [], INBOX, [0]
    )

    assert _paths(out) == {KEY_A, KEY_B}, (
        f"the confirmed namesake must not swallow the daily-only one, "
        f"got {_deletes(out)}"
    )
    assert _reason_for(out, KEY_A) == "Origin consumed by 1 atomic.", (
        "A's reason must not credit A with B's daily capture"
    )
    assert _reason_for(out, KEY_B) == "Content fully captured in daily note."


@pytest.mark.parametrize("parser_path", ["markdown", "wire"])
def test_daily_suffix_still_fires_for_the_note_that_earned_it(
    parser_path, tmp_path
):
    """Positive control for the `+ daily` suffix: A's OWN daily entry.

    Re-keying must not make the suffix unreachable — it must fire when the
    daily entry belongs to the origin being deleted.
    """
    daily_updates = _daily_updates_via_path(
        parser_path, [(CONTENT_A, KEY_A, "S01")], tmp_path
    )
    confirmed = [_confirmed(KEY_A, "S01")]
    move_notes = [_move_note(KEY_A, "A01")]

    out = ir._build_delete_source_actions(
        confirmed, move_notes, daily_updates, [], INBOX, [0]
    )

    assert _paths(out) == {KEY_A}
    assert _reason_for(out, KEY_A) == "Origin consumed by 1 atomic + daily."


# ──────────────────────────────────────────────────────────────────────
# Regression: a keyless document (pre-034) is unaffected
# ──────────────────────────────────────────────────────────────────────

def test_keyless_document_still_resolves_to_the_inbox_root():
    """A suggestions document minted before spec 034 carries no `item_key`.

    Every input then falls back to the inbox-root reconstruction, so all three
    spellings still join — one origin, one delete, `+ daily` attributed to it.
    """
    confirmed = [{
        "id": "S01",
        "action": "create_note",
        "source_path": "solo-note.md",
        "keep_source": False,
    }]
    move_notes = [_move_note(f"{INBOX}/solo-note.md", "A01")]
    daily_updates = [_daily_day([{
        "accepted": True,
        "source_stem": "solo-note",
        "content": "captured",
    }])]

    out = ir._build_delete_source_actions(
        confirmed, move_notes, daily_updates, [], INBOX, [0]
    )

    assert _paths(out) == {f"{INBOX}/solo-note.md"}
    assert _reason_for(out, f"{INBOX}/solo-note.md") == (
        "Origin consumed by 1 atomic + daily."
    )


def test_non_md_origin_extension_is_not_collapsed():
    """The key strips only `.md`. An `.m4a` origin and an `.md` note of the
    same name are different files and must stay in different buckets."""
    audio_key = f"{INBOX}/Voice/memo.m4a"
    note_key = f"{INBOX}/Voice/memo.md"
    confirmed = [
        {"id": "S01", "action": "create_note", "source_path": "memo.m4a",
         "item_key": audio_key, "keep_source": True},
        {"id": "S02", "action": "create_note", "source_path": "memo.md",
         "item_key": note_key, "keep_source": False},
    ]
    move_notes = [_move_note(audio_key, "A01"), _move_note(note_key, "A02")]

    out = ir._build_delete_source_actions(
        confirmed, move_notes, [], [], INBOX, [0]
    )

    assert _paths(out) == {note_key}, (
        f"the kept .m4a must not suppress the .md, got {_deletes(out)}"
    )


# ──────────────────────────────────────────────────────────────────────
# CON-4 — the emitted shape is unchanged
# ──────────────────────────────────────────────────────────────────────

def test_emitted_action_shape_is_unchanged():
    """Re-keying is internal bookkeeping: every emitted action keeps exactly
    the fields it had, and no key ever leaks onto the wire."""
    confirmed = [_confirmed(KEY_A, "S01"), _confirmed(KEY_B, "S02")]
    move_notes = [_move_note(KEY_A, "A01"), _move_note(KEY_B, "A02")]

    out = ir._build_delete_source_actions(
        confirmed, move_notes, [], [], INBOX, [0]
    )

    for action in _deletes(out):
        assert set(action) == {"id", "action", "source_path", "reason"}, (
            f"unexpected fields on {action}"
        )
