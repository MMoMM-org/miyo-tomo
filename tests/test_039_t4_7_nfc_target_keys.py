#!/usr/bin/env python3
# version: 0.1.1
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

Mutations (isolated copy, 18 tests): drop the `unicodedata.normalize("NFC",
...)` step from `path_key` - 14 of 18 fail (the two audio tests key on
`nfc_lower` and are untouched). Make `same_spelling` plain `a == b` - 5 of 18
fail (K1's `vault_occupied` sentence, the reducer's `_clash_reason`,
`validate_destinations`' `case_only` and its one-path sentence, `_unique_in_order`).
Drop NFC from `nfc_lower` - the NFD stem and folder audio tests fail; casefold
instead of lower - the `Straße`/`Strasse` test fails.

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
    # "only in case", not the pre-T5.4 "differ only in case", which no
    # sentence carries any more and would pass vacuously (spec 039 T5.4).
    assert "only in case" not in decision.withheld["reason"]
    assert "already holds a file at the target" in decision.withheld["reason"]


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
    # Same visible spelling: the one-path sentence, and no case-only note.
    assert "where this run would file" not in clash["reason"]
    assert clash["case_only"] is False


# --- create_moc merge and its resolver ----------------------------------------

from lib.render_actions import _build_create_moc_actions  # noqa: E402
from lib.render_resolve import resolve_section_names  # noqa: E402

MOC_FOLDER = "Atlas/200 Maps/"
MOC_TEMPLATE_BODY = "# {{title}}\n\n> [!blocks] Key Concepts\n> \n"


def _moc_entry(title: str, rendered_file: str, supporting_items) -> dict:
    return {
        "id": "S01", "action": "create_moc", "title": title,
        "rendered_file": rendered_file, "destination": MOC_FOLDER,
        "parent_moc": "", "template": "t_moc_tomo", "tags": [],
        "supporting_items": supporting_items,
    }


class _TemplateClient:
    def __init__(self, notes: dict[str, str]) -> None:
        self.notes = notes

    def read_note(self, path: str) -> dict:
        if path in self.notes:
            return {"content": self.notes[path]}
        raise FileNotFoundError(path)

    def search_by_name(self, stem: str) -> list[dict]:
        return []


def test_create_moc_destinations_differing_only_by_normalisation_merge():
    """(f) One create_moc survives, carrying both proposals' children, and
    `validate_destinations` has no run_collision left to drop it for."""
    nfc = unicodedata.normalize("NFC", "Café (MOC)")
    nfd = unicodedata.normalize("NFD", "Café (MOC)")
    manifest = [
        _moc_entry(nfc, "2026-01-01_0900_cafe-moc.md", ["Dresden"]),
        _moc_entry(nfd, "2026-01-01_0901_cafe-moc.md", ["Kyoto"]),
    ]
    actions = _build_create_moc_actions(manifest, INBOX, [0])
    assert len(actions) == 1, actions
    assert actions[0]["supporting_items"] == ["Dresden", "Kyoto"]
    kept, clashes = validate_destinations(actions)
    assert [a["id"] for a in kept] == [actions[0]["id"]]
    assert clashes == []


def test_link_to_moc_with_nfd_target_finds_its_nfc_in_set_create_moc():
    """(g) The template-body fallback is the only tier that can resolve here,
    so the lookup — not the anchor picker — is what this asserts."""
    nfc_dest = f"{MOC_FOLDER}{unicodedata.normalize('NFC', 'Café (MOC).md')}"
    nfd_dest = f"{MOC_FOLDER}{unicodedata.normalize('NFD', 'Café (MOC).md')}"
    client = _TemplateClient({"Atlas/900 Templates/t_moc_tomo.md": MOC_TEMPLATE_BODY})
    actions = [
        {"id": "I01", "action": "create_moc", "destination": nfc_dest,
         "title": "Café (MOC)", "template": "Atlas/900 Templates/t_moc_tomo.md"},
        {"id": "I02", "action": "link_to_moc", "target_moc": "Café (MOC)",
         "target_moc_path": nfd_dest,
         "anchor": {"type": "callout", "value": None},
         "placement": "inside", "line_to_add": "- [[Dresden]]"},
    ]
    assert resolve_section_names(actions, client, ["connect", "blocks", "anchor"]) == 1
    assert actions[1]["anchor"]["value"] == "[!blocks] Key Concepts"


# --- the remaining comparison sites -------------------------------------------

def test_unique_in_order_collapses_nfc_and_nfd_keeping_the_first_spelling():
    from lib.render_actions import _unique_in_order
    assert _unique_in_order([NFD_NAME, NFC_NAME, "other.png"]) == [NFD_NAME, "other.png"]


def test_typed_folder_inside_an_nfd_spelled_inbox_is_refused():
    """The reverse of T2.2's case: the INBOX path is the decomposed one."""
    from lib.typed_name_check import check_typed_folder
    inbox = unicodedata.normalize("NFD", "Posteingang Ü")
    folder = unicodedata.normalize("NFC", "Posteingang Ü")
    assert check_typed_folder(folder + "/x", inbox_path=inbox).reason == "inside_inbox"


def test_proposed_mocs_differing_only_by_normalisation_merge_in_the_parser():
    parser = _load("suggestion_parser_t039_t4_7", "suggestion-parser.py")
    mocs = [
        {"title": unicodedata.normalize("NFC", "Café (MOC)"), "supporting_items": ["Dresden"]},
        {"title": unicodedata.normalize("NFD", "Café (MOC)"), "supporting_items": ["Kyoto"]},
    ]
    merged = parser._merge_proposed_mocs_by_name(mocs)
    assert len(merged) == 1, merged
    assert merged[0]["supporting_items"] == ["Dresden", "Kyoto"]


def test_audio_paired_with_an_nfc_note_is_not_reflagged_when_spelled_nfd():
    """An NFD recorder filename beside its NFC transcript is paired; leaving
    it unpaired re-transcribes it every run."""
    triage = _load("inbox_triage_t039_t4_7", "inbox-triage.py")
    audio = [{"path": f"{INBOX}{unicodedata.normalize('NFD', 'Café')}.m4a"}]
    notes = [{"path": f"{INBOX}{unicodedata.normalize('NFC', 'Café')}.md"}]
    assert triage.check_audio(audio, notes) is False


def test_audio_pairs_across_nfd_and_case_differing_folder_spellings():
    """The folder half of the pairing key is NFC + lower too: the same folder
    spelled NFD, or in another case, still holds the transcript."""
    triage = _load("inbox_triage_t039_t4_7", "inbox-triage.py")
    nfc_dir = unicodedata.normalize("NFC", "Café Voice")
    nfd_dir = unicodedata.normalize("NFD", "Café Voice")
    notes = [{"path": f"{INBOX}{nfc_dir}/memo.md"}]
    assert triage.check_audio([{"path": f"{INBOX}{nfd_dir}/memo.m4a"}], notes) is False
    assert triage.check_audio([{"path": f"{INBOX}{nfc_dir.upper()}/memo.m4a"}], notes) is False


def test_audio_does_not_pair_with_a_casefold_only_namesake():
    """`Straße.m4a` beside `Strasse.md` is NOT paired: voice-transcribe and
    voice-precheck compare exact sanitized paths, so casefolding `ß` to `ss`
    would skip a transcription the voice tools still need."""
    triage = _load("inbox_triage_t039_t4_7", "inbox-triage.py")
    audio = [{"path": f"{INBOX}Straße.m4a"}]
    notes = [{"path": f"{INBOX}Strasse.md"}]
    assert triage.check_audio(audio, notes) is True
