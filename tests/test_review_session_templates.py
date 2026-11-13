#!/usr/bin/env python3
# version: 0.2.2
"""test_review_session_templates.py — the template choice and the anchor question of `review-session.py match`
(spec 045 Phase 6, live-walk defect: a proposal with `template: null` and `anchor: null` that `setup-input` refused).

On tests/review_fake_vault, with a templates folder like the owner's (`t_week*.md`, `t_month*.md` next to
other templates) and no `templates.mapping.<weekly|monthly>` entry:
- match lists `template_candidates`: the notes of `templates.base_path` whose file name holds `week`/`woche`
  (month: `month`/`monat`), case-insensitive, one listing call, sorted; no template is resolved; a mapping
  entry means no candidates and no listing (as before); no base_path or a `kado-none` listing means `[]`.
- `--template <name>` (with or without `.md`) is the chosen template: its kind and the anchor come from its
  headings; the flag wins over a mapping entry; an unsafe name is a usage error.
- when no anchor can be proposed the proposal carries `needs_anchor: true` and `anchor_candidates` — the
  headings of the two most recent periodic notes of the kind (two `read_note` calls at most) — and
  `setup-input` refuses that proposal unchanged (`/place/anchor`) and accepts it with a candidate put in.
- `setup-input` + `vault-config-writer.py review` save the chosen template to `templates.mapping.weekly`
  and leave `base_path` and the other mapping entries alone; `0 none` (template null) touches no mapping key.
- the two answers survive a rerun (fix round 1 of the live-walk fix): `--template none` is the `0 none` answer
  — no listing, no `template_candidates`, the plain note, and it wins over a mapping entry like any flag;
  `--anchor <heading>` is the typed or picked anchor — trimmed into `place.anchor`, no `needs_anchor`, no
  periodic-note read, winning over the template's proposal and the configured anchor; a blank or multi-line
  anchor is a usage error; a rerun with both keeps both. SKILL.md step 2 carries `--template <template>` on
  every `match` call after the first and `--anchor "<anchor>"` once the anchor is given (pinned structurally
  here; the verbatim lines are in tests/test_review_skill.py).
- code review round 1 of that fix: the candidate filter reads the file name only (a `weekly/` folder lists
  nothing for its name) and matches a substring of it (`t_weekend` is listed); `--template " none "` is the
  `none` answer (trimmed), so `none.md` is chosen with its extension only; `..` is refused as a path segment,
  not as a substring, and a line break is refused; the skill says what a typed template name means.
- the template's frontmatter block (live-walk fix 2026-11-13: the month template's opening `---` came only from a
  Templater include, Pass 2 found no block at line 1 and prepended its own, and the rendered note carried two):
  the proposal says `template_frontmatter` true when the template's first line is `---` and a later line closes
  it, false otherwise (Templater code first, a lone unclosed `---`, an empty template), null without a template (none, the candidate
  list, missing, unreadable); a false value marks the output `needs_template_ok` so the skill asks, and the answer
  `1` is carried back as `--template-frontmatter-ok <name>`, honoured only for the template it was given for, so
  a Correct to another template without a block asks again. The field is dropped from the writer input like
  `template_kind`. No template text reaches stdout (the `BODY` marker sits in the Templater template's body).
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
SKILL = TESTS_DIR.parent / "tomo" / "dot_claude" / "skills" / "periodic-review" / "SKILL.md"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(TESTS_DIR))

from review_fake_vault import ReviewFakeVault  # noqa: E402

TODAY = "2026-11-11"
WEEKLY = "Calendar/302 Weekly/"
MONTHLY = "Calendar/303 Monthly/"
TEMPLATES = "X/900 Support/930 Templater/"
BODY = "BODY-MARKER-4d2c private line"

T_WEEK = "---\ntags: weekly\n---\n# <% tp.file.title %>\n\n## Woche\n\n## In my own words\n"
T_WEEK_PRIVAT = "# Weekly\n\n## Theme\n\n## Reflections\n"
T_WEEK_WORK = "# Work week\n\nno headings below the title\n"
T_MONTH = "# <% tp.file.title %>\n\n## Monat\n\n## Reflections\n"
# the live-walk shape: Templater code at line 1, the opening fence only inside an include, the closing one literal
T_MONTH_INCLUDE = ("<%*\nconst title = tp.file.title;\n-%>\n"
                   "<% await tp.file.include(\"[[x_frontmatter]]\") -%>\ntags: monthly\n---\n"
                   f"# <% title %>\n\n{BODY}\n\n## Monat\n\n## Reflections\n")
T_WEEK_UNCLOSED = "---\ntags: weekly\n# Weekly\n\n## Reflections\n"


def _templates() -> dict:
    return {
        TEMPLATES + "t_week.md": T_WEEK,
        TEMPLATES + "t_week_privat.md": T_WEEK_PRIVAT,
        TEMPLATES + "t_week_work.md": T_WEEK_WORK,
        TEMPLATES + "t_month.md": T_MONTH,
        TEMPLATES + "t_month_privat.md": "# M\n\n## Theme of the month\n",
        TEMPLATES + "Monatsübersicht.md": "# Monat\n",
        TEMPLATES + "archive/Wochenplan alt.md": "# alt\n",
        TEMPLATES + "t_day.md": "## Daily Log\n",
        TEMPLATES + "t_note.md": "# note\n",
    }


def _weekly(name: str, start: str, *headings: str) -> str:
    body = "\n".join(f"## {h}\n{BODY}\n" for h in headings)
    return f"---\njournal-start-date: {start}\n---\n# {name}\n\n{BODY}\n\n{body}"


def _weeklies() -> dict:
    return {
        WEEKLY + "2026-W13.md": _weekly("2026-W13", "2026-03-23", "Review of the Week", "Notes", "In my own words"),
        WEEKLY + "2026-W12.md": _weekly("2026-W12", "2026-03-16", "Review of the Week", "Reflections"),
        WEEKLY + "2026-W11.md": _weekly("2026-W11", "2026-03-09", "Older heading"),
        WEEKLY + "Weekly Index.md": "# Index\n\n## Index heading\n",
    }


def _monthlies() -> dict:
    return {
        MONTHLY + "2026-03.md": f"# March\n\n{BODY}\n\n## Month review\n\n## Reflections\n",
        MONTHLY + "2026-02.md": "# Feb\n\n## Looking back\n",
        MONTHLY + "2026-01.md": "# Jan\n\n## Dropped heading\n",
    }


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("review_session_templates", SCRIPTS_DIR / "review-session.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def instance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "profiles").mkdir()
    profile = {"concept_defaults": {
        "inbox": "100 Inbox/",
        "calendar": {"granularities": {
            "weekly": {"enabled": True, "path": WEEKLY},
            "monthly": {"enabled": True, "path": MONTHLY},
        }},
    }}
    (tmp_path / "profiles" / "miyo.yaml").write_text(yaml.safe_dump(profile), encoding="utf-8")
    return tmp_path


def _config(instance: Path, *, templates=None, review=None) -> Path:
    cfg: dict = {"concepts": {"inbox": "100 Inbox/"}}
    if templates is not None:
        cfg["templates"] = templates
    if review is not None:
        cfg["review"] = review
    path = instance / "config" / "vault-config.yaml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return path


def _no_mapping(**mapping) -> dict:
    return {"base_path": TEMPLATES, "mapping": {"daily": "t_day.md", **mapping}}


def _run(mod, monkeypatch, capsys, argv, fake):
    monkeypatch.setattr(mod, "KadoClient", fake)
    code = mod.main(["--profiles-dir", "profiles", *argv])
    out, err = capsys.readouterr()
    assert BODY not in out and BODY not in err, "note text reached stdout or stderr"
    return code, (json.loads(out) if out else None), err


def _match(mod, monkeypatch, capsys, fake, *extra, kind="week"):
    code, out, err = _run(mod, monkeypatch, capsys, ["match", "--kind", kind, "--today", TODAY, *extra], fake)
    assert code == 0 and out["status"] == "ok", (code, out, err)
    return out


def _vault(**extra) -> ReviewFakeVault:
    return ReviewFakeVault({**_templates(), **_weeklies(), **_monthlies(), **extra},
                           folders=[WEEKLY, MONTHLY, TEMPLATES])


def _listings(fake, folder: str) -> list:
    return [e for e in fake.events if e[0] == "list_dir" and e[1] == folder]


def _note_reads(fake, prefix: str) -> list:
    return [e[1] for e in fake.events if e[0] == "read_note" and e[1].startswith(prefix)]


# ---------------------------------------------------------------- (a) the candidates

def test_no_mapping_entry_lists_the_templates_whose_name_fits_the_kind(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_no_mapping())
    fake = _vault()
    out = _match(mod, monkeypatch, capsys, fake)
    assert out["template_candidates"] == ["archive/Wochenplan alt", "t_week", "t_week_privat", "t_week_work"]
    assert out["proposal"]["template"] is None and out["proposal"]["template_kind"] == "missing"
    assert _listings(fake, TEMPLATES) == [("list_dir", TEMPLATES)], "one listing of the templates folder"
    assert _note_reads(fake, TEMPLATES) == [TEMPLATES + "t_day.md"], \
        "no candidate is read before one is chosen (the daily template read is the daily-sections proposal, as before)"

    fake = _vault()
    out = _match(mod, monkeypatch, capsys, fake, kind="month")
    assert out["template_candidates"] == ["Monatsübersicht", "t_month", "t_month_privat"]
    assert out["proposal"]["template"] is None


def test_a_mapping_entry_means_no_candidates_and_no_listing_as_before(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_no_mapping(weekly="t_week_privat.md"))
    fake = _vault()
    out = _match(mod, monkeypatch, capsys, fake)
    assert "template_candidates" not in out
    assert out["proposal"]["template"] == "t_week_privat.md" and out["proposal"]["template_kind"] == "plain"
    assert out["proposal"]["place"] == {"anchor": "Reflections", "placement": "before"}
    assert _listings(fake, TEMPLATES) == []


def test_without_a_base_path_or_with_a_kado_none_listing_the_candidates_are_empty(mod, instance, monkeypatch, capsys):
    _config(instance)
    fake = _vault()
    out = _match(mod, monkeypatch, capsys, fake)
    assert out["template_candidates"] == [] and _listings(fake, TEMPLATES) == []

    _config(instance, templates=_no_mapping())
    fake = ReviewFakeVault(_weeklies(), folders=[WEEKLY])          # the templates folder answers Path not found
    out = _match(mod, monkeypatch, capsys, fake)
    assert out["template_candidates"] == []
    assert _listings(fake, TEMPLATES) == [("list_dir", TEMPLATES)]
    assert any(TEMPLATES in h and "may not reach" in h for h in out["hints"]), out["hints"]


def test_the_filter_reads_the_file_name_only_and_matches_a_substring_of_it(mod, instance, monkeypatch, capsys):
    """The kind words are looked for in the file name alone — a note in a folder called `weekly/` or `Monatlich/`
    is not listed for the folder's name (mutation: matching the whole relative stem lists them) — and anywhere in
    it: `t_weekend` and `Monatsabschluss` are listed, the user drops them from the numbered list with `0 none`."""
    _config(instance, templates=_no_mapping())
    extra = {
        TEMPLATES + "weekly/t_notes.md": "# in a week folder\n",
        TEMPLATES + "Monatlich/t_x.md": "# in a month folder\n",
        TEMPLATES + "t_weekend.md": "# weekend\n",
        TEMPLATES + "Monatsabschluss.md": "# end of month\n",
    }
    out = _match(mod, monkeypatch, capsys, _vault(**extra))
    assert out["template_candidates"] == ["archive/Wochenplan alt", "t_week", "t_week_privat", "t_week_work",
                                          "t_weekend"]
    out = _match(mod, monkeypatch, capsys, _vault(**extra), kind="month")
    assert out["template_candidates"] == ["Monatsabschluss", "Monatsübersicht", "t_month", "t_month_privat"]


# ---------------------------------------------------------------- (b) the chosen template

def test_the_chosen_template_gives_its_kind_and_the_anchor_from_its_headings(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_no_mapping())
    fake = _vault()
    out = _match(mod, monkeypatch, capsys, fake, "--template", "t_week_privat")
    p = out["proposal"]
    assert p["template"] == "t_week_privat.md" and p["template_kind"] == "plain"
    assert p["place"] == {"anchor": "Reflections", "placement": "before"}
    assert [h["text"] for h in out["evidence"]["template_headings"]] == ["Theme", "Reflections"]
    assert "template_candidates" not in out and "needs_anchor" not in out and "anchor_candidates" not in out
    assert _listings(fake, TEMPLATES) == [], "a chosen template needs no listing"

    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week.md")
    assert out["proposal"]["template"] == "t_week.md" and out["proposal"]["template_kind"] == "templater"
    assert out["proposal"]["place"]["anchor"] == "In my own words"

    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "archive/Wochenplan alt")
    assert out["proposal"]["template"] == "archive/Wochenplan alt.md" and out["proposal"]["template_kind"] == "plain"


def test_the_flag_wins_over_the_mapping_and_a_missing_choice_is_reported_as_today(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_no_mapping(weekly="t_week.md"))
    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_privat")
    assert out["proposal"]["template"] == "t_week_privat.md" and out["proposal"]["place"]["anchor"] == "Reflections"

    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_gone")
    assert out["proposal"]["template"] == "t_gone.md" and out["proposal"]["template_kind"] == "missing"
    assert out["needs_anchor"] is True


@pytest.mark.parametrize("name", ["../t_week", "/t_week", "t\\week", " ", ".", "archive/../t_week", "..",
                                  "t_week\nalt", "t_week\ralt"])
def test_an_unsafe_template_name_is_a_usage_error(mod, instance, capsys, name):
    _config(instance, templates=_no_mapping())
    with pytest.raises(SystemExit) as info:
        mod.main(["--profiles-dir", "profiles", "match", "--kind", "week", "--template", name])
    out, err = capsys.readouterr()
    assert info.value.code == 2 and out == "" and "--template" in err


def test_two_dots_inside_a_segment_are_a_name_not_a_climb():
    """`..` is refused as a path segment (it climbs out of the templates folder), not as a substring: a template
    called `t_week..old` is a name below the folder like any other."""
    from lib.review_templates import template_name
    assert template_name("t_week..old") == "t_week..old.md"
    assert template_name("archive/..week.md") == "archive/..week.md"


def test_the_none_answer_is_trimmed_and_a_template_called_none_needs_its_extension(mod, instance, monkeypatch, capsys):
    """`--template " none "` is the `0 none` answer like the bare word (the flag is trimmed before the word is
    compared), so a template file called `none.md` is chosen with its extension only, never by the bare name."""
    from lib.review_templates import NO_TEMPLATE, template_choice
    assert template_choice(" none ") == NO_TEMPLATE and template_choice("none") == NO_TEMPLATE
    assert template_choice("none.md") == "none.md" and template_choice(" t_week ") == "t_week.md"

    _config(instance, templates=_no_mapping())
    fake = _vault(**{TEMPLATES + "none.md": "# n\n\n## Named none\n"})
    out = _match(mod, monkeypatch, capsys, fake, "--template", " none ")
    assert "template_candidates" not in out and out["proposal"]["template"] is None
    assert _listings(fake, TEMPLATES) == [] and _note_reads(fake, TEMPLATES) == [TEMPLATES + "t_day.md"]


# ---------------------------------------------------------------- (c) the anchor question

def test_without_an_anchor_the_proposal_needs_one_and_names_the_recent_notes_headings(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_no_mapping())
    fake = _vault()
    out = _match(mod, monkeypatch, capsys, fake)
    assert out["needs_anchor"] is True and out["proposal"]["place"]["anchor"] is None
    assert out["anchor_candidates"] == ["Review of the Week", "Notes", "In my own words", "Reflections"]
    assert out["template_candidates"] == ["archive/Wochenplan alt", "t_week", "t_week_privat", "t_week_work"], \
        "the first call carries both questions, so `0 none` needs no rerun"
    assert sorted(_note_reads(fake, WEEKLY)) == [WEEKLY + "2026-W12.md", WEEKLY + "2026-W13.md"], \
        "the two most recent weekly notes, nothing else"

    fake = _vault()
    out = _match(mod, monkeypatch, capsys, fake, kind="month")
    assert out["needs_anchor"] is True
    assert out["anchor_candidates"] == ["Month review", "Reflections", "Looking back"]
    assert sorted(_note_reads(fake, MONTHLY)) == [MONTHLY + "2026-02.md", MONTHLY + "2026-03.md"]


def test_a_template_without_headings_below_the_title_needs_an_anchor_too(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_no_mapping())
    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_work")
    assert out["proposal"]["template"] == "t_week_work.md" and out["proposal"]["template_kind"] == "plain"
    assert out["needs_anchor"] is True and out["proposal"]["place"]["anchor"] is None
    assert out["anchor_candidates"][0] == "Review of the Week"


def test_a_proposed_or_configured_anchor_needs_no_question_and_costs_no_note_read(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_no_mapping(weekly="t_week_privat.md"))
    fake = _vault()
    out = _match(mod, monkeypatch, capsys, fake)
    assert "needs_anchor" not in out and "anchor_candidates" not in out
    assert _note_reads(fake, WEEKLY) == []

    _config(instance, templates=_no_mapping(),
            review={"weekly": {"heading": "Tomo Review", "place": {"anchor": "Notes", "placement": "before"}}})
    fake = _vault()
    out = _match(mod, monkeypatch, capsys, fake)
    assert out["proposal"]["place"]["anchor"] == "Notes" and "needs_anchor" not in out
    assert _note_reads(fake, WEEKLY) == []


def test_no_readable_periodic_note_gives_an_empty_candidate_list_but_still_needs_the_anchor(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_no_mapping())
    fake = ReviewFakeVault(_templates(), folders=[WEEKLY, TEMPLATES])
    out = _match(mod, monkeypatch, capsys, fake)
    assert out["needs_anchor"] is True and out["anchor_candidates"] == []


def _setup_input(mod, monkeypatch, capsys, instance, confirmed: dict, kind="week"):
    path = instance / f"confirmed-{kind}.json"
    path.write_text(json.dumps(confirmed), encoding="utf-8")
    code, out, _ = _run(mod, monkeypatch, capsys,
                        ["setup-input", "--kind", kind, "--confirmed", str(path), "--today", TODAY], _vault())
    assert code == 0
    return out


def test_setup_input_refuses_the_needs_anchor_proposal_unchanged_and_accepts_a_candidate(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_no_mapping())
    out = _match(mod, monkeypatch, capsys, _vault())
    assert out["needs_anchor"] is True
    refused = _setup_input(mod, monkeypatch, capsys, instance, {"kind": "week", **out["proposal"]})
    assert refused["status"] == "invalid" and refused["errors"] == ["/place/anchor"]

    chosen = json.loads(json.dumps(out["proposal"]))
    chosen["place"]["anchor"] = out["anchor_candidates"][0]
    accepted = _setup_input(mod, monkeypatch, capsys, instance, {"kind": "week", **chosen})
    assert accepted["status"] == "ok"
    written = json.loads((instance / accepted["input_path"]).read_text(encoding="utf-8"))
    assert written["place"]["anchor"] == "Review of the Week" and written["template"] is None


# ---------------------------------------------------------------- (d) the writer saves the choice

INSTANCE_LIKE_CONFIG = """concepts:
  inbox: "100 Inbox/"
templates:
  base_path: "X/900 Support/930 Templater/"
  mapping:
    atomic_note: "t_note_tomo.md"
    daily: "t_day.md"
  note_include:
    - "t_*"
"""


def _writer(instance: Path, monkeypatch, capsys, input_path: str) -> dict:
    spec = importlib.util.spec_from_file_location("vault_config_writer_templates", SCRIPTS_DIR / "vault-config-writer.py")
    writer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = writer
    spec.loader.exec_module(writer)
    monkeypatch.setattr(sys, "argv", ["vault-config-writer.py", "review", "--input", input_path])
    rc = writer.main()
    out, err = capsys.readouterr()
    assert rc == 0 and err == "", (rc, err)
    return json.loads(out)


def test_the_chosen_template_is_saved_to_the_mapping_and_the_rest_of_the_block_stays(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_no_mapping())
    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_privat")
    accepted = _setup_input(mod, monkeypatch, capsys, instance, {"kind": "week", **out["proposal"]})
    assert accepted["status"] == "ok"
    config_path = instance / "config" / "vault-config.yaml"
    config_path.write_text(INSTANCE_LIKE_CONFIG, encoding="utf-8")
    written = _writer(instance, monkeypatch, capsys, accepted["input_path"])
    assert written["status"] == "written" and "templates.mapping.weekly" in written["keys"]
    after = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert after["templates"]["mapping"]["weekly"] == "t_week_privat.md"
    assert after["templates"]["base_path"] == TEMPLATES
    assert after["templates"]["mapping"]["daily"] == "t_day.md" and after["templates"]["note_include"] == ["t_*"]
    assert after["review"]["weekly"]["place"] == {"anchor": "Reflections", "placement": "before"}


def test_none_saves_nothing_to_the_mapping(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_no_mapping())
    out = _match(mod, monkeypatch, capsys, _vault())
    assert out["proposal"]["template"] is None, "`0 none` keeps the first proposal: no template"
    confirmed = json.loads(json.dumps(out["proposal"]))
    confirmed["place"]["anchor"] = out["anchor_candidates"][0]
    accepted = _setup_input(mod, monkeypatch, capsys, instance, {"kind": "week", **confirmed})
    assert accepted["status"] == "ok"
    config_path = instance / "config" / "vault-config.yaml"
    config_path.write_text(INSTANCE_LIKE_CONFIG, encoding="utf-8")
    written = _writer(instance, monkeypatch, capsys, accepted["input_path"])
    assert written["status"] == "written"
    assert not any(key.startswith("templates.") for key in written["keys"]), written["keys"]
    after = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert after["templates"]["mapping"] == {"atomic_note": "t_note_tomo.md", "daily": "t_day.md"}


# ---------------------------------------------------------------- (e) the two answers carried on a rerun

def test_template_none_lists_nothing_and_proposes_the_plain_note(mod, instance, monkeypatch, capsys):
    """`--template none` is the `0 none` answer passed back: the templates folder is not listed again, the
    output carries no `template_candidates`, and the plain note is proposed; the anchor question still stands."""
    _config(instance, templates=_no_mapping())
    fake = _vault()
    out = _match(mod, monkeypatch, capsys, fake, "--template", "none")
    assert "template_candidates" not in out
    assert out["proposal"]["template"] is None and out["proposal"]["template_kind"] == "missing"
    assert _listings(fake, TEMPLATES) == [], "`none` answers the question: no second listing"
    assert _note_reads(fake, TEMPLATES) == [TEMPLATES + "t_day.md"], "no template is read"
    assert out["needs_anchor"] is True and out["proposal"]["place"]["anchor"] is None

    # `none` wins over a mapping entry like every flag (a Correct from a mapped template to the plain note)
    _config(instance, templates=_no_mapping(weekly="t_week_privat.md"))
    fake = _vault()
    out = _match(mod, monkeypatch, capsys, fake, "--template", "none")
    assert out["proposal"]["template"] is None and "template_candidates" not in out
    assert _note_reads(fake, TEMPLATES) == [TEMPLATES + "t_day.md"]

    # a template file literally named `none` is chosen with its extension
    extra = {TEMPLATES + "none.md": "# n\n\n## Named none\n"}
    out = _match(mod, monkeypatch, capsys, _vault(**extra), "--template", "none.md")
    assert out["proposal"]["template"] == "none.md" and out["proposal"]["place"]["anchor"] == "Named none"


def test_anchor_flag_sets_the_place_and_asks_no_anchor_question(mod, instance, monkeypatch, capsys):
    """`--anchor` is the typed or picked heading passed back: trimmed into `place.anchor`, no `needs_anchor`,
    no `anchor_candidates`, no periodic-note read; it wins over the template's proposal and the configured anchor."""
    _config(instance, templates=_no_mapping())
    fake = _vault()
    out = _match(mod, monkeypatch, capsys, fake, "--template", "none", "--anchor", "  Review of the Week ")
    assert out["proposal"]["place"] == {"anchor": "Review of the Week", "placement": "before"}
    assert "needs_anchor" not in out and "anchor_candidates" not in out and "template_candidates" not in out
    assert _note_reads(fake, WEEKLY) == [], "a given anchor costs no periodic-note read"
    assert _listings(fake, TEMPLATES) == []

    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_privat", "--anchor", "Theme")
    assert out["proposal"]["template"] == "t_week_privat.md" and out["proposal"]["place"]["anchor"] == "Theme"
    assert [h["text"] for h in out["evidence"]["template_headings"]] == ["Theme", "Reflections"], \
        "the template's headings are still the evidence; the flag only sets the place"

    _config(instance, templates=_no_mapping(),
            review={"weekly": {"heading": "Tomo Review", "place": {"anchor": "Notes", "placement": "inside"}}})
    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "none", "--anchor", "Reflections")
    assert out["proposal"]["place"] == {"anchor": "Reflections", "placement": "inside"}


def test_a_rerun_with_both_flags_keeps_both_choices(mod, instance, monkeypatch, capsys):
    """The week-rule rerun and every Correct rerun of SKILL.md step 2 carry the user's two answers: the
    rerun asks neither question again and spends neither the listing nor the two note reads."""
    _config(instance, templates=_no_mapping())
    first = _match(mod, monkeypatch, capsys, _vault())
    assert first["template_candidates"] and first["needs_anchor"] is True
    anchor = first["anchor_candidates"][0]
    fake = _vault()
    rerun = _match(mod, monkeypatch, capsys, fake, "--folder", WEEKLY, "--format", "GGGG-[W]WW",
                   "--first-day", "monday", "--min-days", "4", "--template", "none", "--anchor", anchor)
    assert rerun["proposal"]["template"] is None and rerun["proposal"]["place"]["anchor"] == anchor
    assert "template_candidates" not in rerun and "needs_anchor" not in rerun and "anchor_candidates" not in rerun
    assert _listings(fake, TEMPLATES) == [] and _note_reads(fake, WEEKLY) == []
    assert rerun["proposal"]["folder"] == WEEKLY and rerun["proposal"]["first_day"] == "monday"


@pytest.mark.parametrize("value", ["", "   ", "a\nb"])
def test_a_blank_or_multi_line_anchor_is_a_usage_error(mod, instance, capsys, value):
    _config(instance, templates=_no_mapping())
    with pytest.raises(SystemExit) as info:
        mod.main(["--profiles-dir", "profiles", "match", "--kind", "week", "--anchor", value])
    out, err = capsys.readouterr()
    assert info.value.code == 2 and out == "" and "--anchor" in err


# ---------------------------------------------------------------- (g) the template's frontmatter block

def test_a_template_that_opens_a_frontmatter_block_at_its_first_line_needs_no_ok(mod, instance, monkeypatch, capsys):
    """`t_week.md` starts with `---` and closes it: Pass 2 merges Tomo's block into it, so nothing is asked."""
    _config(instance, templates=_no_mapping())
    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week")
    assert out["proposal"]["template_frontmatter"] is True
    assert "needs_template_ok" not in out

    _config(instance, templates=_no_mapping(weekly="t_week.md"))
    out = _match(mod, monkeypatch, capsys, _vault())
    assert out["proposal"]["template_frontmatter"] is True and "needs_template_ok" not in out, \
        "a mapped template is checked like a chosen one"


def test_a_fence_that_comes_only_from_a_templater_include_is_no_block(mod, instance, monkeypatch, capsys):
    """The live-walk template: line 1 is Templater code and the opening `---` is rendered by an include, so the
    text Tomo reads has no block at line 1 (mutation: looking for `---` anywhere reads the closing fence as one)."""
    _config(instance, templates=_no_mapping())
    extra = {TEMPLATES + "t_month_include.md": T_MONTH_INCLUDE}
    out = _match(mod, monkeypatch, capsys, _vault(**extra), "--template", "t_month_include", kind="month")
    assert out["proposal"]["template_kind"] == "templater" and out["proposal"]["place"]["anchor"] == "Reflections"
    assert out["proposal"]["template_frontmatter"] is False
    assert out["needs_template_ok"] is True

    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_privat")
    assert out["proposal"]["template_frontmatter"] is False and out["needs_template_ok"] is True, \
        "a plain template without any frontmatter is asked about too: Tomo would prepend its block"


def test_a_lone_opening_fence_without_a_closing_one_is_no_block(mod, instance, monkeypatch, capsys):
    """An unclosed fence is what Pass 2 cannot merge into (it falls back to the plain note), so it counts as no
    block (mutation: the first line alone deciding reads it as true)."""
    _config(instance, templates=_no_mapping())
    extra = {TEMPLATES + "t_week_unclosed.md": T_WEEK_UNCLOSED}
    out = _match(mod, monkeypatch, capsys, _vault(**extra), "--template", "t_week_unclosed")
    assert out["proposal"]["template_frontmatter"] is False and out["needs_template_ok"] is True


def test_an_empty_template_is_a_read_text_without_a_block(mod, instance, monkeypatch, capsys):
    """An empty template was read (kind `plain`), so the field is false and the question is asked: Tomo would
    prepend its block to it (mutation: a truthiness test on the text reads it as never read, null, never asked)."""
    _config(instance, templates=_no_mapping())
    extra = {TEMPLATES + "t_week_empty.md": ""}
    out = _match(mod, monkeypatch, capsys, _vault(**extra), "--template", "t_week_empty")
    assert out["proposal"]["template_kind"] == "plain"
    assert out["proposal"]["template_frontmatter"] is False and out["needs_template_ok"] is True


def test_without_a_template_the_field_is_null_and_nothing_is_asked(mod, instance, monkeypatch, capsys):
    """`none`, the candidate list, a missing name and an unreadable template: no text was read, so the field is
    null and the question is not asked (the plain-note line of the skill already covers these)."""
    from lib.kado_client import KadoError
    _config(instance, templates=_no_mapping())
    for extra in (["--template", "none"], [], ["--template", "t_gone"]):
        out = _match(mod, monkeypatch, capsys, _vault(), *extra)
        assert out["proposal"]["template_frontmatter"] is None, extra
        assert "needs_template_ok" not in out, extra

    fake = _vault()
    fake.fail[("read_note", TEMPLATES + "t_week.md")] = KadoError("tool error")
    out = _match(mod, monkeypatch, capsys, fake, "--template", "t_week")
    assert out["proposal"]["template_kind"] == "unreadable"
    assert out["proposal"]["template_frontmatter"] is None and "needs_template_ok" not in out


def test_the_ok_answer_is_carried_as_a_flag_bound_to_the_template_it_answered_for(mod, instance, monkeypatch, capsys):
    """`--template-frontmatter-ok <name>` is the `1 Use it as it is` answer passed back on every rerun of the step:
    the output says the truth (`template_frontmatter` false) but asks no more. The flag names the template it
    answered for, with or without `.md`, so a Correct to another template without a block asks again, and a
    template with a block is never asked whatever the flag names."""
    _config(instance, templates=_no_mapping())
    first = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_privat")
    assert first["needs_template_ok"] is True

    for ok in ("t_week_privat", "t_week_privat.md", " t_week_privat "):
        fake = _vault()
        rerun = _match(mod, monkeypatch, capsys, fake, "--template", "t_week_privat", "--anchor", "Theme",
                       "--first-day", "monday", "--min-days", "4", "--template-frontmatter-ok", ok)
        assert rerun["proposal"]["template_frontmatter"] is False, ok
        assert "needs_template_ok" not in rerun, ok
        assert rerun["proposal"]["place"]["anchor"] == "Theme" and "needs_anchor" not in rerun
        assert _listings(fake, TEMPLATES) == []

    corrected = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_work",
                       "--template-frontmatter-ok", "t_week_privat")
    assert corrected["proposal"]["template_frontmatter"] is False and corrected["needs_template_ok"] is True, \
        "the OK was given for t_week_privat, not for the corrected template"

    with_block = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week",
                        "--template-frontmatter-ok", "t_week_privat")
    assert with_block["proposal"]["template_frontmatter"] is True and "needs_template_ok" not in with_block


@pytest.mark.parametrize("value", ["../t_week", "t_week\nalt", " "])
def test_an_unsafe_ok_value_is_a_usage_error_like_the_template_name(mod, instance, capsys, value):
    _config(instance, templates=_no_mapping())
    with pytest.raises(SystemExit) as info:
        mod.main(["--profiles-dir", "profiles", "match", "--kind", "week", "--template", "t_week_privat",
                  "--template-frontmatter-ok", value])
    out, err = capsys.readouterr()
    assert info.value.code == 2 and out == "" and "--template-frontmatter-ok" in err


def test_the_frontmatter_field_is_dropped_from_the_writer_input_like_template_kind(mod, instance, monkeypatch, capsys):
    _config(instance, templates=_no_mapping())
    out = _match(mod, monkeypatch, capsys, _vault(), "--template", "t_week_privat")
    assert out["proposal"]["template_frontmatter"] is False
    accepted = _setup_input(mod, monkeypatch, capsys, instance, {"kind": "week", **out["proposal"]})
    assert accepted["status"] == "ok"
    written = json.loads((instance / accepted["input_path"]).read_text(encoding="utf-8"))
    assert "template_frontmatter" not in written and "template_kind" not in written
    assert written["template"] == "t_week_privat.md"


# ---------------------------------------------------------------- (f) the skill carries both answers

def _setup_step() -> str:
    text = SKILL.read_text(encoding="utf-8")
    begin = text.index("\n## 2. Setup\n")
    return text[begin:text.index("\n## ", begin + 1)]


def test_every_later_match_call_of_the_setup_step_carries_the_template_choice():
    """A literal model drops a flag it is not shown: every `match` call of step 2 after the first carries
    `--template <template>`, `<template>` is defined once (the chosen name in quotes, or `none`), and the
    rule names `--anchor "<anchor>"` for every call after the anchor is given."""
    step = _setup_step()
    calls = re.findall(r"python3 scripts/review-session\.py match[^`\n]*", step)
    assert calls[0] == "python3 scripts/review-session.py match --kind <kind>", calls
    assert len(calls) >= 3, "the template rerun and the week-rule rerun are written out"
    assert all("--template <template>" in call for call in calls[1:]), calls
    assert "`0` → `<template>` is `none`" in step
    assert "A number → `<template>` is `\"<name>\"`" in step
    assert "a typed name → `<template>` is that name in double quotes" in step
    assert "Every later `match` call of this step carries `--template <template>`" in step
    assert "`--anchor \"<anchor>\"`" in step
    assert "The answer is `<anchor>`" in step
