"""Tests for tomo/scripts/lib/moc_structure.py — T1.1 (spec 022, Phase 1).

Verifies pure MOC-structure parsing: heading discovery before footer,
editable-callout scanning against a caller-supplied set, and footer
boundary detection. No IO, no Kado, no external dependencies.
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "tomo" / "scripts"))

from lib.moc_structure import footer_index, parse_headings, parse_editable_callouts

# ---------------------------------------------------------------------------
# Shared fixture — mirrors Atlas/200 Maps/Systems Thinking (MOC).md shape
# ---------------------------------------------------------------------------
#
# Structure:
#   H1 title
#   editable callout: [!blocks] Key Concepts
#   ## H2 content section
#   ### H3 sub-section
#   another ### H3
#   footer callout: [!video] Action Items
#   footer callout: [!calendar]- Recent Updates
#
FIXTURE_BODY = """\
# Systems Thinking (MOC)

> [!connect]- Navigation
> up:: [[200 Maps]]

> [!blocks] Key Concepts

## Core Concepts
### Feedback Loops
#### Reinforcing vs Balancing
### Emergence

## Applications

> [!video] Action Items

> [!calendar]- Recent Updates
"""

FOOTER_SET = {"video", "calendar", "puzzle", "compass"}
EDITABLE_SET = {"blocks", "connect", "other"}


class TestFooterIndex:
    def test_detects_first_footer_callout(self):
        lines = FIXTURE_BODY.splitlines()
        idx = footer_index(lines, FOOTER_SET)
        # "[!video] Action Items" line should be before "[!calendar]- Recent Updates"
        assert 0 < idx < len(lines)
        video_line = lines[idx].rstrip()
        assert "video" in video_line.lower()

    def test_returns_len_when_no_footer(self):
        body = "# Title\n\n## Section\n\nSome content\n"
        lines = body.splitlines()
        assert footer_index(lines, FOOTER_SET) == len(lines)

    def test_empty_body(self):
        lines: list[str] = []
        assert footer_index(lines, FOOTER_SET) == 0

    def test_footer_at_first_line(self):
        body = "> [!video] Action Items\n## After\n"
        lines = body.splitlines()
        assert footer_index(lines, FOOTER_SET) == 0

    def test_custom_footer_set(self):
        body = "## Heading\n> [!custom_footer] Marker\n### Sub\n"
        lines = body.splitlines()
        assert footer_index(lines, {"custom_footer"}) == 1
        # Default FOOTER_SET does not match — no footer found
        assert footer_index(lines, FOOTER_SET) == len(lines)


class TestParseHeadings:
    def test_returns_headings_before_footer(self):
        headings = parse_headings(FIXTURE_BODY, FOOTER_SET)
        texts = [h["text"] for h in headings]
        assert "Core Concepts" in texts
        assert "Feedback Loops" in texts
        assert "Emergence" in texts
        assert "Applications" in texts

    def test_excludes_h1(self):
        headings = parse_headings(FIXTURE_BODY, FOOTER_SET)
        texts = [h["text"] for h in headings]
        assert "Systems Thinking (MOC)" not in texts

    def test_levels_are_correct(self):
        headings = parse_headings(FIXTURE_BODY, FOOTER_SET)
        by_text = {h["text"]: h["level"] for h in headings}
        assert by_text["Core Concepts"] == 2
        assert by_text["Applications"] == 2
        assert by_text["Feedback Loops"] == 3
        assert by_text["Emergence"] == 3
        # H4 in scope — proves regex caps at H6, not H3
        assert by_text["Reinforcing vs Balancing"] == 4

    def test_order_preserved(self):
        headings = parse_headings(FIXTURE_BODY, FOOTER_SET)
        texts = [h["text"] for h in headings]
        assert texts.index("Core Concepts") < texts.index("Feedback Loops")
        assert texts.index("Feedback Loops") < texts.index("Applications")

    def test_empty_body_returns_empty_list(self):
        assert parse_headings("", FOOTER_SET) == []

    def test_no_headings_below_h1(self):
        body = "# Title Only\n\nJust prose.\n"
        assert parse_headings(body, FOOTER_SET) == []

    def test_headings_after_footer_excluded(self):
        body = "## Before Footer\n> [!video] Footer\n## After Footer\n"
        headings = parse_headings(body, FOOTER_SET)
        texts = [h["text"] for h in headings]
        assert "Before Footer" in texts
        assert "After Footer" not in texts

    def test_returns_dict_with_text_and_level_keys(self):
        headings = parse_headings(FIXTURE_BODY, FOOTER_SET)
        assert len(headings) > 0
        for h in headings:
            assert "text" in h
            assert "level" in h
            assert isinstance(h["text"], str)
            assert isinstance(h["level"], int)


class TestParseEditableCallouts:
    def test_returns_matching_callout_lines(self):
        result = parse_editable_callouts(FIXTURE_BODY, EDITABLE_SET)
        # [!blocks] and [!connect] are both in EDITABLE_SET
        assert any("blocks" in line.lower() for line in result)
        assert any("connect" in line.lower() for line in result)

    def test_respects_editable_set_filter(self):
        # Only ask for "blocks" — connect should be excluded
        result = parse_editable_callouts(FIXTURE_BODY, {"blocks"})
        assert len(result) == 1
        assert "blocks" in result[0].lower()

    def test_excludes_footer_callouts_not_in_editable_set(self):
        # "video" and "calendar" callouts are NOT in EDITABLE_SET
        result = parse_editable_callouts(FIXTURE_BODY, EDITABLE_SET)
        assert not any("video" in line.lower() for line in result)
        assert not any("calendar" in line.lower() for line in result)

    def test_empty_body_returns_empty(self):
        assert parse_editable_callouts("", EDITABLE_SET) == []

    def test_no_callouts_returns_empty(self):
        body = "# Title\n\n## Section\n\nProse only.\n"
        assert parse_editable_callouts(body, EDITABLE_SET) == []

    def test_returned_lines_strip_leading_gt(self):
        result = parse_editable_callouts(FIXTURE_BODY, {"blocks"})
        assert len(result) == 1
        # Must NOT start with "> "
        assert not result[0].startswith(">")
        assert result[0].startswith("[!")

    def test_order_preserved(self):
        body = "> [!other] Section A\n> [!blocks] Section B\n"
        result = parse_editable_callouts(body, {"other", "blocks"})
        assert result[0].startswith("[!other]")
        assert result[1].startswith("[!blocks]")

    def test_empty_editable_set_returns_empty(self):
        result = parse_editable_callouts(FIXTURE_BODY, set())
        assert result == []

    def test_scans_whole_body_including_after_footer(self):
        # Pins the documented whole-body-scan contract: parse_editable_callouts
        # is NOT bounded by the footer. A callout that the caller marks editable
        # is returned even when it sits after the footer boundary — both future
        # consumers (moc-tree-builder, instruction-render) rely on this for
        # template bodies that have no footer.
        body = (
            "## Section\n"
            "> [!calendar]- Recent Updates\n"  # footer marker → footer boundary here
            "> [!video] Action Items\n"        # after footer, but editable_set asks for it
        )
        result = parse_editable_callouts(body, {"video"})
        assert len(result) == 1
        assert result[0].startswith("[!video]")
