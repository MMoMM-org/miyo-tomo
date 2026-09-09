#!/usr/bin/env python3
# version: 0.1.0
"""test_pass2_flat_instruction_golden.py — the Pass-2 no-regression baseline.

WHAT THIS GUARDS: every future change to the Pass-2 chain —
`suggestion-parser.py` then `instruction-render.py` and the `lib/render_*.py`
modules under them — measured against a recording of that chain at `ee44cb3`.

It was recorded for spec 034 T6.2, and its fixture lives under
`tests/fixtures/034-t6-2-instructions-golden/` for that reason. The name of
this file deliberately does NOT carry that task: recursive discovery is the
occasion for the baseline, not its subject. Someone changing how an
instruction document is assembled a year from now needs to find this, and
would not think to look in a file named for a spec-034 phase gate.

The fixture is its own flat inbox — three plain root-level notes, no name
collisions, no attachments — driven through the real chain by
`fixtures/034-t6-2-instructions-golden/record.py`. See the README beside it for
the baseline's provenance and the reason `git worktree` rather than `git show`.

WHY THIS IS NOT A BYTE-COMPARE, and what that costs. One change in spec 034
deliberately alters a flat inbox's instruction document: T5.5 (`e3aefec`)
replaced a delete-source heading that named one of five possible causes — and
contradicted the Action line beneath it for the other four. Re-recording the
golden at HEAD would have absorbed that change and destroyed the evidence, so
the golden stays the OLD document and `DELIBERATE_DELTAS` names the deviation.

Each delta DERIVES the line it expects from the golden's own content rather
than matching its shape, so a regression that mangles the note name fails here
rather than slipping through a permissive `.+`. What the mechanism still
cannot do is tell "this line changed for a reason we reviewed" from "someone
added a delta to make the test pass" — only the pinned count and code review
separate those, and a diff that touches this list is the review.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
GOLDEN_DIR = TESTS_DIR / "fixtures" / "034-t6-2-instructions-golden"

sys.path.insert(0, str(SCRIPTS_DIR))

RE_OLD_DELETE_HEADING = re.compile(
    r"^(### I\d+ — Delete source note) \(content captured in daily note\)$"
)
# `[[stem]]` or the path-qualified `[[path|stem]]` T5.1 renders on collision.
RE_SOURCE_LINE = re.compile(r"^- \*\*Source:\*\* \[\[(?:[^\]|]*\|)?([^\]|]+)\]\]$")


def _t5_5_delete_heading(old_line: str, golden: list[str], index: int) -> str | None:
    """The exact heading T5.5 replaces `old_line` with, or None if this is not
    that delta.

    The new heading names the note, and the note is already named two lines
    below by the `- **Source:**` line — which this delta does not touch. So the
    expectation is derived from the golden itself and no stem is hardcoded:
    a run that renamed the note in the heading, or named a different note
    there, produces a line this does not return.
    """
    match = RE_OLD_DELETE_HEADING.match(old_line)
    if not match:
        return None
    try:
        source_line = golden[index + 2]
    except IndexError:
        return None
    source = RE_SOURCE_LINE.match(source_line)
    if not source:
        return None
    return f"{match.group(1)}: {source.group(1)}"


# Every line on which today's Pass 2 differs from `ee44cb3`'s for this fixture,
# each attributed. Anything diverging that no entry here reproduces EXACTLY
# fails, and re-recording the golden would destroy the evidence.
DELIBERATE_DELTAS = (
    (_t5_5_delete_heading,
     "T5.5 (e3aefec): the old heading stated ONE of the five causes "
     "`delete_source` is emitted for, and contradicted the Action line "
     "beneath it for the other four. The heading now names the note."),
)


def _load(module_name: str, filename: str, directory: Path):
    spec = importlib.util.spec_from_file_location(module_name, directory / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestFlatInboxInstructionGolden:
    @pytest.fixture(scope="class")
    def record(self):
        return _load("pass2_golden_record", "record.py", GOLDEN_DIR)

    @pytest.fixture(scope="class")
    def replayed(self, record, tmp_path_factory) -> str:
        return record.normalise(
            record.run_pass2(SCRIPTS_DIR, tmp_path_factory.mktemp("pass2_golden"))
        )

    @pytest.fixture(scope="class")
    def golden(self) -> str:
        return (GOLDEN_DIR / "instructions.md").read_text(encoding="utf-8")

    def _differing(self, golden: str, replayed: str) -> list[tuple[int, str, str]]:
        old_lines, new_lines = golden.splitlines(), replayed.splitlines()
        assert len(old_lines) == len(new_lines), (
            f"the instruction document changed length: {len(old_lines)} lines at "
            f"ee44cb3, {len(new_lines)} today — an action was added or dropped"
        )
        return [(i, a, b) for i, (a, b) in enumerate(zip(old_lines, new_lines))
                if a != b]

    def test_todays_pass_2_differs_only_where_this_spec_meant_it_to(
        self, golden, replayed,
    ):
        lines = golden.splitlines()
        for index, old, new in self._differing(golden, replayed):
            assert any(
                build(old, lines, index) == new
                for build, _why in DELIBERATE_DELTAS
            ), (
                "the flat-inbox instruction set changed in a way this spec did "
                "not intend — a Pass-2 change must not alter what is instructed "
                f"for a flat inbox.\n  ee44cb3: {old!r}\n  today:   {new!r}"
            )

    def test_exactly_the_three_delete_headings_moved(self, golden, replayed):
        """One per `delete_source` action in this fixture. Pinning the count
        stops a fourth, unrelated divergence from hiding behind a delta that
        happens to reproduce it."""
        assert len(self._differing(golden, replayed)) == 3

    def test_a_mangled_note_name_would_not_pass_the_delta(self, golden):
        """The delta is content-anchored, not shape-matched. Proven here rather
        than asserted: a heading naming the wrong note is not reproduced."""
        lines = golden.splitlines()
        index, old, _new = self._differing(
            golden, golden.replace(
                "### I07 — Delete source note (content captured in daily note)",
                "### I07 — Delete source note: !!!WRONG!!!", 1,
            ),
        )[0]
        assert _t5_5_delete_heading(old, lines, index) == (
            "### I07 — Delete source note: Dresden"
        )
        assert _t5_5_delete_heading(old, lines, index) != (
            "### I07 — Delete source note: !!!WRONG!!!"
        )

    def test_the_golden_is_not_trivially_empty(self, golden):
        """A normaliser that ate the document would make the comparison
        vacuous. Pin the parts that carry the pipeline's actual output."""
        assert "action_count: 9" in golden
        assert golden.count("- [ ] Applied") == 9
        assert "## New Files" in golden and "## MOC Links" in golden

    def test_only_render_time_stamps_were_normalised(self, replayed):
        """Every placeholder stands for a value minted at render time. If a
        future renderer moves real content onto one of these, this fails."""
        for line in replayed.splitlines():
            if "<NORMALISED>" in line:
                assert line in ("generated: <NORMALISED>",
                                "  updated_at: '<NORMALISED>'"), line
            if "<STAMP>" in line:
                assert "<STAMP>_" in line, line

    def test_the_fixture_covers_three_of_the_renderers_action_kinds(self):
        """The baseline's known reach, asserted rather than assumed.

        A flat inbox with no attachments and no daily updates renders three of
        the roughly fifteen kinds `lib/render_md.py` emits. A Pass-2 change to
        a section this fixture never produces ships unpinned by this file. That
        is a recorded limit, not a defect — widening the fixture is a separate,
        deliberate act, and this assertion is what makes the widening visible.
        """
        golden = (GOLDEN_DIR / "instructions.md").read_text(encoding="utf-8")
        assert sorted({
            heading for heading in ("Move note", "Add link to", "Delete source note")
            if heading in golden
        }) == ["Add link to", "Delete source note", "Move note"]
        for absent in ("Move attachment", "Create MOC", "Insert under",
                       "Add log link", "Skip — "):
            assert absent not in golden, (
                f"the fixture grew a {absent!r} section — update this test and "
                "the README's statement of what the baseline reaches"
            )
