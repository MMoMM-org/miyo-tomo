#!/usr/bin/env python3
# version: 0.1.0
"""test_review_deliver_rerun.py — a rerun of a period writes its set over the first run's fully applied set
(spec 045 T6.1 fix round; owner decision 2026-11-12; PRD F6-AC2, F6-AC3; SDD Error Handling `set-exists`).

Split out of test_review_deliver.py (its fixtures and helpers are imported) to keep that file from growing.
Pinned here, on `review-instructions.py` against the guarded fake: a set at the stem's path that this delivery
did not write is `set-exists` while any action in it waits — none applied, or some — and nothing is written;
once every action carries `applied: true` the set is the finished one of an earlier run, `preview` says so
(`set_applied`) and `deliver` writes the new set JSON over it under the `modified` the probe read, and the new MD
over the old one, with the usual steps recorded; a delivery that fails after the set JSON landed resumes over
the old MD without `name-taken`, and never rewrites the set it wrote itself — also when Hashi applied it in
between. The emptied set of a drop (`actions: []`) never counts as applied. The classifier's side of the same
decision is in tests/test_review_state.py (a fresh record over a fully applied set reads `open`).

Mechanisms a mutation falsifies: `review_state.all_applied` answering True for an empty or partly applied set, or
False for a fully applied one, flips `test_deliver_refuses_a_set_that_is_not_fully_applied` or
`test_deliver_writes_the_new_set_over_a_fully_applied_one`; the overwrite path going through the loop's
`deliver_step` fails the latter with `name-taken`; a resume that forgets `set_replaced` fails
`test_resume_after_the_set_json_landed_overwrites_the_old_md_and_keeps_its_own_set`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import test_review_deliver as deliver_tests  # noqa: E402 — puts tomo/scripts on the path
from test_review_deliver import (  # noqa: E402
    DOC, LANDED, SET_JSON, SET_MD, STEM, TARGET, meta_of, ready, set_json_of, vault, writes,
)
from lib.kado_client import KadoError  # noqa: E402

# the fixtures of test_review_deliver.py, found by pytest in this module's globals
doc_mod, ins, instance = deliver_tests.doc_mod, deliver_tests.ins, deliver_tests.instance

OLD_MD = "---\ntomo:\n  doc_type: instructions\n---\n# old readable instructions\n- [x] Applied\n"


def _old_set(*applied: bool) -> bytes:
    """A first run's set at the path: one `replace_section` per flag, applied as the flag says."""
    actions = [{"action": "replace_section", "target_path": TARGET, "anchor": {"type": "heading", "value": "Tomo Review"},
                "content": "## Tomo Review\n", "applied": flag} for flag in applied]
    return (json.dumps({"schema_version": "1.0.0", "type": "tomo-instructions", "generated": "2026-01-01T00:00:00Z",
                        "profile": "miyo", "md_peer": f"{STEM}_instructions", "actions": actions}, indent=2)
            + "\n").encode("utf-8")


def _rerun(doc_mod, ins, instance, monkeypatch, capsys, *applied: bool):
    """Pass 1 of a rerun over a target that holds the section and the first run's set with the given flags."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys,
                      vault(LANDED, **{SET_JSON: _old_set(*applied), SET_MD: OLD_MD}))
    assert meta_of(instance)["steps_done"] == [] and meta_of(instance)["failed_step"] == ""
    return cli, fake


@pytest.mark.parametrize("applied", [(False,), (True, False), ()], ids=["none-applied", "partly-applied", "emptied"])
def test_deliver_refuses_a_set_that_is_not_fully_applied(doc_mod, ins, instance, monkeypatch, capsys, applied):
    cli, fake = _rerun(doc_mod, ins, instance, monkeypatch, capsys, *applied)
    before = dict(fake.files)
    _, out, _ = cli("preview", "--stem", STEM)
    assert out["status"] == "ok" and out["problems"] == ["set-exists"], out
    assert out["set_exists"] is True and out["set_applied"] is False
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "refused" and out["problems"] == ["set-exists"] and err == ""
    assert writes(fake) == [] and fake.files == before
    assert meta_of(instance)["steps_done"] == [] and "set_replaced" not in meta_of(instance)


def test_deliver_writes_the_new_set_over_a_fully_applied_one(doc_mod, ins, instance, monkeypatch, capsys):
    cli, fake = _rerun(doc_mod, ins, instance, monkeypatch, capsys, True, True)
    old_modified = fake.modified[SET_JSON]
    _, out, _ = cli("preview", "--stem", STEM)
    assert out["status"] == "ok" and out["problems"] == [] and out["mode"] == "replace", out
    assert out["set_exists"] is True and out["set_applied"] is True
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "delivered" and err == "" and out["paths"] == {"set_json": SET_JSON, "set_md": SET_MD}, out
    assert writes(fake) == [("write_file", SET_JSON), ("write_note", SET_MD), ("write_note", DOC)]
    assert fake.guards[-1] == (SET_JSON, old_modified), "the set JSON is written under the modified the probe read"
    new = set_json_of(fake)
    assert [a["action"] for a in new["actions"]] == ["replace_section"] and not any(a.get("applied") for a in new["actions"])
    assert "old readable instructions" not in fake.text(SET_MD) and "### I01" in fake.text(SET_MD)
    meta = meta_of(instance)
    assert meta["steps_done"] == ["set_json", "set_md", "doc_mark"] and meta["set_replaced"] is True
    # the new set waits unapplied: the stem reads delivered, and a second deliver is set-exists as for any first set
    assert cli("status", "--stem", STEM)[1] == {"state": "delivered", "stem": STEM}
    assert cli("deliver", "--stem", STEM)[1]["problems"] == ["set-exists"]


def test_deliver_over_an_applied_set_that_hashi_rewrote_meanwhile_stops_resumably(doc_mod, ins, instance,
                                                                                   monkeypatch, capsys):
    cli, fake = _rerun(doc_mod, ins, instance, monkeypatch, capsys, True)
    original = fake.read_file

    def read_then_bump(path, *a, **kw):
        out = original(path, *a, **kw)
        if path == SET_JSON:
            fake._bump(SET_JSON)                                # rewritten between the probe and the write
        return out
    monkeypatch.setattr(fake, "read_file", read_then_bump)
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "stopped" and out["problems"] == ["kado-write-failed"] and out["failed_step"] == "set_json"
    assert err == "review-instructions: delivery failed at set_json (KadoToolError)\n"
    assert set_json_of(fake)["actions"][0]["applied"] is True, "the old set is untouched"
    monkeypatch.setattr(fake, "read_file", original)
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed" and meta_of(instance)["steps_done"] == ["set_json", "set_md", "doc_mark"]


@pytest.mark.parametrize("hashi_applies_between", [False, True], ids=["set-waits", "hashi-applied-meanwhile"])
def test_resume_after_the_set_json_landed_overwrites_the_old_md_and_keeps_its_own_set(
        doc_mod, ins, instance, monkeypatch, capsys, hashi_applies_between):
    cli, fake = _rerun(doc_mod, ins, instance, monkeypatch, capsys, True)
    fake.fail[("write_note", SET_MD)] = KadoError("503")
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "stopped" and out["failed_step"] == "set_md"
    assert meta_of(instance)["steps_done"] == ["set_json"] and meta_of(instance)["set_replaced"] is True
    assert "old readable instructions" in fake.text(SET_MD), "the old MD is still there"
    fake.fail.clear()
    if hashi_applies_between:
        doc = set_json_of(fake)
        doc["actions"][0]["applied"] = True
        fake.files[SET_JSON] = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
        fake._bump(SET_JSON)
    fake.events.clear()
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed" and err == "", out
    assert writes(fake) == [("write_note", SET_MD), ("write_note", DOC)], "the set JSON is never written twice"
    assert "### I01" in fake.text(SET_MD) and "old readable instructions" not in fake.text(SET_MD)
    assert bool(set_json_of(fake)["actions"][0].get("applied")) is hashi_applies_between
    assert meta_of(instance)["steps_done"] == ["set_json", "set_md", "doc_mark"]
    assert cli("status", "--stem", STEM)[1]["state"] == ("applied" if hashi_applies_between else "delivered")
