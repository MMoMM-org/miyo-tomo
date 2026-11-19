#!/usr/bin/env python3
# version: 0.1.1
"""test_046_t4_4_skill_sections.py — the periodic-review skill proposes by section (spec 046 T4.4).

What each section receives is model behaviour (PRD F1-AC2, the model part of
F1-AC3); this file proves that each rule has its imperative in step 5 and
that the names the skill branches on are the scripts' own:
- items per `read.json` `sections` entry, the key copied, from its
  description and keywords; reminders, never finished text; at most `cap`,
  merged with the sources kept; one place per item, the rest in the groups;
  analysis rows (`analysis` true, as `review-read.py` marks them) as overviews;
  the month marks; counts per section in the report, by the configured heading
- the rewrite-once loop names a fix for every section error of
  `lib/review_sections`; `sections-changed` reads the period again, once
- the `section-checkbox-missing` stop: step 6 names the section by the
  configured heading of its `key` and gives `restore` (the keys of
  `SectionProblem.public()`), then stops; step 7 runs `parse` for it
"""
from __future__ import annotations

from types import SimpleNamespace

from review_cli_contract import load_script
from review_skill_helpers import _section

STEP5 = "5. Propose and write the document"
STEP6 = "6. Continue an open review"
STEP7 = "7. Preview"


def test_sections_are_written_beside_the_groups_with_the_read_keys_only():
    text = _section(STEP5)
    assert ('- `read.json` holds `sections` → add `"sections": [{"key": "<key>", "items": [{"text": "<reminder>", '
            '"sources": ["<path or stem from read.json>"]}]}]` beside `groups`: one entry per `sections` entry with '
            'something to propose, its `key` copied; no other key.') in text


def test_a_section_receives_what_its_description_and_keywords_ask_for_as_reminders_within_its_cap():
    text = _section(STEP5)
    assert ("- A section's items are what its `description` and `keywords` ask for in the period's notes, whatever "
            "group they would fit.") in text
    assert ("Each is a reminder of what happened or will need to happen, with its sources; never finished review "
            "text, never a judgement.") in text
    assert "At most `cap` items: merge findings that say the same, keeping the sources of each." in text


def test_a_sections_groups_are_its_starting_point_and_the_field_is_the_one_review_read_writes():
    """F2-AC7: a mapped row's `groups` name the spec 045 groups the section starts from (046 close-out gap)."""
    assert ("- A section whose `groups` names groups starts from what those groups would hold; such a finding goes "
            "into the section, not into the group.") in _section(STEP5)
    assert "groups" in load_script("review-read.py").DEFINITION_FIELDS


def test_one_place_per_item_and_the_rest_in_the_groups():
    assert ("- Each finding goes in one place: the section it fits best, else its group; never in a second section "
            "or a group as well.") in _section(STEP5)


def test_own_sections_carve_out_the_mapped_sections():
    assert ("Never propose text for the user's own sections other than the `sections` of `read.json`."
            in _section(STEP5))


def test_analysis_rows_are_overviews_and_the_flag_is_the_one_review_read_writes():
    assert ("- A `sections` entry with `analysis` true → items that sum up what the period's values for it show, "
            "each an overview, never one item per day.") in _section(STEP5)
    mod = load_script("review-read.py")
    rows = [{"id": "s1", "heading": "A", "level": 2, "parent": None, "description": "d", "keywords": [],
             "groups": [], "cap": 3, "placement": "end"},
            {"id": "s2", "heading": "B", "level": 2, "parent": None, "description": "d", "keywords": [],
             "groups": [], "cap": 3, "placement": "review"}]
    defs = mod.section_definitions(SimpleNamespace(sections=rows))
    assert "analysis" not in defs[0] and defs[1]["analysis"] is True


def test_month_section_items_carry_the_child_note_marks():
    assert ('- Month: a section item that only the weekly notes hold, or that they left out, carries '
            '`"mark": "weekly_only"` or `"mark": "not_in_weekly"`; its sources as for that group.') in _section(STEP5)


def test_a_section_is_named_by_the_configured_heading_of_its_key():
    text = _section(STEP5)
    assert ("- `<section heading>` of a key is the `heading` of the row with that `id` under "
            "`review.<weekly|monthly|quarterly>.sections` (the kind's) in `config/vault-config.yaml`.") in text
    assert "`counts` per group and per section (by `<section heading>`)" in text
    load_script("review-doc.py")
    from lib.review_config import GRANULARITY  # the scripts put tomo/scripts on sys.path

    assert "|".join(GRANULARITY.values()) == "weekly|monthly|quarterly"


def test_the_rewrite_names_a_fix_for_every_section_error():
    load_script("review-doc.py")
    from lib import review_sections as rs

    line = ("In the rewrite, fix each `errors` entry in the item or entry its pointer names: `unknown-section` or "
            "`duplicate-section` → each `read.json` key once, no other; `over-cap (<key>)` → merge that section's "
            "items down to its `cap`; `double-placement` → remove that item; `mark-not-allowed` → drop its `mark`.")
    text = _section(STEP5)
    assert line in text
    errors = {rs.UNKNOWN_SECTION, rs.DUPLICATE_SECTION, rs.OVER_CAP, rs.MARK_NOT_ALLOWED, rs.DOUBLE_PLACEMENT}
    assert all(f"`{e}" in line for e in errors)
    assert text.index("- `refused` with `proposals-invalid`") < text.index(line) < text.index(
        "- `refused` with `doc-name-taken`")


def test_sections_changed_reads_the_period_again_once_before_the_catch_all():
    text = _section(STEP5)
    line = ("- `refused` with `sections-changed` → say the section setup changed since the read; run step 4 again, "
            "once, and continue there; a second `sections-changed` → show it and stop.")
    assert line in text
    assert text.index(line) < text.index("- `refused` with any other problem")


def test_step_6_stops_on_a_missing_section_checkbox_naming_the_section_and_the_restore_line():
    load_script("review-doc.py")
    from lib import review_doc_parse as rdp

    assert set(rdp.SectionProblem("s1", "H", "- [x] x %%s1%%").public()) == {"key", "restore"}
    text = _section(STEP6)
    line = ("- `section-checkbox-missing` → per entry of `section_problems`: the checkbox line of the section "
            "`<section heading>` (step 5) of its `key` is missing or broken; restore the line `restore`, verbatim, "
            "under that heading and run `/review` again. Stop after the warnings; nothing is delivered.")
    assert line in text
    assert text.index(line) < text.index("Then: `approved` false")


def test_step_7_runs_parse_for_the_section_stop():
    text = _section(STEP7)
    assert ("- `section-checkbox-missing` → run `python3 scripts/review-doc.py parse --stem <stem>` and say its "
            "`section-checkbox-missing` line of step 6; stop.") in text
