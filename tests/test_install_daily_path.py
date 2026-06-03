#!/usr/bin/env python3
# version: 0.1.0
"""test_install_daily_path.py — regression guard for the calendar daily-path
extraction in scripts/install-tomo.sh.

Bug (fixed 2026-06-03): the miyo profile declares the daily calendar entry as an
inline YAML flow-map — `daily: { enabled: true, path: "Calendar/301 Daily/" }`
— with a space before the closing `}`. install-tomo.sh extracted the path with
`... | tr -d '{}' | sed 's/^ *//'`: `tr -d '{}'` deletes the `}` but leaves the
space in front of it, and the final sed only stripped LEADING whitespace, so the
value became `Calendar/301 Daily/ ` (trailing space). That landed verbatim in
every miyo install's vault-config.yaml, breaking daily-note path resolution. The
fix strips both leading AND trailing whitespace.

These tests pull the live extraction pipeline out of install-tomo.sh (so they
cannot drift from the source) and run it against the real miyo profile.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install-tomo.sh"
MIYO_PROFILE = REPO_ROOT / "tomo" / "profiles" / "miyo.yaml"


def _extract_pipeline() -> str:
    """Return the body of the `CALENDAR_DAILY_PATH=$(...)` command substitution."""
    text = INSTALL_SH.read_text()
    m = re.search(r"CALENDAR_DAILY_PATH=\$\((.*?)\)", text, re.DOTALL)
    assert m, "CALENDAR_DAILY_PATH extraction not found in install-tomo.sh"
    return m.group(1)


def _run_extraction(profile_path: Path) -> str:
    """Run the real extraction pipeline against a profile, return the value."""
    body = _extract_pipeline()
    script = (
        f'PROFILE_FILE="{profile_path}"\n'
        f"CALENDAR_DAILY_PATH=$({body})\n"
        f'printf %s "$CALENDAR_DAILY_PATH"\n'
    )
    r = subprocess.run(
        ["bash", "-c", script],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_daily_path_has_no_surrounding_whitespace():
    """The extracted daily path must not carry leading/trailing whitespace."""
    out = _run_extraction(MIYO_PROFILE)
    assert out == out.strip(), (
        f"daily path has surrounding whitespace (the bug): {out!r}"
    )


def test_daily_path_matches_profile_value():
    """The extracted daily path equals the profile's declared value, untrimmed-clean."""
    out = _run_extraction(MIYO_PROFILE)
    assert out == "Calendar/301 Daily/", f"unexpected daily path: {out!r}"


def test_internal_space_is_preserved():
    """Trimming must not eat the legitimate internal space in '301 Daily'."""
    out = _run_extraction(MIYO_PROFILE)
    assert "301 Daily" in out, f"internal space lost: {out!r}"
