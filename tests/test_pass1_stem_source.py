"""The Pass 1 document stem comes from the container clock, not from the model.

A live run derived `2026-11-02_1919` from earlier filenames and "a UTC+1 local
clock". The skills named only the placeholder, so nothing told the model where
the time comes from.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parent.parent / "tomo" / "dot_claude" / "skills"
CALL = "one `date +%Y-%m-%d_%H%M` call"


@pytest.mark.parametrize("skill", ["suggest-handling", "force-atomic-handling"])
def test_stem_is_read_from_the_clock_before_the_writes(skill):
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    assert text.count(CALL) == 1
    first_write = text.index("python3 scripts/kado-write-file.py")
    section = text[text.rindex("### ", 0, first_write) : first_write]
    assert CALL in section
    assert "`<YYYY-MM-DD_HHMM>` stem, the output of" in section
