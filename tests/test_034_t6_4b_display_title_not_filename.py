#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t6_4b_display_title_not_filename.py — `source_note_title` is a
display field, not a filename.

Spec 034 (recursive inbox discovery), Phase 6 T6.4b. Found by the T6.4 live
run: the emitter wrote `sanitize_stem(title)` into `link_to_moc.
source_note_title`, while `derive_expected` keys the coverage audit on the raw
`item["title"]`. Every title containing a character `sanitize_stem` replaces
(`\\ / : * ? " < > |`) therefore failed to join, and the audit hard-failed a
run whose instruction set was correct. Observed live on a title carrying a
colon that the analyst produced unprompted.

Under ADR-2 `source_note_title` is display text. The sanitised stem is a real
need — three withholding joins key on it (`_orphaned_link_titles`,
`_links_for`, `_qualify_contested_bullets`) — so it moves to its own field,
`source_note_stem`, which is Tomo-internal and stripped before the wire
(Hashi's `link_to_moc` schema is `additionalProperties: false`).

Two fields, two jobs, neither lying — the same shape ADR-2 gave `item_key`
and `stem` one layer up.

CON-7: fixtures and fakes only, no live vault run.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

from lib.obsidian_filename import is_obsidian_safe, sanitize_stem  # noqa: E402
from lib.render_actions import build_actions, validate_destinations  # noqa: E402
from lib.render_resolve import (  # noqa: E402
    _merge_new_section_links,
    _strip_internal_link_fields,
)

_spec_diff = importlib.util.spec_from_file_location(
    "instructions_diff", SCRIPTS_DIR / "instructions-diff.py"
)
diff = importlib.util.module_from_spec(_spec_diff)
assert _spec_diff.loader is not None
_spec_diff.loader.exec_module(diff)

SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"

NOTES = "Atlas/202 Notes/"
INBOX = "100 Inbox/"
ASSETS = "Atlas/290 Assets/295 Attachments/"
TRAVEL = "Travel (MOC)"

CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": ASSETS,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
}

# The live case, verbatim in shape: a colon the analyst produced by itself.
COLON_TITLE = "Elbe-Schifffahrt: Tschechischer Pegel bei Usti nad Labem"
COLON_STEM = sanitize_stem(COLON_TITLE)
SAFE_TITLE = "Prager Burg"

COLON_KEY = "100 Inbox/Reise/Elbe.md"
SAFE_KEY = "100 Inbox/Reise/Prag.md"


def _atomic(item_key: str, title: str, *, idx: int,
            parents: list[str] | None = None) -> tuple[dict, dict]:
    """One manifest entry + its confirmed item, as instruction-render pairs them."""
    stem = item_key.rsplit("/", 1)[-1][:-3]
    manifest = {
        "action": "create_atomic_note",
        "title": title,
        "rendered_file": f"2026-09-09_10{idx:02d}_note.md",
        "destination": NOTES,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": list(parents or []),
        "tags": [],
        "attachments": [],
    }
    confirmed = {
        "id": f"S{idx:02d}",
        "title": title,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": list(parents or []),
        "attachments": [],
    }
    return manifest, confirmed


def _build(pairs: list[tuple[dict, dict]]) -> tuple[list[dict], list[dict]]:
    return build_actions(
        [m for m, _ in pairs], [c for _, c in pairs],
        [], [], CFG, kado_client=None,
    )


def _link_for(actions: list[dict], target_moc: str) -> dict:
    return next(
        a for a in actions
        if a.get("action") == "link_to_moc" and a.get("target_moc") == target_moc
    )


def _run_audit(parsed: dict, instrs: dict) -> tuple[int, list[str], str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc, obs = diff.run_diff(parsed, instrs)
    return rc, obs, buf.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# 1. The two fields carry the two values
# ──────────────────────────────────────────────────────────────────────────────

def test_source_note_title_carries_the_raw_display_title():
    """`source_note_title` is display text under ADR-2. A title with a
    forbidden character keeps it — the filename is a separate concern
    [ref: SDD/ADR-2]."""
    actions, _ = _build([_atomic(COLON_KEY, COLON_TITLE, idx=1, parents=[TRAVEL])])
    link = _link_for(actions, TRAVEL)
    assert link["source_note_title"] == COLON_TITLE, (
        f"source_note_title must carry the raw display title, got "
        f"{link['source_note_title']!r} — a sanitised filename here is the "
        f"category error T6.4b exists to close"
    )
    assert ":" in link["source_note_title"]


def test_source_note_stem_carries_the_sanitised_form():
    """The sanitised stem is a real need — three withholding passes join on
    it — so it gets its own honestly-named field."""
    actions, _ = _build([_atomic(COLON_KEY, COLON_TITLE, idx=1, parents=[TRAVEL])])
    link = _link_for(actions, TRAVEL)
    assert link["source_note_stem"] == COLON_STEM, (
        f"source_note_stem must carry the sanitised stem, got "
        f"{link.get('source_note_stem')!r}"
    )
    assert is_obsidian_safe(link["source_note_stem"])


def test_wikilink_still_targets_the_safe_stem():
    """#69 must not regress: the bullet still points at the renamed file and
    aliases the original title for display."""
    actions, _ = _build([_atomic(COLON_KEY, COLON_TITLE, idx=1, parents=[TRAVEL])])
    link = _link_for(actions, TRAVEL)
    assert link["line_to_add"] == f"- [[{COLON_STEM}|{COLON_TITLE}]]", (
        f"the emitted wikilink must still resolve to the safe stem (#69), got "
        f"{link['line_to_add']!r}"
    )


def test_a_title_with_no_forbidden_character_is_unchanged():
    """The fix must not move the cases that already pass. Where sanitisation
    is a no-op, both fields hold the same string — as they did before."""
    actions, _ = _build([_atomic(SAFE_KEY, SAFE_TITLE, idx=2, parents=[TRAVEL])])
    link = _link_for(actions, TRAVEL)
    assert link["source_note_title"] == SAFE_TITLE
    assert link["source_note_stem"] == SAFE_TITLE
    assert link["line_to_add"] == f"- [[{SAFE_TITLE}]]"


# ──────────────────────────────────────────────────────────────────────────────
# 2. The audit's own outcome — the assertion that matters
# ──────────────────────────────────────────────────────────────────────────────

def _audit_inputs(pairs: list[tuple[dict, dict]]) -> tuple[dict, dict]:
    actions, _ = _build(pairs)
    parsed = {
        "confirmed_items": [c for _, c in pairs],
        "daily_updates": [],
        "skipped": [],
    }
    instrs = {
        "schema_version": "1", "type": "tomo-instructions",
        "action_count": len(actions), "actions": actions,
    }
    return parsed, instrs


def test_audit_link_coverage_ok_for_a_colon_title():
    """The live failure, as its own outcome: a correct instruction set whose
    title carries a colon must reconcile, not hard-fail.

    This is the assertion the task asks for — the audit's verdict, not the
    field's value. Against HEAD it yields
    `links=[DIFF want=['Travel (MOC)'] got=[]]` [ref: PRD/Feature 6]."""
    parsed, instrs = _audit_inputs([
        _atomic(COLON_KEY, COLON_TITLE, idx=1, parents=[TRAVEL]),
    ])
    rc, obs, out = _run_audit(parsed, instrs)
    line = next(ln for ln in out.splitlines() if "S01" in ln)
    assert "links=[OK]" in line, (
        f"a correct render of a colon-titled note must show links=[OK]:\n{line}"
    )
    assert rc == 0, f"the audit must not hard-fail a correct run:\n{out}"
    assert obs == [], f"no observations expected, got {obs}"


def test_audit_still_catches_a_genuinely_missing_link():
    """Negative control: the fix must not turn link coverage into a rubber
    stamp. Strip the link from a colon-titled item and the audit must still
    hard-fail — otherwise test 5 proves nothing."""
    parsed, instrs = _audit_inputs([
        _atomic(COLON_KEY, COLON_TITLE, idx=1, parents=[TRAVEL]),
    ])
    instrs["actions"] = [
        a for a in instrs["actions"] if a.get("action") != "link_to_moc"
    ]
    instrs["action_count"] = len(instrs["actions"])
    rc, _obs, out = _run_audit(parsed, instrs)
    assert rc == 1, f"a missing link_to_moc must still be caught:\n{out}"
    line = next(ln for ln in out.splitlines() if "S01" in ln)
    assert "links=[DIFF" in line, line


def test_audit_link_coverage_ok_for_two_items_one_safe_one_not():
    """Both together in one run: the live case had three siblings, and the two
    with clean titles passed only by accident of their own spelling."""
    parsed, instrs = _audit_inputs([
        _atomic(COLON_KEY, COLON_TITLE, idx=1, parents=[TRAVEL]),
        _atomic(SAFE_KEY, SAFE_TITLE, idx=2, parents=[TRAVEL]),
    ])
    rc, _obs, out = _run_audit(parsed, instrs)
    lines = [ln for ln in out.splitlines() if "S01" in ln or "S02" in ln]
    assert len(lines) == 2, lines
    for ln in lines:
        assert "links=[OK]" in ln, ln
    assert rc == 0, out


# ──────────────────────────────────────────────────────────────────────────────
# 3. The triad an internal field on a wire action owes
# ──────────────────────────────────────────────────────────────────────────────

def test_source_note_stem_never_reaches_the_wire():
    """Hashi's `link_to_moc` schema is `additionalProperties: false`; an
    unstripped internal field makes it reject every MOC link. Same lifetime as
    `new_section` and `fit_confidence`."""
    actions, _ = _build([_atomic(COLON_KEY, COLON_TITLE, idx=1, parents=[TRAVEL])])
    assert any("source_note_stem" in a for a in actions), (
        "precondition: the field must exist before the strip, or this test "
        "passes vacuously"
    )
    _strip_internal_link_fields(actions)
    leaked = [a for a in actions if "source_note_stem" in a]
    assert leaked == [], f"source_note_stem must not survive to the wire: {leaked}"


def test_stripped_actions_validate_against_hashis_schema():
    """The schema test half of the triad: the wire payload still validates."""
    from jsonschema import validate

    schema = json.loads(
        (SCHEMAS_DIR / "hashi-instructions.schema.json").read_text()
    )
    actions, _ = _build([_atomic(COLON_KEY, COLON_TITLE, idx=1, parents=[TRAVEL])])
    _strip_internal_link_fields(actions)
    validate(
        instance={
            "schema_version": "2", "type": "tomo-instructions",
            "generated": "2026-09-09T10:00:00Z", "profile": "miyo",
            "action_count": len(actions), "actions": actions,
        },
        schema=schema,
    )


def test_withholding_still_withdraws_a_colon_titled_bullet():
    """Paired-consumer half of the triad. `_orphaned_link_titles` joins on the
    sanitised stem; if it is not moved onto the new field with the emitter,
    a withheld colon-titled note keeps a bullet pointing at a path that will
    hold nothing — the dead link T5.5 exists to prevent [ref: SDD/ADR-4]."""
    pairs = [
        _atomic("100 Inbox/Notizen/Elbe.md", COLON_TITLE, idx=1, parents=[TRAVEL]),
        _atomic("100 Inbox/Reise/Elbe.md", COLON_TITLE, idx=2, parents=[TRAVEL]),
        _atomic(SAFE_KEY, SAFE_TITLE, idx=3, parents=[TRAVEL]),
    ]
    actions, _ = _build(pairs)
    kept, clashes = validate_destinations(actions)
    assert len(clashes) == 1, clashes
    surviving = [
        (a.get("source_note_title") or "", a.get("target_moc") or "")
        for a in kept if a.get("action") == "link_to_moc"
    ]
    assert surviving == [(SAFE_TITLE, TRAVEL)], (
        f"the colon-titled bullet must be withdrawn with its withheld moves, "
        f"got {surviving}"
    )
    withdrawn = clashes[0].get("withdrawn_moc_links") or []
    assert len(withdrawn) == 1, (
        f"the withdrawal must be reported to the user, got {withdrawn}"
    )
    assert withdrawn[0]["source_note_title"] == COLON_TITLE, (
        f"the report names the note the user reads, not its filename: "
        f"{withdrawn[0]}"
    )


def test_merge_survivor_clears_both_identity_fields():
    """A merged `new_section` spans several source notes, so the survivor may
    not answer to any one of them. Clearing only the title would leave the
    stem as a live join key — the withholding passes would then withdraw a
    shared bullet on one member's account."""
    def _link(action_id: str, title: str) -> dict:
        return {
            "id": action_id, "action": "link_to_moc", "target_moc": TRAVEL,
            "target_moc_path": None, "new_section": "Tschechien",
            "anchor": {"type": "callout", "value": None}, "placement": "after",
            "line_to_add": f"- [[{sanitize_stem(title)}|{title}]]",
            "source_note_title": title,
            "source_note_stem": sanitize_stem(title),
        }

    actions = [_link("I01", COLON_TITLE), _link("I02", SAFE_TITLE)]
    removed = _merge_new_section_links(actions)
    assert removed == 1, removed
    survivor = actions[0]
    assert survivor["source_note_title"] is None, survivor
    assert survivor["source_note_stem"] is None, (
        f"the stem must be cleared with the title, or it stays a live join "
        f"key on a bullet that belongs to nobody: {survivor}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# 4. The second victim of the same defect
# ──────────────────────────────────────────────────────────────────────────────

def test_a_withheld_unresolvable_link_subtracts_for_a_colon_title():
    """`_subtract_unresolvable_links` joins the withholding record's
    `source_note_title` against the item's raw title (`instructions-diff.py`
    :902). It was the same broken join as link coverage, one pass over: a
    colon-titled note whose target MOC could not be confirmed had its link
    withheld by the renderer and then counted as missing by the audit — a
    second hard-fail on a correct run, from one cause [ref: SDD/ADR-2].

    Found while tracing T6.4b's blast radius, not by the live run."""
    parsed, instrs = _audit_inputs([
        _atomic(COLON_KEY, COLON_TITLE, idx=1, parents=[TRAVEL]),
    ])
    # The renderer withheld the bullet: drop the action and record why, exactly
    # as filter_unresolvable_moc_links does (T6.0d).
    withheld = next(
        a for a in instrs["actions"] if a.get("action") == "link_to_moc"
    )
    instrs["actions"] = [a for a in instrs["actions"] if a is not withheld]
    instrs["action_count"] = len(instrs["actions"])
    instrs["tomo"] = {
        "unresolvable_moc_links": [{
            "id": withheld["id"],
            "target_moc": TRAVEL,
            "source_note_title": withheld["source_note_title"],
            "cause": "absent",
        }],
    }

    rc, _obs, out = _run_audit(parsed, instrs)
    line = next(ln for ln in out.splitlines() if "S01" in ln)
    assert "links=[OK]" in line, (
        f"a deliberately withheld link must be subtracted from the expected "
        f"tally, not reported as drift:\n{line}"
    )
    assert rc == 0, out
