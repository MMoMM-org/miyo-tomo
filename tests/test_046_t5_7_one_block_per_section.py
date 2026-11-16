#!/usr/bin/env python3
# version: 0.1.0
"""test_046_t5_7_one_block_per_section.py — a re-run never offers `review` beside Tomo's intact earlier block
(spec 046 T5.7 drift check, owner decision; PRD Rule 8, F5-AC5 "one block per section").

On the mapped T4.2 week through `review-instructions.py` against the guarded fake (helpers of
tests/test_046_t5_5_delivery_choices.py). The note holds s4's intact block of the period while the mapped
heading "Notes" was renamed (`section-missing`) or stands twice (`section-ambiguous`). What a mutation falsifies:
`plan_section` dropping `review` from the step 5 stops when a pair exists — without it the preview offers
`review` and `--section-choice s4=review` delivers the items into "Tomo Review" beside the earlier block.

All data is synthetic.
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))

from review_deliver_helpers import ins  # noqa: E402,F401 — fixture
from test_046_t4_2_doc_sections import inst, script  # noqa: E402,F401 — fixtures
from test_046_t5_5_delivery_choices import NOTE, S4_BLOCK, STEM, approved, by_key, cli, writes  # noqa: E402

__all__ = ["ins", "inst", "script"]

RENAMED = NOTE.replace("## Notes\nnote text\n", f"## Notes renamed\n{S4_BLOCK}note text\n")
TWICE = NOTE.replace("## Notes\nnote text\n", f"## Notes\n{S4_BLOCK}note text\n\n## Notes\nzweite\n")


def test_a_renamed_heading_beside_an_intact_block_offers_skip_and_confirm_moved(script, inst, ins, monkeypatch,
                                                                                capsys):
    fake = approved(script, inst, monkeypatch, capsys, note=RENAMED)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM)
    assert out["problems"] == ["section-missing"], out
    assert by_key(out)["s4"]["choices"] == ["skip", "confirm-moved"]
    before = dict(fake.files)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "deliver", "--stem", STEM, "--section-choice", "s4=review")
    assert out["status"] == "refused" and "choice-invalid" in out["problems"], out
    assert out["choices_invalid"] == ["s4"]
    assert writes(fake) == [] and fake.files == before, "no second copy of s4 for the period"


def test_an_ambiguous_heading_beside_an_intact_block_offers_skip_only(script, inst, ins, monkeypatch, capsys):
    fake = approved(script, inst, monkeypatch, capsys, note=TWICE)
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "preview", "--stem", STEM)
    assert out["problems"] == ["section-ambiguous"], out
    assert by_key(out)["s4"]["choices"] == ["skip"]
    _, out, _ = cli(ins, monkeypatch, capsys, fake, "deliver", "--stem", STEM, "--section-choice", "s4=review")
    assert out["status"] == "refused" and out["choices_invalid"] == ["s4"], out
    assert writes(fake) == []
