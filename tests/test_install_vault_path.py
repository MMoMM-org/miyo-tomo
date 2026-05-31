#!/usr/bin/env python3
# version: 0.1.0
"""test_install_vault_path.py — regression guard for the vault-path tilde
expansion in scripts/install-tomo.sh.

Bug (fixed 2026-05-31): the `case "$VAULT_PATH" in ~/*)` pattern used a BARE
tilde. Bash performs tilde expansion on unquoted case patterns, so `~/*`
expanded to `$HOME/*` and matched any absolute path already under $HOME — then
`$HOME/` was prepended again, producing a doubled path like
`/Users/marcus//Users/marcus/Local/Obsidian/Privat`. The fix quotes the tilde
(`\\~/*`) so the pattern stays literal.

These tests run ONLY the extracted tilde-case block (never the installer) so
they are safe and fast. The block is pulled from the real script so the test
cannot drift from the source.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install-tomo.sh"


def _tilde_case_line() -> str:
    """Return the single `case` arm that does the tilde expansion."""
    text = INSTALL_SH.read_text()
    # The arm: <pattern>) VAULT_PATH="$HOME/${VAULT_PATH#\~/}" ;;
    m = re.search(r'^\s*(\S+\)) VAULT_PATH="\$HOME/\$\{VAULT_PATH#\\~/\}" ;;',
                  text, re.MULTILINE)
    assert m, "tilde-expansion case arm not found in install-tomo.sh"
    return m.group(0).strip()


def _expand(vault_path: str) -> str:
    """Run the real tilde-case arm against a given input, return VAULT_PATH."""
    arm = _tilde_case_line()
    script = (
        f'VAULT_PATH="{vault_path}"\n'
        f'case "$VAULT_PATH" in\n'
        f'    {arm}\n'
        f'esac\n'
        f'printf %s "$VAULT_PATH"\n'
    )
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True, text=True, timeout=10,
        env={"HOME": "/Users/tester", "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_pattern_quotes_the_tilde():
    """Static guard: the case pattern must quote the tilde (regression pin)."""
    arm = _tilde_case_line()
    assert arm.startswith(r"\~/*)"), (
        f"tilde case pattern must be quoted as '\\~/*)' to prevent bash "
        f"tilde-expanding the pattern; got: {arm!r}"
    )


def test_absolute_home_path_is_unchanged():
    """The original bug: an absolute path under $HOME must NOT be doubled."""
    out = _expand("/Users/tester/Local/Obsidian/Privat")
    assert out == "/Users/tester/Local/Obsidian/Privat", (
        f"absolute home-dir path was rewritten (double-path bug): {out!r}"
    )


def test_tilde_path_still_expands():
    """A genuine ~/ path must still expand to $HOME/...."""
    out = _expand("~/Local/Obsidian/Privat")
    assert out == "/Users/tester/Local/Obsidian/Privat", (
        f"~/ path did not expand correctly: {out!r}"
    )


def test_absolute_non_home_path_is_unchanged():
    out = _expand("/Volumes/Moon/vault")
    assert out == "/Volumes/Moon/vault", out
