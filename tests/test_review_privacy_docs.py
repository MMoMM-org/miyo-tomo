#!/usr/bin/env python3
# version: 0.5.0
"""test_review_privacy_docs.py — spec 045 T5.3, spec 047 T7.1: the privacy and setup documentation of /review.

Pins PRIVACY.md (PRD F7-AC2, ADR-9): "metadata only" is scoped to Tomo's own
records; every place read content rests is named — the session transcripts in
the container home, one transcript per review model among them (spec 047
F7-AC3), the stage `tomo-tmp/review/<period>_review/` with every file that
holds note content (CON-3: days/, growth/, children/, previous/, context*.json,
digests/, carryover.json, proposals.json), deleted on write, Pass 1 abort, drop
and a new read (ADR-10), an interrupted run resting until one of those or that
period's next /review, a Kado stop storing nothing (F7-AC2), no old read.json
named, the inbox (removing
the delivered files is the user's job); removal is the user's choice; both
`instance/` and `home/` are to be protected like the vault (for example an
encrypted disk); the /review paragraph names what reaches the model (paths of
the created notes, not their content; in Pass 2 the parsed document gives the
model counts and ids only and the preview shows the section as it will land —
the habit averages among its lines — never "read back"; the note's headings
reach the model when the place cannot be resolved, which is every refusal
that sets them, not only a missing heading; during the setup the names of the
templates in the templates folder and the headings of the two most recent
weekly or monthly notes reach the model, their headings and not their text —
fix round 1 of the Phase 6 live-walk fix; the previous reviews as a source read
through Kado; the three models haiku, sonnet and opus — spec 047 F7-AC3) and
recommends Kado deny rules for folders not to be reviewed, in one sentence.

Each phrase test is pinned to the clause it guards: deleting that clause from
PRIVACY.md fails the test (proven by mutation in an isolated copy, T5.3-fix1).

Pins docs/setup.md linking to that PRIVACY.md section (and, drift round D of
Phase 5: the credentials and restore paragraphs staying under the Backup and
Restore heading ahead of the Protect subsection, and the IDE lock path naming
the instance home `home/`, never `tomo-home/`) and naming the three models
with their own transcripts, the README naming /review and listing the three
review agents, docs/usage.md explaining each carried mark as lib/review_doc
writes it (English and German), and tomo/config/vault-example.yaml: the weekly pattern GGGG-[W]WW and
a commented review: example that the real reader (lib.review_config) accepts
for week, month and quarter, whose section rows and off-limits marks it reads
for the mapped template (spec 046 T1.3), and whose writer-input form validates
against vault-config-review.schema.json.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
PRIVACY = ROOT / "PRIVACY.md"
SETUP = ROOT / "docs" / "setup.md"
README = ROOT / "README.md"
USAGE = ROOT / "docs" / "usage.md"
EXAMPLE = ROOT / "tomo" / "config" / "vault-example.yaml"
PROFILE = ROOT / "tomo" / "profiles" / "miyo.yaml"
SCHEMA = ROOT / "tomo" / "schemas" / "vault-config-review.schema.json"

sys.path.insert(0, str(ROOT / "tomo" / "scripts"))
from lib import review_config as rc  # noqa: E402
from lib import review_doc  # noqa: E402

TODAY = date(2026, 11, 12)


def _privacy() -> str:
    return PRIVACY.read_text(encoding="utf-8")


def _section(text: str, heading_pattern: str) -> str:
    """The body of the first heading matching ``heading_pattern`` up to the next heading of the same or a higher level."""
    m = re.search(rf"^(#+) ({heading_pattern})\s*$", text, re.M | re.I)
    assert m, f"missing heading matching {heading_pattern!r}"
    level = len(m.group(1))
    rest = text[m.end():]
    nxt = re.search(rf"^#{{1,{level}}} ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _review_paragraph() -> str:
    """The `/review` paragraph of 'What vault content reaches the LLM': from its 'During' line to the next 'During' line or heading."""
    section = _section(_privacy(), r"What vault content reaches the LLM")
    m = re.search(r"^During \*\*`/review`\*\*", section, re.M)
    assert m, "PRIVACY.md needs a paragraph starting 'During **`/review`**'"
    rest = section[m.start():]
    nxt = re.search(r"^(During |#+ )", rest[1:], re.M)
    return rest[: nxt.start() + 1] if nxt else rest


def _plain(text: str) -> str:
    """Lower-cased, wrapped lines joined, bold markers dropped — so a phrase matches across a line break."""
    return re.sub(r"\s+", " ", text.replace("**", "")).lower()


def _has(text: str, *phrases: str) -> None:
    plain = _plain(text)
    missing = [p for p in phrases if p.lower() not in plain]
    assert not missing, f"missing phrases: {missing}"


def _sentences(text: str) -> list[str]:
    """The plain-text sentences of ``text`` (split at '.' or ';')."""
    return re.split(r"(?<=[.;])\s", _plain(text))


def _one_sentence_has(text: str, *phrases: str) -> None:
    """Some single sentence of ``text`` holds every phrase — the phrases make one claim, not several."""
    assert any(all(p.lower() in s for p in phrases) for s in _sentences(text)), \
        f"no single sentence holds all of {phrases}"


# --- (a) metadata only is scoped to Tomo's own records ----------------------------------

def test_metadata_only_is_scoped_to_tomos_own_records() -> None:
    recorded = _section(_privacy(), r"What Tomo records.*")
    _has(recorded, "metadata only", "tomo's own records", "logs", "error output", "cost records")
    # the scope is stated: the claim covers Tomo's records, not every place content rests
    _has(recorded, "not a promise that no content rests", "where read content rests")


# --- (b) every place read content rests is named ----------------------------------------

def test_names_every_place_read_content_rests() -> None:
    rests = _section(_privacy(), r"Where read content rests")
    _has(rests, "session transcript", "container home", "home/.claude/projects/")
    _has(rests, "inbox", "review.md", "_instructions.json")


def test_names_every_stage_file_that_holds_note_content() -> None:
    """CON-3 / ADR-10: the stage files that hold note content, as lib/review_stage.write lays them out."""
    rests = _section(_privacy(), r"Where read content rests")
    _one_sentence_has(rests, "`tomo-tmp/review/<period>_review/`", "`days/`", "`growth/`", "`children/`",
                      "`previous/`", "`context.json`", "`digests/`", "`carryover.json`", "`proposals.json`")


def test_stage_content_is_deleted_at_each_moment() -> None:
    """review-doc.py write and replace --abort, review-instructions.py drop, review-read.py before a new read."""
    rests = _section(_privacy(), r"Where read content rests")
    _one_sentence_has(rests, "deletes them", "written to your inbox", "abort the review", "drop the review",
                      "new read of the period")


def test_an_interrupted_run_rests_until_one_of_those_moments() -> None:
    """F7-AC2: an interrupted Pass 1 keeps its material until a deletion moment or that period's next new read."""
    rests = _section(_privacy(), r"Where read content rests")
    _one_sentence_has(rests, "interrupted", "stays there until", "that period's next `/review`")


def test_a_kado_stop_leaves_nothing_stored() -> None:
    """F7-AC2 / F6-AC4: review-read.py discards before its first Kado call and writes nothing when Kado stops it."""
    rests = _section(_privacy(), r"Where read content rests")
    _one_sentence_has(rests, "stopped because kado", "stores nothing")


def test_each_model_writes_its_own_transcript_in_the_container_home() -> None:
    """F7-AC3: every review subagent runs as its own Claude Code session with its own transcript."""
    rests = _section(_privacy(), r"Where read content rests")
    _one_sentence_has(rests, "each of the three models", "its own session transcript", "container home")


def test_the_old_read_files_are_gone() -> None:
    """Spec 047 replaced read.json (and the quarter's read parts) with the stage folder."""
    rests = _plain(_section(_privacy(), r"Where read content rests"))
    assert "read.json" not in rests


def test_removing_the_delivered_inbox_files_is_the_users_job() -> None:
    rests = _section(_privacy(), r"Where read content rests")
    _one_sentence_has(rests, "stay in the inbox", "removing them is yours to do")


# --- (c) removal is the user's choice; protect instance and home like the vault ---------

def test_removal_is_the_users_choice_and_protection_is_recommended() -> None:
    rests = _section(_privacy(), r"Where read content rests")
    _has(rests, "your choice", "does not remove", "encrypted disk")
    _one_sentence_has(rests, "protect the instance directory", "both `instance/` and `home/`", "like your vault")


# --- (d) the /review paragraph names what reaches the model -----------------------------

def test_review_paragraph_names_what_reaches_the_model() -> None:
    para = _review_paragraph()
    _has(para, "daily note", "sections", "5 year journal", "tracker values", "sleep", "energy", "sport")
    _one_sentence_has(para, "paths", "notes created in the period", "not their content")


def test_review_paragraph_says_what_pass_2_shows_the_model() -> None:
    para = _review_paragraph()
    _one_sentence_has(para, "review document you edited", "only counts and ids")
    _one_sentence_has(para, "section as it will land", "items you kept", "your wording")
    _has(para, "instruction set", "not shown to the model")
    assert "read back" not in _plain(para), "Pass 2 does not read the document back to the model"


def test_review_paragraph_names_when_the_headings_reach_the_model() -> None:
    """The note's headings reach the model on every refusal that sets them (lib/review_actions `_refuse`:
    place-missing, place-too-deep, user-heading-collision), not only when the heading is missing."""
    para = _review_paragraph()
    _one_sentence_has(para, "place cannot be resolved", "note's headings")
    assert "when that heading cannot be found" not in _plain(para)


def test_review_paragraph_names_what_the_setup_shows_the_model() -> None:
    """`review-session.py match` prints `template_candidates` (names below templates.base_path) and, when no
    anchor can be proposed, `anchor_candidates` (the headings of the two most recent periodic notes): both
    reach the model during the setup, so the paragraph names them in one plain sentence — headings, not text."""
    para = _review_paragraph()
    _one_sentence_has(para, "during the setup", "names of the templates", "headings of your two most recent",
                      "not their text")


def test_review_paragraph_says_the_previewed_section_holds_the_habit_averages() -> None:
    """The habits group is a group of the document (lib/review_doc GROUPS); its kept items land in
    section_md like every other group, so the preview the model sees carries the averages."""
    para = _review_paragraph()
    _one_sentence_has(para, "habit averages", "part of the section")


def test_review_paragraph_names_the_previous_reviews_as_a_read_source() -> None:
    """F7-AC3 / F3-AC1..3: lib/review_previous reads the previous notes through Kado in the same paced read."""
    _one_sentence_has(_review_paragraph(), "previous reviews", "read through kado", "previous week's note")


def test_review_paragraph_names_the_three_models() -> None:
    """F7-AC3: review-digester (haiku), review-carryover (sonnet), review-proposer (opus) see note content."""
    _one_sentence_has(_review_paragraph(), "three claude models", "haiku", "sonnet", "opus")


def test_review_paragraph_recommends_kado_deny_rules() -> None:
    para = _review_paragraph()
    _one_sentence_has(para, "kado", "deny rules", "folders you do not want reviewed")


# --- docs/setup.md links to the privacy section; README names /review -------------------

def test_setup_guide_links_to_the_privacy_section() -> None:
    setup = SETUP.read_text(encoding="utf-8")
    links = re.findall(r"\]\(\.\./PRIVACY\.md#([a-z0-9-]+)\)", setup)
    assert links, "docs/setup.md needs a link into ../PRIVACY.md"
    headings = {re.sub(r"[^a-z0-9 -]", "", h.lower()).replace(" ", "-")
                for h in re.findall(r"^#+ (.+)$", _privacy(), re.M)}
    assert set(links) <= headings, f"dangling anchors: {set(links) - headings}"
    _has(setup, "like your vault")


def test_setup_guide_keeps_the_credentials_paragraph_under_the_backup_heading() -> None:
    """D6: the "Protect the instance like your vault" subsection follows the archive-credentials and
    restore paragraphs, so those stay under the Backup and Restore heading instead of under Protect."""
    backup = _section(SETUP.read_text(encoding="utf-8"), r"Backup and Restore")
    credentials = backup.index("The archive contains your Kado and Claude Code credentials")
    restore = backup.index("To restore, run the installer first")
    protect = backup.index("### Protect the instance like your vault")
    assert credentials < restore < protect, (credentials, restore, protect)


def test_setup_guide_names_the_instance_home_for_the_ide_lock() -> None:
    """D7: the instance home is `home/` (setup.md names it so for the gitconfig and the Docker mount);
    the IDE lock path the wizard writes is `<home>/.claude/ide/<port>.lock` (scripts/lib/configure-ide-bridge.sh)."""
    setup = SETUP.read_text(encoding="utf-8")
    assert "tomo-home/.claude" not in setup
    assert "`home/.claude/ide/<port>.lock`" in setup


def test_setup_guide_names_the_three_models() -> None:
    """F7-AC3: docs/setup.md names the models whose transcripts rest in the instance home."""
    _one_sentence_has(SETUP.read_text(encoding="utf-8"), "haiku", "sonnet", "opus", "own transcript")


def test_readme_lists_the_three_review_agents() -> None:
    readme = README.read_text(encoding="utf-8")
    for agent in ("review-digester", "review-carryover", "review-proposer"):
        assert re.search(rf"^\| `{agent}` \|", readme, re.M), f"README agents table needs a {agent} row"


def test_usage_explains_every_carried_mark() -> None:
    """The Could Have passage of docs/usage.md names each mark exactly as lib/review_doc writes it."""
    usage = _section(USAGE.read_text(encoding="utf-8"), r"What the marks of a review mean")
    for lang in ("en", "de"):
        for key in ("carried_done", "carried_still_open", "carried_not_mentioned"):
            mark = review_doc._LABELS[lang][key]
            assert f"`{mark}`" in usage, f"docs/usage.md does not explain {mark!r}"


def test_readme_names_review() -> None:
    readme = README.read_text(encoding="utf-8")
    assert re.search(r"^- \*\*`/review`\*\* — ", readme, re.M), "README 'What Tomo Does' needs a /review line"
    assert re.search(r"^\| `/review` \|", readme, re.M), "README command table needs a /review row"


# --- vault-example.yaml ------------------------------------------------------------------

def _example_config() -> dict:
    return yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


def _commented_review_example() -> dict:
    """The `review:` block that sits commented out in vault-example.yaml, uncommented and parsed."""
    lines = EXAMPLE.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("# review:")
    except ValueError:
        pytest.fail("vault-example.yaml needs a commented '# review:' example")
    block = []
    for line in lines[start:]:
        if line.startswith("# ───") or not line.startswith("#"):
            break
        block.append(line[2:] if line.startswith("# ") else line[1:])
    data = yaml.safe_load("\n".join(block))
    assert isinstance(data, dict) and isinstance(data.get("review"), dict)
    return data["review"]


def test_weekly_pattern_is_iso_week_year() -> None:
    assert _example_config()["naming"]["calendar_patterns"]["weekly"] == "GGGG-[W]WW"


@pytest.mark.parametrize("kind", ["week", "month", "quarter"])
def test_commented_review_example_is_a_valid_setup(kind: str) -> None:
    config = _example_config()
    config["review"] = _commented_review_example()
    # `/review setup` enables the periodic folder; the example keeps the profile default (disabled)
    config["concepts"]["calendar"]["granularities"][rc.GRANULARITY[kind]] = {
        "enabled": True, "path": f"Calendar/{rc.GRANULARITY[kind].title()}/"}
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))

    setup = rc.review_setup(config, profile, kind, today=TODAY)       # the real reader accepts it
    assert setup is not None and setup.heading and setup.daily_sections

    proposal = rc.current_setup(config, profile, kind, TODAY)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    # the None keys are dropped before validation — only keys the schema leaves optional may be, so a
    # required field missing from the proposal cannot hide behind the filter
    dropped = {k for k, v in proposal.items() if v is None}
    assert dropped.isdisjoint(_required_keys(schema, kind)), f"required keys dropped: {dropped}"
    writer_input = {"kind": kind, **{k: v for k, v in proposal.items() if v is not None}}
    jsonschema.Draft202012Validator(schema).validate(writer_input)   # the writer input validates
    assert rc.input_problems(writer_input, today=TODAY) == []


def test_commented_review_example_rows_are_read_for_the_mapped_template() -> None:
    config = _example_config()
    config["review"] = _commented_review_example()
    config["concepts"]["calendar"]["granularities"]["weekly"] = {"enabled": True, "path": "Calendar/Weekly/"}
    template = config["templates"]["mapping"]["weekly"]
    assert set(config["review"]["weekly"]["sections"]) == {template}, "the example keys rows by the mapped template"
    setup = rc.review_setup(config, {}, "week", today=TODAY)
    assert [r["placement"] for r in setup.sections] == ["end", "review"]
    assert setup.off_limits and setup.off_limits[0]["with_subsections"] is True
    stored = config["review"]["weekly"]
    writer_input = {"kind": "week", "folder": "Calendar/Weekly/", "format": "GGGG-[W]WW", "first_day": "monday",
                    "min_days": 4, "template": template, "heading": stored["heading"], "place": stored["place"],
                    "language": "de", "sections": stored["sections"][template],
                    "off_limits": stored["off_limits"][template]}
    assert rc.input_problems(writer_input, today=TODAY) == []


def _required_keys(schema: dict, kind: str) -> set[str]:
    """The keys vault-config-review.schema.json requires for ``kind``: the top-level list plus the kind's allOf branch."""
    required = set(schema["required"])
    for clause in schema.get("allOf", []):
        if clause["if"]["properties"]["kind"]["const"] == kind:
            required |= set(clause["then"].get("required", []))
    assert "kind" in required and (kind != "week" or {"first_day", "min_days"} <= required)
    return required
