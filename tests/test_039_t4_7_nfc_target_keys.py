#!/usr/bin/env python3
# version: 0.1.0
"""test_039_t4_7_nfc_target_keys.py — spec 039 Phase 4 drift check W7.

A target path is compared under ONE key: NFC-normalised, then case-folded
(`lib.vault_paths.path_key`). Before the fix K1's run-collision map
(`claimed`) and K2's maps (`VaultFolderLookup.notes/assets/
occupied_by_folder`) folded case only, while the census and the in-run name
key already normalised — so an NFD-spelled target (a macOS-typed `Café.png`)
missed an NFC-stored occupier or an NFC-claimed target, and the move was
emitted only to fail at apply with both source and destination present.

A separate file rather than more rows in the T4.2 file: the defect spans K1,
K2 and both of K2's other consumers (the Pass-1 reducer and Pass 2's
`validate_destinations`), and the T4.2 file is K1's decision table alone.

Mutations (isolated copy): drop the `unicodedata.normalize("NFC", ...)` step
from `path_key` — all ten tests fail. Make `same_spelling` plain `a == b` — the
three sentence assertions fail (K1's `vault_occupied` sentence, the reducer's
`_clash_reason`, `validate_destinations`' `case_only`).

CON-7: fixtures and fakes only.
"""
from __future__ import annotations

import importlib.util
import sys
import unicodedata
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from attachment_plan_fakes import FakeVault  # noqa: E402
from lib.attachment_plan import build_attachment_plan  # noqa: E402
from lib.render_actions import validate_destinations  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load("suggestions_reducer_t039_t4_7", "suggestions-reducer.py")

INBOX = "100 Inbox/"
ASSET = "Atlas/290 Assets/295 Attachments/"
NOTES = "Atlas/200 Notes"
NFC_NAME = unicodedata.normalize("NFC", "Café.png")
NFD_NAME = unicodedata.normalize("NFD", "Café.png")
assert NFC_NAME != NFD_NAME


def _plan(confirmed, vault, remedies=()):
    return build_attachment_plan(
        confirmed, {r["source"]: r for r in remedies},
        asset_folder=ASSET, inbox_path=INBOX,
        folder_lookup=vault.lookup, census=vault.census,
    )


def _held_kind(decision) -> str | None:
    return decision.withheld["kind"] if decision.withheld else None


# --- K1 row 8: vault occupancy ------------------------------------------------

def test_typed_nfd_target_is_occupied_by_an_nfc_vault_file():
    """(a) An owner-typed NFD name lands on an NFC file already in the vault."""
    source = "100 Inbox/Scans/karte.png"
    vault = FakeVault([source, f"{ASSET}{NFC_NAME}"], existing_folders=[ASSET])
    remedy = {"source": source, "remedy": "rename", "proposed_name": NFD_NAME,
              "name_is_owner_supplied": True, "proposed_dir": None,
              "dir_is_owner_supplied": False}
    plan = _plan([{"source_path": "karte.md", "attachments": [source]}], vault, [remedy])
    (decision,) = plan.decisions
    assert _held_kind(decision) == "vault_occupied", decision
    assert decision.withheld["destination"] == f"{ASSET}{NFD_NAME}"


def test_nfd_source_basename_is_occupied_by_an_nfc_vault_file():
    """(b) The default target built from an NFD inbox basename."""
    source = f"100 Inbox/Scans/{NFD_NAME}"
    vault = FakeVault([source, f"{ASSET}{NFC_NAME}"], existing_folders=[ASSET])
    plan = _plan([{"source_path": "cafe.md", "attachments": [source]}], vault)
    (decision,) = plan.decisions
    assert _held_kind(decision) == "vault_occupied", decision


def test_nfd_target_is_occupied_by_an_nfc_folder():
    """Row 8's folder half: a FOLDER spelled NFC holds the NFD target's name."""
    source = f"100 Inbox/Scans/{NFD_NAME}"
    vault = FakeVault([source], existing_folders=[ASSET, f"{ASSET}{NFC_NAME}"])
    plan = _plan([{"source_path": "cafe.md", "attachments": [source]}], vault)
    (decision,) = plan.decisions
    assert _held_kind(decision) == "vault_occupied", decision


def test_an_nfc_only_difference_is_not_reported_as_a_case_difference():
    """The sentence's case note is for names that differ in case; an
    NFC/NFD pair spells the same visible name."""
    source = f"100 Inbox/Scans/{NFD_NAME}"
    vault = FakeVault([source, f"{ASSET}{NFC_NAME}"], existing_folders=[ASSET])
    plan = _plan([{"source_path": "cafe.md", "attachments": [source]}], vault)
    (decision,) = plan.decisions
    assert "differ only in case" not in decision.withheld["reason"]


# --- K1 row 7: run collision --------------------------------------------------

def test_targets_differing_only_by_normalisation_collide_in_the_run():
    """(c) The second source's target is the first's, spelled NFD."""
    first = f"100 Inbox/A/{NFC_NAME}"
    second = f"100 Inbox/B/{NFD_NAME}"
    vault = FakeVault([first, second], existing_folders=[ASSET])
    plan = _plan([{"source_path": "a.md", "attachments": [first]},
                  {"source_path": "b.md", "attachments": [second]}], vault)
    assert plan.by_source[first].withheld is None
    assert _held_kind(plan.by_source[second]) == "collision", plan.by_source[second]


# --- Pass 1: the reducer reads the same K2 maps -------------------------------

def test_pass_1_detects_an_nfd_attachment_over_an_nfc_vault_file():
    """(d) `detect_attachment_conflicts` over K2's `assets` view."""
    source = f"100 Inbox/Scans/{NFD_NAME}"
    vault = FakeVault([source, f"{ASSET}{NFC_NAME}"], existing_folders=[ASSET])
    items = [("100 Inbox/cafe.md",
              [{"kind": "create_atomic_note", "attachments": [source]}])]
    conflicts = REDUCER.detect_attachment_conflicts(
        items, ASSET, vault.lookup.assets,
        content_reader=lambda _p: b"different",
        folder_listing=vault.lookup.occupied_by_folder,
    )
    assert [c["source"] for c in conflicts] == [source]


def test_pass_1_proposes_past_an_nfc_spelled_variant():
    """(d) The first-free proposal skips a variant the vault holds as NFC."""
    source = f"100 Inbox/Scans/{NFD_NAME}"
    taken = unicodedata.normalize("NFC", "Café (2).png")
    vault = FakeVault([source, f"{ASSET}{NFC_NAME}", f"{ASSET}{taken}"],
                      existing_folders=[ASSET])
    items = [("100 Inbox/cafe.md",
              [{"kind": "create_atomic_note", "attachments": [source]}])]
    (conflict,) = REDUCER.detect_attachment_conflicts(
        items, ASSET, vault.lookup.assets,
        content_reader=lambda _p: b"different",
        folder_listing=vault.lookup.occupied_by_folder,
    )
    assert conflict["proposed_name"] == unicodedata.normalize("NFD", "Café (3).png")


def test_pass_1_renames_an_nfd_title_over_an_nfc_vault_note():
    """(d) `resolve_destination_clashes` over K2's `notes` view."""
    vault = FakeVault([f"{NOTES}/{unicodedata.normalize('NFC', 'Café.md')}"],
                      existing_folders=[NOTES])
    title = unicodedata.normalize("NFD", "Café")
    adjustments = REDUCER.resolve_destination_clashes(
        [("c1", NOTES, title)], vault.lookup.notes,
    )
    renamed, reason = adjustments["c1"]
    assert renamed == f"{title} (2)"
    assert "only in case" not in reason


# --- Pass 2: validate_destinations --------------------------------------------

def _move(action_id: str, title: str) -> dict:
    return {"id": action_id, "action": "move_note",
            "source": f"{INBOX}{action_id}.md",
            "destination": f"{NOTES}/{title}.md"}


def test_validate_destinations_drops_two_moves_differing_only_by_normalisation():
    """(e) The run half: two claimants on one destination, NFC and NFD."""
    actions = [_move("a1", unicodedata.normalize("NFC", "Café")),
               _move("a2", unicodedata.normalize("NFD", "Café"))]
    kept, clashes = validate_destinations(actions)
    assert [a["id"] for a in kept] == []
    (clash,) = clashes
    assert clash["kind"] == "run_collision"
    assert clash["case_only"] is False


def test_validate_destinations_drops_an_nfd_move_over_an_nfc_vault_note():
    """(e) The vault half, through K2's `notes` view."""
    vault = FakeVault([f"{NOTES}/{unicodedata.normalize('NFC', 'Café.md')}"],
                      existing_folders=[NOTES])
    kept, clashes = validate_destinations(
        [_move("a1", unicodedata.normalize("NFD", "Café"))], vault.lookup.notes,
    )
    assert kept == []
    (clash,) = clashes
    assert clash["kind"] == "vault_collision"
