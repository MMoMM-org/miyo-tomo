#!/usr/bin/env python3
# version: 0.2.0
"""test_034_t5_4_attachment_clash_suppression.py — spec 034 T5.4.

PRD Feature 8 / ADR-6. Two different files sharing a basename cannot both be
filed into the flat asset folder. The attachment guard skips the second one —
and until now filed its note anyway, leaving a note in the permanent collection
whose embed points at a file still sitting in the inbox. Nothing rescues that
afterwards: moving a note does not carry its attachments, and nothing is ever
moved that was not instructed.

This **reverses spec 031** (`plan/phase-2.md:85`,
`tests/test_031_t2_4_destination_collision_guard.py:121`). That decision was
right while a flat inbox made the clash unreachable; recursion made it
reachable.

What each block pins:

  1. The second file is not filed **and neither is its note**; the first note
     and its attachment are filed normally — one clash does not hold up another.
  2. One file embedded by two notes is a duplicate reference, not a clash: it
     is filed once, both notes move, and the whole action list equals the
     baseline recorded at `1edaccd` before any of this code existed.
  3. A suppressed move takes its paired `delete_source` with it — the origin's
     and the audio peer's. The note stays in the inbox, so deleting its source
     would destroy the note the suppression exists to protect. A `keep_source`
     item has no paired delete and must report none.
  4. The join is on `item_key`, through `resolve_source_path` — the same helper
     `_build_move_note_actions` derives `source_inbox_item` with. Asserted on
     subfolder notes, where an inbox-root composition matches nothing, and
     against a root-level namesake that must not be suppressed.
  5. Statelessness: rename one file, re-run, everything files. Nothing carries
     between invocations.
  6. The two post-passes compose. A note can clash on its destination AND own a
     skipped attachment; neither report may double-count it.
  7. The user can tell the two reasons apart — "two items claim one
     destination" is fixed by renaming a note, "its attachment could not be
     filed" by renaming a file.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
GOLDEN_DIR = TESTS_DIR / "fixtures" / "034-t5-4-duplicate-reference-golden"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import (  # noqa: E402
    build_actions,
    suppress_moves_for_unfiled_attachments,
    validate_destinations,
)
from lib.render_md import render_instructions_md  # noqa: E402

NOTES = "Atlas/202 Notes/"
INBOX = "100 Inbox/"
ASSETS = "Atlas/290 Assets/295 Attachments/"

DRESDEN_PLACES = "100 Inbox/Places/Dresden.md"
ELBE_REISE = "100 Inbox/Reise/Elbe.md"
ROOT_NOTE = "100 Inbox/Root Note.md"

UFER_PLACES = "100 Inbox/Places/Ufer.jpg"
UFER_REISE = "100 Inbox/Reise/Ufer.jpg"

CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": ASSETS,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
}


# ---------------------------------------------------------------------------
# Fixtures and builders
# ---------------------------------------------------------------------------

def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _atomic(item_key: str, title: str, *, idx: int, attachments: list[str] | None = None,
            audio_peer: str | None = None, keep_source: bool = False,
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
        "parent_mocs": [],
        "tags": [],
        "attachments": list(attachments or []),
    }
    if audio_peer:
        manifest["audio_peer"] = audio_peer
    confirmed = {
        "id": f"S{idx:02d}",
        "title": title,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": [],
        # The parser puts attachments and audio_peer on the confirmed item
        # too (suggestion-parser.py:348/2216); instructions-diff derives the
        # expected move_asset and audio-peer delete counts from there, so a
        # fixture that omits them would test the audit against a shape the
        # parser never produces.
        "attachments": list(attachments or []),
    }
    if audio_peer:
        confirmed["audio_peer"] = audio_peer
    if keep_source:
        confirmed["keep_source"] = True
    return manifest, confirmed


def _build(pairs: list[tuple[dict, dict]], **kw) -> tuple[list[dict], list[dict]]:
    return build_actions(
        [m for m, _ in pairs], [c for _, c in pairs],
        kw.pop("daily_updates", []), kw.pop("skipped", []),
        CFG, kado_client=None,
    )


def _suppressed(pairs: list[tuple[dict, dict]], **kw):
    actions, skipped_assets = _build(pairs, **kw)
    return suppress_moves_for_unfiled_attachments(actions, skipped_assets)


def _moves(actions: list[dict]) -> list[dict]:
    return [a for a in actions if a.get("action") == "move_note"]


def _assets(actions: list[dict]) -> list[str]:
    return [a["source"] for a in actions if a.get("action") == "move_asset"]


def _deletes(actions: list[dict]) -> list[str]:
    return [a["source_path"] for a in actions if a.get("action") == "delete_source"]


# Two files sharing the basename `Ufer.jpg`, each embedded by its own note, in
# two different inbox subfolders. Both notes sit in subfolders on purpose: an
# inbox-root reconstruction of either path matches nothing, so a broken join
# and a correct one cannot look alike here.
CLASHING_PAIR = [
    _atomic(DRESDEN_PLACES, "Dresden", idx=1, attachments=[UFER_PLACES]),
    _atomic(ELBE_REISE, "Elbe", idx=2, attachments=[UFER_REISE],
            audio_peer="100 Inbox/Reise/Elbe.m4a"),
    _atomic(ROOT_NOTE, "Root note takeaway", idx=3),
]

# The same run after the user renames the second file.
RENAMED_PAIR = [
    _atomic(DRESDEN_PLACES, "Dresden", idx=1, attachments=[UFER_PLACES]),
    _atomic(ELBE_REISE, "Elbe", idx=2, attachments=["100 Inbox/Reise/Elbufer.jpg"],
            audio_peer="100 Inbox/Reise/Elbe.m4a"),
    _atomic(ROOT_NOTE, "Root note takeaway", idx=3),
]


# ---------------------------------------------------------------------------
# 1. The clash keeps its note in the inbox — and only its note
# ---------------------------------------------------------------------------

def test_the_unfiled_attachments_note_does_not_move():
    kept, suppressions = _suppressed(CLASHING_PAIR)
    titles = [m["title"] for m in _moves(kept)]
    assert "Elbe" not in titles, (
        "Elbe's attachment was left in the inbox; filing Elbe anyway leaves a "
        f"permanent-collection note depending on an inbox file: {titles}"
    )
    assert len(suppressions) == 1, suppressions
    assert [d["title"] for d in suppressions[0]["dropped"]] == ["Elbe"]
    assert suppressions[0]["attachment"] == UFER_REISE


def test_the_first_note_and_its_attachment_are_filed_normally():
    """One note's clash does not hold up another `[ref: PRD/AC Feature 8]`."""
    kept, _suppressions = _suppressed(CLASHING_PAIR)
    titles = sorted(m["title"] for m in _moves(kept))
    assert titles == ["Dresden", "Root note takeaway"], titles
    assert _assets(kept) == [UFER_PLACES], (
        "first claim wins on the attachment itself — only the note whose "
        f"attachment was refused stays behind: {_assets(kept)}"
    )


def test_an_unrelated_note_keeps_its_move_and_its_delete():
    kept, _suppressions = _suppressed(CLASHING_PAIR)
    assert ROOT_NOTE in _deletes(kept)
    assert DRESDEN_PLACES in _deletes(kept)


# ---------------------------------------------------------------------------
# 2. The duplicate-reference path is provably untouched
# ---------------------------------------------------------------------------

def _golden() -> dict:
    return json.loads((GOLDEN_DIR / "actions.json").read_text(encoding="utf-8"))


def _golden_actions() -> tuple[list[dict], list[dict]]:
    data = json.loads((GOLDEN_DIR / "input.json").read_text(encoding="utf-8"))
    return build_actions(
        data["manifest"], data["confirmed"], data["daily_updates"],
        data["skipped"], data["cfg"], kado_client=None,
    )


def test_build_actions_still_emits_the_recorded_duplicate_reference_baseline():
    """The baseline was recorded at 1edaccd, before any T5.4 code existed."""
    actions, skipped_assets = _golden_actions()
    assert actions == _golden()["actions"]
    assert skipped_assets == _golden()["skipped_assets"] == []


def test_the_suppression_pass_is_a_no_op_on_a_duplicate_reference():
    actions, skipped_assets = _golden_actions()
    kept, suppressions = suppress_moves_for_unfiled_attachments(
        actions, skipped_assets
    )
    assert suppressions == [], (
        "one file embedded by two notes is a duplicate reference, not a "
        f"clash — both notes must move: {suppressions}"
    )
    assert kept == _golden()["actions"], (
        "whole-list comparison, not selected fields — a pass that quietly "
        "reorders or rewrites an untouched run is a regression"
    )


# ---------------------------------------------------------------------------
# 3. A suppressed move withdraws its paired delete_source
# ---------------------------------------------------------------------------

def test_the_suppressed_notes_origin_delete_is_withdrawn():
    kept, suppressions = _suppressed(CLASHING_PAIR)
    assert ELBE_REISE not in _deletes(kept), (
        "the note stays in the inbox — deleting its source destroys it "
        "outright, which is strictly worse than filing it incompletely"
    )
    assert ELBE_REISE in suppressions[0]["withdrawn_deletes"]


def test_the_suppressed_notes_audio_peer_delete_is_withdrawn_too():
    kept, suppressions = _suppressed(CLASHING_PAIR)
    assert "100 Inbox/Reise/Elbe.m4a" not in _deletes(kept), (
        "the audio peer's delete is paired with the same move; leaving it "
        "deletes the recording of a note that never moved"
    )
    assert "100 Inbox/Reise/Elbe.m4a" in suppressions[0]["withdrawn_deletes"]


def test_a_keep_source_item_reports_no_phantom_withdrawal():
    """`keep_source` means no delete was ever emitted, so none was withdrawn."""
    pairs = [
        _atomic(DRESDEN_PLACES, "Dresden", idx=1, attachments=[UFER_PLACES]),
        _atomic(ELBE_REISE, "Elbe", idx=2, attachments=[UFER_REISE],
                keep_source=True),
    ]
    kept, suppressions = _suppressed(pairs)
    assert ELBE_REISE not in _deletes(kept)
    assert suppressions[0]["withdrawn_deletes"] == [], (
        "reporting a withdrawal that never happened makes both the document "
        f"and the coverage audit claim a delete existed: {suppressions[0]}"
    )


# ---------------------------------------------------------------------------
# 4. The join is on item_key, not on the stem or the inbox root
# ---------------------------------------------------------------------------

def test_a_namesake_at_the_inbox_root_keeps_its_move():
    """Two notes with the stem `Elbe`; only the subfolder one owns the clash.

    A stem-keyed link, or a path composed as `<inbox>/<stem>.md`, suppresses
    the root note instead of — or as well as — the real owner. That is the
    defect this spec has spent six tasks removing.
    """
    pairs = [
        _atomic(DRESDEN_PLACES, "Dresden", idx=1, attachments=[UFER_PLACES]),
        _atomic(ELBE_REISE, "Elbe Ufer", idx=2, attachments=[UFER_REISE]),
        _atomic("100 Inbox/Elbe.md", "Elbe Quelle", idx=3),
    ]
    kept, suppressions = _suppressed(pairs)
    titles = sorted(m["title"] for m in _moves(kept))
    assert titles == ["Dresden", "Elbe Quelle"], (
        "the root-level namesake owns no unfiled attachment and must move; "
        f"only the subfolder note that does stays behind: {titles}"
    )
    assert [d["source_inbox_item"] for d in suppressions[0]["dropped"]] == [
        ELBE_REISE,
    ]
    assert "100 Inbox/Elbe.md" in _deletes(kept)


def test_a_second_note_referencing_the_same_refused_file_also_stays():
    """Two notes can embed the one path that was refused; both must stay.

    The global `seen` dedup means the path is examined once, so a link that
    records only the first note that mentioned it leaves the second note filed
    with an embed pointing into the inbox — the exact residue ADR-6 forbids.
    """
    pairs = [
        _atomic(DRESDEN_PLACES, "Dresden", idx=1, attachments=[UFER_PLACES]),
        _atomic(ELBE_REISE, "Elbe", idx=2, attachments=[UFER_REISE]),
        _atomic("100 Inbox/Reise/Fahrt.md", "Fahrt", idx=3,
                attachments=[UFER_REISE]),
    ]
    kept, suppressions = _suppressed(pairs)
    titles = sorted(m["title"] for m in _moves(kept))
    assert titles == ["Dresden"], (
        f"both notes embedding the refused file must stay behind: {titles}"
    )
    dropped = sorted(d["source_inbox_item"] for d in suppressions[0]["dropped"])
    assert dropped == [ELBE_REISE, "100 Inbox/Reise/Fahrt.md"], dropped


def test_an_attachment_with_no_filename_also_keeps_its_note():
    """`no_basename` is an attachment that could not be filed either.

    Its remedy differs — inspect the inbox path rather than rename a file —
    but the residue is identical, so the note stays with it.
    """
    pairs = [
        _atomic(ELBE_REISE, "Elbe", idx=2, attachments=["100 Inbox/Reise/"]),
    ]
    kept, suppressions = _suppressed(pairs)
    assert _moves(kept) == [], f"{_moves(kept)}"
    assert suppressions[0]["kind"] == "no_basename"


# ---------------------------------------------------------------------------
# 5. Statelessness — rename one file, re-run, everything files
# ---------------------------------------------------------------------------

def test_renaming_one_file_files_everything_on_the_next_invocation():
    _clashing, suppressions = _suppressed(CLASHING_PAIR)
    assert suppressions, "precondition: the first invocation suppressed a move"

    kept, second = _suppressed(RENAMED_PAIR)
    assert second == [], (
        "nothing may outlive the input that caused it — no memo of the "
        f"earlier clash: {second}"
    )
    assert sorted(m["title"] for m in _moves(kept)) == [
        "Dresden", "Elbe", "Root note takeaway",
    ]
    assert sorted(_assets(kept)) == [UFER_PLACES, "100 Inbox/Reise/Elbufer.jpg"]
    assert ELBE_REISE in _deletes(kept)


def test_the_clean_invocation_does_not_prime_the_next_one():
    """The reverse order — a clean run must not immunise a later clash."""
    _kept, first = _suppressed(RENAMED_PAIR)
    assert first == []
    _kept2, second = _suppressed(CLASHING_PAIR)
    assert len(second) == 1, second


# ---------------------------------------------------------------------------
# 6. The two post-passes compose
# ---------------------------------------------------------------------------

def _both_passes(pairs, **kw):
    actions, skipped_assets = _build(pairs, **kw)
    kept, clashes = validate_destinations(actions)
    kept, suppressions = suppress_moves_for_unfiled_attachments(
        kept, skipped_assets
    )
    return kept, clashes, suppressions


# `Elbe` in two folders: both claim `Atlas/202 Notes/Elbe.md`, and the second
# also owns an attachment that cannot be filed. Both passes apply to it.
BOTH_CAUSES = [
    _atomic(DRESDEN_PLACES, "Dresden", idx=1, attachments=[UFER_PLACES]),
    _atomic("100 Inbox/Wasser/Elbe.md", "Elbe", idx=2),
    _atomic(ELBE_REISE, "Elbe", idx=3, attachments=[UFER_REISE],
            audio_peer="100 Inbox/Reise/Elbe.m4a"),
]


# Three causes in one run, so that BOTH reports are non-empty and their
# disjointness is a claim that can actually be violated:
#   - `Ufer.jpg` under `Bilder/` and `Reise/` both lose to `Places/Ufer.jpg`;
#   - `Elbe` in two folders claim one destination, and one of those two ALSO
#     owns a refused attachment — the note both passes could report.
# A fixture where the only attachment-owning note is also the clashing one
# leaves `suppression_withdrawals` empty by construction, and an intersection
# against the empty set holds however the withdrawal logic behaves.
MIXED_CAUSES = [
    _atomic(ROOT_NOTE, "Root note takeaway", idx=1, attachments=[UFER_PLACES]),
    _atomic("100 Inbox/Wasser/Elbe.md", "Elbe", idx=2),
    _atomic(ELBE_REISE, "Elbe", idx=3, attachments=[UFER_REISE],
            audio_peer="100 Inbox/Reise/Elbe.m4a"),
    _atomic("100 Inbox/Bilder/Fahrt.md", "Fahrt", idx=4,
            attachments=["100 Inbox/Bilder/Ufer.jpg"]),
]


def test_a_move_already_dropped_by_the_clash_guard_is_a_no_op_here():
    kept, clashes, suppressions = _both_passes(BOTH_CAUSES)
    assert len(clashes) == 1 and len(clashes[0]["dropped"]) == 2
    assert [m["title"] for m in _moves(kept)] == ["Dresden"]
    withheld = (
        sum(len(c["dropped"]) for c in clashes)
        + sum(len(s["dropped"]) for s in suppressions)
    )
    assert withheld == 2, (
        "two moves were withheld, both by the destination guard; a second "
        f"report of either tells the user three notes stayed behind: "
        f"clashes={clashes} suppressions={suppressions}"
    )
    assert suppressions == [], (
        "the attachment pass withheld nothing of its own here — an entry "
        "with an empty `dropped` list still renders a section heading the "
        f"user has to read past: {suppressions}"
    )


def test_neither_report_counts_the_same_withdrawn_delete_twice():
    _kept, clashes, suppressions = _both_passes(MIXED_CAUSES)
    clash_withdrawals = [p for c in clashes for p in c["withdrawn_deletes"]]
    suppression_withdrawals = [
        p for s in suppressions for p in s["withdrawn_deletes"]
    ]
    # Both sides must have something to overlap, or the intersection below is
    # true by construction and pins nothing.
    assert sorted(clash_withdrawals) == [
        "100 Inbox/Reise/Elbe.m4a", ELBE_REISE, "100 Inbox/Wasser/Elbe.md",
    ], clash_withdrawals
    assert suppression_withdrawals == ["100 Inbox/Bilder/Fahrt.md"], (
        suppression_withdrawals
    )

    overlap = set(clash_withdrawals) & set(suppression_withdrawals)
    assert overlap == set(), (
        "one delete can only be withdrawn once; counted twice, the audit "
        f"subtracts it twice and reports drift on a correct set: {overlap}"
    )


def test_the_composed_run_still_files_the_untouched_note():
    kept, _clashes, _suppressions = _both_passes(BOTH_CAUSES)
    assert [m["title"] for m in _moves(kept)] == ["Dresden"]
    assert _assets(kept) == [UFER_PLACES]


def _drive_render(monkeypatch, tmp_path, pairs) -> Path:
    """Drive the real `instruction-render.main()` over `pairs`.

    The two post-passes compose only because `instruction-render.py` calls
    them in that order, and nothing in the module enforces it. Every other
    test in this file hardcodes the order in its own helper, so none of them
    would notice a reordering. This one reads the order out of the source
    under test instead of restating it.
    """
    from unittest.mock import MagicMock

    ir = _load("instruction_render_t5_4", "instruction-render.py")
    built = _build(pairs)
    suggestions_file = tmp_path / "suggestions.json"
    suggestions_file.write_text(json.dumps({
        "confirmed_items": [{
            "id": "S01", "action": None, "title": "placeholder",
            "source_path": "", "tags": [], "parent_mocs": [], "candidate_mocs": [],
        }],
        "daily_updates": [], "skipped": [],
    }), encoding="utf-8")
    cfg_file = tmp_path / "vault-config.yaml"
    cfg_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(ir, "load_config", lambda _p: {
        "concepts.inbox": INBOX, "profile": "miyo", "callouts.editable": ["NOTE"],
    })
    monkeypatch.setattr(ir, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(
        ir, "build_actions",
        lambda *_a, **_kw: ([dict(a) for a in built[0]], [dict(s) for s in built[1]]),
    )
    monkeypatch.setattr(ir, "resolve_target_moc_paths", lambda _a, _c: 0)
    monkeypatch.setattr(ir, "resolve_section_names", lambda *_a, **_kw: 0)
    monkeypatch.setattr(ir, "_validate_action_paths", lambda _a: [])

    out_dir = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "instruction-render.py", "--suggestions", str(suggestions_file),
        "--output-dir", str(out_dir), "--config", str(cfg_file),
    ])
    assert isinstance(ir.main(), int)
    return out_dir


def test_the_clash_guard_still_sees_both_claimants_in_the_real_call_order():
    """Order-sensitive, and asserted through the module that fixes the order.

    `Reise/Elbe` owns a refused attachment AND contests `Elbe.md` with
    `Wasser/Elbe`. Suppressing it first would leave `Wasser/Elbe` the sole
    claimant, so the destination guard would find no clash and file it — into
    the path the other note was contesting, which is the overwrite ADR-4
    exists to stop. The destination guard must therefore run first.
    """
    kept, clashes, suppressions = _both_passes(MIXED_CAUSES)
    assert len(clashes[0]["dropped"]) == 2, (
        "both Elbe claimants must be dropped; one surviving means the clash "
        f"was evaluated after a claimant had already been removed: {clashes}"
    )
    assert [m["title"] for m in _moves(kept)] == ["Root note takeaway"]
    assert [s["attachment"] for s in suppressions] == ["100 Inbox/Bilder/Ufer.jpg"]


def test_the_real_render_stage_composes_the_two_passes_in_that_order(
    monkeypatch, tmp_path
):
    out_dir = _drive_render(monkeypatch, tmp_path, MIXED_CAUSES)
    doc = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))
    tomo = doc["tomo"]

    moves = [a["title"] for a in doc["actions"] if a["action"] == "move_note"]
    assert moves == ["Root note takeaway"], (
        "with the passes reversed, `Wasser/Elbe` becomes the sole claimant "
        f"and is filed into the path `Reise/Elbe` was contesting: {moves}"
    )
    assert len(tomo["destination_clashes"][0]["dropped"]) == 2
    assert [s["attachment"] for s in tomo["attachment_suppressions"]] == [
        "100 Inbox/Bilder/Ufer.jpg",
    ]
    clash_withdrawals = {
        p for c in tomo["destination_clashes"] for p in c["withdrawn_deletes"]
    }
    suppression_withdrawals = {
        p for s in tomo["attachment_suppressions"] for p in s["withdrawn_deletes"]
    }
    assert clash_withdrawals & suppression_withdrawals == set()
    deletes = {a["source_path"] for a in doc["actions"]
               if a["action"] == "delete_source"}
    assert deletes == {ROOT_NOTE}, (
        "every withheld note keeps its source; only the filed note's origin "
        f"is deleted: {deletes}"
    )


# ---------------------------------------------------------------------------
# 7. The user can tell the two reasons apart
# ---------------------------------------------------------------------------

def _render(kept, clashes, suppressions, skipped_assets=None) -> str:
    return render_instructions_md(
        kept,
        {
            "generated": "2026-09-07T10:00:00+02:00",
            "destination_clashes": clashes,
            "attachment_suppressions": suppressions,
            "skipped_assets": skipped_assets or [],
        },
        CFG,
    )


def test_the_document_names_the_note_and_the_file_that_held_it_back():
    kept, suppressions = _suppressed(CLASHING_PAIR)
    md = _render(kept, [], suppressions)
    assert ELBE_REISE in md, md
    assert UFER_REISE in md, "the user must be told which file to rename"
    assert "re-run" in md, "the user must be told the halt is recoverable"


def _section_of(md: str, needle: str) -> tuple[str, str]:
    """The `## ` heading and body of the section that first mentions `needle`."""
    heading = ""
    body: list[str] = []
    for line in md.splitlines():
        if line.startswith("## "):
            if any(needle in ln for ln in body):
                return heading, "\n".join(body)
            heading, body = line, []
            continue
        body.append(line)
    assert any(needle in ln for ln in body), f"{needle!r} appears nowhere:\n{md}"
    return heading, "\n".join(body)


def test_the_two_reasons_are_distinguishable_in_one_document():
    """Rename a note, versus rename a file — different remedies, so the
    reader must be able to tell which happened to which note.

    Both withholdings are in one document: two `Dresden` notes claim one
    destination, and `Elbe`'s attachment could not be filed.
    """
    pairs = CLASHING_PAIR + [_atomic("100 Inbox/Wasser/Dresden.md", "Dresden", idx=4)]
    kept, clashes, suppressions = _both_passes(pairs)
    assert clashes and suppressions, (clashes, suppressions)
    md = _render(kept, clashes, suppressions)

    clash_head, clash_body = _section_of(md, DRESDEN_PLACES)
    attach_head, attach_body = _section_of(md, ELBE_REISE)
    assert clash_head != attach_head, (
        "one heading over both withholdings tells the reader nothing about "
        f"which remedy applies to which note:\n{md}"
    )
    assert clash_head == "## Not filed — a destination is claimed twice", clash_head
    assert "attachment" in attach_head.lower(), attach_head

    assert UFER_REISE in attach_body, (
        f"the attachment section must name the file to rename:\n{attach_body}"
    )
    assert UFER_REISE not in clash_body, (
        "the clash section is resolved by renaming a NOTE; naming the file "
        f"there points the reader at the wrong remedy:\n{clash_body}"
    )
    assert ELBE_REISE not in clash_body and DRESDEN_PLACES not in attach_body, (
        "each withheld note belongs to exactly one section"
    )


def test_the_intro_does_not_prescribe_a_remedy_the_kind_does_not_have():
    """A `no_basename` skip has no second file to rename.

    Same defect class as T5.3's heading, which counted two claimants above a
    vault collision that had one: under CON-2 the user approves on what the
    document says, so an intro that is false for one of the kinds it covers is
    a wrong basis for approval even when the withholding is right.
    """
    pairs = [_atomic(ELBE_REISE, "Elbe", idx=2, attachments=["100 Inbox/Reise/"])]
    kept, suppressions = _suppressed(pairs)
    md = _render(kept, [], suppressions)
    _head, body = _section_of(md, ELBE_REISE)
    intro = body.strip().splitlines()[0]
    assert "rename" not in intro.lower(), (
        f"nothing here can be renamed — the bullet carries the remedy: {intro}"
    )
    assert "no filename" in body, body


def test_a_clean_run_renders_no_suppression_block():
    actions, skipped_assets = _golden_actions()
    kept, suppressions = suppress_moves_for_unfiled_attachments(
        actions, skipped_assets
    )
    md = _render(kept, [], suppressions)
    assert "could not be filed" not in md, md


def test_the_skipped_attachment_report_is_unchanged_by_the_new_link():
    """`skipped_assets` is rendered for the user today; the field the join
    needs must not leak into that output (`test_031_t2_skipped_assets…`)."""
    _actions, skipped_assets = _build(CLASHING_PAIR)
    md = _render([], [], [], skipped_assets=skipped_assets)
    bullets = [ln for ln in md.splitlines() if ln.startswith("- `move_asset`")]
    assert len(bullets) == 1, bullets
    assert bullets[0] == (
        f"- `move_asset` → `{UFER_REISE}` — destination collision: "
        f"'{UFER_REISE}' also resolves to '{ASSETS}Ufer.jpg', already claimed "
        f"by '{UFER_PLACES}'. rename one of the two files so they no longer "
        f"share `{ASSETS}Ufer.jpg`, then re-run `/inbox`."
    ), bullets[0]


# ---------------------------------------------------------------------------
# 8. The report survives the whole render stage, and the paired consumer
# ---------------------------------------------------------------------------

def _diff_module():
    return _load("instructions_diff_t5_4", "instructions-diff.py")


def _diff(pairs, **kw) -> tuple[int, list[str]]:
    """Run the real audit over the emitter's own output for the same input."""
    confirmed = [c for _, c in pairs]
    actions, skipped_assets = _build(pairs, **kw)
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
            # Projected exactly as instruction-render.py writes it — the
            # audit reads this block, so a fixture that omits it would test
            # the audit against a document Tomo never produces.
            "skipped_assets": [
                {
                    "source": s.get("source"),
                    "destination": s.get("destination"),
                    "reason": s.get("reason"),
                }
                for s in skipped_assets
            ],
        },
    }
    parsed = {
        "confirmed_items": confirmed,
        "daily_updates": kw.get("daily_updates") or [],
        "skipped": kw.get("skipped") or [],
    }
    return _diff_module().run_diff(parsed, instrs)


def test_a_suppressed_move_reconciles_instead_of_reporting_drift(capsys):
    rc, observations = _diff(CLASHING_PAIR)
    capsys.readouterr()
    assert rc == 0, (
        "the pass withheld a move and its deletes deliberately; a FAIL here "
        "stops the conductor and blames Tomo for its own guard"
    )
    assert any("attachment" in o for o in observations), observations


def test_the_audit_note_distinguishes_the_two_withholdings(capsys):
    pairs = CLASHING_PAIR + [_atomic("100 Inbox/Wasser/Dresden.md", "Dresden", idx=4)]
    rc, observations = _diff(pairs)
    capsys.readouterr()
    assert rc == 0, observations
    assert any("claimed twice" in o for o in observations), observations
    assert any("attachment" in o for o in observations), observations
