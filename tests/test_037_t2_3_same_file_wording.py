#!/usr/bin/env python3
# version: 0.1.0
"""test_037_t2_3_same_file_wording.py — spec 037 T2.3.

`render_attachment_conflicts_block` (spec 037 T2.2) gains one sentence per
conflict entry, keyed on `same_file` (T1.3, PRD S1): same file / different
file / could not be compared. The sentence lands beside the tick logic that
decides which remedy is pre-checked, but it is a SEPARATE conditional on a
SEPARATE field — it changes no remedy and no default (SDD/Complex Logic).
This file pins that wording and its independence, per the T2.3 deviation
block in `docs/XDD/specs/037-asset-destination-collision-is-a-pass1-decision/
plan/phase-2.md`.

Every bullet below names the mutation it kills:

  1. `test_same_file_true_renders_second_copy_warning` — mutation: emit only
     one of the two clauses (the "same file" statement or the second-copy
     warning), not both `[ref: PRD/S1-AC1]`.
  2. `test_same_file_false_renders_different_file_statement` — mutation: swap
     in the `true`-branch wording `[ref: PRD/S1-AC2]`.
  3. `test_same_file_null_renders_could_not_compare` — mutation: fall through
     silently, emitting no sentence `[ref: PRD/S1-AC3]`.
  4. `test_remedies_unchanged_from_t2_2_baseline` — the three checkbox lines,
     hardcoded from T2.2's own fixture (`test_037_t2_2_render_conflicts.py`'s
     `test_exactly_three_remedies_with_rename_ticked` /
     `test_rename_remedy_names_fully_composed_destination`), must be
     byte-identical regardless of `same_file`. Mutation: any change to the
     checkbox lines when a `same_file` sentence is added.
  5. `test_same_file_true_still_ships_rename_ticked` — mutation: untick
     rename, or pre-tick keep-in-inbox, when the file is identical
     `[ref: SDD/Complex Logic]`. The bullet most likely to be "helpfully"
     broken, per the task text — the new sentence lands physically beside
     the tick logic.
  6. `test_same_file_true_and_no_proposed_name_render_both` — mutation: one
     `if/elif` chain treating "what is special about this entry" as mutually
     exclusive, dropping a sentence when `same_file: true` and
     `proposed_name: null` both hold (T1.3 and T2.1 are independent fields;
     the combination is reachable).

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


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load_module("suggestions_reducer_t037_t2_3", "suggestions-reducer.py")

ITEM_KEY = "Inbox/Scans/karte.md"
ASSET_SOURCE = "Inbox/Scans/karte.png"
ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"

# Exact substrings unique to each branch — chosen so no branch's assertion
# text is a substring of another branch's rendered sentence.
TRUE_TEXT = "renaming would create a second copy of it"
FALSE_TEXT = "A different file already holds this name"
NULL_TEXT = "The files could not be compared"

# Hardcoded from T2.2's own fixture (test_037_t2_2_render_conflicts.py),
# NOT recomputed here — this anchors T2.3 against T2.2's shipped baseline
# rather than comparing this file's output against itself.
BASELINE_CHECKBOXES = [
    f"- [x] Rename to `{ASSET_FOLDER}karte (2).png`",
    "- [ ] Keep in inbox",
    "- [ ] Ignore (the move is sent as-is and will fail — the attachment stays in the inbox)",
]


def _conflict(**overrides) -> dict:
    base = {
        "source": ASSET_SOURCE,
        "destination": f"{ASSET_FOLDER}karte.png",
        "same_file": None,
        "owner_source_items": [ITEM_KEY],
        "proposed_name": "karte (2).png",
    }
    base.update(overrides)
    return base


def _checkbox_lines(md: str) -> list[str]:
    return [
        ln.strip() for ln in md.splitlines()
        if ln.strip().startswith(("- [ ]", "- [x]"))
    ]


# ---------------------------------------------------------------------------
# 1. same_file: true (S1-AC1)
# ---------------------------------------------------------------------------

def test_same_file_true_renders_second_copy_warning():
    md = REDUCER.render_attachment_conflicts_block([_conflict(same_file=True)], ASSET_FOLDER)
    assert "same file" in md.lower(), md
    assert TRUE_TEXT in md, md
    assert FALSE_TEXT not in md, md
    assert NULL_TEXT not in md, md


# ---------------------------------------------------------------------------
# 2. same_file: false (S1-AC2)
# ---------------------------------------------------------------------------

def test_same_file_false_renders_different_file_statement():
    md = REDUCER.render_attachment_conflicts_block([_conflict(same_file=False)], ASSET_FOLDER)
    assert FALSE_TEXT in md, md
    assert TRUE_TEXT not in md, md
    assert NULL_TEXT not in md, md


# ---------------------------------------------------------------------------
# 3. same_file: null (S1-AC3)
# ---------------------------------------------------------------------------

def test_same_file_null_renders_could_not_compare():
    md = REDUCER.render_attachment_conflicts_block([_conflict(same_file=None)], ASSET_FOLDER)
    assert NULL_TEXT in md, md
    assert TRUE_TEXT not in md, md
    assert FALSE_TEXT not in md, md


# ---------------------------------------------------------------------------
# 4. The remedies do not move (byte-identical to T2.2's baseline)
# ---------------------------------------------------------------------------

def test_remedies_unchanged_from_t2_2_baseline():
    for same_file_value in (True, False, None):
        md = REDUCER.render_attachment_conflicts_block(
            [_conflict(same_file=same_file_value)], ASSET_FOLDER
        )
        assert _checkbox_lines(md) == BASELINE_CHECKBOXES, (
            same_file_value, _checkbox_lines(md)
        )


# ---------------------------------------------------------------------------
# 5. same_file: true still ships rename TICKED (SDD/Complex Logic)
# ---------------------------------------------------------------------------

def test_same_file_true_still_ships_rename_ticked():
    md = REDUCER.render_attachment_conflicts_block([_conflict(same_file=True)], ASSET_FOLDER)
    checkboxes = _checkbox_lines(md)
    assert checkboxes[0].startswith("- [x] Rename"), checkboxes[0]
    assert checkboxes[1] == "- [ ] Keep in inbox", checkboxes[1]


# ---------------------------------------------------------------------------
# 6. same_file: true AND proposed_name: null — both must render (independent
#    fields, T1.3 + T2.1)
# ---------------------------------------------------------------------------

def test_same_file_true_and_no_proposed_name_render_both():
    entry = _conflict(same_file=True, proposed_name=None)
    md = REDUCER.render_attachment_conflicts_block([entry], ASSET_FOLDER)

    assert TRUE_TEXT in md, "the duplicate-file warning must still render"

    checkboxes = _checkbox_lines(md)
    rename_line = next(ln for ln in checkboxes if "Rename" in ln)
    keep_line = next(ln for ln in checkboxes if "Keep in inbox" in ln)
    assert rename_line.startswith("- [ ]"), rename_line
    assert "no free name" in rename_line.lower(), rename_line
    assert keep_line.startswith("- [x]"), keep_line
