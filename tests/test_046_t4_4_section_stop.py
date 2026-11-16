#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t4_4_section_stop.py — Pass 2 stops on a section checkbox it cannot read (spec 046 T4.4).

- ``lib/review_actions._gate`` refuses ``section-checkbox-missing`` right after
  ``approved-line-missing`` and before ``not-approved``; the plan then holds no
  action and ``lib/review_delivery.classify`` calls it refusing (F3-AC6, Rule 7)
- a document whose ``s1`` heading carries ``%%s3%% %%s1%%`` with ``s3`` ticked
  files ``t1``/``t2`` under ``s3``; only the gate keeps them from landing
- ``review-doc.py parse`` prints ``section_problems`` (key, restore line; no
  heading text) and ``section_counts`` for a mapped document, neither key for
  an unmapped one (spec 045's stdout unchanged)

Documents are the T4.2 renderer's own output, edited the way a user would.
All data is synthetic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent / "tomo" / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

from lib import review_actions as ra  # noqa: E402
from lib import review_delivery as rdl  # noqa: E402
from lib import review_doc_parse as rdp  # noqa: E402
from test_046_t4_2_doc_sections import WEEK_PROPS, inst, mapped_week, meta_of, script, write  # noqa: E402
from test_046_t4_3_section_parse import S1_BOX, S1_HEAD, S3_BOX, edit, parse  # noqa: E402
from test_review_doc import _config, item, proposals, week_read  # noqa: E402
from test_review_instructions import plan  # noqa: E402

__all__ = ["inst", "script"]                       # the T4.2 fixtures, used by name

MISSING = rdp.SECTION_CHECKBOX_MISSING
APPROVE = ("- [ ] Approved", "- [x] Approved")


@pytest.fixture
def written(script, inst, monkeypatch, capsys):
    """``(document text, meta.json, the fake vault, its doc path)`` of the mapped T4.2 week, approved."""
    _, out, fake = write(script, monkeypatch, capsys, inst, mapped_week(), WEEK_PROPS)
    path = out["doc_path"]
    fake.files[path] = edit(fake.text(path), *APPROVE)
    return fake.text(path), meta_of(inst), fake, path


def _plan_of(text: str, meta: dict) -> ra.ReviewPlan:
    return plan(review=parse(text, meta).approved_review())


@pytest.mark.parametrize(("warnings", "approved", "expected"), [
    ([MISSING], True, MISSING),
    ([MISSING], False, MISSING),                                   # before not-approved
    ([rdp.APPROVED_MISSING, MISSING], False, rdp.APPROVED_MISSING),  # after approved-line-missing
    ([], True, None),
])
def test_the_gate_refuses_a_missing_section_checkbox_after_the_approved_line(warnings, approved, expected):
    assert ra._gate({"warnings": warnings, "approved": approved}, [("Erledigt", [["- x"]])]) == expected


def test_section_checkbox_missing_is_refusing():
    assert MISSING in rdl.REFUSING and MISSING not in rdl.NOTICES


def test_an_intact_approved_mapped_document_plans_actions(written):
    text, meta, _, _ = written
    p = _plan_of(text, meta)
    assert MISSING not in p.problems and p.actions, "the control: the edit below is what stops it"


def test_a_deleted_section_checkbox_plans_nothing_and_refuses(written):
    text, meta, _, _ = written
    p = _plan_of(edit(text, S1_BOX + "\n", ""), meta)
    assert p.problems[0] == MISSING and p.actions == [] and p.section_md == ""
    assert rdl.classify(p)[0] == [MISSING]       # the refusing side; unlanded-items stays a notice


def test_another_expected_key_first_on_a_heading_with_that_section_ticked_delivers_nothing(written):
    text, meta, _, _ = written
    doubled = edit(edit(text, S1_HEAD, "## What Went Well This Week? %%s3%% %%s1%%"),
                   S3_BOX, S3_BOX.replace("- [ ]", "- [x]"))
    parsed = parse(doubled, meta)
    assert parsed.sections["s3"] is True and parsed.sections["s1"] is None
    assert {it.id: it.group for it in parsed.items if it.id in ("t1", "t2")} == {"t1": "s3", "t2": "s3"}
    p = _plan_of(doubled, meta)
    assert rdl.classify(p)[0] == [MISSING] and p.actions == []


def _parse_out(script, monkeypatch, capsys, fake):
    monkeypatch.setattr(script, "KadoClient", fake)
    code = script.main(["--profiles-dir", "profiles", "parse", "--stem", "2026-W13_review"])
    out, err = capsys.readouterr()
    return code, json.loads(out), out + err


def test_parse_prints_the_section_problems_and_counts_of_a_mapped_document(script, monkeypatch, capsys, written):
    text, _, fake, path = written
    fake.files[path] = edit(text, S1_BOX + "\n", "")
    code, out, raw = _parse_out(script, monkeypatch, capsys, fake)
    assert code == 0 and MISSING in out["warnings"]
    assert out["section_problems"] == [{"key": "s1", "restore": S1_BOX}]
    assert out["section_counts"]["s1"] == {"ticked": None, "kept": 2, "unticked": 0, "added": 0, "empty": False}
    assert set(out["section_counts"]) == {"s1", "s3", "s4", "s2"}
    assert "What Went Well" not in raw, "no heading text on stdout or stderr"


def test_parse_of_an_intact_mapped_document_has_no_section_problems(script, monkeypatch, capsys, written):
    _, _, fake, _ = written
    code, out, _ = _parse_out(script, monkeypatch, capsys, fake)
    assert code == 0 and out["section_problems"] == [] and out["section_counts"]["s3"]["ticked"] is False


def test_parse_of_an_unmapped_document_carries_no_section_keys(script, inst, monkeypatch, capsys):
    _config(inst)
    props = proposals(done=[item("Woche aufgeräumt", "2026-03-28")])
    _, _, fake = write(script, monkeypatch, capsys, inst, week_read(), props)
    code, out, _ = _parse_out(script, monkeypatch, capsys, fake)
    assert code == 0 and "section_problems" not in out and "section_counts" not in out
