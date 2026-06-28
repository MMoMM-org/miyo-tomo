#!/usr/bin/env python3
# version: 0.1.0
"""test_validate_yaml.py — Tests for tomo/scripts/validate-yaml.py.

Spec 026, T1.4 (Companion Mode P1 — Deterministic Safety Scripts, ADR-4 correction).
ADR-4 (corrected): .base files are YAML, not JSON; this gate runs before any .base write.
ADR-9: safety logic must be deterministic and unit-tested, not LLM-judged.

Assertions:
  - valid .base YAML → exit 0
  - malformed YAML → exit 1, error message on stderr
  - non-existent input path → exit 1, error on stderr
  - validator writes nothing (read-only gate)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tomo" / "scripts" / "validate-yaml.py"


def run(path: str | Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Valid YAML — exit 0
# ---------------------------------------------------------------------------


def test_valid_base_yaml_exits_0(tmp_path: Path) -> None:
    """A syntactically valid .base file must pass the gate."""
    f = tmp_path / "frame.base"
    f.write_text(
        "filters:\n"
        "  and:\n"
        "    - 'status == \"active\"'\n"
        "views:\n"
        "  - type: table\n"
        "    name: My View\n"
        "    order:\n"
        "      - file.name\n"
    )
    result = run(f)
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_valid_minimal_yaml_exits_0(tmp_path: Path) -> None:
    """A minimal valid YAML mapping must pass the gate."""
    f = tmp_path / "minimal.base"
    f.write_text("views:\n  - type: list\n    name: All\n")
    result = run(f)
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_valid_yaml_with_formulas_exits_0(tmp_path: Path) -> None:
    """A .base file with formulas and summaries must pass the gate."""
    f = tmp_path / "full.base"
    f.write_text(
        "formulas:\n"
        "  days_old: '(now() - file.ctime).days'\n"
        "views:\n"
        "  - type: table\n"
        "    name: With Formulas\n"
        "    order:\n"
        "      - file.name\n"
        "      - formula.days_old\n"
    )
    result = run(f)
    assert result.returncode == 0, f"stderr: {result.stderr}"


# ---------------------------------------------------------------------------
# Malformed YAML — exit 1 with error on stderr
# ---------------------------------------------------------------------------


def test_malformed_yaml_exits_1(tmp_path: Path) -> None:
    """Malformed YAML must be rejected with exit 1."""
    f = tmp_path / "bad.base"
    # Tab character where spaces are required causes a ScannerError
    f.write_text("key:\n\t- bad_tab_indent\n")
    result = run(f)
    assert result.returncode == 1


def test_malformed_yaml_prints_error_to_stderr(tmp_path: Path) -> None:
    """The parse error must appear on stderr (not stdout)."""
    f = tmp_path / "bad.base"
    # Unclosed bracket is a YAML scan error
    f.write_text("filters:\n  - [unclosed bracket\n")
    result = run(f)
    assert result.returncode == 1
    assert result.stderr.strip(), "expected a parse error message on stderr"
    # stdout must stay clean
    assert result.stdout.strip() == ""


def test_invalid_yaml_mapping_exits_1(tmp_path: Path) -> None:
    """Tab characters in indentation are a YAML scanner error."""
    f = tmp_path / "dup.base"
    f.write_text("key:\n\t- tab_indented\n")
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
    missing = tmp_path / "ghost.base"
    result = run(missing)
    assert result.returncode == 1
    assert result.stderr.strip(), "expected an error message on stderr"


# ---------------------------------------------------------------------------
# Read-only gate — writes nothing
# ---------------------------------------------------------------------------


def test_validator_writes_nothing_for_valid_input(tmp_path: Path) -> None:
    """The script must not create any files in the working directory."""
    f = tmp_path / "data.base"
    f.write_text("views:\n  - type: list\n    name: All\n")
    before = set(tmp_path.iterdir())
    run(f)
    after = set(tmp_path.iterdir())
    assert before == after, f"unexpected new files: {after - before}"


def test_validator_writes_nothing_for_invalid_input(tmp_path: Path) -> None:
    """Even on rejection the script must not create any files."""
    f = tmp_path / "bad.base"
    f.write_text("key:\n\t- tab_indent_is_invalid\n")
    before = set(tmp_path.iterdir())
    run(f)
    after = set(tmp_path.iterdir())
    assert before == after, f"unexpected new files: {after - before}"
