#!/usr/bin/env python3
# version: 0.1.0
"""test_039_t4_3_move_builder_projection.py — spec 039 T4.3, K5.

`_build_move_asset_actions(manifest, plan, counter, inbox_path)` is a
projection of the attachment plan (K1): it decides nothing, it reads.

Cases (phase-4.md T4.3 step 2 plus the review carry-forwards):

a. Same fixture as the pre-change builder → the same moves, ids, order and
   skipped entries. The expected values were captured by running the builder
   at 9e2cb307 (before this task) on `_LEGACY_MANIFEST` / `_LEGACY_REMEDIES`,
   not written by hand.
b. The two new withheld kinds reach `skipped_assets` with every owner.
c. `move_ids_by_origin` names EVERY owner of a shared attachment (not
   first-only), and `build_actions` leaves it on the plan.
d. `suppress_moves_for_unfiled_attachments` holds the notes for
   `typed_folder_refused` and `vault_occupied`, still not for
   `vault_collision_held`.
e. `_attachment_suppression_reason` gives each new kind its own sentence —
   never "correct that inbox path".
f. The plan's `[warn]` lines are printed once per run, never re-printed by the
   projection.
g. Through `instruction-render.py main()`: an item without a template does not
   claim a target ahead of a rendered item (its attachment is not planned).
h. The builder's source holds no decision logic.

CON-7: fixtures and fakes only.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from attachment_plan_fakes import FakeVault, plan_from_remedies  # noqa: E402
from lib import render_actions  # noqa: E402
from lib.render_actions import (  # noqa: E402
    _attachment_suppression_reason,
    _build_move_asset_actions,
    build_actions,
    suppress_moves_for_unfiled_attachments,
)

INBOX = "100 Inbox/"
ASSET = "Atlas/290 Assets/295 Attachments/"
CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": ASSET,
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}

A = "100 Inbox/x/photo.png"
B = "100 Inbox/bad/"
C = "100 Inbox/held.png"
D = "100 Inbox/y/photo.png"
E = "100 Inbox/r.png"
F = "100 Inbox/t.png"
G = "100 Inbox/ign.png"

_LEGACY_MANIFEST = [
    {"id": "S01", "item_key": "100 Inbox/a.md", "source_path": "a.md",
     "attachments": [A, B, C]},
    {"id": "S02", "item_key": "100 Inbox/sub/b.md", "source_path": "b.md",
     "attachments": [A, D, E]},
    {"id": "S03", "source_path": "c.md", "attachments": [F, D, G]},
]
_LEGACY_REMEDIES = [
    {"source": C, "remedy": "keep_in_inbox", "proposed_name": None},
    {"source": E, "remedy": "rename", "proposed_name": "renamed.png",
     "name_is_owner_supplied": False},
    {"source": F, "remedy": "rename", "proposed_name": "bad/name.png",
     "name_is_owner_supplied": True},
    {"source": G, "remedy": "ignore", "proposed_name": None},
]

# Captured from the pre-change builder (9e2cb307), counter started at [5].
_EXPECTED_MOVES = [
    {"id": "I06", "action": "move_asset", "source": A,
     "destination": f"{ASSET}photo.png"},
    {"id": "I07", "action": "move_asset", "source": E,
     "destination": f"{ASSET}renamed.png"},
    {"id": "I08", "action": "move_asset", "source": G,
     "destination": f"{ASSET}ign.png"},
]
_EXPECTED_SKIPPED = [
    {"source": B, "destination": None,
     "reason": "the inbox path has no filename",
     "kind": "no_basename", "owner_source_items": ["100 Inbox/a.md"]},
    {"source": C, "destination": f"{ASSET}held.png",
     "reason": ("kept in inbox: the owner chose not to file it over the "
                f"occupied destination `{ASSET}held.png`"),
     "kind": "vault_collision_held", "owner_source_items": ["100 Inbox/a.md"]},
    {"source": D, "destination": f"{ASSET}photo.png",
     "reason": ("destination collision: it also resolves to "
                f"`{ASSET}photo.png`, already claimed by `{A}`"),
     "kind": "collision",
     "owner_source_items": ["100 Inbox/sub/b.md", "100 Inbox/c.md"]},
    {"source": F, "destination": None,
     "reason": ("typed name refused: `bad/name.png` contains a path "
                "separator, which is not allowed in a filename"),
     "refusal_reason": "separator_present",
     "kind": "typed_name_refused", "owner_source_items": ["100 Inbox/c.md"]},
]
_EXPECTED_COUNTER_END = 8


def _legacy_plan():
    return plan_from_remedies(_LEGACY_MANIFEST, _LEGACY_REMEDIES,
                              inbox_path=INBOX, asset_folder=ASSET)


# ── a ─────────────────────────────────────────────────────────────────────

def test_a_projection_matches_the_pre_change_builder():
    counter = [5]
    moves, skipped, _ids = _build_move_asset_actions(
        _LEGACY_MANIFEST, _legacy_plan(), counter, INBOX)
    assert moves == _EXPECTED_MOVES
    assert skipped == _EXPECTED_SKIPPED
    assert counter == [_EXPECTED_COUNTER_END]


def test_a_entry_key_order_matches_the_pre_change_builder():
    """JSON consumers serialise these dicts; key order is part of the bytes."""
    _moves, skipped, _ids = _build_move_asset_actions(
        _LEGACY_MANIFEST, _legacy_plan(), [5], INBOX)
    assert [list(s) for s in skipped] == [list(s) for s in _EXPECTED_SKIPPED]


def test_a_unrendered_attachment_emits_nothing():
    """The plan covers a source only the confirmed list names → no move, no
    skipped entry: the projection filters by the manifest, as today."""
    confirmed = _LEGACY_MANIFEST + [
        {"id": "S09", "item_key": "100 Inbox/z.md", "attachments": ["100 Inbox/z.png"]},
    ]
    plan = plan_from_remedies(confirmed, _LEGACY_REMEDIES,
                              inbox_path=INBOX, asset_folder=ASSET)
    moves, skipped, _ids = _build_move_asset_actions(_LEGACY_MANIFEST, plan, [5], INBOX)
    assert moves == _EXPECTED_MOVES
    assert skipped == _EXPECTED_SKIPPED


def test_a_withheld_owners_are_filtered_to_the_manifest():
    """An owner whose item did not render is not named on the skipped entry."""
    confirmed = _LEGACY_MANIFEST + [
        {"id": "S09", "item_key": "100 Inbox/z.md", "attachments": [D]},
    ]
    plan = plan_from_remedies(confirmed, _LEGACY_REMEDIES,
                              inbox_path=INBOX, asset_folder=ASSET)
    assert "100 Inbox/z.md" in plan.by_source[D].withheld["owner_source_items"]
    _moves, skipped, _ids = _build_move_asset_actions(_LEGACY_MANIFEST, plan, [5], INBOX)
    assert skipped == _EXPECTED_SKIPPED


def test_a_a_manifest_attachment_the_plan_does_not_cover_is_a_wiring_error():
    plan = plan_from_remedies(_LEGACY_MANIFEST[:1], [], inbox_path=INBOX, asset_folder=ASSET)
    with pytest.raises(ValueError, match="not in the attachment plan"):
        _build_move_asset_actions(_LEGACY_MANIFEST, plan, [0], INBOX)


def test_a_build_actions_without_a_plan_refuses_a_manifest_with_attachments():
    """No plan + attachments → ValueError, never a fabricated "nothing known"
    plan that would flag every move unchecked and qualify every embed."""
    manifest = [dict(m, rendered_file=f"r{i}.md", title=f"T{i}",
                     destination="Atlas/202 Notes/")
                for i, m in enumerate(_LEGACY_MANIFEST)]
    assert any(m.get("attachments") for m in manifest)
    with pytest.raises(ValueError, match="attachment_plan is required"):
        build_actions(manifest, [], [], [], CFG)


def test_a_build_actions_without_a_plan_proceeds_when_nothing_is_attached():
    """No plan + no attachments → nothing to plan, the run proceeds."""
    manifest = [{"id": "S01", "item_key": "100 Inbox/n.md", "source_path": "n.md",
                 "title": "N", "rendered_file": "r.md",
                 "destination": "Atlas/202 Notes/", "attachments": []}]
    actions, skipped = build_actions(manifest, [], [], [], CFG)
    kinds = [a["action"] for a in actions]
    assert "move_note" in kinds
    assert "move_asset" not in kinds
    assert skipped == []


# ── b ─────────────────────────────────────────────────────────────────────

SHARED = "100 Inbox/s/karte.png"
OWNER_1 = "100 Inbox/one.md"
OWNER_2 = "100 Inbox/two.md"


def _two_owner_manifest(attachments=(SHARED,)) -> list[dict]:
    return [
        {"id": "S01", "item_key": OWNER_1, "source_path": "one.md", "title": "One",
         "rendered_file": "r1.md", "destination": "Atlas/202 Notes/",
         "attachments": list(attachments)},
        {"id": "S02", "item_key": OWNER_2, "source_path": "two.md", "title": "Two",
         "rendered_file": "r2.md", "destination": "Atlas/202 Notes/",
         "attachments": list(attachments)},
    ]


def _typed_folder_remedy(folder="Atlas/Maps/") -> dict:
    return {"source": SHARED, "remedy": "rename", "proposed_name": "karte (2).png",
            "name_is_owner_supplied": False, "proposed_dir": folder,
            "dir_is_owner_supplied": True}


def _occupied_vault() -> FakeVault:
    return FakeVault([SHARED, f"{ASSET}karte.png"])


def test_b_typed_folder_refused_carries_every_owner():
    manifest = _two_owner_manifest()
    plan = plan_from_remedies(manifest, [_typed_folder_remedy()],
                              inbox_path=INBOX, asset_folder=ASSET)
    moves, skipped, ids = _build_move_asset_actions(manifest, plan, [0], INBOX)
    assert moves == [] and ids == {}
    assert [(s["kind"], s["refusal_reason"], s["owner_source_items"]) for s in skipped] == [
        ("typed_folder_refused", "trailing_separator", [OWNER_1, OWNER_2]),
    ]


def test_b_vault_occupied_carries_every_owner():
    manifest = _two_owner_manifest()
    plan = plan_from_remedies(manifest, [], inbox_path=INBOX, asset_folder=ASSET,
                              vault=_occupied_vault())
    moves, skipped, _ids = _build_move_asset_actions(manifest, plan, [0], INBOX)
    assert moves == []
    assert [(s["kind"], s["destination"], s["owner_source_items"]) for s in skipped] == [
        ("vault_occupied", f"{ASSET}karte.png", [OWNER_1, OWNER_2]),
    ]


# ── c ─────────────────────────────────────────────────────────────────────

def test_c_move_ids_by_origin_names_every_owner():
    manifest = _two_owner_manifest([SHARED, "100 Inbox/s/other.png"])
    plan = plan_from_remedies(manifest, [], inbox_path=INBOX, asset_folder=ASSET)
    moves, _skipped, ids = _build_move_asset_actions(manifest, plan, [3], INBOX)
    assert [m["id"] for m in moves] == ["I04", "I05"]
    assert ids == {OWNER_1: ["I04", "I05"], OWNER_2: ["I04", "I05"]}


def test_c_build_actions_leaves_move_ids_on_the_plan():
    manifest = _two_owner_manifest()
    plan = plan_from_remedies(manifest, [], inbox_path=INBOX, asset_folder=ASSET)
    actions, _skipped = build_actions(manifest, [], [], [], CFG, attachment_plan=plan)
    move_id = [a["id"] for a in actions if a["action"] == "move_asset"]
    assert len(move_id) == 1
    assert plan.move_ids_by_origin == {OWNER_1: move_id, OWNER_2: move_id}


def test_c_withheld_moves_get_no_id():
    manifest = _two_owner_manifest()
    plan = plan_from_remedies(manifest, [], inbox_path=INBOX, asset_folder=ASSET,
                              vault=_occupied_vault())
    build_actions(manifest, [], [], [], CFG, attachment_plan=plan)
    assert plan.move_ids_by_origin == {}


# ── d / e ─────────────────────────────────────────────────────────────────

def _held_titles(manifest, plan):
    actions, skipped = build_actions(manifest, [], [], [], CFG, attachment_plan=plan)
    kept, suppressions = suppress_moves_for_unfiled_attachments(actions, skipped)
    filed = [a["title"] for a in kept if a["action"] == "move_note"]
    return filed, suppressions


def test_d_typed_folder_refused_holds_the_notes():
    manifest = _two_owner_manifest()
    plan = plan_from_remedies(manifest, [_typed_folder_remedy()],
                              inbox_path=INBOX, asset_folder=ASSET)
    filed, suppressions = _held_titles(manifest, plan)
    assert filed == []
    assert [s["kind"] for s in suppressions] == ["typed_folder_refused"]


def test_d_vault_occupied_holds_the_notes():
    manifest = _two_owner_manifest()
    plan = plan_from_remedies(manifest, [], inbox_path=INBOX, asset_folder=ASSET,
                              vault=_occupied_vault())
    filed, suppressions = _held_titles(manifest, plan)
    assert filed == []
    assert [s["kind"] for s in suppressions] == ["vault_occupied"]


def test_d_vault_collision_held_still_files_the_notes():
    manifest = _two_owner_manifest()
    plan = plan_from_remedies(
        manifest, [{"source": SHARED, "remedy": "keep_in_inbox", "proposed_name": None}],
        inbox_path=INBOX, asset_folder=ASSET, vault=_occupied_vault())
    filed, suppressions = _held_titles(manifest, plan)
    assert filed == ["One", "Two"]
    assert suppressions == []


@pytest.mark.parametrize("kind,reason,remedy_words", [
    ("typed_folder_refused",
     "typed folder refused: `Atlas/Maps/` ends in a path separator",
     "retype a usable folder"),
    ("vault_occupied",
     "target occupied: the vault already holds `X/karte.png` at the target "
     "`X/karte.png`, so the attachment is not filed over it",
     "free the target"),
])
def test_e_new_kinds_get_their_own_sentence(kind, reason, remedy_words):
    entry = {"source": SHARED, "destination": "X/karte.png", "reason": reason,
             "kind": kind, "owner_source_items": [OWNER_1]}
    sentence = _attachment_suppression_reason(entry, 2)
    assert sentence.startswith(f"`{SHARED}` cannot be filed — {reason} — ")
    assert "the 2 notes that embed it are not filed either" in sentence
    assert remedy_words in sentence
    assert "inbox path" not in sentence


def test_e_the_sentences_differ_per_kind():
    entry = {"source": SHARED, "destination": "X", "reason": "r",
             "owner_source_items": [OWNER_1]}
    sentences = {
        kind: _attachment_suppression_reason(dict(entry, kind=kind), 1)
        for kind in ("typed_folder_refused", "vault_occupied",
                     "typed_name_refused", "no_basename")
    }
    assert len(set(sentences.values())) == 4


# ── f ─────────────────────────────────────────────────────────────────────

def test_f_warn_lines_print_once_per_run(capsys):
    manifest = [dict(m, rendered_file=f"r{i}.md", title=f"T{i}",
                     destination="Atlas/202 Notes/")
                for i, m in enumerate(_LEGACY_MANIFEST)]
    plan = plan_from_remedies(manifest, _LEGACY_REMEDIES,
                              inbox_path=INBOX, asset_folder=ASSET)
    build_actions(manifest, [], [], [], CFG, attachment_plan=plan)
    warns = [ln for ln in capsys.readouterr().err.splitlines() if "[warn]" in ln]
    assert len(warns) == 2, warns
    assert len(set(warns)) == 2, warns


# ── g ─────────────────────────────────────────────────────────────────────

def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


IR = _load("instruction_render_t039_t4_3", "instruction-render.py")


def _item(item_id, source_path, attachments, *, template="templates/atomic.md"):
    return {
        "id": item_id, "action": None, "title": item_id, "template": template,
        "source_path": source_path, "tags": [], "parent_moc": "",
        "parent_mocs": [], "destination": "Atlas/202 Notes/", "summary": "",
        "attachments": attachments, "candidate_mocs": [],
    }


def _run_main(monkeypatch, tmp_path, confirmed) -> dict:
    sf = tmp_path / "suggestions.json"
    sf.write_text(json.dumps({"confirmed_items": confirmed, "daily_updates": [],
                              "skipped": []}), encoding="utf-8")
    cf = tmp_path / "vault-config.yaml"
    cf.write_text("", encoding="utf-8")
    monkeypatch.setattr(IR, "load_config", lambda _p: dict(CFG, **{
        "callouts.editable": ["NOTE"]}))
    monkeypatch.setattr(IR, "KadoClient", lambda: MagicMock())
    monkeypatch.setattr(IR, "read_template", lambda _c, _r: "# {{title}}\n")
    monkeypatch.setattr(IR, "read_note_body", lambda *_a, **_kw: "")
    monkeypatch.setattr(IR, "render_via_script", lambda *_a, **_kw: "body\n")
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["instruction-render.py", "--suggestions", str(sf),
                                      "--output-dir", str(out), "--config", str(cf)])
    assert IR.main() == 0
    return json.loads((out / "instructions.json").read_text(encoding="utf-8"))


def test_g_an_unrendered_item_claims_no_target(monkeypatch, tmp_path):
    instr_only = "100 Inbox/a/photo.png"
    rendered = "100 Inbox/b/photo.png"
    confirmed = [
        _item("S01", "a.md", [instr_only], template=""),
        _item("S02", "b.md", [rendered]),
    ]
    instr = _run_main(monkeypatch, tmp_path, confirmed)
    moves = [(a["source"], a["destination"]) for a in instr["actions"]
             if a["action"] == "move_asset"]
    assert moves == [(rendered, f"{ASSET}photo.png")]
    assert "skipped_assets" not in instr.get("tomo", {})


# ── h ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("needle", ["check_typed_name", "remedy ==", "claimed"])
def test_h_the_builder_holds_no_decision_logic(needle):
    assert needle not in inspect.getsource(render_actions._build_move_asset_actions)
