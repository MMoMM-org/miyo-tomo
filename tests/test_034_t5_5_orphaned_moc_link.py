#!/usr/bin/env python3
# version: 1.0.0
"""test_034_t5_5_orphaned_moc_link.py — spec 034 T5.5.

A `link_to_moc` outlived the move it described. Both Dresden moves were
withheld by the destination guard, and the rendered document still told the
user to add `- [[Dresden]]` to `Travel (MOC)` — a bullet pointing at a path
this run had just guaranteed would hold nothing. The guard exists to stop one
note overwriting another; it was writing a dead link instead.

T5.3 shipped naming this exact risk as the assumption its diff could not
verify ("that `link_to_moc` bullets for a dropped note are harmless"), and it
is reachable from **both** withholding passes. 3596 tests and six review gates
missed it; reading the document as prose found it.

What each block below pins:

  1. Both passes withdraw the bullet with the move.
  2. The withdrawal is scoped: a note still being filed keeps its bullet.
  3. A `link_to_moc` CAN legitimately exist for a note with no `move_note` —
     a new MOC's own parent bullet, the garden-audit branch, and a surviving
     namesake that still authors a shared bullet. None of them may be lost.
  4. The report records what it withdrew, the document says so, and the
     coverage audit reconciles instead of halting the run.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import (  # noqa: E402
    build_actions,
    build_garden_audit_actions,
    suppress_moves_for_unfiled_attachments,
    validate_destinations,
)
from lib.render_md import render_instructions_md  # noqa: E402

NOTES = "Atlas/202 Notes/"
INBOX = "100 Inbox/"
ASSETS = "Atlas/290 Assets/295 Attachments/"
TRAVEL = "Travel (MOC)"

DRESDEN_PLACES = "100 Inbox/Places/Dresden.md"
DRESDEN_REISE = "100 Inbox/Reise/Dresden.md"
ROOT_NOTE = "100 Inbox/Root Note.md"
HAFEN = "100 Inbox/Bilder/Hafen.md"
ELBE = "100 Inbox/Elbe.md"

UFER_BILDER = "100 Inbox/Bilder/Ufer.jpg"
UFER_REISE = "100 Inbox/Reise/Ufer.jpg"

CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": ASSETS,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
}


class FakeKado:
    """`list_dir` only — the one call the vault half of the guard makes."""

    def __init__(self, occupied: set[str] | None = None):
        self.occupied = occupied or set()

    def list_dir(self, path: str, *, depth: int | None = None, limit: int = 500):
        prefix = path.rstrip("/") + "/"
        return [
            {"path": p, "type": "file", "modified": 1716300000000, "size": 100}
            for p in sorted(self.occupied)
            if p.startswith(prefix) and "/" not in p[len(prefix):]
        ]


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _atomic(item_key: str, title: str, *, idx: int, parents: list[str] | None = None,
            attachments: list[str] | None = None,
            location: str = NOTES) -> tuple[dict, dict]:
    """One manifest entry + its confirmed item, as instruction-render pairs them."""
    stem = item_key.rsplit("/", 1)[-1][:-3]
    manifest = {
        "action": "create_atomic_note",
        "title": title,
        "rendered_file": f"2026-09-07_10{idx:02d}_{title.lower().replace(' ', '-')}.md",
        "destination": location,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": list(parents or []),
        "tags": [],
        "attachments": list(attachments or []),
    }
    confirmed = {
        "id": f"S{idx:02d}",
        "title": title,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": list(parents or []),
        "attachments": list(attachments or []),
    }
    return manifest, confirmed


def _moc(item_key: str, title: str, *, idx: int, parents: list[str] | None = None,
         supporting: str | None = None) -> tuple[dict, dict]:
    stem = item_key.rsplit("/", 1)[-1][:-3]
    manifest = {
        "action": "create_moc",
        "title": title,
        "rendered_file": f"2026-09-07_10{idx:02d}_{title.lower().replace(' ', '-')}.md",
        "destination": "Atlas/200 Maps/",
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": list(parents or []),
        "tags": [],
        "attachments": [],
        "supporting_items": supporting,
    }
    confirmed = {
        "id": f"S{idx:02d}",
        "action": "create_moc",
        "title": title,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": list(parents or []),
        "supporting_items": supporting,
    }
    return manifest, confirmed


def _build(pairs: list[tuple[dict, dict]], **kw) -> tuple[list[dict], list[dict]]:
    return build_actions(
        [m for m, _ in pairs], [c for _, c in pairs],
        kw.pop("daily_updates", []), kw.pop("skipped", []),
        CFG, kado_client=None,
    )


def _links(actions: list[dict]) -> list[tuple[str, str]]:
    return [
        (a.get("source_note_title") or "", a.get("target_moc") or "")
        for a in actions if a.get("action") == "link_to_moc"
    ]


def _render(actions, clashes=None, suppressions=None, **kw) -> str:
    return render_instructions_md(
        actions,
        {
            "run_id": "t5-5",
            "generated": "2026-09-07T14:04:49Z",
            "profile": "miyo",
            "sources": [{"path": "100 Inbox/_suggestions.md"}],
            "destination_clashes": clashes or [],
            "attachment_suppressions": suppressions or [],
            **kw,
        },
        CFG,
    )


TWO_NAMESAKES_UNDER_ONE_MOC = [
    _atomic(DRESDEN_PLACES, "Dresden", idx=1, parents=[TRAVEL]),
    _atomic(DRESDEN_REISE, "Dresden", idx=2, parents=[TRAVEL]),
    _atomic(ROOT_NOTE, "Root note takeaway", idx=3, parents=[TRAVEL]),
]


# ---------------------------------------------------------------------------
# 1. A link_to_moc may not outlive the move it describes
# ---------------------------------------------------------------------------

def test_a_destination_clash_withdraws_the_moc_link_for_the_unfiled_note():
    actions, _ = _build(TWO_NAMESAKES_UNDER_ONE_MOC)
    kept, clashes = validate_destinations(actions)
    assert len(clashes) == 1, clashes
    assert _links(kept) == [("Root note takeaway", TRAVEL)], (
        "no note will exist at Atlas/202 Notes/Dresden.md, so a bullet "
        f"pointing there is a link to nothing: {_links(kept)}"
    )


def test_an_unfiled_attachment_withdraws_the_moc_link_for_its_note():
    pairs = [
        _atomic(HAFEN, "Hafen at dusk", idx=1, parents=[TRAVEL],
                attachments=[UFER_BILDER]),
        _atomic("100 Inbox/Reise/Steg.md", "Steg", idx=2, parents=[TRAVEL],
                attachments=[UFER_REISE]),
    ]
    actions, skipped_assets = _build(pairs)
    kept, suppressions = suppress_moves_for_unfiled_attachments(
        actions, skipped_assets
    )
    assert len(suppressions) == 1, suppressions
    # First claim on the shared destination wins, so `Steg` is the note whose
    # attachment was refused and whose move is therefore withheld.
    assert [d["title"] for d in suppressions[0]["dropped"]] == ["Steg"], suppressions
    assert _links(kept) == [("Hafen at dusk", TRAVEL)], (
        "the attachment guard withholds the note's move for the same reason "
        f"the clash guard does; its MOC link is orphaned too: {_links(kept)}"
    )


def test_a_moc_link_whose_note_is_still_filed_survives_the_clash():
    pairs = [
        _atomic(DRESDEN_PLACES, "Dresden", idx=1, parents=[TRAVEL]),
        _atomic(DRESDEN_REISE, "Dresden", idx=2, parents=[TRAVEL]),
        _atomic(ROOT_NOTE, "Root note takeaway", idx=3, parents=[TRAVEL]),
        _atomic(ELBE, "Elbe", idx=4, parents=[TRAVEL]),
    ]
    kept, _clashes = validate_destinations(_build(pairs)[0])
    assert ("Elbe", TRAVEL) in _links(kept), (
        "withdrawal must be scoped to the notes actually withheld"
    )
    assert ("Root note takeaway", TRAVEL) in _links(kept)


def test_a_new_mocs_own_parent_link_is_not_withdrawn_with_a_clashing_note():
    """A `create_moc` has no `move_note`, so "no move" cannot mean "orphaned"."""
    pairs = [
        _atomic(DRESDEN_PLACES, "Dresden", idx=1, parents=[TRAVEL]),
        _atomic(DRESDEN_REISE, "Dresden", idx=2, parents=[TRAVEL]),
        _moc("100 Inbox/Rivers.md", "Rivers (MOC)", idx=3, parents=[TRAVEL]),
    ]
    kept, _clashes = validate_destinations(_build(pairs)[0])
    assert ("Rivers (MOC)", TRAVEL) in _links(kept), (
        "the new MOC is still created; blanket withdrawal would strip a link "
        f"to a note that does exist: {_links(kept)}"
    )


def test_a_surviving_namesake_keeps_the_link_the_dropped_one_shared():
    """`_emit` dedups by (target MOC, title), so one bullet can have two authors.

    A create_moc titled `Dresden` survives the clash between two atomic notes
    of the same name and is the sole remaining author of `- [[Dresden]]`.
    """
    pairs = [
        _atomic(DRESDEN_PLACES, "Dresden", idx=1, parents=[TRAVEL]),
        _atomic(DRESDEN_REISE, "Dresden", idx=2, parents=[TRAVEL]),
        _moc("100 Inbox/Dresden Map.md", "Dresden", idx=3, parents=[TRAVEL]),
    ]
    kept, _clashes = validate_destinations(_build(pairs)[0])
    assert ("Dresden", TRAVEL) in _links(kept), (
        "the surviving create_moc still needs its bullet on Travel (MOC)"
    )


def test_a_garden_audit_link_has_no_move_and_is_never_withdrawn():
    confirmed = [{
        "garden_action": "file_note",
        "path": "Atlas/202 Notes/Dresden.md",
        "stem": "Dresden",
        "target_moc": TRAVEL,
        "target_moc_path": f"Atlas/200 Maps/{TRAVEL}.md",
    }]
    actions = build_garden_audit_actions(confirmed)
    kept, clashes = validate_destinations(actions)
    assert clashes == [], "the garden branch emits no move_note"
    assert _links(kept) == [("Dresden", TRAVEL)], _links(kept)


def test_the_clash_report_records_the_moc_links_it_withdrew():
    _kept, clashes = validate_destinations(_build(TWO_NAMESAKES_UNDER_ONE_MOC)[0])
    assert clashes[0]["withdrawn_moc_links"] == [
        {"source_note_title": "Dresden", "target_moc": TRAVEL}
    ], clashes[0]


def test_the_not_filed_section_says_the_moc_link_went_with_the_move():
    actions, _ = _build(TWO_NAMESAKES_UNDER_ONE_MOC)
    kept, clashes = validate_destinations(actions)
    md = _render(kept, clashes=clashes)
    assert "withdrawn with it" in md, (
        "the user approved that bullet in Pass 1; its disappearance from the "
        f"action list must be stated, not silent:\n{md}"
    )


def test_the_withdrawal_reconciles_with_the_coverage_audit(capsys):
    """The audit derives expected links from the suggestions doc, so a
    withdrawn link must be subtracted or the guard reads as drift."""
    confirmed = [c for _, c in TWO_NAMESAKES_UNDER_ONE_MOC]
    actions, skipped_assets = _build(TWO_NAMESAKES_UNDER_ONE_MOC)
    kept, clashes = validate_destinations(actions)
    kept, suppressions = suppress_moves_for_unfiled_attachments(
        kept, skipped_assets
    )
    instrs = {
        "actions": kept,
        "action_count": len(kept),
        "tomo": {
            "destination_clashes": clashes,
            "attachment_suppressions": suppressions,
            "skipped_assets": [],
        },
    }
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    rc, observations = _load("instructions_diff_t5_5", "instructions-diff.py").run_diff(
        parsed, instrs
    )
    capsys.readouterr()
    assert rc == 0, (
        "a deliberate withdrawal must not stop the conductor and blame Tomo "
        f"for its own guard: {observations}"
    )
