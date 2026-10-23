#!/usr/bin/env python3
# version: 0.1.0
"""test_settings_permission_rules.py — the shipped instance settings.json holds
no path-scoped permission rule that Claude Code rejects at startup.

Claude Code matches file permissions only against Edit(path) rules; Edit covers
every file-editing tool, Write included. A Write(path) rule is ignored and
prints a warning on every container start (#184, #172).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SETTINGS = REPO_ROOT / "tomo" / "dot_claude" / "settings.json"

PATH_SCOPED_WRITE = re.compile(r"^Write\(.+\)$")


def _rules(kind: str) -> list[str]:
    return json.loads(SETTINGS.read_text(encoding="utf-8")).get("permissions", {}).get(kind, [])


def test_no_path_scoped_write_rules() -> None:
    offending = [r for kind in ("allow", "deny", "ask") for r in _rules(kind) if PATH_SCOPED_WRITE.match(r)]
    assert not offending, f"Write(path) rules are ignored by Claude Code — use Edit(path): {offending}"


def test_edit_rules_still_cover_tomo_write_targets() -> None:
    allow = set(_rules("allow"))
    for path in ("config/*", ".claude/*", "tomo-tmp/*"):
        assert f"Edit({path})" in allow, f"Edit({path}) missing — Tomo can no longer write {path}"
