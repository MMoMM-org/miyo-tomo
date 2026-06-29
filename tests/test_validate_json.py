#!/usr/bin/env python3
# version: 0.1.0
"""test_validate_json.py — Tests for tomo/scripts/validate-json.py.

Spec 026, T1.1 (Companion Mode P1 — Deterministic Safety Scripts).
ADR-4: parse-gate must reject malformed JSON before any .base/.canvas write.
ADR-9: safety logic must be deterministic and unit-tested, not LLM-judged.

Assertions:
  - valid .base JSON → exit 0
  - valid .canvas JSON → exit 0
  - malformed JSON → exit 1, error message on stderr
  - non-existent input path → exit 1
  - validator writes nothing (read-only gate)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tomo" / "scripts" / "validate-json.py"


def run(path: str | Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Valid JSON — exit 0
# ---------------------------------------------------------------------------


def test_valid_base_json_exits_0(tmp_path: Path) -> None:
    """A syntactically valid .base file must pass the gate."""
    f = tmp_path / "frame.base"
    f.write_text('{"type": "base", "items": [1, 2, 3]}')
    result = run(f)
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_valid_canvas_json_exits_0(tmp_path: Path) -> None:
    """A syntactically valid .canvas file must pass the gate."""
    f = tmp_path / "board.canvas"
    f.write_text('{"nodes": [], "edges": []}')
    result = run(f)
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_valid_plain_json_exits_0(tmp_path: Path) -> None:
    """Any extension with valid JSON content must pass the gate."""
    f = tmp_path / "data.json"
    f.write_text('{"key": "value"}')
    result = run(f)
    assert result.returncode == 0, f"stderr: {result.stderr}"


# ---------------------------------------------------------------------------
# Malformed JSON — exit 1 with error on stderr
# ---------------------------------------------------------------------------


def test_malformed_json_exits_1(tmp_path: Path) -> None:
    """Malformed JSON must be rejected with exit 1."""
    f = tmp_path / "bad.base"
    f.write_text('{"key": "unclosed string}')
    result = run(f)
    assert result.returncode == 1


def test_malformed_json_prints_error_to_stderr(tmp_path: Path) -> None:
    """The parse error must appear on stderr (not stdout)."""
    f = tmp_path / "bad.base"
    f.write_text("{invalid json here")
    result = run(f)
    assert result.returncode == 1
    assert result.stderr.strip(), "expected a parse error message on stderr"
    # stdout must stay clean
    assert result.stdout.strip() == ""


def test_empty_file_exits_1(tmp_path: Path) -> None:
    """An empty file is not valid JSON — must exit 1."""
    f = tmp_path / "empty.base"
    f.write_text("")
    result = run(f)
    assert result.returncode == 1


# ---------------------------------------------------------------------------
# Non-existent path — exit 1
# ---------------------------------------------------------------------------


def test_nonexistent_path_exits_1(tmp_path: Path) -> None:
    """A path that does not exist must produce exit 1."""
    missing = tmp_path / "does_not_exist.base"
    result = run(missing)
    assert result.returncode == 1


def test_nonexistent_path_error_on_stderr(tmp_path: Path) -> None:
    """Missing-file error must appear on stderr."""
    missing = tmp_path / "ghost.canvas"
    result = run(missing)
    assert result.returncode == 1
    assert result.stderr.strip(), "expected an error message on stderr"


# ---------------------------------------------------------------------------
# Read-only gate — writes nothing
# ---------------------------------------------------------------------------


def test_validator_writes_nothing_for_valid_input(tmp_path: Path) -> None:
    """The script must not create any files in the working directory."""
    f = tmp_path / "data.base"
    f.write_text('{"ok": true}')
    before = set(tmp_path.iterdir())
    run(f)
    after = set(tmp_path.iterdir())
    assert before == after, f"unexpected new files: {after - before}"


def test_validator_writes_nothing_for_invalid_input(tmp_path: Path) -> None:
    """Even on rejection the script must not create any files."""
    f = tmp_path / "bad.base"
    f.write_text("not json at all")
    before = set(tmp_path.iterdir())
    run(f)
    after = set(tmp_path.iterdir())
    assert before == after, f"unexpected new files: {after - before}"
