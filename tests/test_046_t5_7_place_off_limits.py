#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t5_7_place_off_limits.py — the "Tomo Review" place landing off limits has its own skill line
(spec 046 T5.7 drift check; PRD Rule 4; SDD Error Handling, `landing-off-limits`).

`landing-off-limits` is also a plan-level problem: `lib/review_actions._insertion` (the place of a new "Tomo Review")
and `_existing_note` (`review_off_limits`, where an earlier one sits) append it with no `sections[]` entry carrying a
`stop`. The step 7 stop bullet speaks per entry of `sections` with a `stop`, so without its own line the user is told
nothing. What each test falsifies:

- the script's output in that case — `problems` `["landing-off-limits"]`, no `stop` in `sections`, `place` with
  `anchor` — so the line names only real fields (`test_the_place_landing_off_limits_carries_no_section_stop`);
- the skill line, its wording, and its standing before the stop bullet, which also matches `landing-off-limits`
  (`test_the_skill_says_the_tomo_review_place_lands_off_limits_before_the_stop_bullet`).

All data is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))

from review_deliver_helpers import ins  # noqa: E402,F401 — fixture
from review_skill_helpers import _section  # noqa: E402
from test_046_t4_2_doc_sections import TEMPLATE, inst, script  # noqa: E402,F401 — fixtures
from test_046_t5_5_delivery_choices import NOTE, STEM, approved, cli, writes  # noqa: E402
from test_046_t5_6_skill_choices import STOPS_HEAD  # noqa: E402

__all__ = ["ins", "inst", "script"]

PRIVATE = NOTE.replace("## In my own words", "## Private\nx\n\n## In my own words")   # the place: before it
PLACE_LINE = ("- `landing-off-limits` with no entry of `sections` carrying a `stop` → say that the \"Tomo Review\" "
              "section, placed at `place.anchor`, would land in an off-limits section, that the place is changed "
              "with `/review setup`, and that nothing is delivered; stop.")


def _off_limits_private(inst: Path) -> None:
    path = inst / "config" / "vault-config.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["review"]["weekly"]["off_limits"] = {TEMPLATE: [
        {"heading": "Private", "level": 2, "parent": None, "occurrence": 1, "with_subsections": False}]}
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")


def test_the_place_landing_off_limits_carries_no_section_stop(script, inst, ins, monkeypatch, capsys):
    _off_limits_private(inst)
    fake = approved(script, inst, monkeypatch, capsys, note=PRIVATE)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM)
    assert out["status"] == "ok" and out["problems"] == ["landing-off-limits"], out
    assert out["sections"] and not any("stop" in s for s in out["sections"]), out["sections"]
    assert out["place"] == {"anchor": "In my own words", "placement": "before"}
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "deliver", "--stem", STEM)
    assert out["status"] == "refused" and out["problems"] == ["landing-off-limits"], out
    assert writes(fake) == []


def test_the_skill_says_the_tomo_review_place_lands_off_limits_before_the_stop_bullet():
    text = _section("7. Preview")
    assert text.count(PLACE_LINE) == 1
    assert text.index(PLACE_LINE) < text.index(STOPS_HEAD), "the stop bullet matches landing-off-limits too"
