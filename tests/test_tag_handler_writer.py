#!/usr/bin/env python3
# version: 0.1.0
"""test_tag_handler_writer.py — Behavioural tests for tag-handler-writer.py.

Covers T5.1 (XDD 024 Phase 5): atomic schema-validated write of handler JSON
to config/tag-handlers/<id>.json.

Spec: docs/XDD/specs/024-tag-handler-framework/solution.md §7; PRD FR-13, AC-2
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
WRITER_PATH = SCRIPTS_DIR / "tag-handler-writer.py"

# Load resolve module for round-trip tests
_RESOLVER_PATH = SCRIPTS_DIR / "tag-handler-resolve.py"
_resolver_spec = importlib.util.spec_from_file_location("tag_handler_resolve", _RESOLVER_PATH)
_resolver_mod = importlib.util.module_from_spec(_resolver_spec)
sys.modules["tag_handler_resolve"] = _resolver_mod
_resolver_spec.loader.exec_module(_resolver_mod)

load_registry = _resolver_mod.load_registry
resolve_item = _resolver_mod.resolve_item


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _tsukai_handler() -> dict:
    """Return the canonical tsukai handler shape (matches tomo/config/tag-handlers/tsukai.json)."""
    return {
        "id": "tsukai",
        "enabled": True,
        "match": {
            "tag_prefix": "MiYo/Tsukai/",
            "capture_segments": ["repo"],
            "read_fields": ["category"],
        },
        "action": "insert_under_marker",
        "target": {
            "by": "repo",
            "map": {"Tomo": "Efforts/Tomo Dev Log.md"},
        },
        "marker": "## Captures",
        "placement": "inside",
        "compose": "Synthesize the batch's captures into one dated logical status update, grouped by category.",
    }


def _run_writer(handler_dict: dict, out_dir: Path, *, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Invoke tag-handler-writer.py via subprocess with a tmp input file."""
    input_file = out_dir.parent / "input.json"
    input_file.write_text(json.dumps(handler_dict), encoding="utf-8")
    cmd = [
        sys.executable, str(WRITER_PATH),
        "--input", str(input_file),
        "--out-dir", str(out_dir),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# (a) valid handler → writes a schema-valid file at <out-dir>/<id>.json
# ---------------------------------------------------------------------------

class TestValidHandlerWrite:
    def test_exits_zero(self, tmp_path):
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        result = _run_writer(_tsukai_handler(), out_dir)
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_creates_file_at_expected_path(self, tmp_path):
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        _run_writer(_tsukai_handler(), out_dir)
        assert (out_dir / "tsukai.json").exists()

    def test_written_file_is_valid_json(self, tmp_path):
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        _run_writer(_tsukai_handler(), out_dir)
        content = (out_dir / "tsukai.json").read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert parsed["id"] == "tsukai"

    def test_written_file_passes_schema_validation(self, tmp_path):
        """File written by the writer must pass the same schema used by load_registry."""
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        _run_writer(_tsukai_handler(), out_dir)
        # load_registry validates each file against the schema; if it loaded, it's valid
        handlers = load_registry(out_dir)
        assert len(handlers) == 1
        assert handlers[0]["id"] == "tsukai"

    def test_creates_out_dir_if_missing(self, tmp_path):
        """Writer must create the output directory if it doesn't exist."""
        out_dir = tmp_path / "new-handlers"
        result = _run_writer(_tsukai_handler(), out_dir)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert (out_dir / "tsukai.json").exists()


# ---------------------------------------------------------------------------
# (b) invalid handler → exits non-zero AND leaves NO file on disk (atomicity)
# ---------------------------------------------------------------------------

class TestInvalidHandlerRejected:
    def test_missing_required_field_id_exits_nonzero(self, tmp_path):
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        handler = _tsukai_handler()
        del handler["id"]
        result = _run_writer(handler, out_dir)
        assert result.returncode != 0

    def test_missing_required_field_id_leaves_no_file(self, tmp_path):
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        handler = _tsukai_handler()
        del handler["id"]
        _run_writer(handler, out_dir)
        # No partial file should exist
        assert not any(out_dir.glob("*.json"))

    def test_missing_required_field_match_exits_nonzero(self, tmp_path):
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        handler = _tsukai_handler()
        del handler["match"]
        result = _run_writer(handler, out_dir)
        assert result.returncode != 0

    def test_missing_required_field_match_leaves_no_file(self, tmp_path):
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        handler = _tsukai_handler()
        del handler["match"]
        _run_writer(handler, out_dir)
        assert not any(out_dir.glob("*.json"))

    def test_compose_wrong_type_exits_nonzero(self, tmp_path):
        """compose must be string OR array — a dict is neither (oneOf violation)."""
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        handler = _tsukai_handler()
        handler["compose"] = {"not": "a-string-or-array"}
        result = _run_writer(handler, out_dir)
        assert result.returncode != 0

    def test_compose_wrong_type_leaves_no_file(self, tmp_path):
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        handler = _tsukai_handler()
        handler["compose"] = {"not": "a-string-or-array"}
        _run_writer(handler, out_dir)
        assert not any(out_dir.glob("*.json"))

    def test_unknown_action_exits_nonzero(self, tmp_path):
        """An action value outside the enum rejects at write time."""
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        handler = _tsukai_handler()
        handler["action"] = "not_a_valid_action"
        result = _run_writer(handler, out_dir)
        assert result.returncode != 0

    def test_unknown_action_leaves_no_file(self, tmp_path):
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        handler = _tsukai_handler()
        handler["action"] = "not_a_valid_action"
        _run_writer(handler, out_dir)
        assert not any(out_dir.glob("*.json"))

    def test_unknown_top_level_key_exits_nonzero(self, tmp_path):
        """additionalProperties:false → unknown key at top level fails schema."""
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        handler = _tsukai_handler()
        handler["unknown_extra_key"] = "value"
        result = _run_writer(handler, out_dir)
        assert result.returncode != 0

    def test_unknown_top_level_key_leaves_no_file(self, tmp_path):
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        handler = _tsukai_handler()
        handler["unknown_extra_key"] = "value"
        _run_writer(handler, out_dir)
        assert not any(out_dir.glob("*.json"))

    def test_invalid_json_input_exits_nonzero(self, tmp_path):
        """Malformed JSON in the input file exits non-zero."""
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        input_file = tmp_path / "bad.json"
        input_file.write_text("{not valid json}", encoding="utf-8")
        cmd = [
            sys.executable, str(WRITER_PATH),
            "--input", str(input_file),
            "--out-dir", str(out_dir),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode != 0

    def test_missing_compose_exits_nonzero(self, tmp_path):
        """compose is required — missing it fails schema."""
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        handler = _tsukai_handler()
        del handler["compose"]
        result = _run_writer(handler, out_dir)
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# (c) round-trip: written file → load_registry → resolve_item matches fixture
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_resolve_matches_tsukai_tagged_item(self, tmp_path):
        """Written handler → load_registry → resolve_item returns correct resolution."""
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        _run_writer(_tsukai_handler(), out_dir)

        registry = load_registry(out_dir)
        assert len(registry) == 1

        item = {
            "path": "100 Inbox/capture.md",
            "tags": ["MiYo/Tsukai/Tomo"],
            "frontmatter": {"category": "feature"},
        }
        result = resolve_item(item, registry)

        assert result is not None
        assert result["handler"] == "tsukai"
        assert result["vars"] == {"repo": "Tomo"}
        assert result["fields"] == {"category": "feature"}
        assert result["target_path"] == "Efforts/Tomo Dev Log.md"
        assert result["marker"] == "## Captures"
        assert result["action"] == "insert_under_marker"

    def test_unmatched_item_returns_none_after_round_trip(self, tmp_path):
        """Unrelated tags still return None after the handler is written."""
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        _run_writer(_tsukai_handler(), out_dir)

        registry = load_registry(out_dir)
        item = {"path": "inbox/other.md", "tags": ["OtherTag/Thing"], "frontmatter": {}}
        result = resolve_item(item, registry)
        assert result is None

    def test_compose_array_round_trips(self, tmp_path):
        """Mechanical compose (array of field names) round-trips via write → load → resolve."""
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        handler = _tsukai_handler()
        handler["compose"] = ["created", "Summary", "link"]
        _run_writer(handler, out_dir)

        registry = load_registry(out_dir)
        assert len(registry) == 1
        assert isinstance(registry[0]["compose"], list)
        assert registry[0]["compose"] == ["created", "Summary", "link"]


# ---------------------------------------------------------------------------
# (d) filename-safety: unsafe id chars are sanitised to produce a safe stem
# ---------------------------------------------------------------------------

class TestSafeStem:
    def test_id_with_unsafe_chars_uses_safe_stem(self, tmp_path):
        """Handler id with a colon (e.g. 'tag:foo') must produce a sanitised filename.

        _safe_stem replaces unsafe filesystem chars (colon, space, slash, …) with
        underscores. The output file must be named after the sanitised stem — NOT
        the raw id — so the file is writable on all target filesystems.
        """
        out_dir = tmp_path / "handlers"
        out_dir.mkdir()
        # Build a handler whose id contains a colon (unsafe on most filesystems)
        handler = _tsukai_handler()
        handler["id"] = "tag:foo"

        result = _run_writer(handler, out_dir)
        assert result.returncode == 0, f"writer failed unexpectedly: {result.stderr}"

        # The raw id "tag:foo" contains ':' → _safe_stem replaces it with '_'
        # so the expected filename is "tag_foo.json", NOT "tag:foo.json"
        assert (out_dir / "tag_foo.json").exists(), (
            f"expected tag_foo.json but found: {list(out_dir.iterdir())}"
        )
        # The raw-id filename must NOT exist
        assert not (out_dir / "tag:foo.json").exists()
