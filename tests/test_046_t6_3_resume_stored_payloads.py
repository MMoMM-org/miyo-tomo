#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t6_3_resume_stored_payloads.py — a resume of an open delivery uploads the payloads the first attempt
built, never a re-plan (spec 046 T6.3 live walk 2026-11-18, owner decision; SDD amendment "Resume uploads the stored
payloads"; docs/tomo/scripts/review-instructions.md "WHY a Resume Uploads the Stored Payloads").

Live: a quarter review in new-note mode stopped at `doc_mark` (`doc-changed`, `open-unsaved`), something in Obsidian
then moved a file onto the target path, and the resume rebuilt the plan against the changed vault and refused
`place-missing` — although only the document mark was undone. On `review-instructions.py deliver` against the
guarded fake (tests/review_deliver_helpers). Mechanisms a mutation falsifies:

- the resume branch that skips the rebuilt plan's problems and `resume_refusal`: without it the mark-only resume
  refuses `place-missing` (`test_a_stop_at_the_mark_resumes_the_mark_alone_when_the_target_appeared`,
  `test_a_stop_at_the_mark_resumes_the_mark_alone_when_the_anchor_heading_vanished`) and a set-step resume refuses
  `replan-differs` (`test_a_stop_at_the_set_md_uploads_the_stored_md_byte_identical`);
- uploading the STORED payload rather than the rebuilt one, through the stored paths: a rebuilt new-note resume
  would write an `insert` set and no note (`test_a_stop_at_the_set_json_of_a_new_note_writes_the_stored_set`);
- storing the payloads before the first step's in-flight mark: a process killed during the first upload still
  resumes with them (`test_a_kill_during_the_first_upload_still_resumes_with_the_stored_payloads`);
- removing the stored payloads once the mark is recorded (`test_a_finished_delivery_keeps_no_stored_payload`).

All data is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_deliver_helpers import (  # noqa: E402,F401 — doc_mod, ins, instance are fixtures
    DOC, NEW_NOTE, NOTE, OWN, SET_JSON, SET_MD, STEM, TARGET, TEMPLATE, GuardedVault, meta_of, prepared,
    ready, run, set_json_of, vault, writes, doc_mod, ins, instance,
)
from note_fake_vault import Killed  # noqa: E402
from lib.kado_client import KadoError, KadoToolError  # noqa: E402

__all__ = ["doc_mod", "ins", "instance"]            # fixtures, used by name

PLACE = {"anchor": OWN, "placement": "before", "level": 2}
OPEN_UNSAVED = ('kado-write returned an error: {"code":"CONFLICT","message":"File ' + DOC + ' is open in the '
                'editor with unsaved changes. Re-read it and retry"}')
ALL_STEPS = ["note", "set_json", "set_md", "doc_mark"]


class RecordingVault(GuardedVault):
    """The guarded fake that also keeps every payload a write was handed, landed or not."""

    def __init__(self, files=None):
        super().__init__(files)
        self.handed: dict = {}

    def write_note(self, path, content, expected_modified=None):
        self.handed.setdefault(path, []).append(content)
        return super().write_note(path, content, expected_modified)

    def write_file(self, path, data, expected_modified=None):
        self.handed.setdefault(path, []).append(data)
        return super().write_file(path, data, expected_modified)


def _clear(fake) -> None:
    fake.fail.clear()
    fake.events.clear()


def _stopped_at_the_mark(cli, fake, instance, steps):
    fake.fail[("write_note", DOC)] = KadoToolError(OPEN_UNSAVED)
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "stopped" and out["problems"] == ["doc-changed"], out
    assert out["reason"] == "open-unsaved" and out["failed_step"] == "doc_mark", out
    assert meta_of(instance)["steps_done"] == steps
    _clear(fake)


def _resumed_with_the_mark_alone(cli, fake, instance, steps, record):
    landed = {path: fake.text(path) for path in (SET_JSON, SET_MD, NEW_NOTE) if path in fake.files}
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed" and err == "", out
    assert out["problems"] == [], out
    assert (out["mode"], out["target"], out["place"]) == record
    assert writes(fake) == [("write_note", DOC)], "only the document mark is written"
    assert meta_of(instance)["steps_done"] == steps + ["doc_mark"]
    assert {path: fake.text(path) for path in landed} == landed, "note and set never rewritten"


def test_a_stop_at_the_mark_resumes_the_mark_alone_when_the_target_appeared(doc_mod, ins, instance, monkeypatch,
                                                                              capsys):
    """The live case: new-note mode, the mark refused `open-unsaved`; then a file without the configured anchor
    lands on the target path, so the rebuilt plan is `insert` with `place-missing`. The resume marks the document
    and reports the record."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault(None))
    _stopped_at_the_mark(cli, fake, instance, ["note", "set_json", "set_md"])
    fake.files[TARGET] = fake.text(SET_MD)
    fake.modified[TARGET] = 1
    _, replan, _ = cli("preview", "--stem", STEM)
    assert replan["mode"] == "insert" and "place-missing" in replan["problems"], replan
    fake.events.clear()
    _resumed_with_the_mark_alone(cli, fake, instance, ["note", "set_json", "set_md"], ("new-note", TARGET, PLACE))


def test_a_stop_at_the_mark_resumes_the_mark_alone_when_the_anchor_heading_vanished(doc_mod, ins, instance,
                                                                                      monkeypatch, capsys):
    """Insert mode: the mark refused `open-unsaved`, then the user renamed the configured anchor heading — the
    rebuilt plan refuses `place-missing`; the set is complete, so the resume marks the document."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault())
    _stopped_at_the_mark(cli, fake, instance, ["set_json", "set_md"])
    fake.files[TARGET] = NOTE.replace(f"## {OWN}", "## Meins")
    fake.modified[TARGET] += 1
    assert cli("preview", "--stem", STEM)[1]["problems"] == ["place-missing"]
    fake.events.clear()
    _resumed_with_the_mark_alone(cli, fake, instance, ["set_json", "set_md"], ("insert", TARGET, PLACE))


def test_a_stop_at_the_set_md_uploads_the_stored_md_byte_identical(doc_mod, ins, instance, monkeypatch, capsys):
    """Insert mode, the set MD write failed; then the anchor heading was demoted, so the rebuilt plan's level
    differs (today `replan-differs`). The resume uploads the MD the first attempt was handed, byte for byte,
    leaves the landed set JSON alone and marks the document."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys,
                      RecordingVault({"Templates/t_week.md": TEMPLATE, TARGET: NOTE}))
    fake.fail[("write_note", SET_MD)] = KadoError("503")
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "stopped" and out["problems"] == ["kado-write-failed"], out
    assert meta_of(instance)["steps_done"] == ["set_json"]
    first_md, first_json = fake.handed[SET_MD][0], fake.text(SET_JSON)
    _clear(fake)
    fake.files[TARGET] = NOTE.replace(f"## {OWN}", f"### {OWN}")
    fake.modified[TARGET] += 1
    assert cli("preview", "--stem", STEM)[1]["place"]["level"] == 3, "the re-plan differs"
    fake.events.clear()
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed" and err == "" and out["problems"] == [], out
    assert out["place"] == PLACE
    assert [w[1] for w in writes(fake)] == [SET_MD, DOC]
    assert fake.text(SET_MD) == first_md and fake.text(SET_JSON) == first_json
    assert meta_of(instance)["steps_done"] == ["set_json", "set_md", "doc_mark"]


def test_a_stop_at_the_set_json_of_a_new_note_writes_the_stored_set(doc_mod, ins, instance, monkeypatch, capsys):
    """New-note mode, the note landed, the set JSON failed; the target appeared since (the rebuilt plan is
    `insert`). The resume writes the stored new-note set — a `move_note` for the waiting note — not an insert."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault(None))
    fake.fail[("write_file", SET_JSON)] = KadoError("503")
    assert cli("deliver", "--stem", STEM)[1]["failed_step"] == "set_json"
    note = fake.text(NEW_NOTE)
    _clear(fake)
    fake.files[TARGET] = NOTE
    fake.modified[TARGET] = 1
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed" and err == "", out
    assert (out["mode"], out["target"]) == ("new-note", TARGET) and "target_appeared" not in out
    assert [w[1] for w in writes(fake)] == [SET_JSON, SET_MD, DOC]
    assert [a["action"] for a in set_json_of(fake)["actions"]] == ["move_note"]
    assert fake.text(NEW_NOTE) == note and fake.text(TARGET) == NOTE
    assert meta_of(instance)["steps_done"] == ALL_STEPS


def test_a_kill_during_the_first_upload_still_resumes_with_the_stored_payloads(doc_mod, ins, instance, monkeypatch,
                                                                                 capsys):
    """The payloads are stored before the first step's in-flight mark: a process killed while the note uploads
    resumes with the new-note payloads even though the target appeared meanwhile."""
    fake = prepared(doc_mod, instance, monkeypatch, capsys, RecordingVault({"Templates/t_week.md": TEMPLATE}))
    fake.fail[("write_note", NEW_NOTE)] = Killed()
    monkeypatch.setattr(ins, "KadoClient", fake)
    with pytest.raises(Killed):
        ins.main(["--profiles-dir", "profiles", "deliver", "--stem", STEM])
    capsys.readouterr()
    assert meta_of(instance)["failed_step"] == "note"
    handed_note = fake.handed[NEW_NOTE][0]
    _clear(fake)
    fake.files[TARGET] = NOTE
    fake.modified[TARGET] = 1
    _, out, _ = run(ins, monkeypatch, capsys, ["deliver", "--stem", STEM], fake)
    assert out["status"] == "resumed" and out["mode"] == "new-note", out
    assert [w[1] for w in writes(fake)] == [NEW_NOTE, SET_JSON, SET_MD, DOC]
    assert fake.text(NEW_NOTE) == handed_note
    assert meta_of(instance)["steps_done"] == ALL_STEPS


def test_a_finished_delivery_keeps_no_stored_payload(doc_mod, ins, instance, monkeypatch, capsys):
    """The stored payloads carry the note's text; once the mark is recorded nothing resumes, so the stage keeps
    only meta.json of the delivery."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault(None))
    fake.fail[("write_note", DOC)] = KadoError("503")
    assert cli("deliver", "--stem", STEM)[1]["status"] == "stopped"
    stage = instance / "tomo-tmp" / "review" / STEM
    held = sorted(p.name for p in stage.iterdir())
    assert len(held) > 1, "an open delivery stores its payloads beside meta.json"
    _clear(fake)
    assert cli("deliver", "--stem", STEM)[1]["status"] == "resumed"
    assert sorted(p.name for p in stage.iterdir()) == ["meta.json"]
