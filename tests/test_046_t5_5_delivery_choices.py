#!/usr/bin/env python3
# version: 0.1.1
"""test_046_t5_5_delivery_choices.py — Pass 2 of a mapped review: section stops, choices, notices (spec 046 T5.5).

SDD Internal API `review-instructions.py preview|deliver --stem <stem> [--section-choice <key>=skip|review ...]
[--confirm-moved <key> ...]`, Error Handling Pass 2 rows, ADR-12; PRD F4-AC4, F4-AC6, F3-AC4, F3-AC5, F5-AC4;
docs/tomo/scripts/review-instructions.md "WHY Every Section Stop Refuses Until a Choice Answers It".

On the mapped T4.2 week (s1 `end` under "In my own words", s3 `before` "Planning" — empty, unticked —, s4 `under`
"Notes", s2 an analysis row), written by `review-doc.py write`, approved, then run through `review-instructions.py`
against the guarded fake. Mechanisms a mutation falsifies:

- `classify` adding the stop of a section with lines: without it a stopped section is left out quietly and
  `deliver` writes (`test_a_missing_heading_stops_the_whole_delivery_before_any_write`);
- a stop of a section without lines refusing nothing (`test_a_stop_of_a_section_without_lines_refuses_nothing`);
- the choice flags reaching `build_review_plan` (`test_skip_leaves_the_section_out_and_review_routes_it`);
- `untaken` (`test_a_choice_the_plan_did_not_take_refuses_choice_invalid`);
- the flag parser's exit 2 (`test_a_malformed_or_doubled_choice_is_a_bad_invocation`);
- `nothing-to-deliver` on a plan without actions (`test_every_section_skipped_and_nothing_for_tomo_review`);
- the section notices and `section_counts` (`test_a_rerun_replaces_the_block_and_says_so`,
  `test_dropped_and_empty_sections_are_named_with_the_users_own_count`);
- `report` naming each section's configured placement, not Hashi's
  (`test_the_preview_names_each_sections_configured_placement`).

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

from review_deliver_helpers import GuardedVault, ins, schema_errors, SCHEMAS  # noqa: E402,F401 — ins is a fixture
from test_046_t4_2_doc_sections import (  # noqa: E402,F401 — inst and script are fixtures
    MARKER, WEEK_PROPS, WEEK_ROWS, inst, map_config, mapped_week, script, section, write,
)
from test_046_t4_3_section_parse import edit  # noqa: E402
from test_review_doc import INBOX, WEEKLY, item  # noqa: E402

__all__ = ["ins", "inst", "script"]                 # fixtures, used by name

STEM = "2026-W13_review"
TARGET = f"{WEEKLY}2026-W13.md"
SET_JSON = f"{INBOX}{STEM}_instructions.json"
SET_MD = f"{INBOX}{STEM}_instructions.md"
NOTE = ("# 2026-W13\n### Planning\nplan text\n\n## Notes\nnote text\n\n## In my own words\nmeine Worte\n\n"
        "#### What Went Well This Week?\ngut\n")
S4_START, S4_END = "%% tomo:s4 2026-W13 %%", "%% /tomo:s4 2026-W13 %%"
S4_BLOCK = f"{S4_START}\n- alt\n{S4_END}\n"
APPROVE = ("- [ ] Approved", "- [x] Approved")
PLACED = {"s1": "end", "s3": "before", "s4": "under"}       # WEEK_ROWS' placements into the note
S4_LINE = "- Notiz zu X ([[2026-03-24]])"


def approved(script, inst, monkeypatch, capsys, note=NOTE, props=WEEK_PROPS, **files) -> GuardedVault:
    """Pass 1 of the mapped week into a guarded fake holding ``note``, then the user ticks Approved."""
    fake = GuardedVault({TARGET: note, **files})
    _, out, _ = write(script, monkeypatch, capsys, inst, mapped_week(), props, fake)
    path = out["doc_path"]
    fake.files[path] = edit(fake.text(path), *APPROVE)
    fake.modified[path] = fake.modified.get(path, 0) + 1
    fake.events.clear()
    fake.writes.clear()
    return fake


def cli(ins, monkeypatch, capsys, fake, *argv):
    monkeypatch.setattr(ins, "KadoClient", fake)
    code = ins.main(["--profiles-dir", "profiles", *argv])
    out, err = capsys.readouterr()
    assert MARKER not in err
    return code, (json.loads(out) if out.strip() else None), err


def writes(fake) -> list:
    return [e for e in fake.events if e[0] in ("write_note", "write_file")]


def set_json(fake) -> dict:
    return json.loads(fake.text(SET_JSON))


def meta(inst) -> dict:
    return json.loads((inst / "tomo-tmp" / "review" / STEM / "meta.json").read_text(encoding="utf-8"))


def by_key(out: dict) -> dict:
    return {s["key"]: s for s in out["sections"]}


# ---------------------------------------------------------------- the first delivery


def test_the_preview_lists_every_section_with_lines_mode_and_lines(script, inst, ins, monkeypatch, capsys):
    fake = approved(script, inst, monkeypatch, capsys)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM)
    assert out["status"] == "ok" and out["problems"] == [], out
    assert [s["key"] for s in out["sections"]] == ["s1", "s4"], "mapping order; s3 holds no lines"
    s4 = by_key(out)["s4"]
    assert s4["mode"] == "insert" and s4["lines"] == [S4_LINE] and s4["notices"] == []
    assert "stop" not in s4 and "choices" not in s4
    assert all(s["placement"] == PLACED[s["key"]] for s in out["sections"]), out["sections"]
    assert "unlanded-items" not in out["notices"], "kept section items land in their block"
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "deliver", "--stem", STEM)
    assert out["status"] == "delivered", out
    assert [s["key"] for s in out["sections"]] == ["s1", "s4"] and "lines" not in out["sections"][0]
    assert all(s["placement"] == PLACED[s["key"]] for s in out["sections"]), out["sections"]
    assert "Notiz zu X" not in json.dumps(out), "deliver prints no item text"
    doc = set_json(fake)
    assert [(a["id"], a["action"]) for a in doc["actions"]] == [
        ("I01", "insert_under_marker"), ("I02", "insert_under_marker"), ("I03", "insert_under_marker")]
    for schema in SCHEMAS:
        assert schema_errors(doc, schema) == []


def test_the_preview_names_each_sections_configured_placement(script, inst, ins, monkeypatch, capsys):
    props = {**WEEK_PROPS, "sections": [*WEEK_PROPS["sections"], section("s3", item("Plan B", "2026-03-24"))]}
    fake = approved(script, inst, monkeypatch, capsys, props=props)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM)
    assert out["problems"] == [], out
    assert {s["key"]: s["placement"] for s in out["sections"]} == PLACED, "before / under / end, as configured"
    assert [s["mode"] for s in out["sections"]] == ["insert"] * 3
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "deliver", "--stem", STEM)
    assert out["status"] == "delivered", out
    assert {s["key"]: s["placement"] for s in out["sections"]} == PLACED
    hashi = {s["key"]: s["placement"] for s in meta(inst)["delivered_plan"]["sections"]}
    assert hashi == {"s1": "inside", "s3": "before", "s4": "after"}, "the record keeps Hashi's placement"


def test_dropped_and_empty_sections_are_named_with_the_users_own_count(script, inst, ins, monkeypatch, capsys):
    fake = approved(script, inst, monkeypatch, capsys)
    path = next(p for p in fake.files if p.endswith(" Review.md"))
    text = fake.text(path)
    text = edit(text, "- [x] Abschnitt übernehmen %%s1%%", "- [ ] Abschnitt übernehmen %%s1%%")
    text = edit(text, "- [x] Notiz zu X ([[2026-03-24]]) %%t3%%\n",
                "- [ ] Notiz zu X ([[2026-03-24]]) %%t3%%\n- [x] meins\n- [x] meins zwei\n")
    fake.files[path] = edit(text, "- [x] Schlaf unter 6", "- [ ] Schlaf unter 6")
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM)
    assert out["status"] == "ok" and out["problems"] == [], out
    assert out["dropped"] == [{"key": "s1", "added": 0}], "s3 started unticked with nothing: not dropped"
    assert out["empty"] == ["s2"]
    assert "section-dropped" in out["notices"] and "section-empty" in out["notices"]
    assert by_key(out)["s4"]["lines"] == ["- meins", "- meins zwei"]
    # the user's own items in an unticked section are counted
    text = edit(fake.text(path), "- [x] Abschnitt übernehmen %%s4%%", "- [ ] Abschnitt übernehmen %%s4%%")
    fake.files[path] = text
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM)
    assert {"key": "s4", "added": 2} in out["dropped"], out


# ---------------------------------------------------------------- the stops


def test_a_missing_heading_stops_the_whole_delivery_before_any_write(script, inst, ins, monkeypatch, capsys):
    fake = approved(script, inst, monkeypatch, capsys, note=NOTE.replace("## Notes\nnote text\n\n", ""))
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM)
    assert out["status"] == "ok" and out["problems"] == ["section-missing"], out
    s4 = by_key(out)["s4"]
    assert s4["stop"] == "section-missing" and s4["choices"] == ["skip", "review"] and s4["mode"] == "missing"
    assert s4["placement"] == "under"
    before = dict(fake.files)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "deliver", "--stem", STEM)
    assert out["status"] == "refused" and out["problems"] == ["section-missing"], out
    assert by_key(out)["s4"]["choices"] == ["skip", "review"] and by_key(out)["s4"]["placement"] == "under"
    assert writes(fake) == [] and fake.files == before
    assert meta(inst)["steps_done"] == [] and "delivered_plan" not in meta(inst)


def test_an_ambiguous_heading_stops_with_skip_and_review(script, inst, ins, monkeypatch, capsys):
    note = NOTE.replace("## In my own words", "## Notes\nzweite\n\n## In my own words")
    fake = approved(script, inst, monkeypatch, capsys, note=note)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM)
    assert out["problems"] == ["section-ambiguous"], out
    assert by_key(out)["s4"]["choices"] == ["skip", "review"]


def test_skip_leaves_the_section_out_and_review_routes_it(script, inst, ins, monkeypatch, capsys):
    fake = approved(script, inst, monkeypatch, capsys, note=NOTE.replace("## Notes\nnote text\n\n", ""))
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM, "--section-choice", "s4=review")
    assert out["problems"] == [] and by_key(out)["s4"]["mode"] == "review", out
    assert by_key(out)["s4"]["placement"] == "under", "routed: still the configured placement"
    assert "Notiz zu X" in out["section_md"], "routed into Tomo Review"
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "deliver", "--stem", STEM, "--section-choice", "s4=skip")
    assert out["status"] == "delivered", out
    assert by_key(out)["s4"]["mode"] == "skip" and by_key(out)["s4"]["placement"] == "under"
    doc = set_json(fake)
    assert [a["id"] for a in doc["actions"]] == ["I01", "I02"], "dense ids without s4"
    assert not any("Notiz zu X" in a["content"] for a in doc["actions"])
    record = meta(inst)["delivered_plan"]
    assert record["choices_given"] is True
    assert record["sections"] == [
        {"key": "s1", "mode": "insert", "placement": "inside", "scope_level": None},
        {"key": "s4", "mode": "skip", "placement": None, "scope_level": None}]


def test_a_broken_block_offers_skip_only(script, inst, ins, monkeypatch, capsys):
    note = NOTE.replace("## Notes\nnote text\n", f"## Notes\n{S4_START}\n- alt\nnote text\n")
    fake = approved(script, inst, monkeypatch, capsys, note=note)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM)
    assert out["problems"] == ["section-broken"] and by_key(out)["s4"]["choices"] == ["skip"], out
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM, "--section-choice", "s4=review")
    assert out["problems"] == ["section-broken", "choice-invalid"] and out["choices_invalid"] == ["s4"], out


def test_a_block_inside_tomo_review_stops(script, inst, ins, monkeypatch, capsys):
    note = NOTE.replace("## In my own words", f"## Tomo Review\n%% tomo-review 2026-W13 %%\n{S4_BLOCK}\n"
                                              "## In my own words")
    fake = approved(script, inst, monkeypatch, capsys, note=note)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM)
    assert "block-in-review-section" in out["problems"] and by_key(out)["s4"]["choices"] == ["skip"], out


def test_a_moved_block_stops_and_is_replaced_there_only_when_confirmed(script, inst, ins, monkeypatch, capsys):
    note = NOTE.replace("plan text\n", f"plan text\n{S4_BLOCK}")
    fake = approved(script, inst, monkeypatch, capsys, note=note)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM)
    s4 = by_key(out)["s4"]
    assert out["problems"] == ["section-moved"] and s4["choices"] == ["skip", "confirm-moved"], out
    assert s4["block_at"] == {"heading": "Planning", "level": 3}
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "deliver", "--stem", STEM, "--confirm-moved", "s4")
    assert out["status"] == "delivered", out
    assert "block-moved-confirmed" in out["notices"] and "block-replaced" in out["notices"]
    [action] = [a for a in set_json(fake)["actions"] if a["action"] == "replace_between_markers"]
    assert action["scope"] == {"heading": "Planning", "level": 3} and action["start_marker"] == S4_START
    assert meta(inst)["delivered_plan"]["sections"][1] == {"key": "s4", "mode": "replace", "placement": None,
                                                           "scope_level": 3}
    for schema in SCHEMAS:
        assert schema_errors(set_json(fake), schema) == []


def test_a_rerun_replaces_the_block_and_says_so(script, inst, ins, monkeypatch, capsys):
    note = NOTE.replace("## Notes\nnote text\n", f"## Notes\n{S4_BLOCK}note text\n")
    fake = approved(script, inst, monkeypatch, capsys, note=note)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM)
    assert out["problems"] == [] and out["notices"] == ["block-replaced"], out
    s4 = by_key(out)["s4"]
    assert s4["mode"] == "replace" and s4["notices"] == ["block-replaced"] and s4["scope_level"] == 2
    assert s4["placement"] == "under", "a replace has no Hashi placement, but the configured one is named"


@pytest.mark.parametrize(("stop", "choices"), [
    ("missing", ("skip", "review")), ("ambiguous", ("skip", "review")), ("broken", ("skip",)),
    ("moved", ("skip", "confirm-moved")), ("in-review", ("skip",)), ("landing-off-limits", ())])
def test_every_section_stop_refuses_with_its_offered_choices(stop, choices):
    from lib import review_actions as ra
    from lib import review_delivery as rdl
    from lib import review_section_plan as rsp
    p = rsp.SectionPlan("s4", stop, S4_START, S4_END, lines=["- x"], placement="under")
    p.offers = choices
    plan = ra.ReviewPlan("insert", TARGET, False, [], {}, sections=[p], actions=[{"id": "I01"}])
    problems, _ = rdl.classify(plan)
    assert problems == [rsp.STOPS[stop]] and rsp.STOPS[stop] in rdl.REFUSING
    assert rdl.section_report(plan, {}, {}, lines=False)["sections"] == [
        {"key": "s4", "mode": stop, "placement": "under", "notices": [], "stop": rsp.STOPS[stop],
         "choices": list(choices)}]


def test_a_stop_of_a_section_without_lines_refuses_nothing():
    from lib import review_actions as ra
    from lib import review_delivery as rdl
    from lib import review_section_plan as rsp
    plan = ra.ReviewPlan("insert", TARGET, False, [], {}, actions=[{"id": "I01"}],
                         sections=[rsp.SectionPlan("s3", "missing", "a", "b")])
    assert rdl.classify(plan) == ([], [])
    assert rdl.section_report(plan, {}, {}, lines=True)["sections"] == []


def test_review_section_kept_is_a_notice():
    from lib import review_actions as ra
    from lib import review_delivery as rdl
    plan = ra.ReviewPlan("replace", TARGET, False, [], {}, notices=["review-section-kept"], actions=[{"id": "I01"}])
    assert rdl.classify(plan) == ([], ["review-section-kept"])


def test_every_section_skipped_and_nothing_for_tomo_review(script, inst, ins, monkeypatch, capsys):
    map_config(inst, WEEK_ROWS, trackers=False)
    props = {"language": "de", "sections": [section("s4", item("Notiz zu X", "2026-03-24"))], "groups": {}}
    fake = approved(script, inst, monkeypatch, capsys, note=NOTE.replace("## Notes\nnote text\n\n", ""),
                    props=props)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "deliver", "--stem", STEM, "--section-choice", "s4=skip")
    assert out["status"] == "refused" and out["problems"] == ["nothing-to-deliver"], out
    assert writes(fake) == []


# ---------------------------------------------------------------- the choice flags


def test_a_choice_the_plan_did_not_take_refuses_choice_invalid(script, inst, ins, monkeypatch, capsys):
    fake = approved(script, inst, monkeypatch, capsys, note=NOTE.replace("## Notes\nnote text\n\n", ""))
    for argv, invalid in ((["--section-choice", "s9=skip"], ["s9"]),          # no such section
                          (["--section-choice", "s1=skip"], ["s1"]),          # s1 has no stop
                          (["--confirm-moved", "s4"], ["s4"])):               # s4 is missing, not moved
        _, out, _ = cli(ins, monkeypatch, capsys, fake, "deliver", "--stem", STEM, *argv)
        assert out["status"] == "refused" and "choice-invalid" in out["problems"], (argv, out)
        assert out["choices_invalid"] == invalid
    assert writes(fake) == []
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM,
                    "--section-choice", "s4=skip", "--section-choice", "s1=review")
    assert out["problems"] == ["choice-invalid"] and out["choices_invalid"] == ["s1"], out


@pytest.mark.parametrize("argv", [["--section-choice", "s4=maybe"], ["--section-choice", "s4"],
                                  ["--section-choice", "=skip"], ["--section-choice", "s 4=skip"],
                                  ["--section-choice", "s4=skip", "--section-choice", "s4=review"],
                                  ["--section-choice", "s4=skip", "--confirm-moved", "s4"]],
                         ids=["unknown-choice", "no-equals", "empty-key", "space", "twice", "both-flags"])
def test_a_malformed_or_doubled_choice_is_a_bad_invocation(ins, argv):
    with pytest.raises(SystemExit) as stop:
        ins.main(["preview", "--stem", STEM, *argv])
    assert stop.value.code == 2


def test_both_flags_parse_into_one_mapping(ins):
    args = ins.build_parser().parse_args(["deliver", "--stem", STEM, "--section-choice", "s1=skip",
                                          "--confirm-moved", "s4", "--section-choice", "s2=review"])
    assert args.choices == {"s1": "skip", "s4": "confirm-moved", "s2": "review"}
    assert ins.build_parser().parse_args(["preview", "--stem", STEM]).choices is None


# ---------------------------------------------------------------- the record and the resume


def _stopped_at_set_md(script, inst, ins, monkeypatch, capsys):
    from lib.kado_client import KadoError
    fake = approved(script, inst, monkeypatch, capsys, note=NOTE.replace("## Notes\nnote text\n\n", ""))
    fake.fail[("write_note", SET_MD)] = KadoError("503")
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "deliver", "--stem", STEM, "--section-choice", "s4=skip")
    assert out["status"] == "stopped" and out["failed_step"] == "set_md", out
    del fake.fail[("write_note", SET_MD)]
    fake.events.clear()
    return fake


def test_a_resume_without_the_original_choices_refuses_choices_needed(script, inst, ins, monkeypatch, capsys):
    fake = _stopped_at_set_md(script, inst, ins, monkeypatch, capsys)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "deliver", "--stem", STEM)
    assert out["status"] == "refused" and out["problems"] == ["choices-needed"], out
    assert writes(fake) == []
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "deliver", "--stem", STEM, "--section-choice", "s4=skip")
    assert out["status"] == "resumed", out


def test_a_resume_with_other_choices_refuses_replan_differs(script, inst, ins, monkeypatch, capsys):
    fake = _stopped_at_set_md(script, inst, ins, monkeypatch, capsys)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "deliver", "--stem", STEM, "--section-choice", "s4=review")
    assert out["status"] == "refused" and out["problems"] == ["replan-differs"], out
    assert writes(fake) == []


def test_the_record_holds_keys_and_enums_only(script, inst, ins, monkeypatch, capsys):
    _stopped_at_set_md(script, inst, ins, monkeypatch, capsys)
    record = meta(inst)["delivered_plan"]
    assert set(record) == {"mode", "target", "place", "sections", "choices_given"}
    for entry in record["sections"]:
        assert set(entry) == {"key", "mode", "placement", "scope_level"}
        assert all(v is None or isinstance(v, int) or v in ("insert", "replace", "skip", "review", "before",
                                                             "after", "inside") or v.startswith("s")
                   for v in entry.values()), entry
    dumped = json.dumps(record, ensure_ascii=False)
    for text in ("What Went Well", "Notes", "Planning", "Notiz", "Steuer"):
        assert text not in dumped, text


def test_replan_differs_compares_the_sections():
    from lib import review_actions as ra
    from lib import review_delivery as rdl
    from lib import review_section_plan as rsp

    def plan_with(mode):
        return ra.ReviewPlan("insert", TARGET, False, [], {"anchor": None, "placement": "before", "level": 2},
                             sections=[rsp.SectionPlan("s4", mode, "a", "b", lines=["- x"])])
    record = rdl.plan_record(plan_with("insert"), None, False, False)
    assert record["sections"] == [{"key": "s4", "mode": "insert", "placement": None, "scope_level": None}]
    assert record["choices_given"] is False
    assert rdl.replan_differs(plan_with("insert"), record) is False
    assert rdl.replan_differs(plan_with("skip"), record) is True
    del record["sections"]                                   # a record begun before T5.5: nothing to compare
    assert rdl.replan_differs(plan_with("skip"), record) is False
    unmapped = ra.ReviewPlan("insert", TARGET, False, [], {"anchor": None, "placement": "before", "level": 2})
    assert set(rdl.plan_record(unmapped, None, False, False)) == {"mode", "target", "place"}, "spec 045 unchanged"
