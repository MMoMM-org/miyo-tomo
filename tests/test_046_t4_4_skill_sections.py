#!/usr/bin/env python3
# version: 0.1.2
"""test_046_t4_4_skill_sections.py — the periodic-review skill proposes by section (spec 046 T4.4).

What each section receives is model behaviour (PRD F1-AC2, the model part of
F1-AC3); this file proves that each step names it and that the names the skill
branches on are the scripts' own:
- counts per section in the report, by the configured heading
- `sections-changed` reads the period again, once
(Spec 047 T6.3 retired the step-5 proposal pins of this file; the section rules and the
rewrite's error-to-fix line are pinned against review-proposer.md in tests/test_047_agents.py.)
- the `section-checkbox-missing` stop: step 6 names the section by the
  configured heading of its `key` and gives `restore` (the keys of
  `SectionProblem.public()`), then stops; step 7 runs `parse` for it
"""
from __future__ import annotations

from review_cli_contract import load_script
from review_skill_helpers import _section

STEP5 = "5. Propose and write the document"
STEP6 = "6. Continue an open review"
STEP7 = "7. Preview"


def test_a_section_is_named_by_the_configured_heading_of_its_key():
    text = _section(STEP5)
    assert ("`<section heading>` of a key is the `heading` of the row with that `id` under "
            "`review.<weekly|monthly|quarterly>.sections` (the kind's) in the same file.") in text
    assert "`review.language` in `config/vault-config.yaml`; Read it. `<section heading>` of a key" in text
    assert "`counts` per group and per section (by `<section heading>`)" in text
    load_script("review-doc.py")
    from lib.review_config import GRANULARITY  # the scripts put tomo/scripts on sys.path

    assert "|".join(GRANULARITY.values()) == "weekly|monthly|quarterly"


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
