"""Deterministic target-structure parser and row/item assembler — spec 025 / T2.1-T2.3.

No IO, no Kado imports, no LLM. Takes raw section lines (strings) in, returns
structured data out. Mirrors the purity contract of moc_structure.py.

Callers supply the raw lines of the target note section under the marker heading
(via Kado section-read in the interpreter) and the output_format config object.
This module parses what table/list structure exists, assembles the row(s)/item(s),
selects the Hashi anchor, and returns either (block, anchor) or a Fallback sentinel.

Parse contract (ADR-9): the FIRST structure of the declared type under the marker
wins. Intervening prose is skipped. If no matching structure is found before the
next heading or end of lines, kind=none is returned, which causes assemble() to
return Fallback("no_structure_under_marker").

Anchor contract:
- table_row + newest_first  → block anchor {type:block, value:header\\nseparator, placement:after}
  The value is the RAW bytes from the section — byte-exact so Hashi resolveBlock
  can match them (trailing-trim only; no reformatting).
- table_row + append        → heading anchor {type:heading, value:<marker>, placement:inside}
- list_item + newest_first  → heading anchor {type:heading, value:<marker>, placement:after}
- list_item + append        → heading anchor {type:heading, value:<marker>, placement:inside}
"""
# version: 0.1.0

from __future__ import annotations

import re as _re
from dataclasses import dataclass
from typing import Union

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class TargetStructure:
    """Parsed result of a target note section.

    kind:           "table" | "list" | "none"
    columns:        number of columns (table only; 0 for list/none)
    header_line:    raw table header line, e.g. "| Date | Type |" (table only)
    separator_line: raw table separator line, e.g. "| --- | --- |" (table only)
    bullet:         list bullet string — "-", "*", or "1." (list only; "" for table/none)
    """

    kind: str  # "table" | "list" | "none"
    columns: int = 0
    header_line: str = ""
    separator_line: str = ""
    bullet: str = ""


@dataclass
class Fallback:
    """Sentinel returned by assemble() when the section cannot be used as-is.

    reason: "no_structure_under_marker" | "cell_count_mismatch"

    Consumers check `isinstance(result, Fallback)` and degrade to prose block + ⚠️.
    """

    reason: str

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Fallback):
            return NotImplemented
        return self.reason == other.reason


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

# Matches a markdown table header row — at least one pipe-delimited cell.
_TABLE_HEADER_RE = _re.compile(r"^\|(.+\|)+\s*$")

# Matches a markdown table separator row. Cells contain only dashes, colons,
# and spaces. Supports:  | --- |  | :-- |  | :-: |  | --: |  |---|  | :---: |
_TABLE_SEP_RE = _re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")

# Matches an unordered list item: "- text", "* text"
_LIST_UNORDERED_RE = _re.compile(r"^([*-])\s+")

# Matches an ordered list item: "1. text", "2. text"
_LIST_ORDERED_RE = _re.compile(r"^(\d+\.)\s+")

# Matches a heading (any level) — used to stop scanning at section boundaries
_HEADING_RE = _re.compile(r"^#{1,6}\s+")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _count_columns(header_line: str) -> int:
    """Count table columns from a header line.

    Splits on '|', strips, and discards the empty strings from leading/trailing pipes.
    """
    parts = header_line.split("|")
    return sum(1 for p in parts if p.strip())


def _is_table_header(line: str) -> bool:
    return bool(_TABLE_HEADER_RE.match(line.rstrip()))


def _is_table_separator(line: str) -> bool:
    return bool(_TABLE_SEP_RE.match(line.rstrip()))


def _list_bullet(line: str) -> str | None:
    """Return the bullet string for a list item line, or None if not a list item."""
    m = _LIST_UNORDERED_RE.match(line)
    if m:
        return m.group(1)
    m = _LIST_ORDERED_RE.match(line)
    if m:
        return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_section(raw_section: list[str], structure_kind: str) -> TargetStructure:
    """Parse the raw lines of a target note section and return a TargetStructure.

    Args:
        raw_section:    Lines of the section under the marker heading. May include
                        prose, tables, lists, or be empty.
        structure_kind: "table_row" or "list_item" — which structure to look for.

    Returns:
        TargetStructure with kind="table"/"list"/"none". Raw header/separator bytes
        are preserved exactly for block-anchor fidelity (ADR-9).
    """
    if not raw_section:
        return TargetStructure(kind="none")

    lines = [line.rstrip() for line in raw_section]

    if structure_kind == "table_row":
        return _parse_table(lines)
    if structure_kind == "list_item":
        return _parse_list(lines)
    return TargetStructure(kind="none")


def _parse_table(lines: list[str]) -> TargetStructure:
    """Scan for the first table (header + separator pair). ADR-9: prose skipped."""
    i = 0
    while i < len(lines):
        line = lines[i]
        # Stop at a new heading (section boundary)
        if _HEADING_RE.match(line):
            break
        if _is_table_header(line):
            # Look ahead for separator
            if i + 1 < len(lines) and _is_table_separator(lines[i + 1]):
                header = line
                separator = lines[i + 1]
                columns = _count_columns(header)
                return TargetStructure(
                    kind="table",
                    columns=columns,
                    header_line=header,
                    separator_line=separator,
                )
        i += 1
    return TargetStructure(kind="none")


def _parse_list(lines: list[str]) -> TargetStructure:
    """Scan for the first list item. ADR-10: first item's bullet style is authoritative."""
    for line in lines:
        if _HEADING_RE.match(line):
            break
        bullet = _list_bullet(line)
        if bullet is not None:
            return TargetStructure(kind="list", bullet=bullet)
    return TargetStructure(kind="none")


def _sanitize(cell: str) -> str:
    """Sanitize a table cell value: collapse newlines to space, escape pipes, strip.

    FR-18: every cell must be single-line and pipe-safe so the assembled row is
    well-formed markdown. A literal '|' in a synth/field value becomes '\\|'.
    """
    return cell.replace("\n", " ").replace("|", "\\|").strip()


def _sanitize_line(cell: str) -> str:
    """Sanitize a list cell value: collapse newlines to space, strip (no pipe-escape needed)."""
    return cell.replace("\n", " ").strip()


def assemble(
    section_lines: list[str],
    output_format: dict,
    cell_values_per_item: list[list[str]],
    marker: str,
) -> Union[tuple[str, dict], Fallback]:
    """Assemble the composed block and select the Hashi anchor for a group.

    Args:
        section_lines:        Raw lines of the target section under the marker heading.
        output_format:        The handler's output_format config dict (structure/order/
                              granularity/cells/join).
        cell_values_per_item: One inner list of rendered cell strings per row.
                              For granularity=merged the caller passes exactly one inner list.
        marker:               The marker heading text (used as the heading anchor value).

    Returns:
        (block, anchor) on success, where block is the composed string and anchor is a
        Hashi-compatible {type, value, placement} dict.
        Fallback(reason) when the section cannot accommodate the structure — the caller
        degrades to a prose block and emits a ⚠️ in the suggestions doc (FR-19).

    Fallback reasons:
        "no_structure_under_marker" — section has no matching table/list
        "cell_count_mismatch"       — at least one inner list has wrong length vs columns
    """
    structure = parse_section(section_lines, output_format["structure"])

    if structure.kind == "none":
        return Fallback("no_structure_under_marker")

    if output_format["structure"] == "table_row":
        # Validate cell counts before building any rows (FR-19: never emit malformed row)
        if any(len(cells) != structure.columns for cells in cell_values_per_item):
            return Fallback("cell_count_mismatch")

        rows = [
            "| " + " | ".join(_sanitize(c) for c in cells) + " |"
            for cells in cell_values_per_item
        ]
        block = "\n".join(rows)

        if output_format["order"] == "newest_first":
            # RAW bytes — byte-exact for Hashi resolveBlock (ADR-6, byte-exact anchor)
            anchor = {
                "type": "block",
                "value": structure.header_line + "\n" + structure.separator_line,
                "placement": "after",
            }
        else:  # append
            anchor = {
                "type": "heading",
                "value": marker,
                "placement": "inside",
            }
        return (block, anchor)

    # list_item
    join = output_format.get("join", " — ")  # default " — "
    items = [
        structure.bullet + " " + join.join(_sanitize_line(c) for c in cells)
        for cells in cell_values_per_item
    ]
    block = "\n".join(items)
    placement = "after" if output_format["order"] == "newest_first" else "inside"
    anchor = {
        "type": "heading",
        "value": marker,
        "placement": placement,
    }
    return (block, anchor)
