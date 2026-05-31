#!/usr/bin/env python3
# version: 0.1.0
"""test_state_scanner_removed.py — Tests for T4.2: delete dead state-scanner.py

Verifies:
A. state-scanner.py file does not exist
B. No runtime files reference state-scanner (excluding spec docs)

Context: state-scanner.py implemented tag-based lifecycle discovery, made dead by
F-47 (state now lives in tomo.state frontmatter). F6-AC2 requirement.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent


class TestStateScannerRemoved:
    """Verify state-scanner.py is deleted and no runtime code references it."""

    def test_state_scanner_file_does_not_exist(self):
        """A. state-scanner.py must not exist on disk."""
        scanner_path = REPO_ROOT / "tomo" / "scripts" / "state-scanner.py"
        assert not scanner_path.exists(), (
            f"state-scanner.py still exists at {scanner_path} — should be deleted"
        )

    def test_no_runtime_references_to_state_scanner(self):
        """B. No runtime files reference state-scanner.

        Scans tomo/, scripts/, and tests/ (excluding test scripts and docs/XDD/specs).
        Pattern: 'state.?scanner' or 'state_scanner' (case-sensitive, not in comments only).
        """
        # Build the rg command: search for the pattern in runtime dirs, exclude docs/XDD
        result = subprocess.run(
            [
                "rg",
                "--type-list",  # Confirm type support (fail early if rg unavailable)
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, "rg command failed; ensure ripgrep is installed"

        # Search for state-scanner references
        result = subprocess.run(
            [
                "rg",
                r"state.?scanner|state_scanner",
                str(REPO_ROOT / "tomo"),
                str(REPO_ROOT / "scripts"),
                str(REPO_ROOT / "tests"),
                # Exclude this test file itself and shell test scaffolding
                f"--glob=!{TESTS_DIR.name}/test_state_scanner_removed.py",
                "--glob=!tests/test-phase*.sh",
                "--glob=!tests/*.sh",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Filter out matches that are inside the state-scanner.py file itself
        # (docstring/usage in the file about to be deleted).
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        runtime_refs = [
            line
            for line in lines
            if line and "state-scanner.py:" not in line
        ]

        assert not runtime_refs, (
            f"Found {len(runtime_refs)} runtime references to state-scanner:\n"
            + "\n".join(runtime_refs)
            + "\n\nTo delete the file safely, remove these references first."
        )
