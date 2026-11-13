#!/usr/bin/env python3
# version: 0.1.0
"""test_review_deliver_resume.py — a resume never writes a set that contradicts what the first attempt delivered
(fix #258; spec 045 SDD Error Handling rows `replan-differs` and `anchor-needed`; PRD F5-AC10).

Split out of test_review_deliver_report.py (its fixtures and helpers are imported). Pinned here, on
`review-instructions.py deliver` against the guarded fake:

A. a resumed run that carries a `delivered_plan` record and still has an undone step among `note`, `set_json`,
   `set_md` compares the re-plan with the record (`mode`, `target`, `place.placement`, `place.level`, and
   `place.anchor` only when the record holds one) and refuses `replan-differs` when they differ — nothing written,
   `meta.json` unchanged; the same resume with nothing changed writes the undone steps; with only `doc_mark` undone
   a changed re-plan still resumes (the set is complete, only the report differs); without a record (a delivery
   begun before it existed) the resume writes the re-plan as before.
B. a delivery begun with `--place-anchor` records `anchor_picked: true` — never the heading — and a resume without
   `--place-anchor` refuses `anchor-needed` with the `headings` of the pick, nothing written, even when the
   configured anchor would now plan cleanly; with `--place-anchor` the resume continues.
C. the skill's step 8 says what each refusal means: `replan-differs` → the vault changed, nothing more was written,
   Drop or Abort; `anchor-needed` → the step 7 heading pick, then deliver again with `--place-anchor`.

Mechanisms a mutation falsifies: skipping the comparison flips `test_resume_refuses_a_replan_that_differs_from_the_
record`; comparing on every resume flips `test_resume_with_only_the_mark_undone_proceeds_on_a_changed_replan`;
refusing without a record flips `test_resume_without_a_record_writes_the_replan_as_before`; dropping `anchor_picked`
or refusing only when the re-plan refuses flips `test_resume_of_a_picked_anchor_needs_the_heading_again`; storing
the heading flips `test_the_record_holds_the_pick_as_a_flag_never_the_heading`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import test_review_deliver as deliver_tests  # noqa: E402 — puts tomo/scripts on the path
from test_review_deliver import (  # noqa: E402
    DOC, NEW_NOTE, NOTE, OWN, SET_JSON, SET_MD, STEM, TARGET, meta_of, ready, set_json_of, vault, writes,
)
from review_skill_helpers import _section  # noqa: E402
from lib.kado_client import KadoError  # noqa: E402

# the fixtures of test_review_deliver.py, found by pytest in this module's globals
doc_mod, ins, instance = deliver_tests.doc_mod, deliver_tests.ins, deliver_tests.instance

PLACE = {"anchor": OWN, "placement": "before", "level": 2}
PICKED = "Woche"


def _meta_text(instance) -> str:
    return (instance / "tomo-tmp" / "review" / STEM / "meta.json").read_text(encoding="utf-8")


def _stopped_after_the_note(doc_mod, ins, instance, monkeypatch, capsys):
    """A new-note delivery stopped at the set JSON: the note landed in the inbox, no set exists."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault(None))
    fake.fail[("write_file", SET_JSON)] = KadoError("503")
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "stopped" and out["failed_step"] == "set_json", out
    assert meta_of(instance)["steps_done"] == ["note"]
    assert meta_of(instance)["delivered_plan"] == {"mode": "new-note", "target": TARGET, "place": PLACE}
    assert NEW_NOTE in fake.files and SET_JSON not in fake.files
    fake.fail.clear()
    fake.events.clear()
    return cli, fake


def _target_appears(fake) -> None:
    """The user created the week's note in Obsidian between the stop and the resume."""
    fake.files[TARGET] = NOTE
    fake.modified[TARGET] = 1


# ---------------------------------------------------------------- A. the re-plan against the record


def test_resume_refuses_a_replan_that_differs_from_the_record(doc_mod, ins, instance, monkeypatch, capsys):
    """Case (a): new-note recorded, the note written, the set undone, the target appeared meanwhile — the re-plan
    is `insert` into the target while the note waits in the inbox; without the refusal the set would insert into
    the target and the note would stay orphaned."""
    cli, fake = _stopped_after_the_note(doc_mod, ins, instance, monkeypatch, capsys)
    _target_appears(fake)
    before = _meta_text(instance)
    _, replan, _ = cli("preview", "--stem", STEM)
    assert replan["mode"] == "insert" and replan["target_appeared"] is True, "the re-plan differs"
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "refused" and out["problems"] == ["replan-differs"], out
    assert err == "" and writes(fake) == [], "nothing written"
    assert _meta_text(instance) == before, "meta.json unchanged"
    assert SET_JSON not in fake.files and fake.text(NEW_NOTE)


def test_resume_writes_the_set_when_nothing_changed(doc_mod, ins, instance, monkeypatch, capsys):
    """Case (b): the same stop, the vault as it was — the resume writes the set and marks the document."""
    cli, fake = _stopped_after_the_note(doc_mod, ins, instance, monkeypatch, capsys)
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed" and err == "", out
    assert (out["mode"], out["target"], out["place"]) == ("new-note", TARGET, PLACE)
    assert [w[1] for w in writes(fake)] == [SET_JSON, SET_MD, DOC]
    assert [a["action"] for a in set_json_of(fake)["actions"]] == ["move_note"]
    assert meta_of(instance)["steps_done"] == ["note", "set_json", "set_md", "doc_mark"]


def test_resume_with_only_the_mark_undone_proceeds_on_a_changed_replan(doc_mod, ins, instance, monkeypatch, capsys):
    """Case (c): the live-walk case — the note and the set landed, the mark failed, Hashi moved the note; the set
    is complete, so the resume marks the document and reports the record."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault(None))
    fake.fail[("write_note", DOC)] = KadoError("503")
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "stopped" and out["failed_step"] == "doc_mark"
    fake.fail.clear()
    fake.events.clear()
    fake.files[TARGET] = fake.text(NEW_NOTE)
    fake.modified[TARGET] = 7
    del fake.files[NEW_NOTE]
    assert cli("preview", "--stem", STEM)[1]["mode"] == "replace", "the re-plan differs"
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed" and err == "", out
    assert writes(fake) == [("write_note", DOC)]
    assert meta_of(instance)["steps_done"] == ["note", "set_json", "set_md", "doc_mark"]


def test_resume_without_a_record_writes_the_replan_as_before(doc_mod, ins, instance, monkeypatch, capsys):
    """Case (d): a delivery begun before the record existed has nothing to compare with — today's behaviour."""
    cli, fake = _stopped_after_the_note(doc_mod, ins, instance, monkeypatch, capsys)
    meta_path = instance / "tomo-tmp" / "review" / STEM / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    del meta["delivered_plan"]
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    _target_appears(fake)
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed" and err == "", out
    assert out["mode"] == "insert" and out["target_appeared"] is True
    assert [w[1] for w in writes(fake)] == [SET_JSON, SET_MD, DOC]
    assert "delivered_plan" not in meta_of(instance)


# ---------------------------------------------------------------- B. a picked anchor survives to the resume


def _stopped_with_a_picked_anchor(doc_mod, ins, instance, monkeypatch, capsys):
    """An insert delivery at the picked heading (the configured one is missing from the note), stopped at the
    set MD: the set JSON landed with the pick, the MD did not."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault(NOTE.replace(f"## {OWN}", "## Meins")))
    assert cli("preview", "--stem", STEM)[1]["problems"] == ["place-missing"]
    fake.fail[("write_note", SET_MD)] = KadoError("503")
    _, out, _ = cli("deliver", "--stem", STEM, "--place-anchor", PICKED)
    assert out["status"] == "stopped" and out["failed_step"] == "set_md", out
    assert meta_of(instance)["steps_done"] == ["set_json"]
    assert set_json_of(fake)["actions"][0]["anchor"]["value"] == PICKED
    fake.fail.clear()
    fake.events.clear()
    return cli, fake


def test_resume_of_a_picked_anchor_needs_the_heading_again(doc_mod, ins, instance, monkeypatch, capsys):
    """Case (e): the configured heading is back in the note, so a re-plan without the pick would land cleanly at
    the wrong place — the MD would say the configured heading while the set JSON says the pick. The resume
    without `--place-anchor` refuses with the pick's headings and writes nothing; with it, the MD lands."""
    cli, fake = _stopped_with_a_picked_anchor(doc_mod, ins, instance, monkeypatch, capsys)
    fake.files[TARGET] = NOTE
    fake.modified[TARGET] += 1
    assert cli("preview", "--stem", STEM)[1]["problems"] == [], "the configured anchor plans cleanly now"
    before = _meta_text(instance)
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "refused" and out["problems"] == ["anchor-needed"], out
    assert out["headings"] == ["2026-W13", PICKED, OWN]
    assert err == "" and writes(fake) == [] and SET_MD not in fake.files
    assert _meta_text(instance) == before
    _, out, err = cli("deliver", "--stem", STEM, "--place-anchor", PICKED)
    assert out["status"] == "resumed" and err == "", out
    assert out["place"] == {"anchor": PICKED, "placement": "before", "level": 2}
    assert [w[1] for w in writes(fake)] == [SET_MD, DOC]
    assert f"`{PICKED}`" in fake.text(SET_MD) or PICKED in fake.text(SET_MD)
    assert meta_of(instance)["steps_done"] == ["set_json", "set_md", "doc_mark"]


def test_the_record_holds_the_pick_as_a_flag_never_the_heading(doc_mod, ins, instance, monkeypatch, capsys):
    """Case (f): `anchor_picked: true` is recorded; the heading is the note's text and never enters tomo-tmp
    (the privacy walk scans every working file as well)."""
    cli, fake = _stopped_with_a_picked_anchor(doc_mod, ins, instance, monkeypatch, capsys)
    assert meta_of(instance)["delivered_plan"] == {
        "mode": "insert", "target": TARGET, "place": {"anchor": None, "placement": "before", "level": 2},
        "anchor_picked": True}
    assert PICKED not in _meta_text(instance) and "Meins" not in _meta_text(instance)
    _, out, _ = cli("deliver", "--stem", STEM, "--place-anchor", PICKED)
    assert out["status"] == "resumed"
    assert PICKED not in _meta_text(instance)


def test_a_delivery_at_the_configured_anchor_records_no_pick(doc_mod, ins, instance, monkeypatch, capsys):
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault())
    fake.fail[("write_note", DOC)] = KadoError("503")
    assert cli("deliver", "--stem", STEM)[1]["status"] == "stopped"
    assert meta_of(instance)["delivered_plan"] == {"mode": "insert", "target": TARGET, "place": PLACE}
    fake.fail.clear()
    assert cli("deliver", "--stem", STEM)[1]["status"] == "resumed"


# ---------------------------------------------------------------- C. the skill's step 8 lines (case g)


REPLAN_LINE = ("- `replan-differs` → say the vault changed since the stopped delivery: the target note or its place "
               "is not what the first attempt wrote for; nothing more was written, and Resume would refuse again. "
               "Ask `1 Drop · 2 Abort`; Drop → step 9 with `<stem>`, Abort → stop.")
ANCHOR_LINE = ("- `anchor-needed` → say the stopped delivery used a chosen heading that is asked again: print "
               "`headings` as a numbered list and ask: Which number, or 0 Abort? A number → rerun `preview` of step 7 "
               "with that heading as `--place-anchor`, keep it for this step and branch on the rerun by the step 7 "
               "list. 0 → stop.")


def test_the_skill_says_what_a_differing_replan_means_and_offers_drop():
    text = _section("8. Deliver")
    assert REPLAN_LINE in text
    assert "`replan-differs` or `anchor-needed` → the two lines below." in text
    assert text.index("`replan-differs` or `anchor-needed`") < text.index("Any other → the step 7 lines")


def test_the_skill_asks_the_heading_again_on_anchor_needed():
    text = _section("8. Deliver")
    assert ANCHOR_LINE in text
    assert "Add `--place-anchor \"<heading>\"` when a heading was chosen in step 7." in text
