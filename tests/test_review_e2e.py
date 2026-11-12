#!/usr/bin/env python3
# version: 0.1.0
"""test_review_e2e.py — the 2-pass /review flow end to end on the fake vault, without an AI in the loop
(spec 045 T6.1; PRD Secondary User Journeys 1, 2, 5, 6, 7; PRD Edge Cases; KPI Quality; F1-AC10; SDD Runtime View).

Every scenario drives the four review scripts in-process through tests/review_e2e_walk.py, exactly as
tomo/dot_claude/skills/periodic-review/SKILL.md calls them; the user's edits and Hashi's apply are
simulated on the fake vault's files. Pinned here: the week — start with no setup, the setup dialogue
confirmed through `vault-config-writer.py review`, read, proposals, write, the user's edits (untick,
rewrite without links, add, tick Approved), parse counts, preview, deliver, Hashi's apply, the next
start reporting `applied` once; a setup Abort writes nothing; a rerun of the period writes its set over the
first run's applied set and replaces the section (one marker, one heading) — also under a renamed heading; the target created between the
passes turns new-note into insert; the target moved to another folder is found by name and targeted
there; an Abort before Pass 2 (the document deleted) and after it (the set deleted, never applied)
leaves the vault outside the inbox unchanged; every write attempted through the client lands under the
inbox prefix — per test (the fixture) and over whatever ran before the sweep test. The failure paths of
delivery and drop, and the month, are in test_review_e2e_failures.py; the document edge cases, the
setup rerun and the sparse period in test_review_e2e_edges.py. All data is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from review_e2e_walk import (  # noqa: E402
    CONFIG, INBOX, MONTH, MONTH_DOC, MONTH_PERIOD, MONTH_STEM, MONTH_TARGET, TICKED, WEEK, WEEK_DOC, WEEK_PERIOD,
    WEEK_STEM, WEEK_TARGET, WEEK_TARGET_TEXT, WRITES, Walk, frontmatter, tomo_sections,
)

SET_JSON, SET_MD = f"{INBOX}{WEEK_STEM}_instructions.json", f"{INBOX}{WEEK_STEM}_instructions.md"
ARCHIVE_TARGET = f"Archive/{WEEK_PERIOD}.md"


@pytest.fixture
def walk(tmp_path, monkeypatch, capsys, request):
    w = Walk(tmp_path, monkeypatch, capsys, request.node.nodeid)
    yield w
    outside = [p for p in w.vault.recorded if not p.startswith(INBOX)]
    assert outside == [], f"Tomo wrote outside the inbox: {outside}"


@pytest.fixture
def ready(tmp_path, monkeypatch, capsys, request):
    """A walk whose setup is already confirmed (the fixture config), for the scenarios after the first run."""
    w = Walk(tmp_path, monkeypatch, capsys, request.node.nodeid, config=CONFIG)
    yield w
    outside = [p for p in w.vault.recorded if not p.startswith(INBOX)]
    assert outside == [], f"Tomo wrote outside the inbox: {outside}"


def _week_items(text: str) -> list[str]:
    """The three proposals of the week (done, open, theme), in document order; the habits follow them."""
    return [ln for ln in text.splitlines() if ln.startswith("- [x] ") and "%%t" in ln][:3]


# ── journey 1 + the primary journey: first run, the week, applied ─────────────────────────


def test_week_from_first_start_through_hashi_apply(walk: Walk):
    config_before = (walk.root / "config" / "vault-config.yaml").read_bytes()
    outside_before = walk.vault.outside_inbox()
    # 1. start: the request parses, the week is not set up
    out = walk.start(WEEK_PERIOD)
    assert out["status"] == "ok" and out["request"] == {
        "kind": WEEK, "period": WEEK_PERIOD, "year_inferred": False, "source": "arg",
        "start": "2026-03-23", "end": "2026-03-29"}, out
    assert out["setup"] == {"week": "missing", "month": "missing"} and out["open_reviews"] == []
    # 2. setup: match proposes from the vault, the user confirms, the writer saves it, start is rerun
    saved = walk.setup(WEEK)
    assert saved["status"] == "written" and "review.weekly.heading" in saved["keys"], saved
    config = yaml.safe_load((walk.root / "config" / "vault-config.yaml").read_text(encoding="utf-8"))
    assert config["review"]["weekly"]["place"] == {"anchor": "In my own words", "placement": "before"}
    assert config["naming"]["calendar_patterns"]["weekly"] == "GGGG-[W]WW"
    assert config_before != (walk.root / "config" / "vault-config.yaml").read_bytes()
    assert walk.start(WEEK_PERIOD)["setup"] == {"week": "present", "month": "missing"}
    assert not (walk.root / "tomo-tmp" / "review" / "confirmed-week.json").exists()
    # 4 + 5. read the period, propose, write the document to the inbox
    out = walk.pass1(WEEK_PERIOD, WEEK)
    assert out["status"] == "written" and out["doc_path"] == WEEK_DOC and out["target"] == WEEK_TARGET, out
    assert out["target_exists"] is True and out["counts"]["done"] == 1 and out["counts"]["habits"] >= 1
    assert walk.vault.recorded == [WEEK_DOC], "Pass 1 writes the document and nothing else"
    assert not (walk.stage(WEEK_STEM) / "read.json").exists() and walk.meta(WEEK_STEM)["mode"] == "insert"
    assert walk.listing() == [(WEEK_STEM, "open")]
    # 6 before approval: parse says not approved, nothing is delivered
    out = walk.parse(WEEK_STEM)
    assert out["status"] == "ok" and out["approved"] is False and out["warnings"] == []
    assert walk.preview(WEEK_STEM)["problems"] == ["not-approved"]
    assert walk.deliver(WEEK_STEM)["status"] == "refused"
    # 7. the user edits in Obsidian: untick the open item, rewrite the theme without its links, add one, approve
    text = walk.doc(WEEK_DOC)
    done, open_, theme = _week_items(text)
    assert "[[2026-03-23]]" in done and "[[2026-03-26]]" in open_ and "[[2026-03-25]]" in theme
    text = text.replace(open_, open_.replace("- [x]", "- [ ]", 1), 1)
    text = text.replace(theme, "- [x] Sleep was short all week " + theme[theme.index("%%"):], 1)
    text = text.replace("## Open\n", "## Open\n- [x] A line of my own\n", 1)
    text = text.replace("- [ ] Approved", TICKED, 1)
    walk.edit_document(WEEK_DOC, text)
    out = walk.parse(WEEK_STEM)
    assert out["approved"] is True and out["nothing_to_deliver"] is False, out
    assert out["counts"] == {"kept": 5, "unticked": 1, "deleted": 0, "added": 1}, out["counts"]   # 2 + 3 habits
    assert [i["edited"] for i in out["items"]["themes"]] == [True] and out["items"]["open"][0]["origin"] == "user"
    # 8. preview: the section as it will land, then Deliver
    out = walk.preview(WEEK_STEM)
    assert out["status"] == "ok" and out["problems"] == [] and out["notices"] == [], out
    assert out["mode"] == "insert" and out["target"] == WEEK_TARGET
    assert out["place"] == {"anchor": "In my own words", "placement": "before", "level": 2}
    section = out["section_md"]
    assert section.startswith("## Tomo Review\n%% tomo-review 2026-W13 %%\n### Done\n")
    assert "Sleep was short all week" in section and "A line of my own" in section
    assert "Taxes" not in section, "the unticked item is absent"
    assert "### Recurring themes" in section and "### Habits" in section
    assert "[[2026-03-23]]" in section, "a kept Tomo item keeps its source-day link (KPI Quality)"
    out = walk.deliver(WEEK_STEM)
    assert out["status"] == "delivered" and out["next"] == "hashi-or-by-hand", out
    assert out["paths"] == {"set_json": SET_JSON, "set_md": SET_MD} and out["place"]["anchor"] == "In my own words"
    assert walk.vault.recorded == [WEEK_DOC, SET_JSON, SET_MD, WEEK_DOC], "set, MD, then the mark"
    assert walk.doc(WEEK_DOC).split("---\n")[2].startswith("# 2026-W13 Review — delivered\n")
    assert frontmatter(walk.doc(WEEK_DOC))["tomo"]["state"] == "approved"
    assert walk.meta(WEEK_STEM)["steps_done"] == ["set_json", "set_md", "doc_mark"]
    assert walk.listing() == [(WEEK_STEM, "delivered")]
    assert walk.vault.outside_inbox() == outside_before, "nothing outside the inbox changed before Hashi"
    assert walk.deliver(WEEK_STEM)["problems"] == ["set-exists"], "no second set (F6-AC2)"
    # 10. Hashi applies; the next start reports applied, once
    assert walk.hashi_apply(WEEK_STEM) == ["applied"]
    target = walk.vault.text(WEEK_TARGET)
    assert tomo_sections(target) == 1 and target.index("## Tomo Review") < target.index("## In my own words")
    assert "Sleep was short all week" in target and "Taxes" not in target and "own words" in target
    assert walk.status(WEEK_STEM) == {"state": "applied", "stem": WEEK_STEM}
    assert walk.listing() == [(WEEK_STEM, "applied")]
    assert walk.meta(WEEK_STEM)["applied_reported"] is True
    assert walk.listing() == [], "reported once"
    assert walk.status(WEEK_STEM)["state"] == "applied"


# ── journey 1, the other answer: Abort at the setup question ─────────────────────────────


def test_setup_abort_saves_nothing_and_writes_nothing(walk: Walk):
    config_before = (walk.root / "config" / "vault-config.yaml").read_bytes()
    assert walk.start(WEEK_PERIOD)["setup"]["week"] == "missing"
    out = walk.match(WEEK)
    assert out["status"] == "ok" and out["proposal"]["folder"] == "Calendar/302 Weekly/", out
    # the user answers Abort: no confirmed file, no setup-input, no writer, no further script
    assert (walk.root / "config" / "vault-config.yaml").read_bytes() == config_before
    assert walk.vault.recorded == [] and walk.vault.writes == []
    assert not (walk.root / "tomo-tmp").exists() or list((walk.root / "tomo-tmp").rglob("*")) == []
    assert walk.start(WEEK_PERIOD)["setup"]["week"] == "missing"


# ── F6-AC3: a rerun replaces the section, also under a renamed heading ───────────────────


def _applied_week(walk: Walk) -> None:
    """Pass 1, approve, deliver, Hashi applies: the target holds Tomo's section."""
    assert walk.pass1(WEEK_PERIOD, WEEK)["status"] == "written"
    walk.approve(WEEK_DOC)
    assert walk.deliver(WEEK_STEM)["status"] == "delivered"
    assert walk.hashi_apply(WEEK_STEM) == ["applied"]
    assert walk.listing() == [(WEEK_STEM, "applied")]
    assert walk.vault.text(WEEK_TARGET).count("### Done") == 1


@pytest.mark.parametrize("renamed", [False, True], ids=["same-heading", "renamed-heading"])
def test_rerun_replaces_the_section_instead_of_adding_a_second(ready: Walk, renamed: bool):
    walk = ready
    _applied_week(walk)
    if renamed:
        walk.vault.files[WEEK_TARGET] = walk.vault.text(WEEK_TARGET).replace("## Tomo Review", "## Rückblick", 1)
    # the applied set waits in the inbox: a start-over Pass 1 is refused, replaced on confirmation
    out = walk.pass1(WEEK_PERIOD, WEEK)
    assert out["status"] == "refused" and out["problems"] == ["review-exists"] and out["doc_path"] == WEEK_DOC
    assert walk.replace(WEEK_STEM)["status"] == "needs-confirm"
    out = walk.replace(WEEK_STEM, "--confirm")
    assert out["status"] == "replaced" and walk.meta(WEEK_STEM)["steps_done"] == [], out
    assert "- [ ] Approved" in walk.doc(WEEK_DOC)
    assert walk.listing() == [(WEEK_STEM, "open")], "the rerun is open, not the first run's applied"
    walk.approve(WEEK_DOC)
    assert walk.listing() == [(WEEK_STEM, "open")]
    # the applied set of the first run still sits in the inbox: the rerun writes its set over it (owner decision)
    old_modified = walk.vault.modified[SET_JSON]
    out = walk.preview(WEEK_STEM)
    assert out["mode"] == "replace" and out["problems"] == [] and out["set_applied"] is True, out
    assert out["notices"] == (["heading-renamed"] if renamed else [])
    assert out["place"] == {"anchor": "Rückblick" if renamed else "Tomo Review", "placement": "replace", "level": 2}
    out = walk.deliver(WEEK_STEM)
    assert out["status"] == "delivered" and out["mode"] == "replace", out
    assert walk.vault.guards[-1] == (SET_JSON, old_modified), "the old set is replaced under its modified stamp"
    assert walk.set_json(WEEK_STEM)["actions"][0]["action"] == "replace_section"
    assert not walk.set_json(WEEK_STEM)["actions"][0].get("applied") and "### I01" in walk.vault.text(SET_MD)
    assert walk.listing() == [(WEEK_STEM, "delivered")]
    assert walk.hashi_apply(WEEK_STEM) == ["applied"]
    target = walk.vault.text(WEEK_TARGET)
    assert tomo_sections(target) == 1 and target.count("### Done") == 1, "one Tomo section (KPI Quality)"
    assert target.count("## Rückblick" if renamed else "## Tomo Review") == 1
    assert "## In my own words\nown words" in target, "the user's own section is untouched"
    assert walk.listing() == [(WEEK_STEM, "applied")]


# ── F6-AC4 and the edge cases: the target appears, the target moved ──────────────────────


def test_target_created_between_the_passes_turns_new_note_into_insert(ready: Walk):
    walk = ready
    walk.user_deletes(WEEK_TARGET)
    out = walk.pass1(WEEK_PERIOD, WEEK)
    assert out["status"] == "written" and out["target_exists"] is False and walk.meta(WEEK_STEM)["mode"] == "new-note"
    assert "(will be created)" in walk.doc(WEEK_DOC)
    walk.approve(WEEK_DOC)
    assert walk.preview(WEEK_STEM)["mode"] == "new-note"
    walk.vault.files[WEEK_TARGET] = WEEK_TARGET_TEXT                    # the user creates the weekly note
    out = walk.preview(WEEK_STEM)
    assert out["mode"] == "insert" and out["target_appeared"] is True and out["problems"] == [], out
    out = walk.deliver(WEEK_STEM)
    assert out["status"] == "delivered" and out["target_appeared"] is True and "note" not in out["paths"]
    assert walk.set_json(WEEK_STEM)["actions"][0]["action"] == "insert_under_marker"
    assert walk.hashi_apply(WEEK_STEM) == ["applied"]
    assert tomo_sections(walk.vault.text(WEEK_TARGET)) == 1 and "own words" in walk.vault.text(WEEK_TARGET)
    assert f"{INBOX}{WEEK_PERIOD}.md" not in walk.vault.files, "no new note was written"


def test_target_moved_to_another_folder_is_found_by_name_and_targeted_there(ready: Walk):
    walk = ready
    assert walk.pass1(WEEK_PERIOD, WEEK)["target"] == WEEK_TARGET
    walk.approve(WEEK_DOC)
    walk.vault.files[ARCHIVE_TARGET] = walk.vault.files.pop(WEEK_TARGET)   # the user moves the note
    out = walk.preview(WEEK_STEM)
    assert out["mode"] == "insert" and out["target"] == ARCHIVE_TARGET and out["target_moved"] is True, out
    assert out["problems"] == [] and "target_appeared" not in out
    out = walk.deliver(WEEK_STEM)
    assert out["status"] == "delivered" and out["target"] == ARCHIVE_TARGET
    assert walk.set_json(WEEK_STEM)["actions"][0]["target_path"] == ARCHIVE_TARGET
    assert walk.hashi_apply(WEEK_STEM) == ["applied"]
    assert tomo_sections(walk.vault.text(ARCHIVE_TARGET)) == 1 and WEEK_TARGET not in walk.vault.files
    assert walk.listing() == [(WEEK_STEM, "applied")]


# ── journey 7: Abort and discard, before and after Pass 2 ────────────────────────────────


def test_abort_before_pass_2_by_deleting_the_document_changes_nothing_outside_the_inbox(ready: Walk):
    walk = ready
    before = walk.vault.outside_inbox()
    assert walk.pass1(WEEK_PERIOD, WEEK)["status"] == "written"
    assert walk.listing() == [(WEEK_STEM, "open")]
    walk.user_deletes(WEEK_DOC)                                            # the user discards the review
    assert walk.listing() == [], "no document, nothing offered"
    out = walk.parse(WEEK_STEM)
    assert out == {"status": "not-found", "stem": WEEK_STEM, "doc_path": WEEK_DOC}
    assert walk.preview(WEEK_STEM)["status"] == "not-found"
    assert walk.drop(WEEK_STEM) == {"status": "dropped", "stem": WEEK_STEM, "removed": True}
    assert walk.vault.outside_inbox() == before and walk.vault.recorded == [WEEK_DOC]


def test_abort_after_pass_2_by_not_applying_changes_nothing_outside_the_inbox(ready: Walk):
    walk = ready
    before = walk.vault.outside_inbox()
    assert walk.pass1(WEEK_PERIOD, WEEK)["status"] == "written"
    walk.approve(WEEK_DOC)
    assert walk.preview(WEEK_STEM)["problems"] == []                      # the user answers Abort here first
    assert walk.vault.recorded == [WEEK_DOC] and walk.listing() == [(WEEK_STEM, "open")]
    assert walk.deliver(WEEK_STEM)["status"] == "delivered"                # then delivers, and never applies
    assert walk.listing() == [(WEEK_STEM, "delivered")]
    walk.user_deletes(SET_JSON, SET_MD)                                    # the set deleted by hand in Obsidian
    assert walk.vault.outside_inbox() == before
    assert walk.listing() == [(WEEK_STEM, "failed-delivery")], "an approved document whose set is gone"
    assert set(walk.vault.recorded) == {WEEK_DOC, SET_JSON, SET_MD}


# ── journey 6: a period with nothing to review ───────────────────────────────────────────


def test_empty_period_reports_and_writes_nothing(ready: Walk):
    walk = ready
    out = walk.start("2026-W15")
    assert out["request"]["period"] == "2026-W15" and out["open_reviews"] == []
    out = walk.read("2026-W15", WEEK)
    assert out["status"] == "ok" and out["nothing_to_review"] is True and "check-key-access" in out["report"]["advice"]
    assert out["read_path"] is None and not walk.stage("2026-W15_review").exists()
    assert walk.vault.recorded == []


# ── the month, briefly: journey 4 is walked in full in test_review_e2e_failures.py ────────


def test_month_setup_then_new_note_targets_the_monthly_folder(walk: Walk):
    assert walk.start("month")["setup"]["month"] == "missing"
    assert walk.setup(MONTH)["status"] == "written"
    assert walk.start("month")["request"]["period"] == "2026-10"
    out = walk.pass1(MONTH_PERIOD, MONTH)
    assert out["status"] == "written" and out["doc_path"] == MONTH_DOC and out["target"] == MONTH_TARGET
    assert out["target_exists"] is False and out["counts"]["weekly_only"] == 1
    walk.approve(MONTH_DOC)
    out = walk.preview(MONTH_STEM)
    assert out["mode"] == "new-note" and out["problems"] == [] and "templater_hint" in out["notices"], out


# ── the module's sweep: every write of every test above, under the inbox prefix ──────────


def test_every_write_attempted_so_far_was_under_the_inbox_prefix():
    """Order-independent: whatever tests ran before this one, in this module or a sibling, every write they
    attempted through the client (landed or refused) was under the inbox; nothing is assumed about how many."""
    assert [(t, p) for t, p in WRITES if not p.startswith(INBOX)] == []
    assert all(isinstance(t, str) and Path(t.split("::")[0]).name.startswith("test_review_e2e") for t, _ in WRITES)
