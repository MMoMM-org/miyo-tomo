#!/usr/bin/env python3
# version: 0.1.0
"""test_review_doc.py — lib/review_doc.py and review-doc.py write (spec 045 T3.6, PRD F4, F3-AC13).

On tests/review_fake_vault with synthetic read.json / proposals.json files:
- review-proposals.schema.json: a habits group, an unknown group (an own
  section), an item without sources or text are refused; a valid file passes
- an item without a source inside the period is rejected and listed with
  its group, index and reason; a theme naming fewer than two days is rejected
- habits come from the tracker values of read.json (T3.5), never from the
  proposals; an item with value None renders from its text
- groups in the SDD order; weekly_only / not_in_weekly only for a month with
  weekly notes; an empty group shows one "nothing found" bullet (growth with
  kado_none too, without an access hint); no habits → no habits heading
- every Tomo item ends its checkbox line with a unique %%t<n>%%; %% in the
  model's text cannot forge one; a second text line is a continuation line
- labels from the de/en table, English for any other language
- the info callout names the target, its existence (exists / will be
  created / found elsewhere), the place and the not-read parts
- Approved is unticked; the frontmatter is a schema-valid tomo: block plus
  the top-level review_* keys; the path comes from review_config.inbox_path
- an existing non-Tomo "<name> Review.md" gives doc-name-taken and nothing
  is written; Tomo's own review document is overwritten
- a failed Kado write gives status stopped, kado-write-failed, no doc_path,
  and keeps read.json and proposals.json; an invalid proposals file gives
  proposals-invalid and writes nothing
- Pass 1 counts go to meta.json; read.json and proposals.json are deleted
  after the write; a week write stays within five Kado calls
- exit 2 for a bad invocation, exit 1 with the class name only on an
  unexpected exception; stdout and stderr never carry proposal text

All data is synthetic.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "review-doc.py"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from review_fake_vault import ReviewFakeVault, split_frontmatter  # noqa: E402
from lib import review_doc as rd  # noqa: E402
from lib.kado_client import KadoToolError  # noqa: E402
from lib.period import ISO  # noqa: E402

INBOX = "100 Inbox/"
WEEKLY = "Calendar/302 Weekly/"
MONTHLY = "Calendar/303 Monthly/"
DAILY = "Calendar/301 Daily/"
MARKER = "MARKER-7f3a private proposal text"
WEEK_DAYS = [f"2026-03-{d}" for d in range(23, 30)]          # 2026-W13
DOC_SCHEMA = json.loads((SCRIPTS_DIR.parent / "schemas" / "doc-frontmatter.schema.json").read_text())


# ---------------------------------------------------------------- fixtures

def _daily(day: str) -> str:
    return f"{DAILY}{day}.md"


def _day(day: str, **fields) -> dict:
    return {"date": day, "dailies": [_daily(day)], "sections": {"Daily Log": "x"}, "fields": fields,
            "partly_read": False, "has_content": True, "links": [], "problems": [], "tasks": [], "linked": []}


def week_read(**overrides) -> dict:
    read = {
        "period": {"kind": "week", "name": "2026-W13", "start": "2026-03-23", "end": "2026-03-29"},
        "days": [_day(d, Sport="ja" if d != "2026-03-28" else "-") for d in WEEK_DAYS],
        "open_tasks": [], "growth": {"created": [], "mocs_changed": [], "mocs_linked_by_new": []},
        "not_read": [],
        "report": {"days": [], "growth": {"created": 0, "mocs_changed": 0, "mocs_linked_by_new": 0,
                                          "moc_folders": 1, "kado_none": []},
                   "kado_empty": [], "not_read": [], "advice": []},
    }
    read.update(overrides)
    return read


def month_read(weekly=True, **overrides) -> dict:
    days = [f"2026-03-{d:02d}" for d in range(1, 32)]
    read = week_read(period={"kind": "month", "name": "2026-03", "start": "2026-03-01", "end": "2026-03-31"},
                     days=[_day(d) for d in days], **overrides)
    read["weekly"] = [{"path": f"{WEEKLY}2026-W13.md", "week": "2026-W13", "overlap_days": 7}] if weekly else []
    return read


def item(text: str, *sources: str) -> dict:
    return {"text": text, "sources": list(sources)}


def proposals(language="de", **groups) -> dict:
    return {"language": language, "groups": groups}


def _config(instance: Path, *, language="de", trackers=True, inbox=INBOX) -> None:
    cfg: dict = {
        "concepts": {"inbox": inbox, "calendar": {"granularities": {
            "daily": {"enabled": True, "path": DAILY},
            "weekly": {"enabled": True, "path": WEEKLY},
            "monthly": {"enabled": True, "path": MONTHLY}}}},
        "naming": {"calendar_patterns": {"weekly": "GGGG-[W]WW", "monthly": "YYYY-MM"}},
        "review": {
            "language": language,
            "week": {"first_day": "monday", "min_days_in_first_week": 4},
            "weekly": {"heading": "Tomo Review", "place": {"anchor": "In my own words", "placement": "before"},
                       "own_sections": ["In my own words"]},
            "monthly": {"heading": "Tomo Review", "place": {"anchor": "Reflections", "placement": "inside"},
                        "own_sections": ["Reflections"]},
        },
    }
    if trackers:
        cfg["trackers"] = {"daily_note_trackers": {"today_fields": [{"name": "Sport", "type": "boolean"}]}}
    (instance / "config" / "vault-config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("review_doc_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "profiles").mkdir()
    (tmp_path / "profiles" / "miyo.yaml").write_text(yaml.safe_dump({"concept_defaults": {}}), encoding="utf-8")
    _config(tmp_path)
    return tmp_path


def stage(instance: Path, read: dict, props, stem: str | None = None) -> tuple[str, Path]:
    stem = stem or f"{read['period']['name']}_review"
    folder = instance / "tomo-tmp" / "review" / stem
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "read.json").write_text(json.dumps(read), encoding="utf-8")
    path = folder / "proposals.json"
    path.write_text(props if isinstance(props, str) else json.dumps(props), encoding="utf-8")
    return stem, path


def _run(mod, monkeypatch, capsys, argv, fake):
    monkeypatch.setattr(mod, "KadoClient", fake)
    code = mod.main(["--profiles-dir", "profiles"] + argv)
    out, err = capsys.readouterr()
    assert MARKER not in out and MARKER not in err, "proposal text leaked to stdout/stderr"
    return code, (json.loads(out) if out else None), err


def write(mod, monkeypatch, capsys, instance, read, props, fake=None, *extra, stem=None):
    stem, path = stage(instance, read, props, stem)
    fake = fake or ReviewFakeVault({f"{WEEKLY}2026-W13.md": "# W13\n\n## In my own words\n"})
    code, out, err = _run(mod, monkeypatch, capsys,
                          ["write", "--stem", stem, "--proposals", str(path), "--run-id", "r-test", *extra], fake)
    return code, out, fake


def doc_of(fake: ReviewFakeVault) -> tuple[dict, str]:
    [path] = [p for p in fake.writes if p.endswith(" Review.md")]
    return split_frontmatter(fake.text(path))


def lines_of(fake: ReviewFakeVault) -> list[str]:
    return doc_of(fake)[1].splitlines()


def items_under(lines: list[str], heading: str) -> list[str]:
    start = lines.index(f"## {heading}") + 1
    out = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip():
            out.append(line)
    return out


GOOD = proposals(
    done=[item("Woche aufgeräumt", _daily("2026-03-24"), "2026-03-26")],
    open=[item("Steuer offen", "2026-03-27")],
    themes=[item("Schlaf", "2026-03-23", "2026-03-25")],
    growth=[item("Neue Notiz zu X", "2026-03-24", "Efforts/X.md")],
)


# ---------------------------------------------------------------- the schema

def test_schema_refuses_habits_own_sections_and_items_without_sources():
    assert rd.proposal_problems(GOOD) == []
    # an unknown group key is reported on the closed object (jsonschema's additionalProperties pointer)
    assert rd.proposal_problems(proposals(habits=[item("Sport: 5 von 7", "2026-03-24")])) == ["/groups"]
    assert rd.proposal_problems(proposals(**{"In my own words": [item("x", "2026-03-24")]})) == ["/groups"]
    assert rd.proposal_problems(proposals(done=[{"text": "x", "sources": []}])) == ["/groups/done/0/sources"]
    assert rd.proposal_problems(proposals(done=[{"text": "", "sources": ["2026-03-24"]}])) == ["/groups/done/0/text"]
    assert rd.proposal_problems({"groups": {}}) == ["/"]            # a missing required key, on the object
    assert rd.proposal_problems([]) == ["/"]


# ---------------------------------------------------------------- the source rule

def test_item_without_a_source_inside_the_period_is_rejected_and_listed():
    props = proposals(done=[item("ok", "2026-03-24"), item("outside", "2026-03-22", "Efforts/X.md"),
                            item("other year", f"{DAILY}2025-03-24.md")],
                      open=[item("linked note only", "DP-2026-03-24")])
    accepted, rejected = rd.check_items(props, week_read())
    assert [i["text"] for i in accepted["done"]] == ["ok"]
    assert accepted["open"] == []
    assert rejected == [
        {"group": "done", "index": 1, "reason": "no-source-in-period"},
        {"group": "done", "index": 2, "reason": "no-source-in-period"},
        {"group": "open", "index": 0, "reason": "no-source-in-period"},
    ]


def test_a_theme_naming_fewer_than_two_days_is_rejected():
    props = proposals(themes=[item("one day twice", "2026-03-24", _daily("2026-03-24")),
                              item("two days", "2026-03-24", "2026-03-25")])
    accepted, rejected = rd.check_items(props, week_read())
    assert [i["text"] for i in accepted["themes"]] == ["two days"]
    assert rejected == [{"group": "themes", "index": 0, "reason": "theme-needs-two-days"}]


def test_sources_render_as_links_of_the_note_stem():
    accepted, _ = rd.check_items(GOOD, week_read())
    assert accepted["done"][0]["links"] == ["2026-03-24", "2026-03-26"]
    assert accepted["growth"][0]["links"] == ["2026-03-24", "X"]


def test_weekly_only_needs_a_weekly_note_and_month_groups_need_a_month_with_weeklies():
    props = proposals(weekly_only=[item("only there", f"{WEEKLY}2026-W13.md"), item("daily", "2026-03-24")],
                      not_in_weekly=[item("left out", "2026-03-24")])
    accepted, rejected = rd.check_items(props, month_read())
    assert [i["text"] for i in accepted["weekly_only"]] == ["only there"]
    assert [i["text"] for i in accepted["not_in_weekly"]] == ["left out"]
    assert rejected == [{"group": "weekly_only", "index": 1, "reason": "no-source-in-period"}]
    _, rejected = rd.check_items(props, month_read(weekly=False))
    assert {r["reason"] for r in rejected} == {"no-weekly-notes"}
    _, rejected = rd.check_items(props, week_read())
    assert {r["reason"] for r in rejected} == {"month-only-group"}


# ---------------------------------------------------------------- the document

def test_groups_in_order_with_nothing_found_lines_and_ids(mod, instance, monkeypatch, capsys):
    code, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), GOOD)
    assert code == 0 and out["status"] == "written"
    lines = lines_of(fake)
    assert [ln for ln in lines if ln.startswith("## ")] == [
        "## Erledigt", "## Offen", "## Wiederkehrende Themen", "## Vault-Wachstum", "## Gewohnheiten"]
    assert items_under(lines, "Erledigt") == ["- [x] Woche aufgeräumt ([[2026-03-24]], [[2026-03-26]]) %%t1%%"]
    assert items_under(lines, "Offen") == ["- [x] Steuer offen ([[2026-03-27]]) %%t2%%"]
    assert items_under(lines, "Gewohnheiten") == ["- [x] Sport: 6 von 6 Tagen (7 Tage im Zeitraum; fehlt: 2026-03-28) %%t5%%"]
    assert out["counts"] == {"done": 1, "open": 1, "themes": 1, "growth": 1, "habits": 1}
    assert out["rejected"] == []


def test_every_tomo_item_ends_with_a_unique_id_and_text_cannot_forge_one(mod, instance, monkeypatch, capsys):
    props = proposals(done=[item("a %%t9%% b", "2026-03-24"), item("c\nsecond line", "2026-03-25")],
                      open=[item("d", "2026-03-26")])
    _, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), props)
    lines = lines_of(fake)
    ids = [ln.rsplit(" ", 1)[1] for ln in lines if ln.startswith("- [x]")]
    assert ids == ["%%t1%%", "%%t2%%", "%%t3%%", "%%t4%%"] and len(set(ids)) == 4
    assert items_under(lines, "Erledigt") == ["- [x] a t9 b ([[2026-03-24]]) %%t1%%",
                                              "- [x] c ([[2026-03-25]]) %%t2%%", "  second line"]


def test_empty_groups_show_one_nothing_found_line_also_growth_with_kado_none(mod, instance, monkeypatch, capsys):
    read = week_read()
    read["report"]["growth"]["kado_none"] = ["created"]
    _, out, fake = write(mod, monkeypatch, capsys, instance, read, proposals(done=[item("x", "2026-03-24")]))
    lines = lines_of(fake)
    for heading in ("Offen", "Wiederkehrende Themen", "Vault-Wachstum"):
        assert items_under(lines, heading) == ["- nichts gefunden"], heading
    assert "Kado" not in "\n".join(lines)
    assert out["counts"] == {"done": 1, "open": 0, "themes": 0, "growth": 0, "habits": 1}


def test_month_only_groups_only_for_a_month_with_weekly_notes(mod, instance, monkeypatch, capsys):
    props = proposals(done=[item("x", "2026-03-04")], weekly_only=[item("w", f"{WEEKLY}2026-W13.md")])
    _, out, fake = write(mod, monkeypatch, capsys, instance, month_read(), props,
                         ReviewFakeVault({f"{WEEKLY}2026-W13.md": "# W13\n"}))
    lines = lines_of(fake)
    assert [ln for ln in lines if ln.startswith("## ")][-2:] == ["## Nur in den Wochenreviews", "## Nicht in den Wochenreviews"]
    assert items_under(lines, "Nur in den Wochenreviews") == ["- [x] w ([[2026-W13]]) %%t2%%"]
    assert items_under(lines, "Nicht in den Wochenreviews") == ["- nichts gefunden"]
    assert out["counts"]["weekly_only"] == 1 and out["counts"]["not_in_weekly"] == 0
    assert out["target"] == f"{MONTHLY}2026-03.md" and out["target_exists"] is False

    _, out, fake = write(mod, monkeypatch, capsys, instance, month_read(weekly=False), props,
                         ReviewFakeVault({}))
    headings = [ln for ln in lines_of(fake) if ln.startswith("## ")]
    assert "## Nur in den Wochenreviews" not in headings and "## Nicht in den Wochenreviews" not in headings
    assert "weekly_only" not in out["counts"] and out["rejected"] == [
        {"group": "weekly_only", "index": 0, "reason": "no-weekly-notes"}]

    _, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), props)
    assert "## Nur in den Wochenreviews" not in lines_of(fake)
    assert {"group": "weekly_only", "index": 0, "reason": "month-only-group"} in out["rejected"]


def test_habits_come_from_the_tracker_values_and_are_absent_without_them(mod, instance, monkeypatch, capsys):
    _config(instance, trackers=False)
    _, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), GOOD)
    assert "## Gewohnheiten" not in lines_of(fake) and "habits" not in out["counts"]
    _config(instance)
    code, out, fake = write(mod, monkeypatch, capsys, instance, week_read(),
                            proposals(habits=[item("Sport: 7 von 7 Tagen", "2026-03-24")]))
    assert code == 0 and out["status"] == "refused" and out["problems"] == ["proposals-invalid"]
    assert out["errors"] == ["/groups"] and fake.writes == [] and fake.call_count == 0


def test_a_habit_without_a_clear_average_renders_from_its_text():
    habit = {"tracker": "Bett", "kind": "average", "value": None, "rendered": "kein klarer Durchschnitt",
             "text": "Bett: kein klarer Durchschnitt über 2 Tage (7 Tage im Zeitraum)", "missing": [], "unreadable": []}
    text, counts = rd.render_document(_doc_input(groups={"habits": [{"text": habit["text"], "links": []}]}))
    assert "- [x] Bett: kein klarer Durchschnitt über 2 Tage (7 Tage im Zeitraum) %%t1%%" in text
    assert counts == {"done": 0, "open": 0, "themes": 0, "growth": 0, "habits": 1}


def _doc_input(**overrides) -> rd.DocInput:
    fields = dict(period_name="2026-W13", kind="week", language="de", stem="2026-W13_review", run_id="r-test",
                  target=f"{WEEKLY}2026-W13.md", target_exists=True, target_found_elsewhere=None,
                  anchor="In my own words", placement="before", not_read=[], partly_read=[],
                  month_groups=False, groups={})
    fields.update(overrides)
    return rd.DocInput(**fields)


def test_labels_de_en_with_en_fallback(mod, instance, monkeypatch, capsys):
    _config(instance, language="en")
    _, _, fake = write(mod, monkeypatch, capsys, instance, week_read(), proposals(language="en"))
    lines = lines_of(fake)
    assert [ln for ln in lines if ln.startswith("## ")] == ["## Done", "## Open", "## Recurring themes",
                                                            "## Vault growth", "## Habits"]
    assert items_under(lines, "Open") == ["- nothing found"]
    assert lines[1].startswith("> [!info] Target: [[2026-W13]] (exists) · before \"In my own words\"")
    text, _ = rd.render_document(_doc_input(language="fr"))
    assert "## Done" in text and "- nothing found" in text and "Target:" in text


def test_info_callout_names_target_existence_place_and_not_read(mod, instance, monkeypatch, capsys):
    read = week_read(not_read=[f"{DAILY}DP-2026-03-28.md", "Efforts/Next Todos.md"])
    read["days"][1]["partly_read"] = True
    _, out, fake = write(mod, monkeypatch, capsys, instance, read, GOOD)
    lines = lines_of(fake)
    assert lines[0] == "# 2026-W13 Review"
    assert lines[1] == ("> [!info] Ziel: [[2026-W13]] (vorhanden) · vor \"In my own words\" · "
                        "nicht gelesen: DP-2026-03-28, Next Todos · teilweise gelesen: 2026-03-24")
    assert out["target"] == f"{WEEKLY}2026-W13.md" and out["target_exists"] is True
    assert "target_found_elsewhere" not in out

    _, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), GOOD, ReviewFakeVault({}))
    assert lines_of(fake)[1] == "> [!info] Ziel: [[2026-W13]] (wird angelegt) · vor \"In my own words\""
    assert out["target"] == f"{WEEKLY}2026-W13.md" and out["target_exists"] is False

    moved = ReviewFakeVault({f"{WEEKLY}2025/2026-W13.md": "# moved\n", "Archive/2026-W13.md": "# moved\n",
                             "Archive/2026-W130.md": "# not it\n"})
    _, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), GOOD, moved)
    assert out["target"] == "Archive/2026-W13.md" and out["target_exists"] is True
    assert out["target_found_elsewhere"] == "Archive/2026-W13.md"
    assert lines_of(fake)[1] == ("> [!info] Ziel: [[2026-W13]] (gefunden unter Archive/2026-W13.md) · "
                                 "vor \"In my own words\"")


def test_year_subfolder_target_counts_as_existing(mod, instance, monkeypatch, capsys):
    fake = ReviewFakeVault({f"{WEEKLY}2026/2026-W13.md": "# W13\n"})
    _, out, _ = write(mod, monkeypatch, capsys, instance, week_read(), GOOD, fake)
    assert out["target"] == f"{WEEKLY}2026/2026-W13.md" and out["target_exists"] is True
    assert "target_found_elsewhere" not in out
    assert not any(m == "search_by_name" for m, _ in fake.events)


def test_approved_unticked_and_frontmatter_schema_valid(mod, instance, monkeypatch, capsys):
    _, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), GOOD)
    front, body = doc_of(fake)
    assert body.splitlines()[2] == "- [ ] Approved"
    jsonschema.validate(front, DOC_SCHEMA)
    assert front["tomo"]["doc_type"] == "review" and front["tomo"]["state"] == "pending-approval"
    assert front["tomo"]["run_id"] == "r-test" and front["tomo"]["updated_at"]
    assert {k: v for k, v in front.items() if k != "tomo"} == {
        "review_period": "2026-W13", "review_kind": "week", "review_target": f"{WEEKLY}2026-W13.md",
        "review_target_exists": True, "review_language": "de", "review_stem": "2026-W13_review"}
    assert out["doc_path"] == f"{INBOX}2026-W13 Review.md" and fake.writes == [out["doc_path"]]


def test_doc_path_comes_from_inbox_path(mod, instance, monkeypatch, capsys):
    _config(instance, inbox="Inbox/../Outside/")
    code, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), GOOD)
    assert code == 0 and out["status"] == "refused" and out["problems"] == ["inbox-not-configured"]
    assert fake.writes == []


def test_existing_non_tomo_document_is_doc_name_taken(mod, instance, monkeypatch, capsys):
    taken = ReviewFakeVault({f"{INBOX}2026-W13 Review.md": "---\ntitle: mine\n---\n# My own review\n",
                             f"{WEEKLY}2026-W13.md": "# W13\n"})
    code, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), GOOD, taken)
    assert code == 0 and out == {"status": "refused", "stem": "2026-W13_review", "doc_path": f"{INBOX}2026-W13 Review.md",
                                 "target": f"{WEEKLY}2026-W13.md", "target_exists": True,
                                 "problems": ["doc-name-taken"]}
    assert fake.writes == [] and fake.text(f"{INBOX}2026-W13 Review.md").endswith("# My own review\n")
    stage_dir = instance / "tomo-tmp" / "review" / "2026-W13_review"
    assert (stage_dir / "read.json").exists() and (stage_dir / "proposals.json").exists()

    own = ReviewFakeVault({f"{INBOX}2026-W13 Review.md": "---\ntomo:\n  doc_type: review\n  state: pending-approval\n"
                                                         "  run_id: old\n  updated_at: x\n---\n# old\n"})
    _, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), GOOD, own)
    assert out["status"] == "written" and fake.writes == [f"{INBOX}2026-W13 Review.md"]


def test_failed_kado_write_is_stopped_and_keeps_the_content_files(mod, instance, monkeypatch, capsys):
    fake = ReviewFakeVault({})
    fake.fail[("write_note", f"{INBOX}2026-W13 Review.md")] = KadoToolError("kado-write returned an error: denied")
    code, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), GOOD, fake)
    assert code == 0 and out["status"] == "stopped" and out["problems"] == ["kado-write-failed"]
    assert "doc_path" not in out and fake.writes == []
    stage_dir = instance / "tomo-tmp" / "review" / "2026-W13_review"
    assert (stage_dir / "read.json").exists() and (stage_dir / "proposals.json").exists()
    assert not (stage_dir / "meta.json").exists()


def test_invalid_proposals_file_is_refused_before_any_kado_call(mod, instance, monkeypatch, capsys):
    for bad in ("{not json", json.dumps({"language": "de"}), json.dumps(proposals(done=[{"text": "x"}]))):
        code, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), bad)
        assert code == 0 and out["status"] == "refused" and out["problems"] == ["proposals-invalid"]
        assert out["errors"] and fake.call_count == 0


def test_pass1_counts_in_meta_and_content_files_deleted(mod, instance, monkeypatch, capsys):
    _, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), GOOD)
    stage_dir = instance / "tomo-tmp" / "review" / "2026-W13_review"
    meta = json.loads((stage_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["pass1_counts"] == {"done": 1, "open": 1, "themes": 1, "growth": 1, "habits": 1}
    assert meta["stem"] == "2026-W13_review" and meta["period"] == "2026-W13" and meta["kind"] == "week"
    assert meta["doc_path"] == out["doc_path"] and meta["target"] == out["target"] and meta["mode"] == "insert"
    assert meta["run_id"] == "r-test" and meta["generated"] and meta["steps_done"] == [] and not meta["failed_step"]
    assert not (stage_dir / "read.json").exists() and not (stage_dir / "proposals.json").exists()
    assert MARKER not in (stage_dir / "meta.json").read_text(encoding="utf-8")


def test_a_week_write_costs_at_most_five_kado_calls(mod, instance, monkeypatch, capsys):
    _, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), GOOD, ReviewFakeVault({}))
    assert fake.call_count <= 5 and out["calls"] == fake.call_count
    assert [m for m, _ in fake.events][-1] == "write_note"


def test_proposal_text_never_reaches_stdout_or_stderr(mod, instance, monkeypatch, capsys):
    props = proposals(done=[item(MARKER, "2026-03-24"), item(MARKER + " no source", "2025-01-01")])
    code, out, fake = write(mod, monkeypatch, capsys, instance, week_read(), props)
    assert code == 0 and out["rejected"] == [{"group": "done", "index": 1, "reason": "no-source-in-period"}]
    assert MARKER in fake.text(out["doc_path"])


# ---------------------------------------------------------------- the period and the invocation

def test_period_of_follows_the_configured_rule_and_refuses_a_mismatch():
    period = rd.period_of(week_read(), ISO)
    assert period.name == "2026-W13" and len(period.days()) == 7
    with pytest.raises(rd.ReadInvalid):
        rd.period_of(week_read(period={"kind": "week", "name": "x", "start": "2026-03-23", "end": "2026-03-30"}), ISO)
    with pytest.raises(rd.ReadInvalid):
        rd.period_of({"days": []}, ISO)


def test_missing_read_or_setup_is_refused(mod, instance, monkeypatch, capsys):
    path = instance / "p.json"
    path.write_text(json.dumps(GOOD), encoding="utf-8")
    code, out, _ = _run(mod, monkeypatch, capsys, ["write", "--stem", "2026-W13_review", "--proposals", str(path)],
                        ReviewFakeVault({}))
    assert code == 0 and out["status"] == "refused" and out["problems"] == ["read-missing"]
    (instance / "config" / "vault-config.yaml").write_text("concepts:\n  inbox: 100 Inbox/\n", encoding="utf-8")
    code, out, _ = write(mod, monkeypatch, capsys, instance, week_read(), GOOD, ReviewFakeVault({}))
    assert code == 0 and out["status"] == "refused" and out["problems"] == ["setup-missing"]


def test_exit_codes(mod, instance, monkeypatch, capsys):
    with pytest.raises(SystemExit) as stop:
        mod.main(["write", "--stem", "../x", "--proposals", "p.json"])
    assert stop.value.code == 2
    with pytest.raises(SystemExit) as stop:
        mod.main(["parse", "--stem", "x"])
    assert stop.value.code == 2
    capsys.readouterr()
    stem, path = stage(instance, week_read(), GOOD)

    def boom(*_a, **_k):
        raise RuntimeError(MARKER)

    monkeypatch.setattr(mod, "write_document", boom)
    code = mod.main(["write", "--stem", stem, "--proposals", str(path)])
    out, err = capsys.readouterr()
    assert code == 1 and out == "" and err == "RuntimeError\n"
