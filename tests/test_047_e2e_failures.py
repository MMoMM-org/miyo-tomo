#!/usr/bin/env python3
# version: 0.1.1
"""test_047_e2e_failures.py — failure, resume and re-review of /review end to end on the new flow
(spec 047 T8.2; PRD F3-AC1, F3-AC11, F4-AC9, F5-AC6, F6-AC1..F6-AC8, F7-AC2, F2-AC1; SDD Complex Logic (b), (c),
(d), Error Handling).

The companion of tests/test_047_baseline_e2e.py over the same driver (tests/review_e2e_walk.py, its
`make_walk` fixture and `Case`): every script called the way the skill calls it, the agents' files built by
the privacy fixture (`condense_files`), the review-proposer stood in for by `propose_from_inputs` where the
test is about what reaches it. Pinned here:

- a re-review of a delivered and applied 2026-03 with a mapped section and a carried item: start over, deliver
  again, Hashi's apply by the reference applier of tests/e2e_046_sections_walk.py → one block per section, the
  carried text present, one instruction set; a broken section checkbox line still stops the second delivery
  (F5-AC6, spec 046 F3-AC6);
- resume: run 1 writes four digests and the carryover, then the session ends; another period's whole review
  leaves that stage as it was; run 2 continues with no Kado call and the stored `read_at`, plans only W13 and
  W14, and writes a document whose fingerprint equals an uninterrupted run's (F6-AC4, F7-AC2); a section mapping
  changed in between reads anew and plans every unit (F6-AC5); a Kado stop after the `--fresh` discard leaves no
  stage content and nothing to continue (F6-AC4, F7-AC2);
- one unit failing twice is named at the top and in `written`, its days are no sources, the rest is reviewed
  (F6-AC1); every unit failing stops `check` with every week named and no document (F6-AC8);
- the carryover failing as a whole: no carried mark, the previous-note lines still shown, the one top line; one
  of two notes failing: the other's item carried, the failed note named (F6-AC2);
- proposals invalid twice (a carried error both times): no document, the errors shown (F6-AC3, script side);
- a Pass 1 abort after the read leaves only `meta.json` and `payloads.json`; the next run reads anew (F6-AC6);
- a start over after delivery reads the previous notes as they stand now and nothing of the period's own note
  or Tomo's block in it; a line removed from the previous note is gone from the material (F6-AC7, F4-AC9);
- 2026-W14 reads 2026-W13 and 2026-02, never 2026-03 (F3-AC1 end to end);
- a previous note's folder listing turned away past the retries and recovered by the end pass: the note is read
  after `finish()` and found (T3.2 carry-over);
- a found note that carried nothing: `written.previous` `found, carried 0` and its line (F3-AC11, T5.6
  carry-over);
- vault growth: created notes on two days of two units reach the proposer as each unit's growth candidates and
  the written group is the group of the notes the read lists, by creation day (F2-AC1, T8.1 carry-over).

The growth group's "before" (T8.1 carry-over): no pre-047 growth path remains to run — spec 046's growth group
was model-written from read.json's `growth.created` (path and links, no creation day), so there is no 046
renderer input to replay. The expected group is derived explicitly instead: the created notes the period
reader lists (`review-read.py`'s `_read`, `growth.created`) by the creation day of their `created` stamp, one
item per day (the fixture digester's one candidate per day) linking that day's notes and then its daily, in day
order. Since spec 047 T9.3 (F-R1-3) `review-doc.py write` builds this group; the fixture proposer proposes none.

All data is synthetic. Every write a walk attempts lies under the inbox (the `make_walk` fixture).
"""
from __future__ import annotations

import copy
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import yaml

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_e2e_walk import (  # noqa: E402
    INBOX, MONTH, MONTH_DOC, MONTH_PERIOD, MONTH_STEM, MONTHLY, WEEK, WEEK_DOC, WEEK_PERIOD, WEEK_STEM, WEEKLY, Walk,
)
from review_privacy_fixture import CONFIG, PRP, condense_files, propose_from_inputs, proposals, put_files  # noqa: E402
from e2e_046_sections_walk import APPLY, KIND_ORDER  # noqa: E402
from review_doc_fingerprint import fingerprint  # noqa: E402
from test_047_baseline_e2e import MONTH_SECTION_ROW, Case, make_walk  # noqa: E402
from lib.kado_client import _MAX_RETRIES, KadoConnectionError, KadoError  # noqa: E402

__all__ = ["make_walk"]                            # the baseline's walk fixture, used by name

MONTH_UNITS = ["2026-W09", "2026-W10", "2026-W11", "2026-W12", "2026-W13", "2026-W14"]
W11_DAYS = [f"2026-03-{d:02d}" for d in range(9, 16)]
FEB = f"{MONTHLY}2026-02.md"
MONTH_TARGET = f"{MONTHLY}{MONTH_PERIOD}.md"
SET_JSON = f"{INBOX}{MONTH_STEM}_instructions.json"
TOP_CARRY_FAILED = "> The previous reviews could not be taken into account."


def _mapped_config() -> dict:
    out = copy.deepcopy(CONFIG)
    out["review"]["monthly"]["sections"] = {"t_month.md": [dict(MONTH_SECTION_ROW)]}
    return out


# quarter=True: the vault with a daily in W10 and W12 too, so all six March units take part
MONTH_CASE = Case(MONTH, MONTH_PERIOD, MONTH_STEM, MONTH_DOC, True, lambda: copy.deepcopy(CONFIG),
                  lambda: proposals(MONTH))
MAPPED_MONTH = Case(MONTH, MONTH_PERIOD, MONTH_STEM, MONTH_DOC, False, _mapped_config, lambda: proposals(MONTH))
WEEK_CASE = Case(WEEK, WEEK_PERIOD, WEEK_STEM, WEEK_DOC, False, lambda: copy.deepcopy(CONFIG),
                 lambda: proposals(WEEK))


# ── helpers over the walk ──

def plan(w: Walk, stem: str) -> dict:
    out = w.run("review-digest", "plan", "--stem", stem)
    assert out["status"] == "ok", out
    return out


def check(w: Walk, stem: str) -> dict:
    return w.run("review-digest", "check", "--stem", stem)


def jobs(answer: dict) -> List[str]:
    """The jobs of a plan answer: the unit of a digester, ``carryover`` for the carryover."""
    return [j.get("unit", "carryover") for r in answer["rounds"] for j in r]


def agents_write(w: Walk, stem: str, answer: dict, *, carry=False, only=None, override=None) -> dict:
    """The agents' files for ``answer``'s jobs (``only``: those outs), then ``override`` {out: text} written raw;
    returns every built file by out."""
    files = condense_files(answer, w.stage(stem), carry=carry)
    put_files(w.stage(stem), {k: v for k, v in files.items() if only is None or k in only})
    for name, text in (override or {}).items():
        (w.stage(stem) / name).parent.mkdir(parents=True, exist_ok=True)
        (w.stage(stem) / name).write_text(text, encoding="utf-8")
    return files


def stage_files(w: Walk, stem: str) -> Dict[str, bytes]:
    root = w.stage(stem)
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def top_lines(document: str) -> List[str]:
    """The quoted lines above the Approved box after the info callout's first line."""
    return [line for line in document.split("- [ ] Approved")[0].split("\n")
            if line.startswith("> ") and not line.startswith("> [!info]")]


def reference_apply(w: Walk, stem: str) -> List[str]:
    """Hashi's apply by the reference applier of tests/e2e_046_sections_walk.py (its ``APPLY`` and planner order)
    on the walk's vault; an applied or skipped action is marked applied in the set JSON."""
    path = f"{INBOX}{stem}_instructions.json"
    doc = json.loads(w.vault.text(path))
    outcomes = {}
    for action in sorted(doc["actions"], key=lambda a: KIND_ORDER.index(a["action"])):
        target = action["target_path"]
        if target not in w.vault.files:
            outcomes[action["id"]] = "failed"
            continue
        result, text = APPLY[action["action"]](w.vault.text(target), action)
        outcomes[action["id"]] = result
        if result == "applied":
            w.vault.files[target] = text
            w.vault._bump(target)
        if result != "failed":
            action["applied"] = True
    w.vault.files[path] = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
    w.vault._bump(path)
    return [outcomes[a["id"]] for a in doc["actions"]]


def _write_config(w: Walk, config: dict) -> None:
    (w.root / "config" / "vault-config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")


# ── F5-AC6: a re-review replaces Tomo's block, carried items included ──

S1_BOX = "- [x] Use this section %%s1%%"


def _mapped_props(text: str = "theme day") -> dict:
    props = proposals(MONTH)
    props["sections"] = [{"key": "s1", "items": [{"text": text, "sources": ["2026-03-01"]}]}]
    return props


def _delivered_mapped_month(w: Walk) -> None:
    """2026-03 read, written with one carried item, delivered as a new note and moved by Hashi."""
    assert w.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    out = w.write(MONTH_STEM, MONTH, _mapped_props(), carry=1, proposer=propose_from_inputs)
    assert out["status"] == "written" and out["rejected"] == [], out
    w.approve(MONTH_DOC)
    assert w.deliver(MONTH_STEM)["status"] == "delivered"
    assert w.hashi_apply(MONTH_STEM) == ["applied"]


def _start_over(w: Walk, props: dict) -> dict:
    """Start over from the delivered review: step 4 with --fresh, step 5, review-exists, replace --confirm."""
    read = w.read(MONTH_PERIOD, MONTH, "--fresh")
    assert read["status"] == "ok" and read["continued"] is False, read
    out = w.write(MONTH_STEM, MONTH, props, carry=1, proposer=propose_from_inputs)
    assert out["status"] == "refused" and out["problems"] == ["review-exists"], out
    out = w.replace(MONTH_STEM, "--confirm")
    assert out["status"] == "replaced" and out["rejected"] == [], out
    return out


def test_rereview_replaces_block_with_carried_items(make_walk):
    w = make_walk(MAPPED_MONTH)
    _delivered_mapped_month(w)
    first = w.vault.text(MONTH_TARGET).split("\n")
    assert "- theme day ([[2026-03-01]])" in first and sum("carried c1 " in line for line in first) == 1
    props = _mapped_props("theme day again")
    props["groups"]["done"][0]["text"] = f"March done again {PRP}"
    _start_over(w, props)
    w.approve(MONTH_DOC)
    out = w.deliver(MONTH_STEM)
    assert out["status"] == "delivered" and out["mode"] == "replace", out
    assert reference_apply(w, MONTH_STEM) == ["applied", "applied"]
    lines = w.vault.text(MONTH_TARGET).split("\n")
    assert (lines.count("%% tomo:s1 2026-03 %%"), lines.count("%% /tomo:s1 2026-03 %%")) == (1, 1)
    assert lines.count("%% tomo-review 2026-03 %%") == 1 and lines.count("## Tomo Review") == 1
    assert "- theme day again ([[2026-03-01]])" in lines and "- theme day ([[2026-03-01]])" not in lines
    assert [line for line in lines if line.startswith("- March done")] == [
        f"- March done again {PRP} ([[2026-03-01]], [[2026-03-23]])"]
    assert [line for line in lines if "carried c1 " in line] == [
        f"- carried c1 {PRP} ([[2026-02]]) · not mentioned again (previous review)"]
    sets = sorted(p for p in w.vault.files if p.startswith(INBOX) and "_instructions" in p)
    assert sets == [SET_JSON, f"{INBOX}{MONTH_STEM}_instructions.md"], sets
    assert [a["action"] for a in w.set_json(MONTH_STEM)["actions"]] == ["replace_between_markers", "replace_section"]


def test_a_broken_section_checkbox_still_stops_the_second_delivery(make_walk):
    w = make_walk(MAPPED_MONTH)
    _delivered_mapped_month(w)
    _start_over(w, _mapped_props())
    w.approve(MONTH_DOC)
    document = w.doc(MONTH_DOC)
    assert S1_BOX in document
    w.edit_document(MONTH_DOC, document.replace(S1_BOX + "\n", "", 1))
    before, set_before = w.vault.text(MONTH_TARGET), w.vault.text(SET_JSON)
    assert w.parse(MONTH_STEM)["warnings"] == ["section-checkbox-missing"]
    out = w.deliver(MONTH_STEM)
    assert out["status"] == "refused" and out["problems"] == ["section-checkbox-missing"], out
    assert w.vault.text(MONTH_TARGET) == before and w.vault.text(SET_JSON) == set_before


# ── F6-AC4, F6-AC5, F7-AC2: resume after an interrupted condense ──

FOUR = [f"digests/{u}.json" for u in MONTH_UNITS[:4]] + ["carryover.json"]


def _interrupted_month(w: Walk) -> dict:
    """Run 1: the read, one plan, four digests and the carryover written, then the session ends."""
    read = w.read(MONTH_PERIOD, MONTH)
    assert read["status"] == "ok" and read["continued"] is False, read
    first = plan(w, MONTH_STEM)
    assert jobs(first) == MONTH_UNITS + ["carryover"]
    agents_write(w, MONTH_STEM, first, carry=1, only=FOUR)
    return read


def test_a_resumed_run_continues_the_stored_read_and_equals_an_uninterrupted_one(make_walk):
    straight = make_walk(MONTH_CASE)
    assert straight.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    expected = straight.write(MONTH_STEM, MONTH, carry=1, proposer=propose_from_inputs)
    assert expected["status"] == "written", expected

    w = make_walk(MONTH_CASE)
    run1 = _interrupted_month(w)
    stored = stage_files(w, MONTH_STEM)
    assert set(FOUR) <= set(stored) and "manifest.json" in stored
    assert w.pass1(WEEK_PERIOD, WEEK)["status"] == "written"        # another period's whole review in between
    assert stage_files(w, MONTH_STEM) == stored, "the interrupted stage stays until 2026-03's next /review"
    calls = w.vault.call_count
    run2 = w.read(MONTH_PERIOD, MONTH)
    assert run2["status"] == "ok" and run2["continued"] is True, run2
    assert (run2["read_id"], run2["read_at"]) == (run1["read_id"], run1["read_at"])
    assert w.vault.call_count == calls, "a continued read makes no Kado call"
    second = plan(w, MONTH_STEM)
    assert jobs(second) == ["2026-W13", "2026-W14"] and len(second["rounds"]) == 1, second["rounds"]
    assert second["done"] == MONTH_UNITS[:4] and second["carryover_state"] == "passed"
    out = w.write(MONTH_STEM, MONTH, carry=1, proposer=propose_from_inputs)
    assert out["status"] == "written", out
    assert fingerprint(w.doc(MONTH_DOC)) == fingerprint(straight.doc(MONTH_DOC))
    assert {k: out[k] for k in ("counts", "rejected", "previous")} == \
        {k: expected[k] for k in ("counts", "rejected", "previous")}
    assert out["previous"][0] == {"kind": "month", "name": "2026-02", "state": "found", "carried": 1}


def test_a_changed_section_mapping_reads_anew_and_plans_every_unit(make_walk):
    w = make_walk(MONTH_CASE)
    run1 = _interrupted_month(w)
    _write_config(w, _mapped_config())
    calls = w.vault.call_count
    run2 = w.read(MONTH_PERIOD, MONTH)
    assert run2["status"] == "ok" and run2["continued"] is False and run2["discarded"] == "sections-changed", run2
    assert run2["read_id"] != run1["read_id"] and w.vault.call_count > calls
    assert not (w.stage(MONTH_STEM) / "digests").exists(), "no digest of the earlier read is left"
    assert jobs(plan(w, MONTH_STEM)) == MONTH_UNITS + ["carryover"]


def test_a_kado_stop_after_the_discard_leaves_nothing_to_continue(make_walk):
    w = make_walk(MONTH_CASE)
    _interrupted_month(w)
    assert "manifest.json" in stage_files(w, MONTH_STEM)
    w.vault.connection_error = KadoConnectionError("Kado is not running")
    out = w.read(MONTH_PERIOD, MONTH, "--fresh")                    # Start over: the stored read goes first
    assert out["status"] == "stopped" and out["error"]["kind"] == "kado-unreachable", out
    assert stage_files(w, MONTH_STEM) == {}, "a Kado stop leaves no material"
    w.vault.connection_error = None
    calls = w.vault.call_count
    again = w.read(MONTH_PERIOD, MONTH)
    assert again["status"] == "ok" and again["continued"] is False and "discarded" not in again, again
    assert w.vault.call_count > calls


# ── F6-AC1, F6-AC8: units that cannot be condensed ──

def _w11_outside(files: dict) -> str:
    """W11's digest naming a W13 day: ``source-outside-unit``."""
    digest = copy.deepcopy(files["digests/2026-W11.json"])
    digest["done"] = [{"text": "a W13 day", "sources": ["2026-03-23"]}]
    return json.dumps(digest)


def test_a_unit_failing_twice_is_named_and_its_days_are_no_sources(make_walk):
    w = make_walk(MONTH_CASE)
    assert w.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    first = plan(w, MONTH_STEM)
    files = condense_files(first, w.stage(MONTH_STEM))
    agents_write(w, MONTH_STEM, first, override={"digests/2026-W11.json": _w11_outside(files)})
    one = check(w, MONTH_STEM)
    assert one["units"]["2026-W11"]["state"] == "retry" and one["ready"] is False, one
    assert [r.get("unit") for r in one["retry"]] == ["2026-W11"]
    (w.stage(MONTH_STEM) / "digests/2026-W11.json").write_text(_w11_outside(files), encoding="utf-8")
    two = check(w, MONTH_STEM)
    assert two["units"]["2026-W11"]["state"] == "failed" and two["ready"] is True, two
    assert two["not_condensed"] == [{"unit": "2026-W11", "days": W11_DAYS}]
    assert "digests/2026-W11.json" not in two["proposer"]["inputs"]
    assert "digests/2026-W10.json" in two["proposer"]["inputs"]
    props = proposals(MONTH)
    props["groups"]["done"].append({"text": f"mid march {PRP}", "sources": ["2026-03-10"]})
    out = w.write(MONTH_STEM, MONTH, props, condense=False)
    assert out["status"] == "written", out
    assert out["not_condensed"] == [{"unit": "2026-W11", "days": W11_DAYS}]
    assert out["rejected"] == [{"group": "done", "index": 1, "reason": "no-source-in-period"}]
    document = w.doc(MONTH_DOC)
    assert "> Not condensed: 2026-W11 (2026-03-09 – 2026-03-15)" in top_lines(document)
    assert f"March done {PRP} ([[2026-03-01]], [[2026-03-23]])" in document and "mid march" not in document


def test_every_unit_failing_stops_with_every_week_named_and_no_document(make_walk):
    w = make_walk(MONTH_CASE)
    assert w.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    first = plan(w, MONTH_STEM)
    broken = {f"digests/{u}.json": "not json" for u in MONTH_UNITS}
    agents_write(w, MONTH_STEM, first, override=broken)
    one = check(w, MONTH_STEM)
    assert one["status"] == "ok" and [r.get("unit") for r in one["retry"]] == MONTH_UNITS, one
    out = check(w, MONTH_STEM)                                     # the re-dispatch wrote nothing better
    assert out["status"] == "stopped" and out["problems"] == ["nothing-condensed"], out
    assert [u["unit"] for u in out["not_condensed"]] == MONTH_UNITS
    assert out["not_condensed"][2] == {"unit": "2026-W11", "days": W11_DAYS}
    assert MONTH_DOC not in w.vault.files and w.vault.recorded == []
    assert "manifest.json" in stage_files(w, MONTH_STEM), "the stage stays (F7-AC2)"


# ── F6-AC2: the carryover fails ──

def test_a_carryover_failing_as_a_whole_carries_nothing_and_says_so_once(make_walk):
    w = make_walk(MONTH_CASE)
    assert w.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    first = plan(w, MONTH_STEM)
    agents_write(w, MONTH_STEM, first, carry=1, override={"carryover.json": "not json"})
    assert check(w, MONTH_STEM)["carryover"]["state"] == "retry"
    (w.stage(MONTH_STEM) / "carryover.json").write_text('{"read_id": "x"}', encoding="utf-8")
    two = check(w, MONTH_STEM)
    assert two["carry_failed"] is True and two["proposer"]["carried"] is False, two
    assert "carryover.json" not in two["proposer"]["inputs"]
    w.checked = two                                                # the answer the proposer is dispatched on
    out = w.write(MONTH_STEM, MONTH, condense=False, proposer=propose_from_inputs)
    assert out["status"] == "written" and out["carry_failed"] is True, out
    assert out["previous"][0] == {"kind": "month", "name": "2026-02", "state": "found", "carried": 0,
                                  "carry_failed": True}
    document = w.doc(MONTH_DOC)
    assert top_lines(document) == ["> Previous review · month [[2026-02]]: found, not taken into account",
                                   "> Previous review · quarter 2025-Q4: no note found for 2025-Q4", TOP_CARRY_FAILED]
    assert "(previous review)" not in document and f"March done {PRP}" in document


def test_one_of_two_notes_failing_carries_the_other_and_names_the_failed_one(make_walk):
    w = make_walk(WEEK_CASE)
    assert w.read(WEEK_PERIOD, WEEK)["status"] == "ok"
    first = plan(w, WEEK_STEM)
    carry = agents_write(w, WEEK_STEM, first, carry=2)["carryover.json"]     # c1 on 2026-W12, c2 on 2026-02
    assert [i["sources"] for i in carry["items"]] == [["2026-W12"], ["2026-02"]]
    carry["items"].append({"id": "c1", "type": "open", "text": "again", "sources": ["2026-02"]})   # duplicate id
    answers = []
    for _ in range(2):
        (w.stage(WEEK_STEM) / "carryover.json").write_text(json.dumps(carry), encoding="utf-8")
        answers.append(check(w, WEEK_STEM))
    assert answers[0]["carryover"]["state"] == "retry", answers[0]
    answer = answers[1]
    assert answer["carry_failed"] is False and answer["proposer"]["carried"] is True, answer
    assert {n["path"]: (n["state"], n["items"]) for n in answer["carryover"]["notes"]} == {
        f"{WEEKLY}2026-W12.md": ("passed", 1), FEB: ("failed", 0)}
    w.checked = answer
    out = w.write(WEEK_STEM, WEEK, condense=False, carry=1, proposer=propose_from_inputs)
    assert out["status"] == "written" and "carry_failed" not in out, out
    assert out["previous"] == [{"kind": "week", "name": "2026-W12", "state": "found", "carried": 1},
                               {"kind": "month", "name": "2026-02", "state": "found", "carried": 0,
                                "carry_failed": True}]
    document = w.doc(WEEK_DOC)
    assert top_lines(document) == ["> Previous review · week [[2026-W12]]: found, 1 carried",
                                   "> Previous review · month [[2026-02]]: found, not taken into account"]
    assert document.count("(previous review)") == 1 and "carried c1 " in document


# ── F6-AC3: proposals invalid twice ──

def _carried_unknown(props: dict, stage: Path, inputs: list) -> dict:
    """The fixture proposer plus a carried item naming an id the carryover lacks."""
    out = propose_from_inputs(props, stage, inputs)
    out["groups"]["open"].append({"text": f"carried {PRP}", "sources": ["2026-02"], "carried": "not_mentioned",
                                  "carried_ids": ["c9"]})
    return out


def test_proposals_invalid_twice_write_no_document_and_show_the_errors(make_walk):
    w = make_walk(MONTH_CASE)
    assert w.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    for attempt in (1, 2):                                         # the proposer, then its one re-dispatch
        out = w.write(MONTH_STEM, MONTH, condense=attempt == 1, carry=1, proposer=_carried_unknown)
        assert out["status"] == "refused" and out["problems"] == ["proposals-invalid"], (attempt, out)
        assert any(e.endswith("carried-unknown (c9)") for e in out["errors"]), out["errors"]
    assert MONTH_DOC not in w.vault.files and w.vault.recorded == []
    assert (w.stage(MONTH_STEM) / "manifest.json").is_file(), "the read stays for a later correction"


# ── F6-AC6: a Pass 1 abort after the read ──

def test_a_pass1_abort_after_the_read_leaves_only_meta_and_payloads(make_walk):
    w = make_walk(MONTH_CASE)
    assert w.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    assert w.write(MONTH_STEM, MONTH)["status"] == "written"
    w.approve(MONTH_DOC)
    w.vault.fail[("write_note", f"{INBOX}{MONTH_STEM}_instructions.md")] = KadoError("503")
    assert w.deliver(MONTH_STEM)["status"] == "stopped"            # an open review: failed-delivery
    w.vault.fail.clear()
    kept = stage_files(w, MONTH_STEM)
    assert sorted(kept) == ["meta.json", "payloads.json"], sorted(kept)
    assert w.read(MONTH_PERIOD, MONTH, "--fresh")["continued"] is False     # Start over: step 4
    agents_write(w, MONTH_STEM, plan(w, MONTH_STEM), only=FOUR)
    assert len(stage_files(w, MONTH_STEM)) > len(kept)
    assert w.replace(MONTH_STEM, "--abort") == {"status": "aborted", "stem": MONTH_STEM}   # the user aborts
    assert stage_files(w, MONTH_STEM) == kept
    calls = w.vault.call_count
    again = w.read(MONTH_PERIOD, MONTH)
    assert again["continued"] is False and "discarded" not in again and w.vault.call_count > calls, again


# ── F6-AC7, F4-AC9: a start over reads the previous notes anew ──

FEB_TWO_ITEMS = "# 2026-02\n\n## Theme\n- start running again\n- call Jana about the trip\n\n## Reflections\nown\n"


def test_a_start_over_reads_the_previous_notes_anew_and_never_the_period_itself(make_walk):
    w = make_walk(MONTH_CASE)
    w.vault.files[FEB] = FEB_TWO_ITEMS
    assert w.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    previous = json.loads((w.stage(MONTH_STEM) / "previous/month-2026-02.json").read_text(encoding="utf-8"))
    assert "- call Jana about the trip" in previous["sections"]["Theme"], previous
    assert w.write(MONTH_STEM, MONTH, carry=1)["status"] == "written"
    w.approve(MONTH_DOC)
    assert w.deliver(MONTH_STEM)["status"] == "delivered" and w.hashi_apply(MONTH_STEM) == ["applied"]
    target = w.vault.text(MONTH_TARGET)
    assert "carried c1 " in target and PRP in target and "%% tomo-review 2026-03 %%" in target
    w.edit_document(FEB, FEB_TWO_ITEMS.replace("- call Jana about the trip\n", ""))    # the user removes an item
    read = w.read(MONTH_PERIOD, MONTH, "--fresh")
    assert [(r["kind"], r["name"], r["state"]) for r in read["report"]["previous"]] == [
        ("month", "2026-02", "found"), ("quarter", "2025-Q4", "missing")]
    previous = json.loads((w.stage(MONTH_STEM) / "previous/month-2026-02.json").read_text(encoding="utf-8"))
    assert previous["sections"]["Theme"] == ["- start running again"], previous
    material = b"\n".join(stage_files(w, MONTH_STEM).values()).decode("utf-8")
    assert "start running again" in material
    assert "call Jana" not in material, "an item removed from the previous note is not carried"
    assert PRP not in material and "tomo-review" not in material, "nothing of the period's own note"
    carrier = [j for r in plan(w, MONTH_STEM)["rounds"] for j in r if j["agent"] == "review-carryover"]
    assert [j["previous_files"] for j in carrier] == [["previous/month-2026-02.json"]]


# ── F3-AC1: a week crossing the month edge ──

def test_w14_reads_w13_and_the_month_before_the_month_it_starts_in(make_walk):
    from test_review_e2e_edges import SPARSE_PERIOD, SPARSE_PROPOSALS, SPARSE_STEM

    w = make_walk(WEEK_CASE)
    w.vault.files[MONTH_TARGET] = "# 2026-03\n\n## Theme\n- march note\n"      # April's previous month
    read = w.read(SPARSE_PERIOD, WEEK)
    assert [(r["role"], r["name"], r["state"]) for r in read["report"]["previous"]] == [
        ("previous-week", "2026-W13", "found"), ("previous-month", "2026-02", "found")]
    assert ("read_note", f"{WEEKLY}2026-W13.md") in w.vault.events and ("read_note", FEB) in w.vault.events
    assert ("read_note", MONTH_TARGET) not in w.vault.events
    out = w.write(SPARSE_STEM, WEEK, copy.deepcopy(SPARSE_PROPOSALS), carry=2)
    assert out["status"] == "written", out
    assert top_lines(w.doc(f"{INBOX}{SPARSE_PERIOD} Review.md")) == [
        "> Previous review · week [[2026-W13]]: found, 1 carried", "> Previous review · month [[2026-02]]: found, 1 carried"]


# ── T3.2 carry-over: a previous note's listing recovered only by the end pass ──

def test_a_previous_listing_recovered_by_the_end_pass_reads_the_note_after_finish(make_walk):
    w = make_walk(MONTH_CASE)
    w.vault.rate_limit(MONTHLY, failures=_MAX_RETRIES + 1)
    read = w.read(MONTH_PERIOD, MONTH)
    assert read["report"]["previous"][0] == {"kind": "month", "name": "2026-02", "role": "previous-month",
                                             "path": FEB, "state": "found", "partly_read": False}
    assert read["report"]["not_read"] == [] and read["report"]["retried"] >= _MAX_RETRIES
    listings = [i for i, e in enumerate(w.vault.events) if e == ("list_dir", MONTHLY)]
    reads = [i for i, e in enumerate(w.vault.events) if e == ("read_note", FEB)]
    assert len(listings) == 2 and len(reads) == 1 and reads[0] > listings[1], (listings, reads)
    out = w.write(MONTH_STEM, MONTH, carry=1)
    assert out["previous"][0] == {"kind": "month", "name": "2026-02", "state": "found", "carried": 1}


# ── F3-AC11, T5.6 carry-over: a found note that carried nothing ──

def test_a_found_note_that_carried_nothing_is_written_found_carried_zero(make_walk):
    w = make_walk(MONTH_CASE)
    assert w.read(MONTH_PERIOD, MONTH)["status"] == "ok"
    out = w.write(MONTH_STEM, MONTH, proposer=propose_from_inputs)
    assert out["status"] == "written", out
    assert out["previous"] == [{"kind": "month", "name": "2026-02", "state": "found", "carried": 0},
                               {"kind": "quarter", "name": "2025-Q4", "state": "missing", "carried": 0}]
    assert top_lines(w.doc(MONTH_DOC))[0] == "> Previous review · month [[2026-02]]: found, nothing carried"


# ── F2-AC1, T8.1 carry-over: vault growth on the new flow ──

CREATED = {"Notes/Kettle descaling.md": "2026-03-10", "Notes/Bike chain.md": "2026-03-24",
           "Notes/Bike tyres.md": "2026-03-24"}                 # two creation days in two units (W11, W13)


def _ms(day: str) -> int:
    """Local noon of ``day`` in Unix ms: the creation day reads back as ``day`` in any time zone offset < 12 h."""
    return int(datetime.fromisoformat(f"{day}T12:00:00").timestamp() * 1000)


def _listed(w: Walk) -> List[dict]:
    """``growth.created`` of the period reader as review-read.py calls it (path and links, spec 046's fields)."""
    mod = w.mods["review-read"]
    config, profile, setup = mod._setup(mod.build_parser().parse_args(["--period", MONTH_PERIOD, "--kind", MONTH]))
    period = mod.period_from(MONTH_PERIOD, MONTH, setup.rule)
    return mod._read(period, mod.sources_from_config(config, profile), mod.day_settings(setup, config))["growth"][
        "created"]


def _growth_lines(document: str) -> List[str]:
    part = document.split("## Vault growth\n", 1)[1].split("\n## ", 1)[0]
    return [re.sub(r"\s*%%t\d+%%$", "", line) for line in part.split("\n") if line.startswith("- [")]


def test_vault_growth_reaches_the_proposer_per_unit_and_is_the_group_the_read_lists(make_walk):
    w = make_walk(MONTH_CASE)
    for path, day in CREATED.items():
        w.vault.files[path] = f"# {Path(path).stem}\nnew note\n"
        w.vault.created[path] = w.vault.modified[path] = _ms(day)
    listed = _listed(w)
    assert sorted(c["path"] for c in listed) == sorted(CREATED)
    seen: Dict[str, list] = {}

    def proposer(props: dict, stage: Path, inputs: list) -> dict:
        for name in (n for n in inputs if n.startswith("digests/")):
            growth = json.loads((stage / name).read_text(encoding="utf-8"))["growth"]
            if growth:
                seen[name[len("digests/"):-len(".json")]] = [(c["sources"], sorted(c["notes"])) for c in growth]
        return propose_from_inputs(props, stage, inputs)

    assert w.read(MONTH_PERIOD, MONTH)["report"]["growth"]["created"] == len(CREATED)
    out = w.write(MONTH_STEM, MONTH, proposer=proposer)
    assert out["status"] == "written" and out["counts"]["growth"] == 2, out
    assert seen == {"2026-W11": [(["2026-03-10"], ["Notes/Kettle descaling.md"])],
                    "2026-W13": [(["2026-03-24"], ["Notes/Bike chain.md", "Notes/Bike tyres.md"])]}
    days = sorted({CREATED[c["path"]] for c in listed})
    notes = {day: sorted(Path(c["path"]).stem for c in listed if CREATED[c["path"]] == day) for day in days}
    assert _growth_lines(w.doc(MONTH_DOC)) == [
        f"- [x] created condensed ({', '.join(f'[[{n}]]' for n in notes[day])}, [[{day}]])" for day in days]
    assert fingerprint(w.doc(MONTH_DOC))["links"]["growth"] == [["other"] * len(notes[day]) + ["daily"]
                                                               for day in days]
