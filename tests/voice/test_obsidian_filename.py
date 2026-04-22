#!/usr/bin/env python3
# version: 0.1.0
"""Tests for scripts/lib/obsidian_filename.py."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent.parent
LIB_PATH = REPO_ROOT / "scripts" / "lib"

sys.path.insert(0, str(LIB_PATH))
from obsidian_filename import FORBIDDEN_CHARS, is_obsidian_safe, sanitize_stem  # noqa: E402


def test_sanitize_replaces_colons():
    """iOS Voice Memos / desktop recorders use colon-timestamped names."""
    assert sanitize_stem("memo 11:48:29") == "memo 11-48-29"


def test_sanitize_replaces_every_forbidden_char():
    # Obsidian's published forbidden set.
    stem = 'a\\b/c:d*e?f"g<h>i|j\x00k'
    result = sanitize_stem(stem)
    assert all(c not in FORBIDDEN_CHARS for c in result), (
        f"sanitised stem still contains forbidden char: {result!r}"
    )
    # Length preserved — every offending char replaced 1:1.
    assert len(result) == len(stem)


def test_sanitize_is_idempotent():
    dirty = "memo 11:48:29"
    once = sanitize_stem(dirty)
    twice = sanitize_stem(once)
    assert once == twice


def test_sanitize_passes_safe_strings_unchanged():
    safe = "Apothekerpfädchen 11__2026-04-20 11-48-29"
    assert sanitize_stem(safe) == safe


def test_sanitize_handles_empty_string():
    assert sanitize_stem("") == ""


def test_is_obsidian_safe_rejects_forbidden():
    assert not is_obsidian_safe("memo:with:colons")
    assert not is_obsidian_safe("question?")
    assert not is_obsidian_safe('has"quote')


def test_is_obsidian_safe_accepts_clean():
    assert is_obsidian_safe("Apothekerpfädchen 11__2026-04-20 11-48-29")
    assert is_obsidian_safe("simple_name")
    assert is_obsidian_safe("umlaut äöüß unicode 日本語")


def test_cli_prints_sanitised_stem(tmp_path):
    """The agent can `python3 scripts/lib/obsidian_filename.py <stem>` to
    get the same transformation the CLI uses — contract test so the
    agent and CLI can't drift."""
    script = REPO_ROOT / "scripts" / "lib" / "obsidian_filename.py"
    r = subprocess.run(
        [sys.executable, str(script), "memo 11:48:29"],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0
    assert r.stdout.strip() == "memo 11-48-29"


def test_cli_errors_on_wrong_argv():
    script = REPO_ROOT / "scripts" / "lib" / "obsidian_filename.py"
    r = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 2
    assert "usage" in r.stderr.lower()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
