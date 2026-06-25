#!/usr/bin/env python3
# version: 0.1.0
"""test_target_structure.py — Tests for the target_structure pure helper.

Covers T2.1 (parse_section), T2.2 (assemble + sanitize + anchor selection),
T2.3 (Fallback signalling).

Spec: docs/XDD/specs/025-structure-aware-tag-handler-compose/
FR:   FR-16 (placement matrix), FR-18 (sanitization + positional rows),
      FR-19 (fallback), FR-21 (empty table), FR-22 (separator variants)
ADR:  ADR-3 (deterministic helper), ADR-9 (first-match parse contract),
      ADR-10 (mixed-bullet: first item's style)
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.target_structure` works

from lib.target_structure import (  # noqa: E402
    Fallback,
    assemble,
    parse_section,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TABLE_3COL = """\
| Date | Type | Description |
| --- | --- | --- |
| 2026-06-24 | feature | first row |
"""

_TABLE_3COL_EMPTY = """\
| Date | Type | Description |
| --- | --- | --- |
"""

_LIST_DASH = """\
- first item
- second item
"""

_LIST_STAR = """\
* alpha
* beta
"""

_LIST_NUMBERED = """\
1. one
2. two
"""

_PROSE_ONLY = """\
This is some prose.

No table or list here.
"""

_PROSE_THEN_TABLE = """\
Some intro prose.

More prose.

| A | B |
| --- | --- |
| x | y |
"""


# ---------------------------------------------------------------------------
# T2.1  parse_section — structure detection
# ---------------------------------------------------------------------------


class TestParseSection:
    def test_table_3col_returns_table_kind(self):
        """3-col table → kind=table, columns=3, header+separator captured."""
        result = parse_section(_TABLE_3COL.splitlines(), "table_row")
        assert result.kind == "table"
        assert result.columns == 3
        assert "Date" in result.header_line
        assert "---" in result.separator_line

    def test_table_header_line_raw_bytes_preserved(self):
        """Header line must be raw bytes (not reformatted) for block anchor fidelity."""
        lines = ["| Date | Type | Description |", "| --- | --- | --- |"]
        result = parse_section(lines, "table_row")
        assert result.header_line == "| Date | Type | Description |"
        assert result.separator_line == "| --- | --- | --- |"

    def test_empty_table_parsed_ok(self):
        """FR-21: empty table (header+separator, 0 data rows) — columns from header, not fallback."""
        result = parse_section(_TABLE_3COL_EMPTY.splitlines(), "table_row")
        assert result.kind == "table"
        assert result.columns == 3

    def test_list_dash_bullet(self):
        """List starting with '-' → kind=list, bullet='-'."""
        result = parse_section(_LIST_DASH.splitlines(), "list_item")
        assert result.kind == "list"
        assert result.bullet == "-"

    def test_list_star_bullet(self):
        """List starting with '*' → kind=list, bullet='*'."""
        result = parse_section(_LIST_STAR.splitlines(), "list_item")
        assert result.kind == "list"
        assert result.bullet == "*"

    def test_list_numbered_bullet(self):
        """List starting with '1.' → kind=list, bullet='1.'."""
        result = parse_section(_LIST_NUMBERED.splitlines(), "list_item")
        assert result.kind == "list"
        assert result.bullet == "1."

    def test_prose_only_returns_none(self):
        """Prose-only section → kind=none."""
        result = parse_section(_PROSE_ONLY.splitlines(), "table_row")
        assert result.kind == "none"

    def test_prose_then_table_first_table_wins(self):
        """ADR-9: intervening prose skipped; first table match wins."""
        result = parse_section(_PROSE_THEN_TABLE.splitlines(), "table_row")
        assert result.kind == "table"
        assert result.columns == 2

    def test_separator_variant_dashes_only(self):
        """FR-22: |---| separator variant recognised."""
        lines = ["| A | B |", "|---|---|"]
        result = parse_section(lines, "table_row")
        assert result.kind == "table"
        assert result.columns == 2

    def test_separator_variant_colon_left(self):
        """FR-22: | :-- | alignment separator variant recognised."""
        lines = ["| A | B |", "| :-- | :-- |"]
        result = parse_section(lines, "table_row")
        assert result.kind == "table"

    def test_separator_variant_colon_center(self):
        """FR-22: | :-: | alignment separator variant recognised."""
        lines = ["| A | B |", "| :-: | :-: |"]
        result = parse_section(lines, "table_row")
        assert result.kind == "table"

    def test_separator_variant_colon_right(self):
        """FR-22: | --: | alignment separator variant recognised."""
        lines = ["| A | B |", "| --: | --: |"]
        result = parse_section(lines, "table_row")
        assert result.kind == "table"

    def test_table_not_found_when_looking_for_list(self):
        """Requesting list_item against a table section → kind=none (no match)."""
        result = parse_section(_TABLE_3COL.splitlines(), "list_item")
        assert result.kind == "none"

    def test_list_not_found_when_looking_for_table(self):
        """Requesting table_row against a list section → kind=none."""
        result = parse_section(_LIST_DASH.splitlines(), "table_row")
        assert result.kind == "none"

    def test_empty_section_returns_none(self):
        """Empty section → kind=none (helper accepts gracefully, no error)."""
        result = parse_section([], "table_row")
        assert result.kind == "none"

    def test_heading_stops_table_scan(self):
        """W1: heading boundary halts table scan — table AFTER heading is not found."""
        lines = ["prose", "## Next Section", "| A | B |", "| --- | --- |"]
        result = parse_section(lines, "table_row")
        assert result.kind == "none"

    def test_heading_stops_list_scan(self):
        """W1: heading boundary halts list scan — list AFTER heading is not found."""
        lines = ["prose", "## Next", "- item"]
        result = parse_section(lines, "list_item")
        assert result.kind == "none"

    def test_list_mixed_bullet_first_wins(self):
        """ADR-10: mixed-bullet list — first item's style is authoritative."""
        result = parse_section(["- first", "* second"], "list_item")
        assert result.bullet == "-"

    def test_consecutive_separator_lines_not_parsed_as_table(self):
        """S2: two separator-only lines must NOT be mistaken for header+separator.

        _TABLE_HEADER_RE matches separator lines too (both contain '|').
        The fix: header candidate is excluded when it also matches _TABLE_SEP_RE,
        so |---|---| + |---|---| stays kind=none.
        """
        lines = ["|---|---|", "|---|---|"]
        result = parse_section(lines, "table_row")
        assert result.kind == "none"


# ---------------------------------------------------------------------------
# T2.2  assemble — row/item construction + anchor selection
# ---------------------------------------------------------------------------


_FMT_TABLE_APPEND = {
    "structure": "table_row",
    "order": "append",
    "granularity": "per_item",
}

_FMT_TABLE_NEWEST = {
    "structure": "table_row",
    "order": "newest_first",
    "granularity": "per_item",
}

_FMT_LIST_APPEND = {
    "structure": "list_item",
    "order": "append",
    "granularity": "per_item",
    "join": " — ",
}

_FMT_LIST_NEWEST = {
    "structure": "list_item",
    "order": "newest_first",
    "granularity": "per_item",
    "join": " — ",
}

_SECTION_3COL = ["| Date | Type | Description |", "| --- | --- | --- |"]
_SECTION_LIST = ["- existing item"]
_MARKER = "Captures"


class TestAssembleTableAppend:
    def test_single_row_per_item(self):
        """table_row + append + per_item with 1 capture → 1 well-formed row."""
        block, anchor = assemble(_SECTION_3COL, _FMT_TABLE_APPEND, [["2026-06-25", "fix", "desc"]], _MARKER)
        assert block == "| 2026-06-25 | fix | desc |"

    def test_multi_row_per_item(self):
        """table_row + append + per_item with N captures → N rows."""
        cells = [["2026-06-25", "fix", "a"], ["2026-06-24", "feat", "b"]]
        block, anchor = assemble(_SECTION_3COL, _FMT_TABLE_APPEND, cells, _MARKER)
        rows = block.splitlines()
        assert len(rows) == 2
        assert rows[0] == "| 2026-06-25 | fix | a |"
        assert rows[1] == "| 2026-06-24 | feat | b |"

    def test_append_anchor_is_heading_inside(self):
        """table_row + append → heading anchor with placement=inside, value=marker text."""
        _, anchor = assemble(_SECTION_3COL, _FMT_TABLE_APPEND, [["a", "b", "c"]], _MARKER)
        assert anchor["type"] == "heading"
        assert anchor["placement"] == "inside"
        assert anchor["value"] == _MARKER

    def test_merged_produces_one_row(self):
        """table_row + merged → exactly one row regardless of N source captures."""
        fmt = {**_FMT_TABLE_APPEND, "granularity": "merged"}
        block, _ = assemble(_SECTION_3COL, fmt, [["x", "y", "z"]], _MARKER)
        assert len(block.splitlines()) == 1


class TestAssembleTableNewestFirst:
    def test_newest_first_anchor_is_block(self):
        """table_row + newest_first → block anchor with placement=after."""
        _, anchor = assemble(_SECTION_3COL, _FMT_TABLE_NEWEST, [["a", "b", "c"]], _MARKER)
        assert anchor["type"] == "block"
        assert anchor["placement"] == "after"

    def test_newest_first_anchor_value_is_raw_header_separator(self):
        """Block anchor value must be raw 'header_line\\nseparator_line' bytes (FR-18, byte-exact)."""
        _, anchor = assemble(_SECTION_3COL, _FMT_TABLE_NEWEST, [["a", "b", "c"]], _MARKER)
        expected = "| Date | Type | Description |\n| --- | --- | --- |"
        assert anchor["value"] == expected

    def test_newest_first_multi_row(self):
        """table_row + newest_first + N captures → N rows in the block."""
        cells = [["2026-06-25", "fix", "a"], ["2026-06-24", "feat", "b"]]
        block, _ = assemble(_SECTION_3COL, _FMT_TABLE_NEWEST, cells, _MARKER)
        assert len(block.splitlines()) == 2


class TestAssembleList:
    def test_list_append_anchor_heading_inside(self):
        """list_item + append → heading anchor, placement=inside."""
        _, anchor = assemble(_SECTION_LIST, _FMT_LIST_APPEND, [["note A", "tag B"]], _MARKER)
        assert anchor["type"] == "heading"
        assert anchor["placement"] == "inside"
        assert anchor["value"] == _MARKER

    def test_list_newest_anchor_heading_after(self):
        """list_item + newest_first → heading anchor, placement=after."""
        _, anchor = assemble(_SECTION_LIST, _FMT_LIST_NEWEST, [["note A", "tag B"]], _MARKER)
        assert anchor["type"] == "heading"
        assert anchor["placement"] == "after"

    def test_list_cells_joined_by_join(self):
        """List cells are joined with the 'join' separator."""
        block, _ = assemble(_SECTION_LIST, _FMT_LIST_APPEND, [["foo", "bar"]], _MARKER)
        assert block == "- foo — bar"

    def test_list_custom_join(self):
        """Custom join string respected."""
        fmt = {**_FMT_LIST_APPEND, "join": " | "}
        block, _ = assemble(_SECTION_LIST, fmt, [["foo", "bar"]], _MARKER)
        assert block == "- foo | bar"

    def test_list_default_join_when_absent(self):
        """join key absent → default ' — ' used."""
        fmt = {k: v for k, v in _FMT_LIST_APPEND.items() if k != "join"}
        block, _ = assemble(_SECTION_LIST, fmt, [["alpha", "beta"]], _MARKER)
        assert "alpha" in block and "beta" in block
        assert " — " in block

    def test_list_bullet_from_section(self):
        """Bullet style comes from the first list item in the section."""
        star_section = ["* first item"]
        block, _ = assemble(star_section, _FMT_LIST_APPEND, [["content"]], _MARKER)
        assert block.startswith("*")

    def test_list_multi_item_per_item(self):
        """list_item + per_item with N captures → N list lines."""
        cells = [["a"], ["b"], ["c"]]
        block, _ = assemble(_SECTION_LIST, _FMT_LIST_APPEND, cells, _MARKER)
        assert len(block.splitlines()) == 3


class TestSanitize:
    def test_sanitize_escapes_pipe_in_table_cell(self):
        """_sanitize: pipe in cell value → escaped \\|  (FR-18)."""
        block, _ = assemble(_SECTION_3COL, _FMT_TABLE_APPEND, [["a|b", "c", "d"]], _MARKER)
        assert r"a\|b" in block

    def test_sanitize_collapses_newline_in_table_cell(self):
        """_sanitize: newline in cell → space (single-line requirement)."""
        block, _ = assemble(_SECTION_3COL, _FMT_TABLE_APPEND, [["line1\nline2", "c", "d"]], _MARKER)
        assert "\n" not in block.split("|")[1].strip()

    def test_sanitize_line_collapses_newline_in_list_cell(self):
        """_sanitize_line: newline in list cell → space."""
        block, _ = assemble(_SECTION_LIST, _FMT_LIST_APPEND, [["line1\nline2", "ok"]], _MARKER)
        lines = block.splitlines()
        assert len(lines) == 1  # no extra lines from embedded newline

    def test_empty_field_produces_empty_cell_not_fallback(self):
        """FR-19: empty field → empty cell string; row still well-formed, no Fallback."""
        result = assemble(_SECTION_3COL, _FMT_TABLE_APPEND, [["", "", ""]], _MARKER)
        assert not isinstance(result, Fallback)
        block, _ = result
        assert block == "|  |  |  |"


# ---------------------------------------------------------------------------
# T2.3  Fallback signalling
# ---------------------------------------------------------------------------


class TestFallback:
    def test_cell_count_mismatch_returns_fallback(self):
        """FR-19: 3-col table but 2 cells → Fallback(cell_count_mismatch)."""
        result = assemble(_SECTION_3COL, _FMT_TABLE_NEWEST, [["only", "two"]], _MARKER)
        assert isinstance(result, Fallback)
        assert result.reason == "cell_count_mismatch"

    def test_prose_only_returns_fallback(self):
        """FR-19: no table under marker → Fallback(no_structure_under_marker)."""
        result = assemble(_PROSE_ONLY.splitlines(), _FMT_TABLE_NEWEST, [["a", "b", "c"]], _MARKER)
        assert isinstance(result, Fallback)
        assert result.reason == "no_structure_under_marker"

    def test_empty_section_returns_fallback(self):
        """Empty section (e.g. marker_missing handled upstream) → no_structure_under_marker."""
        result = assemble([], _FMT_TABLE_NEWEST, [["a", "b", "c"]], _MARKER)
        assert isinstance(result, Fallback)
        assert result.reason == "no_structure_under_marker"

    def test_fallback_has_reason_attribute(self):
        """Fallback sentinel exposes .reason for consumer code."""
        fb = Fallback("cell_count_mismatch")
        assert fb.reason == "cell_count_mismatch"

    def test_fallback_equality(self):
        """Fallback instances with same reason are equal (for test assertions)."""
        assert Fallback("cell_count_mismatch") == Fallback("cell_count_mismatch")
        assert Fallback("cell_count_mismatch") != Fallback("no_structure_under_marker")

    def test_fallback_never_returns_malformed_row(self):
        """FR-19: on mismatch, returns Fallback — not a partially-formed row string."""
        result = assemble(_SECTION_3COL, _FMT_TABLE_NEWEST, [["a"]], _MARKER)
        # Must NOT be a tuple with a broken row
        assert isinstance(result, Fallback)

    def test_wrong_cell_count_on_one_of_many(self):
        """cell_count check applies across ALL inner lists — one bad apple → Fallback."""
        cells = [["a", "b", "c"], ["only", "two"]]  # second has 2, not 3
        result = assemble(_SECTION_3COL, _FMT_TABLE_NEWEST, cells, _MARKER)
        assert isinstance(result, Fallback)
        assert result.reason == "cell_count_mismatch"


# ---------------------------------------------------------------------------
# T2.4  Purity contract checks (no IO / Kado / LLM imports)
# ---------------------------------------------------------------------------


def test_no_io_kado_llm_imports():
    """ADR-3: target_structure module must not import IO/Kado/LLM modules."""
    import lib.target_structure as ts
    import importlib
    import sys

    # Reload to get the real module (not a cached patched version)
    importlib.reload(ts)

    forbidden = {"kado_client", "anthropic", "openai", "requests", "httpx"}
    module_imports = set(ts.__dict__.keys())

    for name in forbidden:
        assert name not in sys.modules or name not in module_imports, (
            f"target_structure.py must not use {name}"
        )

    # Check the module's own imports via its __spec__ source.
    # Use bare module names so both `import X` and `from X import Y` forms are caught.
    import inspect
    source = inspect.getsource(ts)
    for bad in ("kado_client", "anthropic", "openai", "requests", "httpx"):
        assert bad not in source, f"Found forbidden module '{bad}' in target_structure.py"
