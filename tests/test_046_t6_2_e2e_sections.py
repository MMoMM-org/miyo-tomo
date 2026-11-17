#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t6_2_e2e_sections.py — a mapped /review end to end for week, month and quarter (spec 046 T6.2;
PRD F6-AC6, F4-AC2, F4-AC3, F5-AC1, F5-AC2; SDD Runtime View "a mapped month, first review then re-run").

Every scenario drives the four review scripts in-process through tests/e2e_046_sections_walk.py (on
tests/review_e2e_walk.Walk), exactly as tomo/dot_claude/skills/periodic-review/SKILL.md calls them: the setup
dialogue with a mapping (`match` → confirmed table → `setup-input` → `vault-config-writer.py review`), `review-read`,
`review-doc write`, the user's edits in Obsidian, `review-instructions preview` / `deliver`, and the reference applier
of Hashi's documented semantics. Every set is validated against the test-only v4 candidate schema
(tests/review_deliver_helpers.candidate_schema; tomo/schemas stays untouched). Mechanisms a mutation falsifies:

- `test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers` (week, month, quarter):
  the unticked section's absence from the set (`review_section_set` routing a dropped section), the user's added
  and edited items reaching the block (`review_doc_parse` → section lines), the first delivery's
  `insert_under_marker` with both markers, the re-run's `replace_between_markers` for a section holding its block
  (`review_section_plan.plan_section` replace branch), nothing for a section unticked on the re-run (its block kept
  byte for byte), an insert for a section delivered for the first time, the ids `I01…In` in mapping order with the
  "Tomo Review" last; the applier shows the user's text unchanged and one block per section after each apply.
- `test_a_section_stop_beside_the_place_problem_takes_one_extra_round` (place first, as SKILL.md step 7 orders it,
  and section first): the first preview reports both `place-missing` and the stop of a section with lines, and
  `deliver` refuses both before any write (`review_delivery.classify` adding the section stop); answering one leaves
  exactly the other; with `--section-choice` and `--place-anchor` the preview is clean, `deliver` takes both flags
  and the skipped section gets no marker.
- `test_an_unmapped_review_keeps_the_spec_045_shape` (week, month, quarter): with no mapping the set is the one
  "Tomo Review" `insert_under_marker` with the spec 045 marker and no section marker.

Every write attempted through the client lands under the inbox prefix (the fixture). All data is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_deliver_helpers import SCHEMAS, schema_errors  # noqa: E402
from e2e_046_sections_walk import (  # noqa: E402
    KINDS, REVIEW_HEADING, Kind, SectionWalk, blocks, marker_count, proposals, user_text,
)
from review_e2e_walk import INBOX, TICKED, tomo_sections  # noqa: E402

KIND_IDS = list(KINDS)


@pytest.fixture
def walk(tmp_path, monkeypatch, capsys, request):
    w = SectionWalk(tmp_path, monkeypatch, capsys, request.node.nodeid)
    yield w
    outside = [p for p in w.vault.recorded if not p.startswith(INBOX)]
    assert outside == [], f"Tomo wrote outside the inbox: {outside}"


def _item(walk: SectionWalk, k: Kind, text: str) -> str:
    [line] = [ln for ln in walk.doc(k.doc).splitlines() if text in ln and "%%t" in ln]
    return line


def _checkbox(sid: str, ticked: bool = True) -> str:
    return f"- [{'x' if ticked else ' '}] Use this section %%{sid}%%"


def _actions(walk: SectionWalk, k: Kind) -> list[tuple]:
    doc = walk.set_json(k.stem)
    for schema in SCHEMAS:
        assert schema_errors(doc, schema) == [], (schema.name, schema_errors(doc, schema))
    return [(a["id"], a["action"], a.get("start_marker") or a["anchor"]["value"]) for a in doc["actions"]]


def _markers(k: Kind, sid: str) -> tuple[str, str]:
    return f"%% tomo:{sid} {k.period} %%", f"%% /tomo:{sid} {k.period} %%"


def _assert_one_block_each(text: str, k: Kind, expected: dict) -> None:
    """Exactly one marker pair per section in `expected` (with those lines), none for the others."""
    for sid in ("s1", "s2", "s3"):
        assert marker_count(text, sid, k.period) == ((1, 1) if sid in expected else (0, 0)), (sid, text)
    assert blocks(text) == {sid: [lines] for sid, lines in expected.items()}, text
    assert tomo_sections(text) == 1 and text.count(f"## {REVIEW_HEADING}\n") == 1, "one Tomo Review section"
    assert user_text(text) == k.target_text, "the user's text outside Tomo's blocks is unchanged"


# ── F6-AC6: week, month and quarter run end to end as a month does ─────────────────────────


@pytest.mark.parametrize("name", KIND_IDS)
def test_a_mapped_review_runs_end_to_end_and_a_rerun_replaces_between_markers(walk: SectionWalk, name: str):
    k = KINDS[name]
    (h1, _), (h2, _), (h3, _) = k.rows
    a, b, c = k.sources
    # setup with a mapping: the confirmed table is saved by the writer
    saved = walk.setup_mapped(k)
    assert saved["status"] == "written" and any(key.endswith(f".sections.{k.template}") for key in saved["keys"])
    assert walk.start(k.period)["setup"][name] == "present"
    # Pass 1: the document by section
    out = walk.pass1(k.period, k.kind, proposals(k, "v1"))
    assert out["status"] == "written" and out["target"] == k.target and out["target_exists"] is True, out
    assert walk.vault.recorded == [k.doc]
    for sid in ("s1", "s2", "s3"):
        assert _checkbox(sid) in walk.doc(k.doc)
    # the user: untick s3, add an item to s1, edit s2's item, approve
    s1_item = _item(walk, k, f"{h1} item v1")
    walk.edit(k, (_checkbox("s3"), _checkbox("s3", False)),
              (s1_item, f"{s1_item}\n- [x] A line of my own"),
              (_item(walk, k, f"{h2} item v1"), "- [x] Rewritten by me %%t2%%"),
              ("- [ ] Approved", TICKED))
    # Pass 2: preview, deliver
    out = walk.preview(k.stem)
    assert out["status"] == "ok" and out["problems"] == [] and out["mode"] == "insert", out
    assert {s["key"]: (s["mode"], s["lines"]) for s in out["sections"]} == {
        "s1": ("insert", [f"- {h1} item v1 ([[{a}]])", "- A line of my own"]),
        "s2": ("insert", ["- Rewritten by me"])}, out["sections"]
    assert out["dropped"] == [{"key": "s3", "added": 0}] and "section-dropped" in out["notices"]
    assert walk.deliver(k.stem)["status"] == "delivered"
    s1_start, s1_end = _markers(k, "s1")
    s2_start, _ = _markers(k, "s2")
    assert _actions(walk, k) == [("I01", "insert_under_marker", h1), ("I02", "insert_under_marker", h2),
                                 ("I03", "insert_under_marker", walk.meta(k.stem)["delivered_plan"]["place"]["anchor"])]
    first = walk.set_json(k.stem)["actions"]
    assert first[0]["content"].startswith(f"{s1_start}\n") and f"\n{s1_end}\n" in first[0]["content"]
    assert first[1]["content"].startswith(f"{s2_start}\n") and "Rewritten by me" in first[1]["content"]
    assert not any(f"{h3} item" in act["content"] for act in first), "the unticked section is not delivered"
    # Hashi applies
    assert walk.hashi_apply(k.stem) == ["applied"] * 3
    applied = walk.vault.text(k.target)
    _assert_one_block_each(applied, k, {"s1": [f"- {h1} item v1 ([[{a}]])", "- A line of my own"],
                                        "s2": ["- Rewritten by me"]})
    s2_block = blocks(applied)["s2"]
    # the re-run: replace the document, untick s2 this time, keep s1 and s3
    out = walk.pass1(k.period, k.kind, proposals(k, "v2"))
    assert out["status"] == "refused" and out["problems"] == ["review-exists"], out
    assert walk.replace(k.stem, "--confirm")["status"] == "replaced"
    walk.edit(k, (_checkbox("s2"), _checkbox("s2", False)), ("- [ ] Approved", TICKED))
    out = walk.preview(k.stem)
    assert out["status"] == "ok" and out["problems"] == [] and out["mode"] == "replace", out
    assert {s["key"]: s["mode"] for s in out["sections"]} == {"s1": "replace", "s3": "insert"}, out["sections"]
    assert out["dropped"] == [{"key": "s2", "added": 0}] and "block-replaced" in out["notices"]
    assert walk.deliver(k.stem)["status"] == "delivered"
    s3_anchor = h3
    assert _actions(walk, k) == [("I01", "replace_between_markers", s1_start), ("I02", "insert_under_marker", s3_anchor),
                                 ("I03", "replace_section", REVIEW_HEADING)]
    [replace] = [act for act in walk.set_json(k.stem)["actions"] if act["action"] == "replace_between_markers"]
    assert replace["end_marker"] == s1_end and replace["scope"] == {"heading": h1, "level": 2}
    assert replace["content"] == f"- {h1} item v2 ([[{a}]])"
    assert walk.hashi_apply(k.stem) == ["applied"] * 3
    rerun = walk.vault.text(k.target)
    _assert_one_block_each(rerun, k, {"s1": [f"- {h1} item v2 ([[{a}]])"], "s2": s2_block[0],
                                      "s3": [f"- {h3} item v2 ([[{c}]])"]})
    assert blocks(rerun)["s2"] == s2_block, "the section unticked on the re-run keeps its block"
    assert f"{h2} item v2" not in rerun and f"[[{b}]]" not in rerun.split(f"## {REVIEW_HEADING}")[0]
    assert "Group item v2" in rerun and "Group item v1" not in rerun, "the Tomo Review section was replaced"
    assert walk.listing() == [(k.stem, "applied")]


# ── carried from Phase 5: a section stop beside the place problem ──────────────────────────


def _without_lessons_and_place(k: Kind) -> str:
    """The user removed "Lessons" (s2's heading) and renamed "In my own words" (the Tomo Review place)."""
    return k.target_text.replace("## Lessons\nmy own lessons text\n\n", "").replace(
        "## In my own words", "## Own words")


def _stopped_twice(walk: SectionWalk, k: Kind) -> str:
    walk.setup_mapped(k)
    assert walk.pass1(k.period, k.kind, proposals(k, "v1"))["status"] == "written"
    walk.approve(k.doc)
    walk.vault.files[k.target] = note = _without_lessons_and_place(k)
    first = walk.preview(k.stem)
    assert first["status"] == "ok" and first["problems"] == ["place-missing", "section-missing"], first
    [s2] = [s for s in first["sections"] if s["key"] == "s2"]
    assert s2["stop"] == "section-missing" and s2["choices"] == ["skip", "review"]
    refused = walk.deliver(k.stem)
    assert refused["status"] == "refused" and set(refused["problems"]) == {"place-missing", "section-missing"}
    assert walk.vault.recorded == [k.doc], "nothing is delivered before both answers"
    return note


def _headings(out: dict) -> list:
    return [h["text"] if isinstance(h, dict) else h for h in out["headings"]]


@pytest.mark.parametrize("order", ["place-first", "section-first"])
def test_a_section_stop_beside_the_place_problem_takes_one_extra_round(walk: SectionWalk, order: str):
    """Both problems come in the first preview. SKILL.md step 7 ("Beside another problem only that problem's line
    applies") answers the place first, then asks the section choice: one extra round. The scripts converge the
    same way when the section choice comes first (the order the Phase 5 carry-over note names)."""
    k = KINDS["week"]
    note = _stopped_twice(walk, k)
    if order == "place-first":
        second = walk.preview(k.stem)
        assert "Own words" in _headings(second) and second["place"]["anchor"] == "In my own words", second
        second = walk.preview(k.stem, "--place-anchor", "Own words")
        assert second["problems"] == ["section-missing"], second
    else:
        second = walk.preview(k.stem, "--section-choice", "s2=skip")
        assert second["problems"] == ["place-missing"] and "Own words" in _headings(second), second
    third = walk.preview(k.stem, "--section-choice", "s2=skip", "--place-anchor", "Own words")
    assert third["problems"] == [] and {s["key"]: s["mode"] for s in third["sections"]} == {
        "s1": "insert", "s2": "skip", "s3": "insert"}, third
    out = walk.deliver(k.stem, "--section-choice", "s2=skip", "--place-anchor", "Own words")
    assert out["status"] == "delivered", out
    assert _actions(walk, k) == [("I01", "insert_under_marker", "Wins"), ("I02", "insert_under_marker", "Next"),
                                 ("I03", "insert_under_marker", "Own words")]
    assert walk.hashi_apply(k.stem) == ["applied"] * 3
    text = walk.vault.text(k.target)
    assert marker_count(text, "s2", k.period) == (0, 0) and "Lessons item" not in text
    assert user_text(text) == note


# ── the unmapped e2e path: spec 045's shape ───────────────────────────────────────────────


@pytest.mark.parametrize("name", KIND_IDS)
def test_an_unmapped_review_keeps_the_spec_045_shape(walk: SectionWalk, name: str):
    k = KINDS[name]
    assert walk.setup(k.kind, *k.match_flags)["status"] == "written"
    props = proposals(k, "v1")
    del props["sections"]
    assert walk.pass1(k.period, k.kind, props)["status"] == "written"
    assert "%%s1%%" not in walk.doc(k.doc)
    walk.approve(k.doc)
    assert walk.deliver(k.stem)["status"] == "delivered"
    [action] = walk.set_json(k.stem)["actions"]
    assert action["action"] == "insert_under_marker" and action["id"] == "I01"
    assert action["content"].startswith(f"## {REVIEW_HEADING}\n%% tomo-review {k.period} %%\n")
    assert walk.hashi_apply(k.stem) == ["applied"]
    text = walk.vault.text(k.target)
    assert "%% tomo:" not in text and tomo_sections(text) == 1
    assert user_text(text) == k.target_text
