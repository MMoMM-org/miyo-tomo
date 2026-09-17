#!/usr/bin/env python3
# version: 0.1.0
"""test_resolve_daily_path.py — Tests for `_resolve_daily_path`'s config hardening.

Standalone bug fix (not a spec task): vault-config `concepts.calendar.
granularities.daily.path` values sometimes carry trailing whitespace after a
trailing slash (e.g. `"Calendar/301 Daily/ "`). The old `.rstrip("/")`
fallback left the slash in place because a space sat after it, producing a
malformed double-separator path (`Calendar/301 Daily/ /2026-09-15.md`) that
never matches a real vault note — every daily note then reads as missing.

`shared-ctx-builder.py` already established the intent that config-derived
path values are not trusted and must be defensively normalised.
`_resolve_daily_path` is the site that never got the same treatment.

Covers the fallback branch (no `daily_note_path` supplied) across the shapes
a real config value can take, plus one pin on the already-`.strip()`ed
`daily_note_path` branch.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.X` works

from lib.render_actions import _resolve_daily_path  # noqa: E402

EXPECTED = "Calendar/301 Daily/2026-09-15.md"


@pytest.mark.parametrize(
    "daily_path_cfg",
    [
        pytest.param("Calendar/301 Daily/", id="happy-path-trailing-slash"),
        pytest.param("Calendar/301 Daily", id="no-trailing-slash"),
        pytest.param("Calendar/301 Daily/ ", id="live-bug-trailing-space-after-slash"),
        pytest.param("Calendar/301 Daily ", id="trailing-space-no-slash"),
        pytest.param(" Calendar/301 Daily/ ", id="leading-and-trailing-whitespace"),
        pytest.param("Calendar/301 Daily//", id="doubled-trailing-slash"),
        pytest.param("Calendar/301 Daily / / ", id="mixed-trailing-slashes-and-spaces"),
    ],
)
def test_resolve_daily_path_normalises_config_value(daily_path_cfg: str) -> None:
    assert _resolve_daily_path(daily_path_cfg, "2026-09-15", None) == EXPECTED


@pytest.mark.parametrize("daily_path_cfg", ["", None])
def test_resolve_daily_path_falls_back_to_default_without_crash(daily_path_cfg) -> None:
    result = _resolve_daily_path(daily_path_cfg, "2026-09-15", None)
    assert result == EXPECTED


def test_resolve_daily_path_prefers_already_stripped_daily_note_path() -> None:
    # Regression guard, not a fix: this branch already `.strip()`s its input.
    result = _resolve_daily_path(
        "Calendar/301 Daily/", "2026-09-15", " Calendar/301 Daily/2026-09-15 "
    )
    assert result == EXPECTED
