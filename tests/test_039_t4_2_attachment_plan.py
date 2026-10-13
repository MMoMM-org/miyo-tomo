#!/usr/bin/env python3
# version: 0.1.0
"""test_039_t4_2_attachment_plan.py — spec 039 T4.2, K1 (the attachment plan).

One test per row of the SDD decision table (K1, rows 1–11, first match wins),
each with an accepting variant (the row's condition holds → its outcome) and a
rejecting variant (the condition just misses → a later row decides), plus the
census (Pass B) and the named extras in phase-4.md T4.2.

Every test runs the plan against `FakeVault` (tests/attachment_plan_fakes.py):
one set of files behind the REAL `VaultFolderLookup` (K2) and a census fake
with K3's interface, so occupancy and uniqueness are always judged on the same
vault. The markdown-path records come from the real Pass-1 renderer and the
real parser join, so "both paths" means both producers, not two hand-written
dicts.

Mutation proven RED in an isolated copy: delete the census subtraction (this
run's moved inbox sources) — `test_f4_ac4_moved_inbox_sources_are_not_counted`
fails (the unrenamed attachment's own inbox copy and the other moved copy make
it read ambiguous).

CON-7: fixtures and fakes only.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from attachment_plan_fakes import FakeVault, plan_from_remedies  # noqa: E402
from lib.attachment_plan import AttachmentDecision, build_attachment_plan  # noqa: E402
from lib.refusal_sentences import (  # noqa: E402
    folder_sentence,
    occupied_target_sentence,
    typed_name_sentence,
)


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


PARSER = _load("suggestion_parser_t039_t4_2", "suggestion-parser.py")
REDUCER = _load("suggestions_reducer_t039_t4_2", "suggestions-reducer.py")

INBOX = "100 Inbox/"
ASSET = "Atlas/290 Assets/295 Attachments/"
DEFAULT_DIR = "Atlas/290 Assets/295 Attachments"
MAPS = "Atlas/296 Maps"
SRC = "100 Inbox/Scans/karte.png"
OWNER = "100 Inbox/karte.md"
DEFAULT_TARGET = f"{ASSET}karte.png"


def _item(source_path="karte.md", attachments=(SRC,), **extra) -> dict:
    return {"id": "S01", "source_path": source_path,
            "attachments": list(attachments), **extra}


def _rename(source=SRC, name="karte (2).png", *, name_typed=False,
            folder=None, folder_typed=False) -> dict:
    return {"source": source, "remedy": "rename", "proposed_name": name,
            "name_is_owner_supplied": name_typed, "proposed_dir": folder,
            "dir_is_owner_supplied": folder_typed}


def _remedy(remedy, source=SRC, *, folder=None, folder_typed=False) -> dict:
    return {"source": source, "remedy": remedy, "proposed_name": None,
            "name_is_owner_supplied": False, "proposed_dir": folder,
            "dir_is_owner_supplied": folder_typed}


def _plan(confirmed, remedies=(), vault=None, *, asset=ASSET):
    if vault is None:
        vault = FakeVault([p for i in confirmed for p in i["attachments"]],
                          existing_folders=[asset, MAPS])
    return build_attachment_plan(
        confirmed, {r["source"]: r for r in remedies},
        asset_folder=asset, inbox_path=INBOX,
        folder_lookup=vault.lookup, census=vault.census,
    )


def _one(plan) -> AttachmentDecision:
    assert len(plan.decisions) == 1, plan.decisions
    return plan.decisions[0]


def _moved(d: AttachmentDecision, target: str) -> None:
    assert d.withheld is None, d.withheld
    assert d.target == target


def _held(d: AttachmentDecision, kind: str) -> dict:
    assert d.target is None, d.target
    assert d.embed is None
    assert d.withheld is not None and d.withheld["kind"] == kind, d.withheld
    assert d.withheld["source"] == d.source
    assert d.withheld["owner_source_items"] == list(d.owners)
    return d.withheld


# Markdown path: the real Pass-1 block, the folder line edited as an owner would.
def _markdown_record(folder_line: str | None = None, name="karte (2).png") -> dict:
    conflict = {
        "source": SRC, "destination": DEFAULT_TARGET, "same_file": False,
        "owner_source_items": [OWNER], "proposed_name": name, "proposed_dir": None,
    }
    md = REDUCER.render_attachment_conflicts_block([conflict], ASSET)
    if folder_line is not None:
        lines = md.splitlines()
        idx = [i for i, ln in enumerate(lines) if ln.startswith("  - Folder:")]
        assert len(idx) == 1, lines
        lines[idx[0]] = folder_line
        md = "\n".join(lines) + "\n"
    records = PARSER._join_attachment_conflict_remedies(
        PARSER.parse_attachment_conflict_remedies(md),
        {"attachment_conflicts": [conflict]},
    )
    assert len(records) == 1 and records[0]["remedy"] == "rename", records
    return records[0]


# Wire path: the projection `build_from_wire` makes (suggestion-parser.py).
def _wire_record(proposed_dir, name="karte (2).png") -> dict:
    return {"source": SRC, "remedy": "rename", "proposed_name": name,
            "name_is_owner_supplied": True, "proposed_dir": proposed_dir,
            "dir_is_owner_supplied": proposed_dir is not None}


# ── Row 1: no basename ──────────────────────────────────────────────────────

def test_row1_no_basename_is_withheld(capsys):
    d = _one(_plan([_item(attachments=["100 Inbox/Scans/"])]))
    entry = _held(d, "no_basename")
    assert entry == {
        "source": "100 Inbox/Scans/", "destination": None,
        "reason": "the inbox path has no filename", "kind": "no_basename",
        "owner_source_items": [OWNER],
    }
    assert "skipping attachment" in capsys.readouterr().err


def test_row1_rejected_a_basename_is_planned():
    _moved(_one(_plan([_item()])), DEFAULT_TARGET)


# ── Row 2: Keep in inbox ────────────────────────────────────────────────────

def test_row2_keep_in_inbox_is_held_with_todays_entry():
    d = _one(_plan([_item()], [_remedy("keep_in_inbox")]))
    assert _held(d, "vault_collision_held") == {
        "source": SRC, "destination": DEFAULT_TARGET,
        "reason": (
            f"kept in inbox: the owner chose not to file it over "
            f"the occupied destination `{DEFAULT_TARGET}`"
        ),
        "kind": "vault_collision_held", "owner_source_items": [OWNER],
    }


def test_row2_rejected_ignore_is_not_held():
    _moved(_one(_plan([_item()], [_remedy("ignore")])), DEFAULT_TARGET)


# ── Row 3: Rename, owner-typed folder refused ──────────────────────────────

@pytest.mark.parametrize("folder, code", [
    ("../outside", "escapes_vault"),
    ("", "blank"),
    ("100 Inbox/Scans", "inside_inbox"),
    ("Atlas/C# Projekte", "breaks_link"),
])
def test_row3_refused_typed_folder_is_withheld_without_fallback(folder, code):
    """F2-AC6: no fallback target. `inside_inbox` only fires when the plan
    hands `check_typed_folder` the vault-relative inbox path (carried from
    Phase 3); `""` owner-supplied is `blank`, never the default folder."""
    d = _one(_plan([_item()], [_rename(folder=folder, folder_typed=True)]))
    assert _held(d, "typed_folder_refused") == {
        "source": SRC, "destination": None,
        "reason": folder_sentence(code, folder), "refusal_reason": code,
        "kind": "typed_folder_refused", "owner_source_items": [OWNER],
    }


def test_row3_rejected_usable_typed_folder_is_used_f1_ac3():
    d = _one(_plan([_item()], [_rename(folder=MAPS, folder_typed=True)]))
    _moved(d, f"{MAPS}/karte (2).png")


# ── Row 4: Rename, name empty, folder owner-typed (F1-AC11) ────────────────

@pytest.mark.parametrize("name", [None, ""])
def test_row4_empty_name_with_typed_folder_is_refused_blank(name):
    d = _one(_plan([_item()], [_rename(name=name, folder=MAPS, folder_typed=True)]))
    entry = _held(d, "typed_name_refused")
    assert entry["refusal_reason"] == "blank"
    assert entry["destination"] is None
    assert entry["reason"] == typed_name_sentence("blank", name or "")


def test_row4_rejected_folder_not_typed_degrades_to_held():
    d = _one(_plan([_item()], [_rename(name=None, folder=DEFAULT_DIR)]))
    assert _held(d, "vault_collision_held")["destination"] == DEFAULT_TARGET


# ── Row 5: Rename, name empty, folder not typed (today's degrade) ──────────

def test_row5_lost_name_degrades_with_todays_reason():
    d = _one(_plan([_item()], [_rename(name=None)]))
    assert _held(d, "vault_collision_held")["reason"] == (
        f"kept in inbox: it was to be filed under a new name "
        f"beside the occupied destination `{DEFAULT_TARGET}`, and "
        f"that name is no longer available to this run — it "
        f"stays in the inbox rather than being filed under a "
        f"name the owner did not choose"
    )


def test_row5_rejected_a_name_is_filed():
    _moved(_one(_plan([_item()], [_rename()])), f"{ASSET}karte (2).png")


# ── Row 6: Rename, owner-typed name refused ─────────────────────────────────

def test_row6_refused_typed_name_is_withheld():
    d = _one(_plan([_item()], [_rename(name="a/b.png", name_typed=True)]))
    assert _held(d, "typed_name_refused") == {
        "source": SRC, "destination": None,
        "reason": typed_name_sentence("separator_present", "a/b.png"),
        "refusal_reason": "separator_present",
        "kind": "typed_name_refused", "owner_source_items": [OWNER],
    }


def test_row6_rejected_computed_name_is_never_checked():
    """The gate is provenance: the same refusable character in a name Pass 1
    computed is filed (038 F3's ninth criterion)."""
    d = _one(_plan([_item()], [_rename(name="kar*te.png", name_typed=False)]))
    _moved(d, f"{ASSET}kar*te.png")


# ── Row 7: target already claimed this run (Ignore included) ───────────────

def test_row7_second_source_onto_a_claimed_target_is_a_collision(capsys):
    a, b = "100 Inbox/a/karte.png", "100 Inbox/b/karte.png"
    plan = _plan([_item(attachments=[a, b])])
    _moved(plan.by_source[a], DEFAULT_TARGET)
    assert _held(plan.by_source[b], "collision") == {
        "source": b, "destination": DEFAULT_TARGET,
        "reason": (
            f"destination collision: it also resolves to "
            f"`{DEFAULT_TARGET}`, already claimed by `{a}`"
        ),
        "kind": "collision", "owner_source_items": [OWNER],
    }
    assert "destination collision" in capsys.readouterr().err


def test_row7_rejected_different_targets_both_move():
    a, b = "100 Inbox/a/karte.png", "100 Inbox/b/plan.png"
    plan = _plan([_item(attachments=[a, b])])
    _moved(plan.by_source[a], DEFAULT_TARGET)
    _moved(plan.by_source[b], f"{ASSET}plan.png")


def test_row7_two_ignores_onto_one_target_second_is_a_collision():
    """PRD Rule 4: Ignore is exempt from the vault half only."""
    a, b = "100 Inbox/a/karte.png", "100 Inbox/b/karte.png"
    vault = FakeVault([a, b, DEFAULT_TARGET])
    plan = _plan([_item(attachments=[a, b])],
                 [_remedy("ignore", a), _remedy("ignore", b)], vault)
    _moved(plan.by_source[a], DEFAULT_TARGET)
    _held(plan.by_source[b], "collision")


def test_row7_case_only_target_is_claimed():
    a, b = "100 Inbox/a/karte.png", "100 Inbox/b/Karte.PNG"
    plan = _plan([_item(attachments=[a, b])])
    _held(plan.by_source[b], "collision")


# ── Row 8: not Ignore, K2 listed, target taken ─────────────────────────────

def test_row8_occupied_rename_target_is_withheld_f3_ac1():
    occupier = f"{ASSET}karte (2).png"
    d = _one(_plan([_item()], [_rename()], FakeVault([SRC, occupier])))
    entry = _held(d, "vault_occupied")
    assert set(entry) == {"source", "destination", "reason", "kind",
                          "owner_source_items"}
    assert entry["destination"] == occupier
    assert f"`{occupier}`" in entry["reason"]
    assert "note" not in entry["reason"]


def test_row8_rejected_ignore_onto_occupied_moves_f3_ac4():
    d = _one(_plan([_item()], [_remedy("ignore")], FakeVault([SRC, DEFAULT_TARGET])))
    _moved(d, DEFAULT_TARGET)
    assert d.unchecked is False


def test_row8_non_conflict_attachment_onto_now_occupied_target_f3_ac2():
    d = _one(_plan([_item()], [], FakeVault([SRC, DEFAULT_TARGET])))
    assert _held(d, "vault_occupied")["destination"] == DEFAULT_TARGET


def test_row8_case_only_occupier_is_occupied_and_named_as_spelled():
    occupier = f"{ASSET}KARTE.png"
    d = _one(_plan([_item()], [], FakeVault([SRC, occupier])))
    entry = _held(d, "vault_occupied")
    assert entry["destination"] == DEFAULT_TARGET
    assert f"`{occupier}`" in entry["reason"]


def test_row8_a_folder_at_the_target_name_occupies_it():
    d = _one(_plan([_item()], [], FakeVault([SRC], existing_folders=[DEFAULT_TARGET])))
    reason = _held(d, "vault_occupied")["reason"]
    assert "already has a folder at" in reason
    assert "already holds" not in reason


def test_row7_is_decided_before_row_8():
    """The target is occupied in the vault AND claimed by an Ignore source this
    run: the claim (row 7) names the claimant, not the occupier (row 8)."""
    a, b = "100 Inbox/a/karte.png", "100 Inbox/b/karte.png"
    vault = FakeVault([a, b, DEFAULT_TARGET])
    plan = _plan([_item(attachments=[a, b])], [_remedy("ignore", a)], vault)
    _moved(plan.by_source[a], DEFAULT_TARGET)
    reason = _held(plan.by_source[b], "collision")["reason"]
    assert f"already claimed by `{a}`" in reason


def test_occupied_target_sentence_variants():
    exact = occupied_target_sentence(DEFAULT_TARGET, DEFAULT_TARGET)
    # same spelling: naming the occupier would repeat the target, so it reads "a file"
    assert "already holds a file at the target" in exact and "only in case" not in exact
    case_only = occupied_target_sentence(DEFAULT_TARGET, f"{ASSET}KARTE.png")
    assert f"`{ASSET}KARTE.png`" in case_only and "only in case" in case_only
    # spec 039 T5.4: the case-only occupier is not AT the target
    assert "at the target" not in case_only, case_only
    folder = occupied_target_sentence(DEFAULT_TARGET, None, occupier_is_folder=True)
    assert "already has a folder at" in folder
    assert "already holds" not in folder and "only in case" not in folder


def test_row8_a_note_in_the_folder_does_not_occupy_an_attachment_target():
    d = _one(_plan([_item()], [], FakeVault([SRC, f"{ASSET}karte.png.md"])))
    _moved(d, DEFAULT_TARGET)


# ── Row 9: K2 unanswered → move, unchecked (F3-AC6) ────────────────────────

def test_row9_unanswered_folder_moves_unchecked():
    vault = FakeVault([SRC, DEFAULT_TARGET], failing_folders=[ASSET])
    d = _one(_plan([_item()], [], vault))
    _moved(d, DEFAULT_TARGET)
    assert d.unchecked is True and d.folder_created is False


def test_row9_rejected_listed_folder_is_checked():
    d = _one(_plan([_item()]))
    assert d.unchecked is False


def test_row9_one_folder_unanswered_other_answered_each_judged_by_its_own():
    a, b = "100 Inbox/a/karte.png", "100 Inbox/b/plan.png"
    vault = FakeVault([a, b], existing_folders=[MAPS], failing_folders=[ASSET])
    plan = _plan([_item(attachments=[a, b])],
                 [_rename(b, "plan.png", folder=MAPS, folder_typed=True)], vault)
    assert plan.by_source[a].unchecked is True
    assert plan.by_source[b].unchecked is False


# ── Row 10: K2 absent → move, folder_created (F2-AC8) ──────────────────────

def test_row10_absent_typed_folder_moves_and_will_be_created():
    vault = FakeVault([SRC], existing_folders=[ASSET])
    d = _one(_plan([_item()], [_rename(folder="Atlas/New Maps", folder_typed=True)], vault))
    _moved(d, "Atlas/New Maps/karte (2).png")
    assert d.folder_created is True and d.unchecked is False


def test_row10_rejected_existing_folder_is_not_created():
    d = _one(_plan([_item()], [_rename(folder=MAPS, folder_typed=True)]))
    assert d.folder_created is False


# ── Row 11: otherwise → move ───────────────────────────────────────────────

def test_row11_plain_attachment_onto_free_target_moves():
    d = _one(_plan([_item()]))
    _moved(d, DEFAULT_TARGET)
    assert (d.unchecked, d.folder_created) == (False, False)


def test_row11_rejected_taken_target_is_not_row_11():
    d = _one(_plan([_item()], [], FakeVault([SRC, DEFAULT_TARGET])))
    assert d.target is None


# ── Folder resolution (F1-AC5, AC6, AC10; trailing `/`; equal to asset) ────

def test_f1_ac5_untouched_folder_line_resolves_to_pass_2_asset_folder():
    """Markdown path untouched (folder == dirname(destination)) and the wire's
    null both resolve to Pass 2's `concepts.asset` — even when the config
    changed between passes."""
    moved_asset = "Atlas/New Attachments/"
    for record in (_markdown_record(), _wire_record(None)):
        vault = FakeVault([SRC], existing_folders=[moved_asset])
        d = _one(_plan([_item()], [record], vault, asset=moved_asset))
        _moved(d, f"{moved_asset}karte (2).png")


def test_default_folder_with_trailing_slash_is_refused_on_both_paths():
    md = _markdown_record(f"  - Folder: `{DEFAULT_DIR}/`")
    for record in (md, _wire_record(f"{DEFAULT_DIR}/")):
        d = _one(_plan([_item()], [record]))
        entry = _held(d, "typed_folder_refused")
        assert entry["refusal_reason"] == "trailing_separator"


def test_owner_supplied_folder_equal_to_asset_folder_is_the_default():
    """Not checked, so not refused and never `folder_created` on its own say:
    it is the configured folder spelled as a folder (without the separator the
    config carries)."""
    d = _one(_plan([_item()], [_wire_record(DEFAULT_DIR)]))
    _moved(d, f"{ASSET}karte (2).png")


def test_owner_supplied_folder_equal_to_asset_folder_is_not_the_typed_branch():
    """Rejecting variant: equal-to-default skips `check_typed_folder`, so an
    empty name beside it is today's degrade (row 5), not F1-AC11's `blank`."""
    d = _one(_plan([_item()], [_wire_record(DEFAULT_DIR, name=None)]))
    _held(d, "vault_collision_held")


@pytest.mark.parametrize("remedy, kind", [
    ("keep_in_inbox", "vault_collision_held"), ("ignore", None),
])
def test_f1_ac6_folder_under_keep_or_ignore_is_ignored(remedy, kind):
    d = _one(_plan([_item()], [_remedy(remedy, folder="../bad", folder_typed=True)]))
    if kind is None:
        _moved(d, DEFAULT_TARGET)
    else:
        assert _held(d, kind)["destination"] == DEFAULT_TARGET


def test_f1_ac10_original_name_in_a_new_folder_is_a_valid_rename():
    d = _one(_plan([_item()], [_rename(name="karte.png", name_typed=True,
                                       folder=MAPS, folder_typed=True)]))
    _moved(d, f"{MAPS}/karte.png")


def test_f2_ac7_a_bad_folder_refuses_one_source_and_plans_the_rest():
    a, b = "100 Inbox/a/karte.png", "100 Inbox/b/plan.png"
    plan = _plan([_item(attachments=[a, b])],
                 [_rename(a, folder="/abs", folder_typed=True)])
    _held(plan.by_source[a], "typed_folder_refused")
    _moved(plan.by_source[b], f"{ASSET}plan.png")


# ── Pass B: the census and the embed (F4) ──────────────────────────────────

def test_f4_ac1_unique_renamed_is_bare_unique_unrenamed_is_untouched():
    a, b = "100 Inbox/a/karte.png", "100 Inbox/b/plan.png"
    plan = _plan([_item(attachments=[a, b])], [_rename(a)])
    assert (plan.by_source[a].embed, plan.by_source[a].qualified_reason) == (
        "karte (2).png", None)
    assert (plan.by_source[b].embed, plan.by_source[b].qualified_reason) == (None, None)


def test_f4_ac2_the_occupier_of_the_original_makes_it_ambiguous():
    """Edge case: moved to a free folder without renaming — the occupier
    still holds `karte.png`."""
    vault = FakeVault([SRC, DEFAULT_TARGET], existing_folders=[MAPS])
    d = _one(_plan([_item()], [_rename(name="karte.png", name_typed=True,
                                       folder=MAPS, folder_typed=True)], vault))
    assert (d.embed, d.qualified_reason) == (f"{MAPS}/karte.png", "ambiguous")


def test_f4_ac2_another_in_run_target_counts_even_when_planned_later():
    """Two passes: B's target is only known after A's outcome is decided."""
    a, b = "100 Inbox/a/karte.png", "100 Inbox/b/foto.png"
    plan = _plan([_item(attachments=[a, b])],
                 [_rename(b, "karte.png", name_typed=True, folder=MAPS, folder_typed=True)])
    assert (plan.by_source[a].embed, plan.by_source[a].qualified_reason) == (
        DEFAULT_TARGET, "ambiguous")
    assert plan.by_source[b].embed == f"{MAPS}/karte.png"


def test_f4_ac3_unrenamed_default_folder_ambiguous_is_qualified():
    vault = FakeVault([SRC, "Atlas/Elsewhere/karte.png"], existing_folders=[ASSET])
    d = _one(_plan([_item()], [], vault))
    assert (d.embed, d.qualified_reason) == (DEFAULT_TARGET, "ambiguous")


def test_f4_ac4_moved_inbox_sources_are_not_counted():
    """Neither the attachment's own inbox copy nor another inbox file this run
    moves away counts: the vault holds two `karte.png`, both in the inbox,
    both leave it (A renamed away, B filed as is) → B is unique."""
    a, b = "100 Inbox/a/karte.png", "100 Inbox/b/karte.png"
    plan = _plan([_item(attachments=[a, b])], [_rename(a)])
    _moved(plan.by_source[a], f"{ASSET}karte (2).png")
    _moved(plan.by_source[b], DEFAULT_TARGET)
    assert (plan.by_source[b].embed, plan.by_source[b].qualified_reason) == (None, None)


def test_f4_census_key_is_nfc_a_decomposed_inbox_source_is_subtracted():
    """The inbox copy is spelled NFD, the target NFC: they are one name to the
    census, so the subtraction must match them."""
    nfd = "100 Inbox/cafe\u0301.png"
    nfc = "caf\u00e9.png"
    assert nfd.rsplit("/", 1)[-1] != nfc
    d = _one(_plan([_item(attachments=[nfd])], [_rename(nfd, nfc, name_typed=True)],
                   FakeVault([nfd], existing_folders=[ASSET])))
    _moved(d, f"{ASSET}{nfc}")
    assert (d.embed, d.qualified_reason) == (nfc, None)


def test_f4_an_undercounting_census_cannot_cancel_another_in_run_target():
    """The census answers 0 for `karte.png`; two sources of the run end up
    named `karte.png` in different folders, so each is ambiguous regardless."""
    class ZeroCensus:
        searches = 0

        def count(self, basename):
            return 0

    a, b = "100 Inbox/a/karte.png", "100 Inbox/b/foto.png"
    vault = FakeVault([a, b], existing_folders=[ASSET, MAPS])
    plan = build_attachment_plan(
        [_item(attachments=[a, b])],
        {b: _rename(b, "karte.png", name_typed=True, folder=MAPS, folder_typed=True)},
        asset_folder=ASSET, inbox_path=INBOX,
        folder_lookup=vault.lookup, census=ZeroCensus(),
    )
    assert (plan.by_source[a].embed, plan.by_source[a].qualified_reason) == (
        DEFAULT_TARGET, "ambiguous")
    assert (plan.by_source[b].embed, plan.by_source[b].qualified_reason) == (
        f"{MAPS}/karte.png", "ambiguous")


def test_f4_ac4_rejected_a_withheld_inbox_copy_stays_and_counts():
    a, b = "100 Inbox/a/karte.png", "100 Inbox/b/karte.png"
    plan = _plan([_item(attachments=[a, b])], [_remedy("keep_in_inbox", a)])
    assert (plan.by_source[b].embed, plan.by_source[b].qualified_reason) == (
        DEFAULT_TARGET, "ambiguous")


def test_a_target_withheld_late_in_pass_a_is_not_counted_in_pass_b():
    """B's would-be target collides with A's; B never moves, so A's name is
    still unique after the run."""
    a, b = "100 Inbox/a/foto.png", "100 Inbox/b/bild.png"
    plan = _plan([_item(attachments=[a, b])],
                 [_rename(a, "karte.png"), _rename(b, "karte.png")])
    _held(plan.by_source[b], "collision")
    assert plan.by_source[a].embed == "karte.png"
    assert plan.by_source[a].qualified_reason is None


def test_f4_ac6_census_unanswered_qualifies():
    vault = FakeVault([SRC], existing_folders=[ASSET], unanswered_names=["karte.png"])
    d = _one(_plan([_item()], [], vault))
    assert (d.embed, d.qualified_reason) == (DEFAULT_TARGET, "unanswered")


def test_unanswered_folder_with_answering_census_follows_the_census():
    vault = FakeVault([SRC], failing_folders=[ASSET])
    d = _one(_plan([_item()], [], vault))
    assert d.unchecked is True
    assert (d.embed, d.qualified_reason) == (None, None)


def test_ignore_onto_occupied_qualifies_with_the_occupiers_path():
    d = _one(_plan([_item()], [_remedy("ignore")], FakeVault([SRC, DEFAULT_TARGET])))
    assert (d.embed, d.qualified_reason) == (DEFAULT_TARGET, "ambiguous")


# ── Owners, order, counters ─────────────────────────────────────────────────

def test_owners_are_complete_for_a_shared_attachment():
    confirmed = [_item(), _item(source_path="dresden.md", id="S02"),
                 _item(source_path="karte.md", id="S03")]
    d = _one(_plan(confirmed))
    assert d.owners == (OWNER, "100 Inbox/dresden.md")


def test_owners_are_complete_on_a_withheld_entry():
    confirmed = [_item(), _item(source_path="dresden.md", id="S02")]
    d = _one(_plan(confirmed, [_remedy("keep_in_inbox")]))
    assert _held(d, "vault_collision_held")["owner_source_items"] == [
        OWNER, "100 Inbox/dresden.md"]


def test_decisions_follow_first_appearance_and_move_ids_start_empty():
    a, b, c = "100 Inbox/a/x.png", "100 Inbox/b/y.png", "100 Inbox/c/z.png"
    plan = _plan([_item(attachments=[b, a]), _item(source_path="o.md", attachments=[c, b])])
    assert [d.source for d in plan.decisions] == [b, a, c]
    assert plan.move_ids_by_origin == {}
    plan.move_ids_by_origin[OWNER] = ["I01"]
    assert plan.move_ids_by_origin == {OWNER: ["I01"]}


def test_no_attachment_makes_no_vault_call():
    vault = FakeVault([])
    plan = _plan([_item(attachments=[])], [], vault)
    assert plan.decisions == []
    assert (plan.folder_listing_calls, plan.basename_searches) == (0, 0)


def test_one_listing_per_folder_one_search_per_basename_none_for_withheld():
    a, b, c = "100 Inbox/a/karte.png", "100 Inbox/b/Karte.png", "100 Inbox/c/plan.png"
    held = "100 Inbox/d/held.png"
    plan = _plan([_item(attachments=[a, b, c, held])],
                 [_rename(b, "karte.png", name_typed=True, folder=MAPS, folder_typed=True),
                  _remedy("keep_in_inbox", held)])
    assert plan.folder_listing_calls == 2          # ASSET and MAPS
    assert plan.basename_searches == 2             # karte.png (folded) and plan.png


def test_plan_from_remedies_reproduces_todays_moves():
    """The migration helper's default vault holds only the inbox copies and a
    free asset folder — the vault the old harnesses assumed."""
    a, b = "100 Inbox/a/karte.png", "100 Inbox/b/karte.png"
    plan = plan_from_remedies([_item(attachments=[a, b])], [_rename(a)],
                              inbox_path=INBOX, asset_folder=ASSET)
    assert [d.target for d in plan.decisions] == [f"{ASSET}karte (2).png", DEFAULT_TARGET]
    assert all(d.unchecked is False and d.folder_created is False for d in plan.decisions)
