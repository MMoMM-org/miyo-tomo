#!/usr/bin/env python3
# version: 0.1.0
"""test_review_e2e_failures.py — the month and the failure paths of /review end to end on the fake vault
(spec 045 T6.1; PRD Secondary User Journeys 3, 4, 5, 7; PRD Edge Cases; F5-AC10; KPI Quality; SDD Runtime View,
Error Handling).

The companion of test_review_e2e.py over the same driver (tests/review_e2e_walk.py): the month over its
dailies and weekly notes in new-note mode — the new note waits in the inbox, Hashi's move lands it in the
monthly folder, the next start reports `applied`; a Kado failure at each delivery step (note, set JSON,
set MD, the document mark) is `stopped` with that `failed_step`, the next start offers `failed-delivery`,
and Resume finishes with every payload written once; a drop after a partial delivery leaves only a
withdrawn set (an empty `actions` list Hashi applies nothing from, an MD naming every file to delete) and
the review is never listed again; a drop whose MD write failed (set emptied, meta unmarked) is listed
again, Resume on it refuses `set-withdrawn` and writes nothing, a second drop completes it. Every write
attempted through the client — the injected failures included — is under the inbox prefix, per test and
over whatever ran before the sweep test. All data is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_e2e_walk import (  # noqa: E402
    CONFIG, INBOX, MONTH, MONTH_DOC, MONTH_PERIOD, MONTH_STEM, MONTH_TARGET, WRITES, Walk, frontmatter,
    tomo_sections,
)
from lib.kado_client import KadoError  # noqa: E402

SET_JSON, SET_MD = f"{INBOX}{MONTH_STEM}_instructions.json", f"{INBOX}{MONTH_STEM}_instructions.md"
NEW_NOTE = f"{INBOX}{MONTH_PERIOD}.md"
STEP_WRITES = {"note": ("write_note", NEW_NOTE), "set_json": ("write_file", SET_JSON),
               "set_md": ("write_note", SET_MD), "doc_mark": ("write_note", MONTH_DOC)}
PAYLOADS = {"set_json": SET_JSON, "set_md": SET_MD, "note": NEW_NOTE}


@pytest.fixture
def ready(tmp_path, monkeypatch, capsys, request):
    """A walk whose setup is confirmed for both kinds (the fixture config)."""
    w = Walk(tmp_path, monkeypatch, capsys, request.node.nodeid, config=CONFIG)
    yield w
    outside = [p for p in w.vault.recorded if not p.startswith(INBOX)]
    assert outside == [], f"Tomo wrote outside the inbox: {outside}"


def _approved_month(walk: Walk) -> None:
    """Journey 4 up to the Deliver question: the month read with its weekly notes, written, approved."""
    assert walk.start("month")["setup"] == {"week": "present", "month": "present"}
    read = walk.read(MONTH_PERIOD, MONTH)
    assert read["status"] == "ok" and read["report"]["weekly_status"] == "found", read
    assert [w["week"] for w in read["report"]["weekly_notes"]] == ["2026-W09", "2026-W10", "2026-W11", "2026-W12",
                                                                 "2026-W13", "2026-W14"]
    out = walk.write(MONTH_STEM, MONTH)
    assert out["status"] == "written" and out["target"] == MONTH_TARGET and out["target_exists"] is False, out
    assert out["counts"]["done"] == 1 and out["counts"]["weekly_only"] == 1 and out["counts"]["not_in_weekly"] == 0
    assert "## Only in the weekly reviews" in walk.doc(MONTH_DOC) and "[[2026-W13]]" in walk.doc(MONTH_DOC)
    assert walk.listing() == [(MONTH_STEM, "open")]
    walk.approve(MONTH_DOC)
    out = walk.preview(MONTH_STEM)
    assert out["mode"] == "new-note" and out["problems"] == [] and out["notices"] == ["templater_hint"], out
    assert out["target"] == MONTH_TARGET and out["section_md"].startswith("## Tomo Review\n")


# ── journey 3 + 4: the month in new-note mode, applied by Hashi's move ───────────────────


def test_month_with_weekly_notes_new_note_waits_in_the_inbox_until_hashi_moves_it(ready: Walk):
    walk = ready
    before = walk.vault.outside_inbox()
    _approved_month(walk)
    out = walk.deliver(MONTH_STEM)
    assert out["status"] == "delivered" and out["paths"] == PAYLOADS, out
    assert walk.vault.recorded == [MONTH_DOC, NEW_NOTE, SET_JSON, SET_MD, MONTH_DOC]
    assert walk.meta(MONTH_STEM)["steps_done"] == ["note", "set_json", "set_md", "doc_mark"]
    note = walk.vault.text(NEW_NOTE)
    assert tomo_sections(note) == 1 and "## Theme" in note and note.index("## Tomo Review") < note.index("## Reflections")
    assert "<% tp.file.title %>" in note, "the template kept as it is: the readable instructions say to run Templater"
    assert "Templater" in walk.vault.text(SET_MD)
    action = walk.set_json(MONTH_STEM)["actions"][0]
    assert action["action"] == "move_note" and (action["source"], action["destination"]) == (NEW_NOTE, MONTH_TARGET)
    assert walk.vault.outside_inbox() == before and walk.listing() == [(MONTH_STEM, "delivered")]
    assert walk.hashi_apply(MONTH_STEM) == ["applied"]
    assert NEW_NOTE not in walk.vault.files and walk.vault.text(MONTH_TARGET) == note
    assert walk.listing() == [(MONTH_STEM, "applied")] and walk.listing() == []
    assert frontmatter(walk.doc(MONTH_DOC))["tomo"]["state"] == "approved"


# ── F5-AC10: a delivery that fails at any step resumes without a duplicate ───────────────


@pytest.mark.parametrize("step", list(STEP_WRITES))
def test_delivery_failure_at_each_step_is_offered_as_failed_delivery_and_resumes_once(ready: Walk, step: str):
    walk = ready
    _approved_month(walk)
    method, path = STEP_WRITES[step]
    walk.vault.fail[(method, path)] = KadoError("503 after retries")
    out = walk.deliver(MONTH_STEM)
    assert out["status"] == "stopped" and out["failed_step"] == step and out["problems"] == ["kado-write-failed"], out
    assert out["paths"] == PAYLOADS and walk.meta(MONTH_STEM)["failed_step"] == step
    order = [STEP_WRITES[s][1] for s in ("note", "set_json", "set_md")]
    landed = [p for p in order if p in walk.vault.files]
    assert landed == order[:list(STEP_WRITES).index(step)], "the steps before the failed one landed, none after"
    assert walk.listing() == [(MONTH_STEM, "failed-delivery")], "the next /review offers Resume or Drop"
    assert walk.status(MONTH_STEM)["state"] == "failed-delivery"
    walk.vault.fail.clear()
    out = walk.deliver(MONTH_STEM)
    assert out["status"] == "resumed" and out["paths"] == PAYLOADS, out
    assert walk.meta(MONTH_STEM) ["steps_done"] == list(STEP_WRITES) and walk.meta(MONTH_STEM)["failed_step"] == ""
    for payload in PAYLOADS.values():
        assert walk.vault.writes.count(payload) == 1, (payload, walk.vault.writes)
    assert walk.vault.writes.count(MONTH_DOC) == 2, "Pass 1 and the one mark"
    assert walk.listing() == [(MONTH_STEM, "delivered")]
    assert walk.hashi_apply(MONTH_STEM) == ["applied"] and walk.listing() == [(MONTH_STEM, "applied")]
    assert tomo_sections(walk.vault.text(MONTH_TARGET)) == 1


# ── the edge case: a drop after a partial delivery leaves only a withdrawn set ───────────


def test_drop_after_a_partial_delivery_leaves_only_a_withdrawn_set(ready: Walk):
    walk = ready
    before = walk.vault.outside_inbox()
    _approved_month(walk)
    walk.vault.fail[("write_note", SET_MD)] = KadoError("503")
    assert walk.deliver(MONTH_STEM)["failed_step"] == "set_md"
    walk.vault.fail.clear()
    assert walk.listing() == [(MONTH_STEM, "failed-delivery")]
    assert walk.set_json(MONTH_STEM)["actions"][0]["action"] == "move_note", "the set Tomo wrote waits for Hashi"
    out = walk.drop(MONTH_STEM)                                              # the user answers Drop
    assert out == {"status": "withdrawn", "stem": MONTH_STEM, "paths": PAYLOADS}, out
    withdrawn = walk.set_json(MONTH_STEM)
    assert withdrawn["actions"] == [] and withdrawn["type"] == "tomo-instructions"
    md = walk.vault.text(SET_MD)
    assert "delete these files" in md and all(f"`{p}`" in md for p in PAYLOADS.values())
    assert walk.hashi_apply(MONTH_STEM) == [], "Hashi applies nothing from it"
    assert walk.vault.outside_inbox() == before and MONTH_TARGET not in walk.vault.files
    assert walk.meta(MONTH_STEM)["withdrawn"] is True
    assert walk.status(MONTH_STEM) == {"state": None, "stem": MONTH_STEM} and walk.listing() == []
    assert walk.deliver(MONTH_STEM)["problems"] == ["set-exists"], "never delivered again over the withdrawn set"
    assert set(walk.vault.recorded) == {MONTH_DOC, NEW_NOTE, SET_JSON, SET_MD}


# ── SDD 1.7: the half-withdrawn drop is listed again; Resume refuses; a second drop completes ──


def test_half_withdrawn_drop_is_listed_again_resume_refuses_and_a_second_drop_completes(ready: Walk):
    walk = ready
    _approved_month(walk)
    walk.vault.fail[("write_note", SET_MD)] = KadoError("503")
    assert walk.deliver(MONTH_STEM)["failed_step"] == "set_md"
    # the drop empties the set, then its MD write fails: half withdrawn, meta unmarked
    out = walk.drop(MONTH_STEM)
    assert out["status"] == "stopped" and out["problems"] == ["kado-write-failed"], out
    assert walk.set_json(MONTH_STEM)["actions"] == [] and walk.meta(MONTH_STEM)["withdrawn"] is False
    assert SET_MD not in walk.vault.files
    assert walk.listing() == [(MONTH_STEM, "failed-delivery")], "listed again until the mark is written"
    # Resume on the emptied set is refused and writes nothing
    recorded = list(walk.vault.recorded)
    out = walk.deliver(MONTH_STEM)
    assert out["status"] == "refused" and out["problems"] == ["set-withdrawn"], out
    assert walk.preview(MONTH_STEM)["problems"] == ["set-withdrawn"]
    assert walk.vault.recorded == recorded and walk.set_json(MONTH_STEM)["actions"] == []
    assert frontmatter(walk.doc(MONTH_DOC))["tomo"]["state"] == "pending-approval", "never marked delivered"
    # Drop once more completes the withdrawal
    walk.vault.fail.clear()
    out = walk.drop(MONTH_STEM)
    assert out == {"status": "withdrawn", "stem": MONTH_STEM, "paths": PAYLOADS}, out
    assert "delete these files" in walk.vault.text(SET_MD) and walk.meta(MONTH_STEM)["withdrawn"] is True
    assert walk.listing() == [] and walk.status(MONTH_STEM)["state"] is None
    assert walk.hashi_apply(MONTH_STEM) == []


# ── the module's sweep: every write of every test above, under the inbox prefix ──────────


def test_every_write_attempted_so_far_was_under_the_inbox_prefix():
    """Order-independent: whatever ran before this test, every write attempted through the client (landed or
    refused — the injected failures above are attempts too) was under the inbox; no count is assumed."""
    assert [(t, p) for t, p in WRITES if not p.startswith(INBOX)] == []
    assert all(isinstance(t, str) and Path(t.split("::")[0]).name.startswith("test_review_e2e") for t, _ in WRITES)
