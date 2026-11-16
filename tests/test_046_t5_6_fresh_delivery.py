#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t5_6_fresh_delivery.py — the two cures the skill offers after `name-taken` at a set step are real
(spec 046 T5.6; SDD Error Handling row "Resume over an uploaded v3 set": the skill offers a fresh delivery;
docs/tomo/dot_claude/skills/periodic-review.md "Why Steps 7 and 8 Ask per Section in the Deliver Step").

A resume over an earlier set waiting at the set's path refuses `name-taken` with `step` `set_json`. The skill
tells the user to apply that set in Hashi, or to delete it and its readable file in Obsidian, then to Resume. On
`review-instructions.py` against the guarded fake (tests/review_deliver_helpers). Mechanisms a mutation falsifies:

- `replaces_set` reading `any_applied` and the set steps going through `_overwrite_step`: without it the resume
  after Hashi applied the earlier set refuses `name-taken` again (`test_an_applied_earlier_set_lets_resume_deliver`);
- `staged_delivery` writing a step in flight when nothing sits at its path
  (`test_a_deleted_earlier_set_lets_resume_deliver`);
- `deliver` reporting `step` with `name-taken`, the field the skill branches on
  (`test_name_taken_names_the_step_the_skill_branches_on`).

All data is synthetic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_deliver_helpers import (  # noqa: E402,F401 — doc_mod, ins, instance are fixtures
    SET_JSON, SET_MD, STEM, meta_of, ready, set_json_of, vault,
    doc_mod, ins, instance,
)
from lib.kado_client import KadoError  # noqa: E402

__all__ = ["doc_mod", "ins", "instance"]            # fixtures, used by name

OLD_MD = "---\ntomo:\n  doc_type: instructions\n---\n# old readable instructions\n"


def _old_set(applied: bool) -> bytes:
    action = {"id": "I01", "action": "replace_section", "target_path": "x.md",
              "anchor": {"type": "heading", "value": "Tomo Review"}, "content": "## Tomo Review\n", "applied": applied}
    return (json.dumps({"schema_version": "3", "type": "tomo-instructions", "generated": "2026-01-01T00:00:00Z",
                        "profile": "miyo", "md_peer": f"{STEM}_instructions", "actions": [action]}, indent=2)
            + "\n").encode("utf-8")


def _stalled_over_an_earlier_set(doc_mod, ins, instance, monkeypatch, capsys):
    """A delivery stopped at `set_json`; meanwhile an earlier set and its readable file wait at the paths."""
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault())
    fake.fail[("write_file", SET_JSON)] = KadoError("503")
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "stopped" and out["failed_step"] == "set_json", out
    del fake.fail[("write_file", SET_JSON)]
    fake.files[SET_JSON], fake.modified[SET_JSON] = _old_set(False), 1
    fake.files[SET_MD], fake.modified[SET_MD] = OLD_MD, 1
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "refused" and out["problems"] == ["name-taken"], out
    return cli, fake, out


def test_name_taken_names_the_step_the_skill_branches_on(doc_mod, ins, instance, monkeypatch, capsys):
    _, _, out = _stalled_over_an_earlier_set(doc_mod, ins, instance, monkeypatch, capsys)
    assert out["exists_path"] == SET_JSON and out["step"] == "set_json", out


def test_an_applied_earlier_set_lets_resume_deliver(doc_mod, ins, instance, monkeypatch, capsys):
    cli, fake, _ = _stalled_over_an_earlier_set(doc_mod, ins, instance, monkeypatch, capsys)
    fake.files[SET_JSON], fake.modified[SET_JSON] = _old_set(True), 2         # Hashi applied it
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed", out
    assert set_json_of(fake)["generated"] != "2026-01-01T00:00:00Z", "the earlier set is written over"
    assert "old readable instructions" not in fake.files[SET_MD]
    assert meta_of(instance)["steps_done"] == ["set_json", "set_md", "doc_mark"]


def test_a_deleted_earlier_set_lets_resume_deliver(doc_mod, ins, instance, monkeypatch, capsys):
    cli, fake, _ = _stalled_over_an_earlier_set(doc_mod, ins, instance, monkeypatch, capsys)
    for path in (SET_JSON, SET_MD):                                            # the user deletes both in Obsidian
        del fake.files[path]
        fake.modified.pop(path, None)
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed", out
    assert set_json_of(fake)["generated"] != "2026-01-01T00:00:00Z", "the earlier set is written over"
    assert meta_of(instance)["steps_done"] == ["set_json", "set_md", "doc_mark"]
