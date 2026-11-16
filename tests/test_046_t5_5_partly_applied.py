#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t5_5_partly_applied.py — a partly applied set is delivered over, and a resume over another set at the
path is `name-taken` (spec 046 T5.5; SDD ADR-12, ADR-5; Error Handling rows "Set partly applied" and "Resume over an
uploaded v3 set"; docs/tomo/scripts/review-instructions.md "WHY a Partly Applied Set Is Written Over").

On `review-instructions.py` against the guarded fake (tests/review_deliver_helpers). Mechanisms a mutation falsifies:

- `load_run` reading `review_state.any_applied` (not `all_applied`) for the overwrite: with `all_applied` the
  partly applied set is `set-exists` and `test_a_partly_applied_set_reads_open_and_is_deliverable` fails;
- the overwrite going through `_overwrite_step` with the `modified` the probe read (the guard assertion);
- `drop` keeping `already-applied` on a partly applied set
  (`test_drop_on_a_partly_applied_set_refuses_and_a_new_delivery_still_lands`);
- `staged_delivery` comparing a step in flight with the set at the path
  (`test_a_resume_over_an_earlier_set_at_the_path_is_name_taken`).

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
    LANDED, SET_JSON, SET_MD, STEM, TARGET, meta_of, ready, set_json_of, vault, writes,
    doc_mod, ins, instance,
)
from review_state_helpers import APPROVED, _doc  # noqa: E402
from lib import review_delivery as rdl  # noqa: E402
from lib import review_state as rs  # noqa: E402
from lib.kado_client import KadoError  # noqa: E402

__all__ = ["doc_mod", "ins", "instance"]            # fixtures, used by name

OLD_MD = "---\ntomo:\n  doc_type: instructions\n---\n# old readable instructions\n"


def _old_set(*applied: bool, version: str = "3") -> bytes:
    actions = [{"id": f"I{n:02d}", "action": "replace_section", "target_path": TARGET,
                "anchor": {"type": "heading", "value": "Tomo Review"}, "content": "## Tomo Review\n", "applied": flag}
               for n, flag in enumerate(applied, start=1)]
    return (json.dumps({"schema_version": version, "type": "tomo-instructions", "generated": "2026-01-01T00:00:00Z",
                        "profile": "miyo", "md_peer": f"{STEM}_instructions", "actions": actions}, indent=2)
            + "\n").encode("utf-8")


def _rerun(doc_mod, ins, instance, monkeypatch, capsys, *applied: bool):
    return ready(doc_mod, ins, instance, monkeypatch, capsys,
                 vault(LANDED, **{SET_JSON: _old_set(*applied), SET_MD: OLD_MD}))


def test_a_partly_applied_set_reads_open_and_is_deliverable(doc_mod, ins, instance, monkeypatch, capsys):
    cli, fake = _rerun(doc_mod, ins, instance, monkeypatch, capsys, True, False)
    held = json.loads(fake.text(SET_JSON))
    assert rs.partly_applied(held) and rs.review_state(_doc("2026-W13", "week", APPROVED), None, held) == "open"
    old_modified = fake.modified[SET_JSON]
    _, out, _ = cli("preview", "--stem", STEM)
    assert out["status"] == "ok" and out["problems"] == [], out
    assert out["set_exists"] is True and out["set_applied"] is False, "set_applied keeps meaning every action"
    _, out, err = cli("deliver", "--stem", STEM)
    assert out["status"] == "delivered" and err == "", out
    assert writes(fake) == [("write_file", SET_JSON), ("write_note", SET_MD), ("write_note", fake_doc(fake))]
    assert fake.guards[-1] == (SET_JSON, old_modified), "written under the modified the probe read"
    assert not any(a.get("applied") for a in set_json_of(fake)["actions"])
    assert "old readable instructions" not in fake.text(SET_MD)
    assert meta_of(instance)["set_replaced"] is True


def fake_doc(fake) -> str:
    return next(p for p in fake.files if p.endswith(" Review.md"))


def test_drop_on_a_partly_applied_set_refuses_and_a_new_delivery_still_lands(doc_mod, ins, instance, monkeypatch,
                                                                            capsys):
    cli, fake = _rerun(doc_mod, ins, instance, monkeypatch, capsys, True, False)
    fake.fail[("write_file", SET_JSON)] = KadoError("503")
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "stopped" and out["failed_step"] == "set_json", out
    before = dict(fake.files)
    _, out, _ = cli("drop", "--stem", STEM)
    assert out == {"status": "refused", "stem": STEM, "problems": [rdl.ALREADY_APPLIED]}
    assert fake.files == before, "nothing withdrawn"
    del fake.fail[("write_file", SET_JSON)]
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "resumed", out
    assert meta_of(instance)["steps_done"] == ["set_json", "set_md", "doc_mark"]


def test_a_resume_over_an_earlier_set_at_the_path_is_name_taken(doc_mod, ins, instance, monkeypatch, capsys):
    cli, fake = ready(doc_mod, ins, instance, monkeypatch, capsys, vault())
    fake.fail[("write_file", SET_JSON)] = KadoError("503")
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "stopped" and out["failed_step"] == "set_json", out
    del fake.fail[("write_file", SET_JSON)]
    fake.files[SET_JSON] = _old_set(False, version="3")       # an earlier set uploaded meanwhile, waiting
    fake.modified[SET_JSON] = 1
    before = dict(fake.files)
    _, out, _ = cli("deliver", "--stem", STEM)
    assert out["status"] == "refused" and out["problems"] == ["name-taken"], out
    assert out["exists_path"] == SET_JSON and out["step"] == "set_json"
    assert fake.files == before, "nothing overwritten"
