#!/usr/bin/env python3
# version: 0.1.0
"""test_037_t2_1_proposed_name.py — spec 037 T2.1.

`detect_attachment_conflicts` (T1.2-T1.5) reports an occupied destination but
never says what a rename remedy would actually be called. `SDD/Interface
Specifications` lists `proposed_name` as a field of `attachment_conflicts[]`;
this file pins its computation, added by `_propose_asset_name` and threaded
into every conflict entry.

Owner decision 2026-09-23: mirror the scheme `resolve_destination_clashes`
already ships for note clashes — `{stem} ({n})`, n from 2, first free wins —
with the counter moved BEFORE the extension, because `_asset_dest_join`
preserves an attachment's basename verbatim and the embed stops resolving
otherwise (`karte.png (2)` is no longer a PNG).

  1. The counter goes before the extension: `karte.png` -> `karte (2).png`.
  2. The stem is everything before the LAST dot: `karte.tar.gz` ->
     `karte.tar (2).gz`, not `karte (2).tar.gz`.
  3. No dot at all: `README` -> `README (2)`.
  4. An occupied proposal advances: `karte.png` AND `karte (2).png` both
     taken -> `karte (3).png`.
  5. The occupancy check folds case (strengthened from the plan's loose
     fixture — see the test's own docstring for why the candidate itself,
     not just the base destination, must be the case-differing name for
     the fixture to actually falsify a literal-string comparison).
  6. A candidate is checked against the FOLDER set too, not only the file
     listing — gating on the file listing alone reproduces T1.4's fixed
     defect one level down.
  7. Two conflicts in ONE run get DIFFERENT proposals — `(2)` and `(3)`,
     never the same.
  8. After 99 taken variants `proposed_name` is `null`, and the conflict is
     still emitted.
  9. Schema: `proposed_name` is required and typed `["string", "null"]`.

FALSIFICATION — named per test, in its own docstring.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

import pytest  # noqa: E402
from jsonschema import validate  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_reducer():
    spec = importlib.util.spec_from_file_location(
        "suggestions_reducer_t037_t2_1", SCRIPTS_DIR / "suggestions-reducer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["suggestions_reducer_t037_t2_1"] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load_reducer()

ASSET_FOLDER = "Atlas/290 Assets/295 Attachments/"  # DEFAULT_ASSET_FOLDER
ITEM_KEY_A = "100 Inbox/A/note-a.md"
ITEM_KEY_B = "100 Inbox/B/note-b.md"


def _owner_actions(attachments: list[str], *, suppressed: bool = False) -> list[dict]:
    return [{
        "kind": "create_atomic_note",
        "suppressed": suppressed,
        "attachments": attachments,
    }]


def _occupied(*names: str) -> dict:
    """A fake `asset_listing` result: case-folded destination -> the path
    as the vault spells it (same shape `_VaultFolderLookup.assets` returns)."""
    return {f"{ASSET_FOLDER}{name}".casefold(): f"{ASSET_FOLDER}{name}" for name in names}


def _occupied_folders(*names: str) -> set:
    """A fake `folder_listing` result: case-folded destinations held by a
    FOLDER entry (same shape `_VaultFolderLookup.occupied_by_folder`
    returns)."""
    return {f"{ASSET_FOLDER}{name}".casefold() for name in names}


# ---------------------------------------------------------------------------
# 1. The counter goes before the extension.
# ---------------------------------------------------------------------------

def test_counter_goes_before_the_extension():
    """`karte.png`, occupied, proposes `karte (2).png`.

    Mutation: append the counter after the whole basename — `karte.png (2)`
    — which is no longer a PNG and whose embed cannot resolve."""
    source = "100 Inbox/A/karte.png"
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([source]))],
        ASSET_FOLDER, lambda folder: _occupied("karte.png"),
    )
    assert result[0]["proposed_name"] == "karte (2).png"


# ---------------------------------------------------------------------------
# 2. The stem is everything before the LAST dot.
# ---------------------------------------------------------------------------

def test_stem_is_everything_before_the_last_dot():
    """`karte.tar.gz`, occupied, proposes `karte.tar (2).gz`, not
    `karte (2).tar.gz`.

    Mutation: split on the FIRST dot instead of the last — correct for a
    single-suffix name, so only this multi-dot fixture separates the two
    (every other fixture in this file uses a single-suffix or no-suffix
    name and cannot tell first-dot and last-dot splitting apart)."""
    source = "100 Inbox/A/karte.tar.gz"
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([source]))],
        ASSET_FOLDER, lambda folder: _occupied("karte.tar.gz"),
    )
    assert result[0]["proposed_name"] == "karte.tar (2).gz"


# ---------------------------------------------------------------------------
# 3. A name with no dot takes the suffix at the end.
# ---------------------------------------------------------------------------

def test_name_with_no_dot_takes_the_counter_at_the_end():
    """`README`, occupied, proposes `README (2)`.

    Mutation: index into a missing extension and raise, or emit
    `README (2).` with a trailing dot."""
    source = "100 Inbox/A/README"
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([source]))],
        ASSET_FOLDER, lambda folder: _occupied("README"),
    )
    assert result[0]["proposed_name"] == "README (2)"


# ---------------------------------------------------------------------------
# 4. An occupied proposal advances.
# ---------------------------------------------------------------------------

def test_an_occupied_proposal_advances():
    """`karte.png` AND `karte (2).png` both taken -> `karte (3).png`.

    Mutation: always propose `(2)` without testing the listing — this
    fixture is the one where that shortcut visibly disagrees with the
    correct, listing-checked answer."""
    source = "100 Inbox/A/karte.png"
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([source]))],
        ASSET_FOLDER, lambda folder: _occupied("karte.png", "karte (2).png"),
    )
    assert result[0]["proposed_name"] == "karte (3).png"


# ---------------------------------------------------------------------------
# 5. The occupancy check folds case.
# ---------------------------------------------------------------------------

def test_occupancy_check_folds_case():
    """`karte.png` incoming collides (case-folded) with vault `Karte.png` —
    that much is already proven at T1.1/T1.2 and is not this test's job.
    What IS this test's job: the CANDIDATE `karte (2).png` this task
    proposes must itself be checked against the listing case-folded, not
    literally. The plan's own fixture (only `Karte.png` occupied) cannot
    exercise that: `karte.png` and `karte (2).png` are different strings
    under ANY comparison, folded or not, so a fixture that occupies only
    the ORIGINAL name can never distinguish the two. This fixture instead
    occupies a case-DIFFERENT spelling of the CANDIDATE itself
    (`Karte (2).png`) so only a folded comparison catches it.

    Mutation: compare candidate destinations as literal strings (drop
    `.casefold()` from the candidate side of the check) — `karte (2).png`
    would then be judged free (it never literally equals `Karte (2).png`),
    proposing the still-taken name instead of advancing to `karte (3).png`.
    VERIFIED LIVE (spec 037 T2.1 report): dropping `.casefold()` entirely
    also fails tests 4, 6 and 8 in this file, because `ASSET_FOLDER` itself
    ("Atlas/290 Assets/...") carries uppercase — an unfolded join never
    matches the folded listings for ANY occupied candidate, not only a
    case-differing one. This test still isolates the CASE-folding behaviour
    specifically (a mutation that folds the join but skips only the
    case-normalisation step would be caught here and nowhere else in this
    file), but does not exclusively catch a wholesale "no casefold at all"
    mutation — that one is caught by four tests, not one."""
    source = "100 Inbox/A/karte.png"
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([source]))],
        ASSET_FOLDER,
        lambda folder: _occupied("Karte.png", "Karte (2).png"),
    )
    assert result[0]["proposed_name"] == "karte (3).png"


# ---------------------------------------------------------------------------
# 6. A candidate is checked against the FOLDER set too.
# ---------------------------------------------------------------------------

def test_candidate_checked_against_folder_set_too():
    """`karte.png` is occupied by a FILE; `karte (2).png` names an existing
    SUBFOLDER (not a file) — the candidate must be rejected all the same
    and the search must advance to `karte (3).png`.

    Mutation: gate the candidate on `asset_listing` (the file listing)
    alone — that reproduces exactly the defect T1.4 fixed for the initial
    destination, one level down in the rename candidate, and every other
    bullet in this file still passes because none of them puts a FOLDER at
    a candidate position."""
    source = "100 Inbox/A/karte.png"
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([source]))],
        ASSET_FOLDER,
        lambda folder: _occupied("karte.png"),
        None,
        lambda folder: _occupied_folders("karte (2).png"),
    )
    assert result[0]["proposed_name"] == "karte (3).png"


# ---------------------------------------------------------------------------
# 7. Two conflicts in ONE run get DIFFERENT proposals.
# ---------------------------------------------------------------------------

def test_two_conflicts_in_one_run_get_different_proposals():
    """Two DIFFERENT sources (different inbox subfolders, T1.5) both
    colliding on `logo.png` must propose `(2)` and `(3)` — never the same
    name twice.

    Mutation: derive each proposal from the vault listing alone, ignoring
    what this run has already proposed — both entries would independently
    walk to `logo (2).png`, and the rename would collide with itself; the
    exact defect T1.5 removed from ownership, reappearing in naming."""
    source_a = "100 Inbox/A/logo.png"
    source_b = "100 Inbox/B/logo.png"
    result = REDUCER.detect_attachment_conflicts(
        [
            (ITEM_KEY_A, _owner_actions([source_a])),
            (ITEM_KEY_B, _owner_actions([source_b])),
        ],
        ASSET_FOLDER, lambda folder: _occupied("logo.png"),
    )
    assert len(result) == 2
    proposals = [entry["proposed_name"] for entry in result]
    assert proposals == ["logo (2).png", "logo (3).png"], proposals


# ---------------------------------------------------------------------------
# 8. After 99 taken variants, proposed_name is null.
# ---------------------------------------------------------------------------

def test_99_taken_variants_gives_up_but_still_emits_the_conflict():
    """`karte.png` and every `karte (2).png` .. `karte (100).png` (99
    variants) are all taken -> `proposed_name` is `null`, and the conflict
    entry is still emitted (the occupancy is real either way).

    Mutation: emit the 100th candidate unchecked, or drop the conflict
    entirely."""
    source = "100 Inbox/A/karte.png"
    taken = ["karte.png"] + [f"karte ({n}).png" for n in range(2, 101)]
    result = REDUCER.detect_attachment_conflicts(
        [(ITEM_KEY_A, _owner_actions([source]))],
        ASSET_FOLDER, lambda folder: _occupied(*taken),
    )
    assert len(result) == 1
    assert result[0]["proposed_name"] is None
    assert result[0]["source"] == source
    assert result[0]["destination"] == f"{ASSET_FOLDER}karte.png"


# ---------------------------------------------------------------------------
# 9. Schema: proposed_name is required and typed ["string", "null"].
# ---------------------------------------------------------------------------

_SUGGESTIONS_DOC_SCHEMA = REPO_ROOT / "tomo" / "schemas" / "suggestions-doc.schema.json"


@pytest.fixture(scope="module")
def conflict_item_schema() -> dict:
    doc_schema = json.loads(_SUGGESTIONS_DOC_SCHEMA.read_text(encoding="utf-8"))
    return doc_schema["properties"]["attachment_conflicts"]["items"]


def test_proposed_name_is_required_and_string_or_null(conflict_item_schema):
    """`proposed_name` is in `required` and typed `["string", "null"]`,
    matching how `same_file` was added in T1.3.

    Mutation: leave it out of `required` — every existing document still
    validates and the field silently becomes optional."""
    assert "proposed_name" in conflict_item_schema["required"]
    assert conflict_item_schema["properties"]["proposed_name"]["type"] == [
        "string", "null"
    ]

    base = {
        "source": "100 Inbox/A/karte.png",
        "destination": f"{ASSET_FOLDER}karte.png",
        "same_file": None,
        "owner_source_items": ["100 Inbox/A/note-a.md"],
    }
    validate(instance={**base, "proposed_name": "karte (2).png"}, schema=conflict_item_schema)
    validate(instance={**base, "proposed_name": None}, schema=conflict_item_schema)
    with pytest.raises(Exception):
        validate(instance=base, schema=conflict_item_schema)
