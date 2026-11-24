#!/usr/bin/env python3
# version: 0.1.0
"""test_047_agents.py — the three /review agents (spec 047 T6.2; ADR-7; PRD F1-AC3, F1-AC4, F1-AC5, F2-AC3,
F4-AC1, F4-AC2, F4-AC3, F4-AC4, F4-AC5, F4-AC6, F4-AC8, F4-AC10, F4-AC11, F6-AC2, F7-AC5).

What each agent writes is model behaviour; this file proves that each rule has its imperative in
tomo/dot_claude/agents/review-{digester,carryover,proposer}.md and that the names the agents use are the
scripts' and schemas' own:
- frontmatter: ``# version: 0.1.0``, the owner's model, ``permissionMode: acceptEdits``, ``tools: Read, Write``
  only (no Bash, no ``mcp__*``, no Agent, no skills) — F7-AC5
- no rationale, spec ids, dates or examples in the runtime text (their WHY lives in docs/tomo/dot_claude/agents/)
- the prompt fields each agent names are the job fields ``review-digest.py plan`` prints
- the schema field names of the file each agent writes are named
- one prose pin per rule (``PINS``), each a literal phrase on the one line that owns it, matched EXACTLY once;
  deleting that line fails the row (proven by a sweep outside the repo, see the T6.2 report)

The step-5 proposal pins of tests/test_review_skill.py, test_046_t4_4_skill_sections.py and
test_046_t4_5_skill_quarter.py are re-created here against review-proposer.md (listed one to one in the
T6.2 commit message); T6.3 removes the old ones.

RED before T6.2: none of the three agent files exists.
"""
from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest
import yaml

from review_cli_contract import REPO, load_script

AGENTS_DIR = REPO / "tomo" / "dot_claude" / "agents"
SCHEMAS = REPO / "tomo" / "schemas"
MODELS = {"review-digester": "haiku", "review-carryover": "sonnet", "review-proposer": "opus"}
AGENTS = sorted(MODELS)
DIGEST_SCRIPT = REPO / "tomo" / "scripts" / "review-digest.py"
PROMPT_EXTRA = {"stem", "read_id", "language"}          # given by the skill's template beside the job's fields


def _text(agent: str) -> str:
    return (AGENTS_DIR / f"{agent}.md").read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _parts(agent: str) -> tuple[dict, str]:
    text = _text(agent)
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"{agent}: no frontmatter block"
    return yaml.safe_load(match.group(1)), text[match.end():]


def _count(agent: str, phrase: str) -> int:
    return len(re.findall(re.escape(phrase), _flat(_text(agent))))


# ── frontmatter (ADR-7, F7-AC5) ──────────────────────────────────────────────


@pytest.mark.parametrize("agent", AGENTS)
def test_carries_version_0_1_0_once(agent):
    assert re.findall(r"^# version: .*$", _text(agent), re.MULTILINE) == ["# version: 0.1.0"]


@pytest.mark.parametrize("agent", AGENTS)
def test_frontmatter_names_the_agent_its_model_and_accept_edits(agent):
    head, _body = _parts(agent)
    assert head["name"] == agent
    assert head["model"] == MODELS[agent]
    assert head["permissionMode"] == "acceptEdits"
    assert "MUST BE USED" in head["description"]


@pytest.mark.parametrize("agent", AGENTS)
def test_tools_are_read_and_write_only(agent):
    head, body = _parts(agent)
    assert [t.strip() for t in str(head["tools"]).split(",")] == ["Read", "Write"]
    assert "skills" not in head
    for banned in ("Bash", "mcp__", "Agent(", "Skill", "kado-", "subagent_type"):
        assert banned not in body, (agent, banned)


@pytest.mark.parametrize("agent", AGENTS)
def test_the_runtime_text_holds_no_rationale_ids_dates_or_examples(agent):
    _head, body = _parts(agent)
    for pattern in (r"\bF\d+-AC\d+", r"\bADR-\d+", r"\bspec \d{3}\b", r"\b\d{4}-\d{2}-\d{2}\b", r"\bWhy\b",
                    r"\bSTRICT\b", r"<example>", r"\be\.g\.", r"[Ff]or example", r"#\d{2,}"):
        assert not re.search(pattern, body), (agent, pattern)


# ── the prompt fields are the job fields of `review-digest.py plan` ─────────


def _job_keys(function: str) -> set:
    source = DIGEST_SCRIPT.read_text(encoding="utf-8")
    body = source[source.index(f"def {function}("):]
    body = body[:body.index("\ndef ", 1)]
    return set(re.findall(r'"([a-z_]+)":', body)) - {"agent"}


def _prompt_fields(agent: str) -> set:
    (line,) = [ln for ln in _text(agent).splitlines() if ln.startswith("The prompt names: ")]
    return set(re.findall(r"`([a-z_]+)`", line))


def test_the_digester_prompt_is_the_digester_job():
    assert _prompt_fields("review-digester") - PROMPT_EXTRA == _job_keys("_digester_job")
    assert {"stem", "read_id", "language"} <= _prompt_fields("review-digester")


def test_the_carryover_prompt_is_the_carryover_job():
    assert _prompt_fields("review-carryover") - PROMPT_EXTRA == _job_keys("_carrier_job")
    assert {"stem", "read_id", "language"} <= _prompt_fields("review-carryover")


def test_the_proposer_prompt_is_plans_proposer_entry():
    assert _prompt_fields("review-proposer") - {"stem", "language", "errors"} == _job_keys("_proposer")
    assert {"stem", "language", "errors"} <= _prompt_fields("review-proposer")


# ── the schema field names of each output file are named ────────────────────


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_the_digester_names_every_digest_field():
    schema = _schema("review-digest.schema.json")
    fields = set(schema["required"]) | {"text", "sources", "days", "key", "items", "notes"}
    text = _text("review-digester")
    assert all(f"`{f}`" in text for f in fields), sorted(f for f in fields if f"`{f}`" not in text)
    assert "`schemas/review-digest.schema.json`" in text


def test_the_carryover_names_every_carryover_field():
    schema = _schema("review-carryover.schema.json")
    note = schema["properties"]["notes"]["items"]["required"]
    item = schema["properties"]["items"]["items"]["required"]
    types = schema["properties"]["items"]["items"]["properties"]["type"]["enum"]
    text = _text("review-carryover")
    for f in set(schema["required"]) | set(note) | set(item) | set(types):
        assert f"`{f}`" in text, f
    assert "`schemas/review-carryover.schema.json`" in text


def test_the_proposer_names_every_proposals_field_and_carried_value():
    schema = _schema("review-proposals.schema.json")
    defs = schema["$defs"]
    names = set(schema["required"]) | {"sections", "key", "items", "text", "sources", "mark"}
    names |= set(defs["items"]["items"]["properties"]) | set(schema["properties"]["groups"]["properties"])
    names |= set(defs["carried"]["enum"]) | set(defs["sectionItem"]["properties"]["mark"]["enum"])
    text = _text("review-proposer")
    missing = sorted(n for n in names if f"`{n}`" not in text and f'"{n}"' not in text)   # a field or a JSON key
    assert not missing, missing
    assert "`schemas/review-proposals.schema.json`" in text


# ── prose pins: one rule each, its own line, exactly once ───────────────────

_COMMON = [
    ("out-path", "Write exactly one file: `out`, once."),
    ("stage-only", "Every path in the prompt is relative to `tomo-tmp/review/<stem>/`; read and write only there."),
    ("never-kado", "Use only Read and Write; never call Kado or any other tool, never read the vault;"),
    ("one-line-reply", "Reply with exactly one line and nothing else:"),
    ("reply-not-written", "| `<out> not written: <reason word>` | nothing was written;"),
    ("no-note-text-in-reply", "Never put note text in your reply."),
    ("input-missing", "| A listed file cannot be read | Write nothing; reply `<out> not written: input-missing` |"),
]

PINS = [(a, label, phrase) for a in AGENTS for label, phrase in _COMMON] + [
    # review-digester
    ("review-digester", "every-day-file", "Read every file of `day_files`, one Read call per file; skip no day."),
    ("review-digester", "growth-and-weekly",
     "Read every file of `growth_files` and the `weekly_note` when it is not null, one Read call per file."),
    ("review-digester", "sections-context", "`sections` true → read `context.json` for its `sections` entries."),
    ("review-digester", "days-exactly", "`days` is exactly the prompt's `days` list."),
    ("review-digester", "daily-sources",
     "Each source is a path from the `dailies` list of a day file of this unit; never a linked note."),
    ("review-digester", "single-day-theme", "keep a matter that shows on one day only."),
    ("review-digester", "weekly-child-notes", "each source the weekly note's `path`; no `weekly_note` → `[]`."),
    ("review-digester", "growth-notes", "`notes` the `path` values of their `created` entries (1 to 10)"),
    ("review-digester", "growth-creation-day",
     "`sources` the `dailies` path of the day file whose `date` equals the growth file's `date`"),
    ("review-digester", "no-judgement", "Record what the days say; never rank, judge or drop a finding"),
    ("review-digester", "language", "Write every `text` in `language`, one short statement each."),
    ("review-digester", "cap", "Keep the file within `cap_bytes` bytes and the schema's item limits"),
    # review-carryover
    ("review-carryover", "every-previous-file", "Read every file of `previous_files`, one Read call per file."),
    ("review-carryover", "user-text-and-tomo-blocks",
     "the user's own sections and Tomo's blocks alike. No marker decides what counts;"),
    ("review-carryover", "as-it-stands", "never add what an earlier proposal may have said."),
    ("review-carryover", "notes-copied", "`path`, `kind` and `name` copied from the file"),
    ("review-carryover", "types",
     "`type` `open` for an open item, `intention` for an intention or goal, `theme` for a recurring theme"),
    ("review-carryover", "stems", "`sources` the stems of the notes it comes from"),
    ("review-carryover", "both-notes-one-item", "The same matter in both notes is one item with both stems in `sources`."),
    ("review-carryover", "language", "Write every `text` in `language`, as the matter stands in the note"),
    ("review-carryover", "cap", "Keep the file within `cap_bytes` bytes and at most 30 items"),
    # review-proposer: inputs and shape
    ("review-proposer", "inputs-in-order", "Read every file of `inputs` in the listed order, one Read call per file."),
    ("review-proposer", "never-manifest",
     "never read `manifest.json`, a file under `days/` or a file under `growth/`."),
    ("review-proposer", "shape",
     '{"language": "<language>", "groups": {"done": [{"text": "<proposal>", "sources": ["<source from the inputs>"]}]'),
    # review-proposer: the proposal rules
    ("review-proposer", "review-language",
     "Every item is in `<language>`, also an item drawn from material in another language and every carried item."),
    ("review-proposer", "daily-source",
     "at least one a daily of the period (for `weekly_only` a weekly note of the period, for `monthly_only` a "
     "monthly note)"),
    ("review-proposer", "continuation-line", "A second line of `text` becomes a continuation line of the item."),
    ("review-proposer", "groups", "`done`: what happened and got done; `open`: what stayed open;"),
    ("review-proposer", "quarter-marks",
     "a section item carries `\"mark\": \"monthly_only\"` or `\"mark\": \"not_in_monthly\"` as a month's carries "
     "its marks."),
    ("review-proposer", "themes-over-the-period",
     "Count a theme over all days of the period: a matter found on at least two days, in one digest or in several, "
     "is a theme;"),
    ("review-proposer", "open-against-later-weeks",
     "Judge open against the whole period: a matter open on one day and done on a later day, in the same or a "
     "later week, is done, not open."),
    ("review-proposer", "one-item-across-weeks",
     "A finding that several digests hold is one item whose sources are the sources of every digest that holds it."),
    ("review-proposer", "child-marks-over-the-period",
     "Compare the child notes with all days of the period for `weekly_only`, `not_in_weekly`, `monthly_only` and "
     "`not_in_monthly`, never with the days of one week."),
    ("review-proposer", "growth-from-digests-and-context",
     "Build `growth` from the digests' `growth` candidates and from the `growth` counts and MOC lists of "
     "`context.json`:"),
    ("review-proposer", "growth-creation-days", "give it the candidates' `sources`, their creation days."),
    ("review-proposer", "habits", "Habits are computed by the script: never propose them."),
    ("review-proposer", "own-sections",
     "Never propose text for the user's own sections other than the `sections` of `context.json`."),
    # review-proposer: the section rules (spec 046)
    ("review-proposer", "sections-beside-groups",
     "beside `groups`: one entry per `sections` entry with something to propose, its `key` copied; no other key."),
    ("review-proposer", "section-description",
     "A section's items are what its `description` and `keywords` ask for in the period's material, whatever group "
     "they would fit."),
    ("review-proposer", "reminders",
     "Each is a reminder of what happened or will need to happen, with its sources; never finished review text, "
     "never a judgement."),
    ("review-proposer", "cap-merge", "At most `cap` items: merge findings that say the same, keeping the sources of each."),
    ("review-proposer", "groups-starting-point",
     "A section whose `groups` names groups starts from what those groups would hold; such a finding goes into the "
     "section, not into the group."),
    ("review-proposer", "one-place",
     "Each finding goes in one place: the section it fits best, else its group; never in a second section or a "
     "group as well."),
    ("review-proposer", "analysis-overview",
     "A `sections` entry with `analysis` true → items that sum up what the period's values for it show, each an "
     "overview, never one item per day."),
    ("review-proposer", "month-marks",
     "Month: a section item that only the weekly notes hold, or that they left out, carries `\"mark\": "
     "\"weekly_only\"` or `\"mark\": \"not_in_weekly\"`; its sources as for that group."),
    # review-proposer: the carried rules (Feature 4)
    ("review-proposer", "carried-false", "`carried` false → no item carries `carried` or `carried_ids`."),
    ("review-proposer", "every-id-once",
     "name every `id` of `carryover.json` exactly once over the whole file, in the `carried_ids` of one item; one "
     "item may list several ids."),
    ("review-proposer", "marks",
     "Mark an `open` or `intention` item `done` when a day of the period shows it done, `still_open` when a day "
     "shows it still open or only partly done, `not_mentioned` when no day of the period mentions it."),
    ("review-proposer", "theme-never-done",
     "Mark a carried `theme` item `still_open` when a day of the period shows it again and `not_mentioned` when "
     "none does; never mark a theme `done`."),
    ("review-proposer", "carried-placement",
     "Place a carried item in the mapped section whose `description` it fits best; without one, in the group of "
     "its mark: `done` in `done`, `still_open` and `not_mentioned` in `open`, a carried theme in `themes`."),
    ("review-proposer", "never-off-limits",
     "Never place a carried item under an off-limits heading: when the best fit is off limits, place it in the "
     "next fitting section, else in the group of its mark."),
    ("review-proposer", "one-carried-item",
     "A carried item the days also hold is ONE item with its carried mark, whose sources are the previous note and "
     "those days; it appears nowhere else in the file."),
    ("review-proposer", "same-mark-merge",
     "Merge carried items of the same mark that say the same into one item, keeping every source and every id; "
     "never merge carried items of different marks."),
    ("review-proposer", "carried-again-no-age",
     "is carried again with the same mark; never count its age and never add text about how long it has been open."),
    ("review-proposer", "carried-sources",
     "A carried item's sources are the previous notes among the `sources` of its `carried_ids`, plus for `done` and "
     "`still_open` the days that show it; a `not_mentioned` item names no day."),
    ("review-proposer", "carried-mark-conflict",
     "A carried section item carries no `mark` other than `not_in_weekly` or `not_in_monthly`, and none with "
     "`not_mentioned`."),
]

REWRITE_LINE = ("Fix each `errors` entry in the item or entry its pointer names: `unknown-section` or "
                "`duplicate-section` → each `context.json` key once, no other; `over-cap (<key>)` → merge that "
                "section's items down to its `cap`; `double-placement` → remove that item; `mark-not-allowed` → "
                "drop its `mark`; a `carried-` error → fix that item's `carried`, `carried_ids` or sources by the "
                "Carried rules.")
PINS.append(("review-proposer", "rewrite", REWRITE_LINE))


@pytest.mark.parametrize("agent,label,phrase", PINS, ids=[f"{a}-{lab}" for a, lab, _p in PINS])
def test_pin(agent, label, phrase):
    found = _count(agent, phrase)
    assert found == 1, f"{agent}.md: {label} must match exactly once, matched {found}"


def test_pin_labels_are_unique_per_agent():
    keys = [(a, lab) for a, lab, _p in PINS]
    assert len(keys) == len(set(keys))


# ── ties of the re-created step-5 pins to the scripts ───────────────────────


def test_the_groups_field_is_the_one_review_read_writes():
    """With `groups-starting-point`: the field the rule reads is a definition field of review-read.py."""
    assert "groups" in load_script("review-read.py").DEFINITION_FIELDS


def test_the_analysis_flag_is_the_one_review_read_writes():
    """With `analysis-overview`: review-read.py marks a `placement: review` row `analysis: true`."""
    mod = load_script("review-read.py")
    rows = [{"id": "s1", "heading": "A", "level": 2, "parent": None, "description": "d", "keywords": [],
             "groups": [], "cap": 3, "placement": "end"},
            {"id": "s2", "heading": "B", "level": 2, "parent": None, "description": "d", "keywords": [],
             "groups": [], "cap": 3, "placement": "review"}]
    defs = mod.section_definitions(SimpleNamespace(sections=rows))
    assert "analysis" not in defs[0] and defs[1]["analysis"] is True


def test_the_rewrite_names_a_fix_for_every_section_error_and_the_carried_errors():
    load_script("review-doc.py")
    from lib import review_carried as rc
    from lib import review_sections as rs

    errors = {rs.UNKNOWN_SECTION, rs.DUPLICATE_SECTION, rs.OVER_CAP, rs.MARK_NOT_ALLOWED, rs.DOUBLE_PLACEMENT}
    assert all(f"`{e}" in REWRITE_LINE for e in errors)
    carried = [v for k, v in vars(rc).items() if k.isupper() and isinstance(v, str) and v.startswith("carried-")]
    assert carried and all(e.startswith("carried-") for e in carried)
    assert "a `carried-` error" in REWRITE_LINE


def test_the_rewrite_runs_only_with_errors():
    text = _flat(_text("review-proposer"))
    assert "| The prompt carries `errors` | Activities 1–5, applying the Rewrite rules in Activity 3 as well |" in text


def test_the_proposer_groups_line_comes_before_the_quarter_line():
    text = _flat(_text("review-proposer"))
    assert text.index("`done`: what happened and got done;") < text.index("Quarter (when `inputs` lists monthly notes)")


def test_plan_hands_the_proposer_its_carried_flag():
    """With `carried-false`: the flag the rule branches on is `plan`'s and `check`'s `proposer.carried`."""
    source = DIGEST_SCRIPT.read_text(encoding="utf-8")
    body = source[source.index("def _proposer("):source.index("# ---", source.index("def _proposer("))]
    assert '"carried": carried' in body
    assert "MANIFEST" not in body and "DAYS" not in body and "GROWTH" not in body
