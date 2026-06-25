"""Tests for tomo/scripts/tag-handler-compose.py — spec 025 Phase 4a / T4.1a.

All tests invoke the script via main(argv) and assert the parsed stdout JSON.
Fixtures use raw markdown lines as a Kado section read would return them.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Load tag-handler-compose.py via importlib (hyphenated filename)
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
_MODULE_PATH = _SCRIPTS_DIR / "tag-handler-compose.py"

_spec = importlib.util.spec_from_file_location("tag_handler_compose", str(_MODULE_PATH))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

main = _mod.main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_payload(tmp_path: Path, payload: dict) -> str:
    p = tmp_path / "payload.json"
    p.write_text(json.dumps(payload))
    return str(p)


def _call_main(payload_path: str, capsys) -> tuple[dict | None, int]:
    """Call main([payload_path]) and return (parsed_stdout_dict, exit_code).

    Returns (None, exit_code) when stdout is not parseable JSON.
    """
    exit_code = 0
    try:
        main([payload_path])
    except SystemExit as e:
        exit_code = int(e.code) if e.code is not None else 0

    captured = capsys.readouterr()
    try:
        return json.loads(captured.out), exit_code
    except json.JSONDecodeError:
        return None, exit_code


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

TABLE_SECTION_LINES = [
    "| Date | Type | Description |",
    "| --- | --- | --- |",
    "| 2026-06-24 | fix | old fix |",
]

LIST_SECTION_LINES = [
    "- 2026-06-24 — fix — old fix",
]

OUTPUT_FORMAT_TABLE_NEWEST = {
    "structure": "table_row",
    "order": "newest_first",
    "granularity": "per_item",
    "cells": [
        {"label": "Date", "source": "field", "field": "date"},
        {"label": "Type", "source": "synthesize", "directive": "classify"},
        {"label": "Description", "source": "synthesize", "directive": "summarize"},
    ],
    "join": " — ",
}

OUTPUT_FORMAT_TABLE_APPEND = {
    "structure": "table_row",
    "order": "append",
    "granularity": "per_item",
    "cells": [
        {"label": "Date", "source": "field", "field": "date"},
        {"label": "Description", "source": "synthesize", "directive": "summarize"},
        {"label": "Type", "source": "synthesize", "directive": "classify"},
    ],
    "join": " — ",
}

OUTPUT_FORMAT_LIST_NEWEST = {
    "structure": "list_item",
    "order": "newest_first",
    "granularity": "per_item",
    "cells": [
        {"label": "Date", "source": "field", "field": "date"},
        {"label": "Description", "source": "synthesize", "directive": "summarize"},
    ],
    "join": " — ",
}

CELL_VALUES_TWO_ITEMS = [
    ["2026-06-25", "fix", "landed"],
    ["2026-06-25", "feature", "schema"],
]

CELL_VALUES_TWO_ITEMS_TABLE_APPEND = [
    ["2026-06-25", "landed", "fix"],
    ["2026-06-25", "schema", "feature"],
]

CELL_VALUES_LIST_TWO = [
    ["2026-06-25", "landed"],
    ["2026-06-25", "schema"],
]

MARKER = "## Captures"


# ---------------------------------------------------------------------------
# T1: table_row + newest_first → status=ok, block anchor
# ---------------------------------------------------------------------------

class TestTableRowNewestFirst:
    def test_status_ok(self, tmp_path, capsys):
        payload = {
            "section_lines": TABLE_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_TABLE_NEWEST,
            "cell_values_per_item": CELL_VALUES_TWO_ITEMS,
            "marker": MARKER,
        }
        result, exit_code = _call_main(_write_payload(tmp_path, payload), capsys)
        assert exit_code == 0
        assert result is not None
        assert result["status"] == "ok"

    def test_composed_block_has_two_rows(self, tmp_path, capsys):
        payload = {
            "section_lines": TABLE_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_TABLE_NEWEST,
            "cell_values_per_item": CELL_VALUES_TWO_ITEMS,
            "marker": MARKER,
        }
        result, _ = _call_main(_write_payload(tmp_path, payload), capsys)
        assert result is not None
        rows = result["composed_block"].strip().splitlines()
        assert len(rows) == 2

    def test_anchor_type_is_block(self, tmp_path, capsys):
        payload = {
            "section_lines": TABLE_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_TABLE_NEWEST,
            "cell_values_per_item": CELL_VALUES_TWO_ITEMS,
            "marker": MARKER,
        }
        result, _ = _call_main(_write_payload(tmp_path, payload), capsys)
        assert result is not None
        anchor = result["resolved_anchor"]
        assert anchor["type"] == "block"

    def test_anchor_value_is_header_and_separator(self, tmp_path, capsys):
        """Block anchor value must be byte-exact: header line + newline + separator line."""
        payload = {
            "section_lines": TABLE_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_TABLE_NEWEST,
            "cell_values_per_item": CELL_VALUES_TWO_ITEMS,
            "marker": MARKER,
        }
        result, _ = _call_main(_write_payload(tmp_path, payload), capsys)
        assert result is not None
        expected_value = TABLE_SECTION_LINES[0] + "\n" + TABLE_SECTION_LINES[1]
        assert result["resolved_anchor"]["value"] == expected_value

    def test_anchor_placement_is_after(self, tmp_path, capsys):
        payload = {
            "section_lines": TABLE_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_TABLE_NEWEST,
            "cell_values_per_item": CELL_VALUES_TWO_ITEMS,
            "marker": MARKER,
        }
        result, _ = _call_main(_write_payload(tmp_path, payload), capsys)
        assert result is not None
        assert result["resolved_anchor"]["placement"] == "after"

    def test_stdout_is_valid_json(self, tmp_path, capsys):
        payload = {
            "section_lines": TABLE_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_TABLE_NEWEST,
            "cell_values_per_item": CELL_VALUES_TWO_ITEMS,
            "marker": MARKER,
        }
        result, _ = _call_main(_write_payload(tmp_path, payload), capsys)
        assert result is not None  # json.loads succeeded in _call_main


# ---------------------------------------------------------------------------
# T2: table_row + append → heading anchor inside
# ---------------------------------------------------------------------------

class TestTableRowAppend:
    def test_status_ok(self, tmp_path, capsys):
        payload = {
            "section_lines": TABLE_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_TABLE_APPEND,
            "cell_values_per_item": CELL_VALUES_TWO_ITEMS_TABLE_APPEND,
            "marker": MARKER,
        }
        result, exit_code = _call_main(_write_payload(tmp_path, payload), capsys)
        assert exit_code == 0
        assert result is not None
        assert result["status"] == "ok"

    def test_anchor_type_heading(self, tmp_path, capsys):
        payload = {
            "section_lines": TABLE_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_TABLE_APPEND,
            "cell_values_per_item": CELL_VALUES_TWO_ITEMS_TABLE_APPEND,
            "marker": MARKER,
        }
        result, _ = _call_main(_write_payload(tmp_path, payload), capsys)
        assert result is not None
        assert result["resolved_anchor"]["type"] == "heading"

    def test_anchor_placement_inside(self, tmp_path, capsys):
        payload = {
            "section_lines": TABLE_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_TABLE_APPEND,
            "cell_values_per_item": CELL_VALUES_TWO_ITEMS_TABLE_APPEND,
            "marker": MARKER,
        }
        result, _ = _call_main(_write_payload(tmp_path, payload), capsys)
        assert result is not None
        assert result["resolved_anchor"]["placement"] == "inside"


# ---------------------------------------------------------------------------
# T3: list_item + newest_first → heading anchor after
# ---------------------------------------------------------------------------

class TestListItemNewestFirst:
    def test_status_ok(self, tmp_path, capsys):
        payload = {
            "section_lines": LIST_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_LIST_NEWEST,
            "cell_values_per_item": CELL_VALUES_LIST_TWO,
            "marker": MARKER,
        }
        result, exit_code = _call_main(_write_payload(tmp_path, payload), capsys)
        assert exit_code == 0
        assert result is not None
        assert result["status"] == "ok"

    def test_anchor_type_heading(self, tmp_path, capsys):
        payload = {
            "section_lines": LIST_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_LIST_NEWEST,
            "cell_values_per_item": CELL_VALUES_LIST_TWO,
            "marker": MARKER,
        }
        result, _ = _call_main(_write_payload(tmp_path, payload), capsys)
        assert result is not None
        assert result["resolved_anchor"]["type"] == "heading"

    def test_anchor_placement_after(self, tmp_path, capsys):
        payload = {
            "section_lines": LIST_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_LIST_NEWEST,
            "cell_values_per_item": CELL_VALUES_LIST_TWO,
            "marker": MARKER,
        }
        result, _ = _call_main(_write_payload(tmp_path, payload), capsys)
        assert result is not None
        assert result["resolved_anchor"]["placement"] == "after"


# ---------------------------------------------------------------------------
# T4: cell-count mismatch → fallback
# ---------------------------------------------------------------------------

class TestCellCountMismatch:
    def test_status_fallback(self, tmp_path, capsys):
        # 3-col table but 2 cells in one row
        payload = {
            "section_lines": TABLE_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_TABLE_NEWEST,
            "cell_values_per_item": [["2026-06-25", "fix"]],  # 2 cells, table has 3 cols
            "marker": MARKER,
        }
        result, exit_code = _call_main(_write_payload(tmp_path, payload), capsys)
        assert exit_code == 0
        assert result is not None
        assert result["status"] == "fallback"

    def test_reason_cell_count_mismatch(self, tmp_path, capsys):
        payload = {
            "section_lines": TABLE_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_TABLE_NEWEST,
            "cell_values_per_item": [["2026-06-25", "fix"]],
            "marker": MARKER,
        }
        result, _ = _call_main(_write_payload(tmp_path, payload), capsys)
        assert result is not None
        assert result["reason"] == "cell_count_mismatch"

    def test_stdout_is_valid_json(self, tmp_path, capsys):
        payload = {
            "section_lines": TABLE_SECTION_LINES,
            "output_format": OUTPUT_FORMAT_TABLE_NEWEST,
            "cell_values_per_item": [["2026-06-25", "fix"]],
            "marker": MARKER,
        }
        result, _ = _call_main(_write_payload(tmp_path, payload), capsys)
        assert result is not None


# ---------------------------------------------------------------------------
# T5: prose-only section → fallback no_structure_under_marker
# ---------------------------------------------------------------------------

class TestProseOnlySection:
    def test_status_fallback(self, tmp_path, capsys):
        payload = {
            "section_lines": ["Some plain prose.", "No table here."],
            "output_format": OUTPUT_FORMAT_TABLE_NEWEST,
            "cell_values_per_item": CELL_VALUES_TWO_ITEMS,
            "marker": MARKER,
        }
        result, exit_code = _call_main(_write_payload(tmp_path, payload), capsys)
        assert exit_code == 0
        assert result is not None
        assert result["status"] == "fallback"

    def test_reason_no_structure(self, tmp_path, capsys):
        payload = {
            "section_lines": ["Some plain prose.", "No table here."],
            "output_format": OUTPUT_FORMAT_TABLE_NEWEST,
            "cell_values_per_item": CELL_VALUES_TWO_ITEMS,
            "marker": MARKER,
        }
        result, _ = _call_main(_write_payload(tmp_path, payload), capsys)
        assert result is not None
        assert result["reason"] == "no_structure_under_marker"


# ---------------------------------------------------------------------------
# T6: missing payload file → non-zero exit, no traceback, parseable error
# ---------------------------------------------------------------------------

class TestMissingPayloadFile:
    def test_non_zero_exit(self, tmp_path, capsys):
        _, exit_code = _call_main(str(tmp_path / "nonexistent.json"), capsys)
        assert exit_code != 0

    def test_no_traceback_in_stdout(self, tmp_path, capsys):
        _call_main(str(tmp_path / "nonexistent.json"), capsys)
        captured = capsys.readouterr()
        assert "Traceback" not in captured.out
        assert "Traceback" not in captured.err

    def test_stdout_is_parseable_json(self, tmp_path, capsys):
        _call_main(str(tmp_path / "nonexistent.json"), capsys)
        captured = capsys.readouterr()
        # stdout may be empty if error goes to stderr; at minimum no raw traceback
        if captured.out.strip():
            json.loads(captured.out)  # must not raise


# ---------------------------------------------------------------------------
# T7: malformed JSON payload → non-zero exit, no traceback, parseable error
# ---------------------------------------------------------------------------

class TestMalformedJsonPayload:
    def test_non_zero_exit(self, tmp_path, capsys):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json")
        _, exit_code = _call_main(str(p), capsys)
        assert exit_code != 0

    def test_no_traceback(self, tmp_path, capsys):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json")
        _call_main(str(p), capsys)
        captured = capsys.readouterr()
        assert "Traceback" not in captured.out
        assert "Traceback" not in captured.err

    def test_stdout_or_stderr_has_error_message(self, tmp_path, capsys):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json")
        result, _ = _call_main(str(p), capsys)
        # _call_main captures stdout inside it; the parsed result carries the error
        assert result is not None
        assert result.get("status") == "error" or "json" in str(result).lower()
