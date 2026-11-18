#!/usr/bin/env python3
# version: 0.2.0
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

Review round: `clear_closed_payloads` in `deliver` / `status` (`test_a_closed_delivery_never_keeps_its_payloads`);
`remove_payloads` ignoring OSError (`test_a_cleanup_that_fails_keeps_the_delivered_output`); the name-taken cleanup
(`test_a_first_deliver_refused_name_taken_at_the_set_json_leaves_no_payloads`); `_stored_shape` (the
`read_payloads` cases set-md-missing, keys-differ, empty-path, unknown-step, new-note-without-note — truncated-json,
paths-not-a-dict and set-json-not-an-object are also caught by the JSON parse, `dict()` and the set-object check);
ValueError caught (`test_a_corrupted_payloads_file_takes_the_legacy_path`); `_overwrite_step` writing to the stored
path (`test_a_resume_after_the_inbox_moved_writes_to_the_stored_paths`); notices cleared
(`test_a_stored_resume_reports_no_notice_of_the_rebuilt_plan`); the approval refusal
(`test_a_stored_resume_refuses_a_document_no_longer_approved`).

All data is synthetic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

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


# ---------------------------------------------------------------- review round: cleanup, shape, coverage


def _stage(instance) -> Path:
    return instance / "tomo-tmp" / "review" / STEM


def _payloads(instance) -> Path:
    return _stage(instance) / "payloads.json"


def _stopped_at_set_md_of_an_insert(cli, fake, instance):
    fake.fail[("write_note", SET_MD)] = KadoError("503")
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "stopped" and out["failed_step"] == "set_md", out
    _clear(fake)


@pytest.mark.parametrize("closed", ["finished", "withdrawn"])
@pytest.mark.parametrize("sub", ["deliver", "status"])
def test_a_closed_delivery_never_keeps_its_payloads(doc_mod, ins, instance, monkeypatch, capsys, closed, sub):
    """A kill between the mark's record and the cleanup (or between drop's meta write and its cleanup) leaves
    payloads.json beside a closed record; the next `deliver` or `status` removes it, whatever it answers."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault())
    if closed == "finished":
        assert cli("deliver", "--stem", STEM)[1]["status"] == "delivered"
    else:
        _stopped_at_set_md_of_an_insert(cli, fake, instance)
        assert cli("drop", "--stem", STEM)[1]["status"] == "withdrawn"
    _payloads(instance).write_text('{"paths": {}, "payloads": {}}\n', encoding="utf-8")   # the killed cleanup
    code, out, _ = cli(sub, "--stem", STEM)
    assert code == 0, out
    assert not _payloads(instance).exists()


def test_a_cleanup_that_fails_keeps_the_delivered_output(doc_mod, ins, instance, monkeypatch, capsys):
    """Removing the file is housekeeping: an OSError there never turns a finished delivery into exit 1."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault())
    real_unlink = Path.unlink

    def unlink(self, *args, **kwargs):
        if self.name == "payloads.json":
            raise PermissionError("denied")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    code, out, _ = cli("deliver", "--stem", STEM)
    assert code == 0 and out["status"] == "delivered", out
    assert meta_of(instance)["steps_done"] == ["set_json", "set_md", "doc_mark"]


class RaceVault(GuardedVault):
    """A set lands at the set JSON path right after `load_run` probed it absent."""

    def __init__(self, files=None):
        super().__init__(files)
        self.probed = False

    def read_file(self, path):
        if path == SET_JSON and not self.probed:
            self.probed = True
            from lib.kado_client import KadoNotFoundError
            self._call("read_file", path)
            raise KadoNotFoundError("not found")
        return super().read_file(path)


def test_a_first_deliver_refused_name_taken_at_the_set_json_leaves_no_payloads(doc_mod, ins, instance, monkeypatch,
                                                                                capsys):
    """Nothing began, so nothing resumes: the stored payloads go with the refusal."""
    fake = RaceVault({"Templates/t_week.md": TEMPLATE, TARGET: NOTE, SET_JSON: b'{"other": true}\n'})
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, fake)
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "refused" and out["problems"] == ["name-taken"] and out["step"] == "set_json", out
    assert meta_of(instance)["steps_done"] == [] and meta_of(instance)["failed_step"] == ""
    assert not _payloads(instance).exists()


def test_a_corrupted_payloads_file_takes_the_legacy_path(doc_mod, ins, instance, monkeypatch, capsys):
    """A damaged store is read as none: the #258 comparison answers (`replan-differs`), never exit 1."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault())
    _stopped_at_set_md_of_an_insert(cli, fake, instance)
    _payloads(instance).write_text('{"paths": {"set_json": "x", ', encoding="utf-8")
    fake.files[TARGET] = NOTE.replace(f"## {OWN}", f"### {OWN}")
    fake.modified[TARGET] += 1
    code, out, err = cli("deliver", "--stem", STEM)
    assert code == 0 and out["status"] == "refused" and out["problems"] == ["replan-differs"], (out, err)
    assert writes(fake) == []


def _old_applied_set() -> bytes:
    action = {"id": "I01", "action": "replace_section", "target_path": "x.md",
              "anchor": {"type": "heading", "value": "Tomo Review"}, "content": "## Tomo Review\n", "applied": True}
    return (json.dumps({"schema_version": "3", "type": "tomo-instructions", "generated": "2026-01-01T00:00:00Z",
                        "profile": "miyo", "md_peer": f"{STEM}_instructions", "actions": [action]}, indent=2)
            + "\n").encode("utf-8")


def test_a_resume_after_the_inbox_moved_writes_to_the_stored_paths(doc_mod, ins, instance, monkeypatch, capsys):
    """The set_replaced path: the delivery writes over an earlier applied set and stops at the MD; the configured
    inbox changes before the resume. The MD lands where the first attempt's set JSON already is."""
    fake = vault(**{SET_JSON: _old_applied_set(), SET_MD: "# old readable instructions\n"})
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, fake)
    _stopped_at_set_md_of_an_insert(cli, fake, instance)
    assert meta_of(instance)["set_replaced"] is True
    cfg_path = instance / "config" / "vault-config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    cfg["concepts"]["inbox"] = "200 Moved/"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed", out
    assert [w[1] for w in writes(fake)] == [SET_MD, DOC]
    assert "old readable instructions" not in fake.text(SET_MD)
    assert not any(path.startswith("200 Moved/") for path in fake.files)


def test_a_stored_resume_reports_no_notice_of_the_rebuilt_plan(doc_mod, ins, instance, monkeypatch, capsys):
    """Insert mode stopped at the set MD, then the target note was deleted: the rebuilt plan is a new note from a
    Templater template and carries `templater_hint`, a notice about a plan this run never writes."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault())
    _stopped_at_set_md_of_an_insert(cli, fake, instance)
    del fake.files[TARGET]
    assert cli("preview", "--stem", STEM)[1]["notices"], "the rebuilt plan has a notice"
    fake.events.clear()
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed" and out["notices"] == [], out


def test_a_stored_resume_refuses_a_document_no_longer_approved(doc_mod, ins, instance, monkeypatch, capsys):
    """The stored payloads are what was approved: unticking Approved since the first attempt refuses
    `not-approved` and writes nothing; an edit to the content alone is ignored."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys,
                      RecordingVault({"Templates/t_week.md": TEMPLATE, TARGET: NOTE}))
    _stopped_at_set_md_of_an_insert(cli, fake, instance)
    first_md = fake.handed[SET_MD][0]
    fake.files[DOC] = fake.files[DOC].replace("- [x] Approved", "- [ ] Approved", 1)
    fake.modified[DOC] += 1
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "refused" and out["problems"] == ["not-approved"], out
    assert writes(fake) == []
    fake.files[DOC] = fake.files[DOC].replace("- [ ] Approved", "- [x] Approved", 1) + "\nnoch ein Satz\n"
    fake.modified[DOC] += 1
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed", out
    assert fake.text(SET_MD) == first_md


_VALID_PATHS = {"set_json": SET_JSON, "set_md": SET_MD}
_VALID_PAYLOADS = {"set_json": '{"actions": []}\n', "set_md": "# md\n"}
_SHAPES = {
    "truncated-json": '{"paths": {"set_json": ',
    "paths-not-a-dict": json.dumps({"paths": [SET_JSON], "payloads": _VALID_PAYLOADS}),
    "set-md-missing": json.dumps({"paths": {"set_json": SET_JSON}, "payloads": {"set_json": '{"a": 1}'}}),
    "keys-differ": json.dumps({"paths": _VALID_PATHS, "payloads": {**_VALID_PAYLOADS, "note": "x"}}),
    "empty-path": json.dumps({"paths": {**_VALID_PATHS, "set_md": ""}, "payloads": _VALID_PAYLOADS}),
    "unknown-step": json.dumps({"paths": {**_VALID_PATHS, "doc_mark": "d.md"},
                                "payloads": {**_VALID_PAYLOADS, "doc_mark": "x"}}),
    "set-json-not-an-object": json.dumps({"paths": _VALID_PATHS, "payloads": {**_VALID_PAYLOADS, "set_json": "[1]"}}),
}


def _meta(mode: str):
    from lib import review_delivery as rdl
    return rdl.ReviewMeta({"delivered_plan": {"mode": mode, "target": TARGET, "place": PLACE}})


@pytest.mark.parametrize("text", list(_SHAPES.values()) + [json.dumps({"paths": _VALID_PATHS,
                                                                        "payloads": _VALID_PAYLOADS})],
                         ids=list(_SHAPES) + ["new-note-without-note"])
def test_read_payloads_answers_none_for_any_other_shape(tmp_path, text):
    from lib import review_delivery as rdl
    (tmp_path / "payloads.json").write_text(text, encoding="utf-8")
    mode = "new-note" if text == json.dumps({"paths": _VALID_PATHS, "payloads": _VALID_PAYLOADS}) else "insert"
    assert rdl.read_payloads(tmp_path, _meta(mode)) is None


def test_read_payloads_returns_a_valid_store(tmp_path):
    """The control of the parametrized test: the same shapes, valid, are read."""
    from lib import review_delivery as rdl
    (tmp_path / "payloads.json").write_text(json.dumps({"paths": _VALID_PATHS, "payloads": _VALID_PAYLOADS}),
                                            encoding="utf-8")
    assert rdl.read_payloads(tmp_path, _meta("insert")) == (_VALID_PATHS, _VALID_PAYLOADS)
