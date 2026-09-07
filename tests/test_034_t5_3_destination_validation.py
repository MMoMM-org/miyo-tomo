#!/usr/bin/env python3
# version: 0.2.0
"""test_034_t5_3_destination_validation.py — spec 034 T5.3.

The Pass-2 half of PRD Feature 7. Pass 1 (T5.2) proposes a distinct name on a
clash and is advisory: the user edits the document afterwards, so nothing it
proposes binds. This is the guard that binds `[ref: SDD/ADR-4]`. If it misses,
two `move_note` actions reach Hashi and one note silently overwrites another.

What it must do, and what each block below pins:

  1. Two approved items claiming one destination -> **neither** is emitted.
     Not first-claim-wins. `_build_move_asset_actions` is the reporting shape
     this follows and its resolution is the opposite: there, the first
     attachment keeps the destination. Here, choosing between two names the
     user set deliberately would itself be a guess.
  2. A destination already occupied in the vault -> the same treatment.
  3. Two names differing only in case are one destination (CON-6), in both
     halves, and the report SAYS the difference is case — on a case-sensitive
     filesystem the two are visibly different names and "duplicate" alone
     would read as a bug in Tomo.
  4. A dropped move takes its paired `delete_source` with it. Emitting the
     delete without the move would delete the user's inbox note while
     refusing to file it — the guard would cause the loss it exists to
     prevent.
  5. The guard is stateless: clashing input then corrected input, and the
     reverse. Nothing may outlive the input that caused it.
  6. A run with no clash emits the recorded baseline, whole-list.
  7. The user's own edit to a Pass-1 disambiguated name is honoured verbatim
     `[ref: PRD/AC Feature 7, Pass-1 criterion 2]`.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
GOLDEN_DIR = TESTS_DIR / "fixtures" / "034-t5-3-actions-golden"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.item_key import to_filename  # noqa: E402
from lib.render_actions import (  # noqa: E402
    build_actions,
    make_folder_listing,
    validate_destinations,
)
from lib.render_md import render_instructions_md  # noqa: E402

NOTES = "Atlas/202 Notes/"
INBOX = "100 Inbox/"
DRESDEN_PLACES = "100 Inbox/Places/Dresden.md"
DRESDEN_REISE = "100 Inbox/Reise/Dresden.md"
ROOT_NOTE = "100 Inbox/Root Note.md"

CFG = {
    "concepts.inbox": INBOX,
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
}


# ---------------------------------------------------------------------------
# Fakes and builders
# ---------------------------------------------------------------------------

class FakeKado:
    """`list_dir` only — the one call the vault half makes.

    `occupied` is the set of vault paths that already hold a note. `raises`
    turns every call into a transport failure: the client constructs, the
    calls fail. `calls` records every folder listed, so the per-folder cache
    is observable.
    """

    def __init__(self, occupied: set[str] | None = None, raises: bool = False):
        self.occupied = occupied or set()
        self.raises = raises
        self.calls: list[str] = []

    def list_dir(self, path: str, *, depth: int | None = None, limit: int = 500):
        self.calls.append(path)
        if self.raises:
            raise RuntimeError("kado unreachable")
        prefix = path.rstrip("/") + "/"
        return [
            {"path": p, "type": "file", "modified": 1716300000000, "size": 100}
            for p in sorted(self.occupied)
            if p.startswith(prefix) and "/" not in p[len(prefix):]
        ]


def _atomic(item_key: str, title: str, *, idx: int, keep_source: bool = False,
            audio_peer: str | None = None, location: str = NOTES) -> tuple[dict, dict]:
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
        "attachments": [],
    }
    if audio_peer:
        manifest["audio_peer"] = audio_peer
    confirmed = {
        "id": f"S{idx:02d}",
        "title": title,
        "source_path": stem,
        "item_key": item_key,
        "parent_mocs": [],
    }
    if keep_source:
        confirmed["keep_source"] = True
    return manifest, confirmed


def _actions(pairs: list[tuple[dict, dict]], **kw) -> list[dict]:
    manifest = [m for m, _ in pairs]
    confirmed = [c for _, c in pairs]
    acts, _skipped = build_actions(
        manifest, confirmed, kw.pop("daily_updates", []), kw.pop("skipped", []),
        CFG, kado_client=None,
    )
    return acts


def _moves(actions: list[dict]) -> list[dict]:
    return [a for a in actions if a.get("action") == "move_note"]


def _deletes(actions: list[dict]) -> list[str]:
    return [a["source_path"] for a in actions if a.get("action") == "delete_source"]


TWO_NAMESAKES = [
    _atomic(DRESDEN_PLACES, "Dresden", idx=1),
    _atomic(DRESDEN_REISE, "Dresden", idx=2),
    _atomic(ROOT_NOTE, "Root note takeaway", idx=3),
]

DISTINCT = [
    _atomic(DRESDEN_PLACES, "Dresden Frauenkirche", idx=1),
    _atomic(DRESDEN_REISE, "Dresden Elbufer", idx=2),
    _atomic(ROOT_NOTE, "Root note takeaway", idx=3),
]


# ---------------------------------------------------------------------------
# 1. Two approved items, one destination — neither is emitted
# ---------------------------------------------------------------------------

def test_two_items_claiming_one_destination_lose_both_moves():
    kept, clashes = validate_destinations(_actions(TWO_NAMESAKES))
    destinations = [m["destination"] for m in _moves(kept)]
    assert destinations == [f"{NOTES}Root note takeaway.md"], (
        "both Dresden claimants must be dropped, not one — first-claim-wins "
        f"is the attachment guard's rule, not this one: {destinations}"
    )
    assert len(clashes) == 1, clashes
    dropped_titles = [d["title"] for d in clashes[0]["dropped"]]
    assert dropped_titles == ["Dresden", "Dresden"], dropped_titles


def test_the_clash_report_names_both_claimants_by_their_source_notes():
    _kept, clashes = validate_destinations(_actions(TWO_NAMESAKES))
    sources = sorted(d["source_inbox_item"] for d in clashes[0]["dropped"])
    assert sources == [DRESDEN_PLACES, DRESDEN_REISE], (
        "the user cannot resolve a clash without being told which two notes "
        f"caused it: {sources}"
    )
    assert clashes[0]["destination"] == f"{NOTES}Dresden.md"
    assert clashes[0]["kind"] == "run_collision"


def test_an_unrelated_item_in_the_same_folder_is_untouched():
    kept, _clashes = validate_destinations(_actions(TWO_NAMESAKES))
    assert [a["id"] for a in _moves(kept)] == ["I03"], (
        "one clash must not hold up an unrelated move into the same folder"
    )


# ---------------------------------------------------------------------------
# 2. A destination already occupied in the vault
# ---------------------------------------------------------------------------

def test_a_destination_occupied_in_the_vault_is_not_emitted():
    kado = FakeKado(occupied={f"{NOTES}Dresden.md"})
    actions = _actions([_atomic(DRESDEN_PLACES, "Dresden", idx=1),
                        _atomic(ROOT_NOTE, "Root note takeaway", idx=2)])
    kept, clashes = validate_destinations(actions, make_folder_listing(kado))
    assert [m["destination"] for m in _moves(kept)] == [f"{NOTES}Root note takeaway.md"]
    assert len(clashes) == 1 and clashes[0]["kind"] == "vault_collision"
    assert clashes[0]["vault_note"] == f"{NOTES}Dresden.md"


def test_no_folder_listing_leaves_the_run_internal_half_working():
    """ADR-4 makes the vault half best-effort; the run half is not."""
    kept, clashes = validate_destinations(_actions(TWO_NAMESAKES), None)
    assert len(_moves(kept)) == 1 and len(clashes) == 1


def test_an_unreachable_kado_never_fabricates_a_clash():
    kado = FakeKado(raises=True)
    kept, clashes = validate_destinations(_actions(DISTINCT), make_folder_listing(kado))
    assert len(_moves(kept)) == 3 and clashes == [], (
        "a transport failure is not a collision — it must cost the check, "
        "never three legitimate moves"
    )


def test_one_listing_per_folder_however_the_folder_is_spelled():
    """T5.2 shipped a raw-`location` cache and fixed it in `00eb712`.

    Asserted on `make_folder_listing` directly, because that is where the
    guarantee lives: the pass derives the folder from the composed
    destination, which `_dest_join` has already normalised, so driving this
    through the pass would pass whether the cache key is normalised or not.
    """
    kado = FakeKado(occupied=set())
    listing = make_folder_listing(kado)
    listing(NOTES)
    listing(NOTES.rstrip("/"))
    listing(f"{NOTES}//")
    assert len(kado.calls) == 1, (
        f"one folder, however spelled, is one listing: {kado.calls}"
    )


def test_the_pass_lists_each_destination_folder_once():
    kado = FakeKado(occupied=set())
    actions = _actions([
        _atomic(DRESDEN_PLACES, "Dresden", idx=1, location=NOTES),
        _atomic(DRESDEN_REISE, "Elbe", idx=2, location=NOTES.rstrip("/")),
        _atomic(ROOT_NOTE, "Root note takeaway", idx=3, location=NOTES),
    ])
    validate_destinations(actions, make_folder_listing(kado))
    assert kado.calls == [NOTES], (
        f"three claims into one folder must cost one listing: {kado.calls}"
    )


# ---------------------------------------------------------------------------
# 3. Case folding (CON-6) — both halves, and the report says so
# ---------------------------------------------------------------------------

def test_two_run_names_differing_only_in_case_are_one_destination():
    actions = _actions([
        _atomic(DRESDEN_PLACES, "Dresden", idx=1),
        _atomic(DRESDEN_REISE, "dresden", idx=2),
        _atomic(ROOT_NOTE, "Root note takeaway", idx=3),
    ])
    kept, clashes = validate_destinations(actions)
    assert len(_moves(kept)) == 1, (
        "the filesystem may fold these into one file; folding is the fail-safe "
        "direction — a false clash costs a rename, a missed one costs a note"
    )
    assert clashes[0]["case_only"] is True


def test_a_vault_note_differing_only_in_case_is_a_clash():
    kado = FakeKado(occupied={f"{NOTES}dresden.md"})
    actions = _actions([_atomic(DRESDEN_PLACES, "Dresden", idx=1)])
    kept, clashes = validate_destinations(actions, make_folder_listing(kado))
    assert _moves(kept) == []
    assert clashes[0]["case_only"] is True
    assert clashes[0]["vault_note"] == f"{NOTES}dresden.md", (
        "the report must show the vault's own spelling, not the claimant's"
    )


def test_a_case_only_clash_says_the_difference_is_case():
    actions = _actions([
        _atomic(DRESDEN_PLACES, "Dresden", idx=1),
        _atomic(DRESDEN_REISE, "dresden", idx=2),
    ])
    _kept, clashes = validate_destinations(actions)
    assert "only in case" in clashes[0]["reason"], clashes[0]["reason"]
    assert "Dresden.md" in clashes[0]["reason"] and "dresden.md" in clashes[0]["reason"], (
        "both spellings must appear — on a case-sensitive filesystem these are "
        f"two visibly different names: {clashes[0]['reason']}"
    )


def test_an_exact_clash_does_not_claim_a_case_difference():
    _kept, clashes = validate_destinations(_actions(TWO_NAMESAKES))
    assert clashes[0]["case_only"] is False
    assert "only in case" not in clashes[0]["reason"]


def test_folding_uses_casefold_not_lower():
    """These are German notes: `ß` folds to `ss`, `.lower()` leaves it alone."""
    actions = _actions([
        _atomic("100 Inbox/A/Strasse.md", "Strasse", idx=1),
        _atomic("100 Inbox/B/Strasse.md", "Straße", idx=2),
    ])
    kept, clashes = validate_destinations(actions)
    assert _moves(kept) == [] and len(clashes) == 1, (
        "casefold() folds ß to ss; lower() does not, and would let these two "
        "reach the executor"
    )


# ---------------------------------------------------------------------------
# 4. A dropped move takes its paired delete_source with it
# ---------------------------------------------------------------------------

def test_a_dropped_move_withdraws_the_delete_of_its_origin():
    kept, _clashes = validate_destinations(_actions(TWO_NAMESAKES))
    remaining = _deletes(kept)
    assert DRESDEN_PLACES not in remaining and DRESDEN_REISE not in remaining, (
        "emitting the delete without the move deletes the user's inbox note "
        f"while refusing to file it: {remaining}"
    )
    assert ROOT_NOTE in remaining, (
        "the unaffected item's own delete must survive"
    )


def test_a_dropped_move_withdraws_its_audio_peer_delete():
    peer = "100 Inbox/Places/Dresden.m4a"
    actions = _actions([
        _atomic(DRESDEN_PLACES, "Dresden", idx=1, audio_peer=peer),
        _atomic(DRESDEN_REISE, "Dresden", idx=2),
    ])
    assert peer in _deletes(actions), "fixture no longer emits the peer delete"
    kept, _clashes = validate_destinations(actions)
    assert peer not in _deletes(kept), (
        "the audio peer of an unfiled origin must stay in the inbox with it"
    )


def test_a_partially_dropped_origin_keeps_its_surviving_atomic_and_loses_its_delete():
    """Two atomics from one note; one clashes. The other is still filed, but
    the origin is no longer fully consumed, so its delete must not fire."""
    m1, c1 = _atomic(DRESDEN_PLACES, "Dresden", idx=1)
    m2 = dict(m1)
    m2["title"] = "Dresden Elbufer"
    m2["rendered_file"] = "2026-09-07_1004_dresden-elbufer.md"
    c2 = dict(c1)
    c2["id"] = "S04"
    c2["title"] = "Dresden Elbufer"
    actions = _actions([(m1, c1), (m2, c2), _atomic(DRESDEN_REISE, "Dresden", idx=2)])
    assert DRESDEN_PLACES in _deletes(actions), "fixture no longer emits the delete"
    kept, _clashes = validate_destinations(actions)
    assert [m["destination"] for m in _moves(kept)] == [f"{NOTES}Dresden Elbufer.md"]
    assert DRESDEN_PLACES not in _deletes(kept), (
        "an origin whose atomics are not all filed must keep its source"
    )


def test_an_unrelated_delete_of_the_same_name_is_not_withdrawn():
    """The withdrawal joins on the origin path, not on a bare filename."""
    actions = _actions(
        TWO_NAMESAKES,
        skipped=[{
            "id": "S09", "source_path": "Dresden",
            "item_key": "100 Inbox/Alt/Dresden.md",
            "disposition": "delete_source",
        }],
    )
    kept, _clashes = validate_destinations(actions)
    assert "100 Inbox/Alt/Dresden.md" in _deletes(kept), (
        "a namesake the user explicitly marked for deletion is a different "
        "note and keeps its delete"
    )


# ---------------------------------------------------------------------------
# 5. The guard is stateless
# ---------------------------------------------------------------------------

def test_the_guard_carries_nothing_between_invocations():
    clashing = _actions(TWO_NAMESAKES)
    corrected = _actions(DISTINCT)

    kept_a, clashes_a = validate_destinations(clashing)
    assert len(_moves(kept_a)) == 1 and len(clashes_a) == 1

    kept_b, clashes_b = validate_destinations(corrected)
    assert len(_moves(kept_b)) == 3 and clashes_b == [], (
        "a suppression that outlives the input that caused it would make the "
        "halt unrecoverable without restarting the run"
    )

    # And the other way round — a clean first call must not license the second.
    kept_c, clashes_c = validate_destinations(_actions(DISTINCT))
    kept_d, clashes_d = validate_destinations(_actions(TWO_NAMESAKES))
    assert len(_moves(kept_c)) == 3 and clashes_c == []
    assert len(_moves(kept_d)) == 1 and len(clashes_d) == 1


def test_the_vault_half_is_stateless_too():
    kado = FakeKado(occupied={f"{NOTES}Dresden.md"})
    one = _actions([_atomic(DRESDEN_PLACES, "Dresden", idx=1)])
    two = _actions([_atomic(DRESDEN_PLACES, "Dresden Frauenkirche", idx=1)])
    assert _moves(validate_destinations(one, make_folder_listing(kado))[0]) == []
    kept, clashes = validate_destinations(two, make_folder_listing(kado))
    assert len(_moves(kept)) == 1 and clashes == []


# ---------------------------------------------------------------------------
# 6. A run with no clash emits exactly what it emits today
# ---------------------------------------------------------------------------

def _golden() -> dict:
    return json.loads((GOLDEN_DIR / "actions.json").read_text(encoding="utf-8"))


def _golden_input() -> dict:
    return json.loads((GOLDEN_DIR / "input.json").read_text(encoding="utf-8"))


def _build_golden_actions() -> list[dict]:
    data = _golden_input()
    actions, _skipped = build_actions(
        data["manifest"], data["confirmed"], data["daily_updates"],
        data["skipped"], data["cfg"], kado_client=None,
    )
    return actions


def test_build_actions_still_emits_the_recorded_baseline():
    """The baseline was recorded at 9afcf73, before any T5.3 code existed."""
    assert _build_golden_actions() == _golden()["actions"]


def test_the_validation_pass_is_a_no_op_on_a_run_without_a_clash():
    kept, clashes = validate_destinations(_build_golden_actions())
    assert clashes == []
    assert kept == _golden()["actions"], (
        "whole-list comparison, not selected fields — a guard that quietly "
        "reorders or rewrites a clean run is a regression"
    )


def test_the_vault_half_is_a_no_op_when_the_folder_is_free():
    kado = FakeKado(occupied={f"{NOTES}Etwas anderes.md"})
    kept, clashes = validate_destinations(
        _build_golden_actions(), make_folder_listing(kado)
    )
    assert clashes == [] and kept == _golden()["actions"]


# ---------------------------------------------------------------------------
# 7. The user's own edit to a Pass-1 disambiguated name is honoured
#    [ref: PRD/AC Feature 7, Pass-1 criterion 2] — relocated from T5.2
# ---------------------------------------------------------------------------

RE_SUGGESTED_NAME = re.compile(r"^\*\*Suggested name:\*\* (.+)$", re.MULTILINE)


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _pass1_document(work: Path) -> str:
    """Drive the real Pass-1 reducer + renderer over the two namesakes."""
    reducer = _load("suggestions_reducer_t5_3", "suggestions-reducer.py")
    items_dir = work / "items"
    items_dir.mkdir(exist_ok=True)
    state_path = work / "inbox-state.jsonl"
    for item_key in (DRESDEN_PLACES, DRESDEN_REISE):
        stem = item_key.rsplit("/", 1)[-1][:-3]
        for status in ("pending", "running", "done"):
            subprocess.run([
                sys.executable, str(SCRIPTS_DIR / "state-update.py"),
                "--state", str(state_path), "--item-key", item_key,
                "--stem", stem, "--path", item_key, "--status", status,
                "--run-id", "t5-3-edit",
            ], check=True, capture_output=True)
        (items_dir / to_filename(item_key)).write_text(json.dumps({
            "schema_version": "1", "stem": stem, "item_key": item_key,
            "path": item_key, "type": "fleeting_note", "type_confidence": 0.9,
            "issues": [], "force_atomic": False,
            "actions": [{
                "kind": "create_atomic_note", "source_stem": stem,
                "suggested_title": "Dresden", "template": "Atomic Note.md",
                "location": NOTES, "candidate_mocs": [], "tags_to_add": [],
                "atomic_note_worthiness": 0.85, "classification": None,
                "force_atomic": False,
            }],
        }, ensure_ascii=False), encoding="utf-8")

    doc_path = work / "suggestions-doc.json"
    real_argv = sys.argv
    try:
        sys.argv = [
            "suggestions-reducer.py", "--state", str(state_path),
            "--items-dir", str(items_dir), "--run-id", "t5-3-edit",
            "--profile", "miyo", "--output", str(doc_path),
            "--shared-ctx", str(work / "absent-shared-ctx.json"),
            "--resolved-attachments", str(work / "absent-resolved.json"),
            "--tag-handler-groups-dir", str(work / "absent-thg"),
            "--threshold", "1", "--no-kado",
        ]
        assert reducer.main() == 0
    finally:
        sys.argv = real_argv

    md_path = work / "suggestions.md"
    subprocess.run([
        sys.executable, str(SCRIPTS_DIR / "suggestions-render.py"),
        "--input", str(doc_path), "--output", str(md_path),
    ], check=True, capture_output=True)
    return md_path.read_text(encoding="utf-8")


def test_the_users_edit_to_a_pass1_adjusted_name_is_used_verbatim(tmp_path):
    doc = _pass1_document(tmp_path)
    names = RE_SUGGESTED_NAME.findall(doc)
    adjusted = [n for n in names if n != "Dresden"]
    assert adjusted, f"Pass 1 no longer disambiguates: {names}"

    user_name = "Dresden Altstadt"
    edited = doc.replace(
        f"**Suggested name:** {adjusted[0]}", f"**Suggested name:** {user_name}"
    ).replace("- [ ] Approved", "- [x] Approved")
    approved = tmp_path / "suggestions-approved.md"
    approved.write_text(edited, encoding="utf-8")

    parsed = json.loads(subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "suggestion-parser.py"),
         "--file", str(approved)],
        check=True, capture_output=True, text=True,
    ).stdout)
    confirmed = parsed["confirmed_items"]
    assert len(confirmed) == 2, confirmed

    manifest = [{
        "action": "create_atomic_note",
        "title": it["title"],
        "rendered_file": f"2026-09-07_10{i:02d}_note.md",
        "destination": it.get("destination") or NOTES,
        "source_path": it.get("source_path"),
        "item_key": it.get("item_key"),
        "parent_mocs": [], "tags": [], "attachments": [],
    } for i, it in enumerate(confirmed)]
    actions, _ = build_actions(manifest, confirmed, [], [], CFG, kado_client=None)
    kept, clashes = validate_destinations(actions)

    assert clashes == [], f"the edited names no longer clash: {clashes}"
    assert sorted(m["destination"] for m in _moves(kept)) == sorted([
        f"{NOTES}Dresden.md", f"{NOTES}{user_name}.md",
    ]), (
        "Pass 2 must use the name the user typed — not re-disambiguate it, "
        "not revert to Pass 1's proposal, and not treat an adjusted name as "
        "special in any way"
    )


# ---------------------------------------------------------------------------
# 8. The clash reaches the user
# ---------------------------------------------------------------------------

def test_the_clash_is_reported_in_the_instructions_document():
    kept, clashes = validate_destinations(_actions(TWO_NAMESAKES))
    md = render_instructions_md(
        kept,
        {"generated": "2026-09-07T10:00:00+02:00", "destination_clashes": clashes},
        CFG,
    )
    assert "Not filed" in md, md
    for source in (DRESDEN_PLACES, DRESDEN_REISE):
        assert source in md, f"the report must name {source}\n{md}"
    assert f"{NOTES}Dresden.md" in md
    assert "re-run" in md, "the user must be told the halt is recoverable"
    headings = re.findall(r"^## (.+)$", md, re.MULTILINE)
    assert headings and "Not filed" in headings[0], (
        "the clash block must be the FIRST section — a user who stops reading "
        f"after the first heading must still have seen it: {headings}"
    )


def _clash_block(md: str) -> list[str]:
    """The clash section's lines, heading included, up to the next section."""
    lines = md.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("## Not filed"))
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return lines[start:end]


def test_a_vault_clash_is_reported_without_claiming_a_second_item():
    """A vault collision names ONE item. The document must not say two.

    Under CON-2 the user approves on what this document says, so a heading
    that miscounts what was withheld is a wrong basis for approval — the same
    class of defect as T5.0b's mis-attributed reason strings, where the action
    was safe and the description was not.
    """
    kado = FakeKado(occupied={f"{NOTES}Dresden.md"})
    actions = _actions([_atomic(DRESDEN_PLACES, "Dresden", idx=1)])
    kept, clashes = validate_destinations(actions, make_folder_listing(kado))
    assert clashes[0]["kind"] == "vault_collision" and len(clashes[0]["dropped"]) == 1

    md = render_instructions_md(
        kept,
        {"generated": "2026-09-07T10:00:00+02:00", "destination_clashes": clashes},
        CFG,
    )
    block = _clash_block(md)
    named = [ln for ln in block if ln.startswith("    - ")]
    assert len(named) == 1, f"one item was withheld, {len(named)} are listed:\n{block}"
    assert "two items" not in "\n".join(block).lower(), (
        "the heading and intro must not count claimants — a vault collision "
        f"has one:\n{block}"
    )
    assert f"{NOTES}Dresden.md" in "\n".join(block)
    assert DRESDEN_PLACES in "\n".join(block)


def test_one_heading_covers_both_kinds_in_one_document():
    """A run collision and a vault collision in one run get one section, and
    the wording must be true of both at once."""
    kado = FakeKado(occupied={f"{NOTES}Root note takeaway.md"})
    kept, clashes = validate_destinations(
        _actions(TWO_NAMESAKES), make_folder_listing(kado)
    )
    kinds = {c["kind"] for c in clashes}
    assert kinds == {"run_collision", "vault_collision"}, clashes

    md = render_instructions_md(
        kept,
        {"generated": "2026-09-07T10:00:00+02:00", "destination_clashes": clashes},
        CFG,
    )
    assert md.count("## Not filed") == 1
    block = _clash_block(md)
    assert len([ln for ln in block if ln.startswith("    - ")]) == 3, block


def test_a_clean_run_renders_no_clash_block():
    md = render_instructions_md(
        _build_golden_actions(),
        {"generated": "2026-09-07T10:00:00+02:00", "destination_clashes": []},
        CFG,
    )
    assert "Not filed" not in md


# ---------------------------------------------------------------------------
# 9. The report survives the whole render stage, not just the renderer
#    (mirrors tests/test_031_t2_skipped_assets_report_wiring.py)
# ---------------------------------------------------------------------------

_CLASHING_MOVES = [
    {
        "id": "I01", "action": "move_note", "applied": False,
        "source": "100 Inbox/2026-09-07_1001_dresden.md",
        "destination": f"{NOTES}Dresden.md", "title": "Dresden",
        "rendered_file": "2026-09-07_1001_dresden.md",
        "source_inbox_item": DRESDEN_PLACES, "audio_peer": None,
        "parent_mocs": [], "tags": [],
    },
    {
        "id": "I02", "action": "move_note", "applied": False,
        "source": "100 Inbox/2026-09-07_1002_dresden.md",
        "destination": f"{NOTES}Dresden.md", "title": "Dresden",
        "rendered_file": "2026-09-07_1002_dresden.md",
        "source_inbox_item": DRESDEN_REISE, "audio_peer": None,
        "parent_mocs": [], "tags": [],
    },
    {
        "id": "I03", "action": "delete_source", "applied": False,
        "source_path": DRESDEN_PLACES, "reason": "Origin consumed by 1 atomic.",
    },
]


def _drive_render(monkeypatch, tmp_path) -> Path:
    """Drive instruction-render.main() with a canned clashing action list."""
    from unittest.mock import MagicMock

    ir = _load("instruction_render_t5_3", "instruction-render.py")
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
        lambda *_a, **_kw: ([dict(a) for a in _CLASHING_MOVES], []),
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


def test_the_clash_never_reaches_the_wire(monkeypatch, tmp_path):
    """The whole point: Hashi must not be handed two moves to one path."""
    out_dir = _drive_render(monkeypatch, tmp_path)
    doc = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))
    moves = [a for a in doc["actions"] if a["action"] == "move_note"]
    assert moves == [], f"a destination clash reached the executor: {moves}"
    deletes = [a["source_path"] for a in doc["actions"]
               if a["action"] == "delete_source"]
    assert deletes == [], (
        "the delete of an origin whose move was refused must go with it — "
        f"otherwise the guard deletes the note it declined to file: {deletes}"
    )


def test_the_clash_populates_the_json_tomo_block(monkeypatch, tmp_path):
    out_dir = _drive_render(monkeypatch, tmp_path)
    doc = json.loads((out_dir / "instructions.json").read_text(encoding="utf-8"))
    entries = doc["tomo"]["destination_clashes"]
    assert len(entries) == 1
    assert entries[0]["destination"] == f"{NOTES}Dresden.md"
    assert sorted(d["source_inbox_item"] for d in entries[0]["dropped"]) == [
        DRESDEN_PLACES, DRESDEN_REISE,
    ]
    # The canned list carries a delete for the Places origin only, so exactly
    # one withdrawal is reported — the field names deletes that existed, not
    # every path the dropped moves touched.
    assert entries[0]["withdrawn_deletes"] == [DRESDEN_PLACES]


def test_the_clash_reaches_the_rendered_document(monkeypatch, tmp_path):
    out_dir = _drive_render(monkeypatch, tmp_path)
    md = (out_dir / "instructions.md").read_text(encoding="utf-8")
    assert "## Not filed — a destination is claimed twice" in md
    assert DRESDEN_PLACES in md and DRESDEN_REISE in md


# ---------------------------------------------------------------------------
# 10. The paired consumer — instructions-diff must not read a deliberate
#     withholding as coverage drift. The conductor STOPs on a diff mismatch
#     (synthesis-conductor.md step 3e), so a stale expectation would halt the
#     run with a message that misdiagnoses the guard.
# ---------------------------------------------------------------------------

def _diff_module():
    return _load("instructions_diff_t5_3", "instructions-diff.py")


def _diff(pairs, **kw) -> tuple[int, list[str]]:
    """Run the real audit over the emitter's own output for the same input.

    The two modules are pinned against each other, never against a
    hand-written number: a count written into the test would agree with
    whichever side drifted.
    """
    confirmed = [c for _, c in pairs]
    actions = _actions(pairs, **kw)
    kept, clashes = validate_destinations(actions)
    instrs = {
        "actions": kept,
        "action_count": len(kept),
        "tomo": {"destination_clashes": clashes},
    }
    parsed = {
        "confirmed_items": confirmed,
        "daily_updates": kw.get("daily_updates") or [],
        "skipped": kw.get("skipped") or [],
    }
    return _diff_module().run_diff(parsed, instrs)


def test_a_guarded_clash_reconciles_instead_of_reporting_drift(capsys):
    rc, observations = _diff(TWO_NAMESAKES)
    capsys.readouterr()
    assert rc == 0, (
        "the guard withheld two moves and their deletes deliberately; a FAIL "
        "here stops the conductor and blames Tomo for its own guard"
    )
    assert any("withheld" in o for o in observations), observations


def test_the_audit_names_the_withheld_moves_and_points_at_the_report():
    _rc, observations = _diff(TWO_NAMESAKES)
    note = next(o for o in observations if "withheld" in o)
    assert "2 move(s)" in note and "Not filed" in note and "re-run" in note, note
    assert "2 paired delete(s)" in note, (
        "the note counts the deletes it actually withdrew — a kept-source item "
        f"has none, and the note must not imply one per move: {note}"
    )


def test_the_audit_note_counts_deletes_it_actually_withdrew():
    pairs = [
        _atomic(DRESDEN_PLACES, "Dresden", idx=1, keep_source=True),
        _atomic(DRESDEN_REISE, "Dresden", idx=2, keep_source=True),
    ]
    _rc, observations = _diff(pairs)
    note = next(o for o in observations if "withheld" in o)
    assert "0 paired delete(s)" in note, (
        f"neither item had a delete to withdraw: {note}"
    )


def test_a_clean_run_still_reconciles(capsys):
    rc, observations = _diff(DISTINCT)
    capsys.readouterr()
    assert rc == 0
    assert not any("withheld" in o for o in observations), observations


def test_the_audit_reconciles_a_withdrawn_audio_peer_delete(capsys):
    peer = "100 Inbox/Places/Dresden.m4a"
    pairs = [
        _atomic(DRESDEN_PLACES, "Dresden", idx=1, audio_peer=peer),
        _atomic(DRESDEN_REISE, "Dresden", idx=2),
    ]
    pairs[0][1]["audio_peer"] = peer  # the differ reads the peer off the item
    rc, _obs = _diff(pairs)
    capsys.readouterr()
    assert rc == 0, "the peer's expected delete must be withdrawn with its origin"
