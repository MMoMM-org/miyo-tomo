#!/usr/bin/env python3
# version: 0.1.2
"""test_review_deliver_report.py — what a `deliver` stop and a resume tell the skill (spec 045 P6 live-walk fix,
owner decision 2026-11-13; PRD F5-AC10, F6-AC4; SDD Error Handling `doc-changed`).

Split out of test_review_deliver.py (its fixtures and helpers are imported) to keep that file from growing. Pinned
here, on `review-instructions.py` against the guarded fake:

A. a `doc-changed` stop carries a `reason`: `open-unsaved` for Kado's dirty-editor refusal (the document is open in
   Obsidian with unsaved changes — the live walk met it through a plugin stamping `Updated:` in the editor buffer),
   `changed-since-read` for Kado's mtime guard and for the client's `KadoConcurrencyError`, `unknown` for a CONFLICT
   with neither message; a `kado-write-failed` stop carries no `reason`; and nothing of Kado's message — the path in
   it least of all — reaches stdout or stderr, only the reason name.
B. a resume reports the plan the delivery wrote — `mode`, `target`, `place`, recorded in `meta.json` with the first
   step's in-flight mark — not the re-plan against the vault as it is now; `target_appeared` on a resume compares the
   Pass 1 mode with the recorded mode; a delivery that began before the record existed falls back to the re-plan.
   The record holds the anchor only when it is the configured one: a heading of the note's own (`--place-anchor`,
   the heading above the marker) is note text and never enters `tomo-tmp` (ADR-9; tests/test_review_privacy.py
   scans every working file for it) — a resume then reports the rebuilt plan's anchor for that one field; the record
   keeps `anchor_picked: true` instead, and a resume without the pick is refused (tests/test_review_deliver_resume.py).

Mechanisms a mutation falsifies: `_conflict_reason` answering one name for every conflict flips
`test_doc_changed_names_why_kado_refused_the_mark`; the stop carrying the reason on every problem flips
`test_kado_write_failed_carries_no_reason`; putting Kado's message on stdout flips the leak assertions; recording the
plan after the loop instead of before the first mark flips `test_the_plan_is_recorded_with_the_first_in_flight_mark`;
reporting the re-plan flips `test_resume_reports_the_recorded_plan_not_the_replan`; reporting the record when none
exists flips `test_resume_without_a_record_reports_the_replan`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_deliver_helpers import (  # noqa: E402,F401 — puts tomo/scripts on the path; doc_mod, ins, instance are fixtures
    DOC, GUARD_REFUSED, NEW_NOTE, NOTE, OWN, SET_JSON, SET_MD, STEM, TARGET, meta_of,
    prepared, ready, run, set_json_of, vault, writes, doc_mod, ins, instance,
)
from note_fake_vault import Killed  # noqa: E402
from lib.kado_client import KadoConcurrencyError, KadoError, KadoToolError  # noqa: E402

EDITOR_TEXT = "is open in the editor with unsaved changes. Re-read it and retry"
# Kado's dirty-editor refusal (src/obsidian/note-adapter.ts conflictEditorError), code CONFLICT, the path in the message
OPEN_UNSAVED = ('kado-write returned an error: {"code":"CONFLICT","message":"File ' + DOC + ' ' + EDITOR_TEXT
                + ' \\u2014 the next read will include the user\'s latest edits once Obsidian auto-saves '
                '(\\u22482 s after the last keystroke).","hints":["the file changed"]}')
PLACE = {"anchor": OWN, "placement": "before", "level": 2}

CONFLICTS = {
    "editor-open-unsaved": (KadoToolError(OPEN_UNSAVED), "open-unsaved"),
    "mtime-guard": (KadoToolError(GUARD_REFUSED), "changed-since-read"),
    "client-concurrency-error": (KadoConcurrencyError("kado-write returned an error: expectedModified mismatch"),
                                 "changed-since-read"),
    "conflict-other-message": (KadoToolError('kado-write returned an error: {"code":"CONFLICT",'
                                             '"message":"File is locked by another process."}'), "unknown"),
    "conflict-without-message": (KadoToolError('kado-write returned an error: {"code":"CONFLICT"}'), "unknown"),
    "conflict-token-in-prose": (KadoToolError('kado-write returned an error: refused: {"code":"CONFLICT",'
                                              '"message":"File was updated in the background."} (see log)'),
                                "unknown"),
}


def _raw(ins, monkeypatch, capsys, argv, fake):
    """``(out, raw stdout, stderr)``: the parsed JSON and the bytes the skill reads, for the leak assertions."""
    monkeypatch.setattr(ins, "KadoClient", fake)
    assert ins.main(["--profiles-dir", "profiles", *argv]) == 0
    stdout, stderr = capsys.readouterr()
    return json.loads(stdout), stdout, stderr


# ---------------------------------------------------------------- A. the reason on a doc-changed stop

@pytest.mark.parametrize("conflict", list(CONFLICTS))
def test_doc_changed_names_why_kado_refused_the_mark(doc_mod, ins, instance, monkeypatch, capsys, conflict):
    exc, reason = CONFLICTS[conflict]
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())
    fake.fail[("write_note", DOC)] = exc
    out, stdout, stderr = _raw(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "stopped" and out["problems"] == ["doc-changed"] and out["failed_step"] == "doc_mark"
    assert out["reason"] == reason, out
    assert out["paths"] == {"set_json": SET_JSON, "set_md": SET_MD}
    # Kado's message and the document's path stay off both streams: the skill reads the reason name only
    for leak in (EDITOR_TEXT, "updated in the background", "mismatch", "locked", DOC, "2026-W13 Review"):
        assert leak not in stdout and leak not in stderr, (leak, stdout, stderr)
    assert stderr == f"review-instructions: delivery failed at doc_mark ({type(exc).__name__})\n"
    assert meta_of(instance)["failed_step"] == "doc_mark" and "reason" not in meta_of(instance)
    fake.fail.clear()
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "resumed" and "reason" not in out
    assert meta_of(instance)["steps_done"] == ["set_json", "set_md", "doc_mark"]


FAILURES = {
    "doc-mark-503": (("write_note", DOC), KadoError("503 after retries")),
    "doc-mark-validation-error": (("write_note", DOC), KadoToolError(
        'kado-write returned an error: {"code":"VALIDATION_ERROR","message":"frontmatter mismatch: expected a mapping"}')),
    "doc-mark-conflict-named-in-the-message-only": (("write_note", DOC), KadoToolError(
        'kado-write returned an error: {"code":"IO_ERROR","message":"CONFLICT while writing"}')),
    "set-md-503": (("write_note", SET_MD), KadoError("503")),
}


@pytest.mark.parametrize("failure", list(FAILURES))
def test_kado_write_failed_carries_no_reason(doc_mod, ins, instance, monkeypatch, capsys, failure):
    target, exc = FAILURES[failure]
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())
    fake.fail[target] = exc
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "stopped" and out["problems"] == ["kado-write-failed"], out
    assert "reason" not in out, out


# ---------------------------------------------------------------- B. a resume reports the plan it wrote

def _stopped_new_note_delivery(doc_mod, ins, instance, monkeypatch, capsys):
    """A new-note delivery stopped at the mark: the note and the set landed, the document is not marked."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault(None))
    assert meta_of(instance)["mode"] == "new-note" and "delivered_plan" not in meta_of(instance)
    fake.fail[("write_note", DOC)] = KadoError("503")
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "stopped" and out["failed_step"] == "doc_mark"
    fake.fail.clear()
    fake.events.clear()
    return cli, fake


def _note_lands_at_the_target(fake) -> None:
    """Hashi applied the move between the stop and the resume: the staged note is now the target note."""
    fake.files[TARGET] = fake.text(NEW_NOTE)
    fake.modified[TARGET] = 7
    del fake.files[NEW_NOTE]


def test_the_plan_is_recorded_with_the_first_in_flight_mark(doc_mod, ins, instance, monkeypatch, capsys):
    """Falsifies a record written after the loop: a kill on the very first upload (the note) already leaves the
    plan in meta.json, as `set_replaced` is left, so a resume after any failure has it."""
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(None))
    fake.fail[("write_note", NEW_NOTE)] = Killed()
    monkeypatch.setattr(ins, "KadoClient", fake)
    with pytest.raises(Killed):
        ins.main(["--profiles-dir", "profiles", "deliver", "--stem", STEM])
    capsys.readouterr()
    meta = meta_of(instance)
    assert meta["steps_done"] == [] and meta["failed_step"] == "note"
    assert meta["delivered_plan"] == {"mode": "new-note", "target": TARGET, "place": PLACE}
    # a refused delivery records nothing: the plan is written with the first step, never before it
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(), approve=False)
    assert run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)[1]["status"] == "refused"
    assert "delivered_plan" not in meta_of(instance)


def test_a_fresh_delivery_reports_the_plan_it_recorded(doc_mod, ins, instance, monkeypatch, capsys):
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault())
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "delivered"
    assert meta_of(instance)["delivered_plan"] == {"mode": out["mode"], "target": out["target"], "place": out["place"]}
    assert meta_of(instance)["delivered_plan"] == {"mode": "insert", "target": TARGET, "place": PLACE}


def test_resume_reports_the_recorded_plan_not_the_replan(doc_mod, ins, instance, monkeypatch, capsys):
    """The live walk of 2026-11-13: the first attempt wrote the new note and a set with one `move_note`, stopped at
    the mark; Hashi moved the note; the resume re-planned `replace` against the landed note and reported that,
    with `target_appeared`, while nothing of the kind had been written."""
    cli, fake = _stopped_new_note_delivery(doc_mod, ins, instance, monkeypatch, capsys)
    assert meta_of(instance)["delivered_plan"] == {"mode": "new-note", "target": TARGET, "place": PLACE}
    _note_lands_at_the_target(fake)
    _, replan, _ = cli("preview", "--stem", STEM)
    assert replan["mode"] == "replace" and replan["place"]["anchor"] == "Tomo Review", "the re-plan differs"
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed" and err == "", out
    assert (out["mode"], out["target"], out["place"]) == ("new-note", TARGET, PLACE), out
    assert "target_appeared" not in out, "Pass 1 said new-note and the delivery wrote new-note"
    assert writes(fake) == [("write_note", DOC)], "the resume wrote only the mark"
    assert [a["action"] for a in set_json_of(fake)["actions"]] == ["move_note"], "the landed set is untouched"
    assert meta_of(instance)["steps_done"] == ["note", "set_json", "set_md", "doc_mark"]


def test_resume_target_appeared_compares_pass1_with_the_recorded_mode(doc_mod, ins, instance, monkeypatch, capsys):
    """Falsifies `target_appeared` read from the re-plan on a resume: Pass 1 said new-note, the target appeared
    before the delivery (recorded `insert`), then vanished before the resume (re-plan new-note) — the resume
    still says the delivery targeted the existing note."""
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(None))
    fake.files[TARGET] = NOTE
    fake.modified[TARGET] = 1
    fake.fail[("write_note", DOC)] = KadoError("503")
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "stopped" and out["failed_step"] == "doc_mark"
    assert meta_of(instance)["delivered_plan"]["mode"] == "insert"
    fake.fail.clear()
    del fake.files[TARGET]
    assert run(ins, monkeypatch, capsys, ["preview", "--stem", STEM], fake)[1]["mode"] == "new-note"
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "resumed" and out["mode"] == "insert" and out["target_appeared"] is True, out
    assert out["target"] == TARGET and out["place"] == PLACE


def test_the_record_never_holds_a_heading_of_the_notes_own(doc_mod, ins, instance, monkeypatch, capsys):
    """Falsifies storing `place.anchor` blind: the heading the user picked with `--place-anchor` is the target
    note's text; the record keeps placement and level and `anchor: null`, and the resume (with the same pick,
    as step 8 passes it) reports the rebuilt plan's anchor in its place."""
    fake = prepared(doc_mod, instance, monkeypatch, capsys, vault(NOTE.replace(f"## {OWN}", "## Meins")))
    fake.fail[("write_note", DOC)] = KadoError("503")
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM, "--place-anchor", "Woche"], fake)
    assert out["status"] == "stopped" and out["failed_step"] == "doc_mark"
    meta_text = (instance / "tomo-tmp" / "review" / STEM / "meta.json").read_text(encoding="utf-8")
    assert "Woche" not in meta_text and "Meins" not in meta_text
    assert meta_of(instance)["delivered_plan"] == {"mode": "insert", "target": TARGET,
                                                   "place": {"anchor": None, "placement": "before", "level": 2},
                                                   "anchor_picked": True}
    fake.fail.clear()
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM, "--place-anchor", "Woche"], fake)
    assert out["status"] == "resumed" and out["mode"] == "insert"
    assert out["place"] == {"anchor": "Woche", "placement": "before", "level": 2}, out


def test_resume_without_a_record_reports_the_replan(doc_mod, ins, instance, monkeypatch, capsys):
    """A delivery that began before the record existed (meta.json without `delivered_plan`) resumes as before:
    the re-plan is reported, `target_appeared` with it."""
    cli, fake = _stopped_new_note_delivery(doc_mod, ins, instance, monkeypatch, capsys)
    meta_path = instance / "tomo-tmp" / "review" / STEM / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    del meta["delivered_plan"]
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    _note_lands_at_the_target(fake)
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed" and err == "", out
    assert out["mode"] == "replace" and out["place"]["anchor"] == "Tomo Review" and out["target_appeared"] is True
    assert "delivered_plan" not in meta_of(instance), "a resume never records a plan it did not write"
    assert writes(fake) == [("write_note", DOC)]
