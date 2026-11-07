"""Tests for tomo/scripts/read-config-field.py batch JSON reads of templates.note_include.

Spec 044 F1-AC5: while templates.note_include is absent, the batch read the
/note session start uses keeps working (key omitted, exit 0); once present it
comes back as a list.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "tomo" / "scripts" / "read-config-field.py"
FIELDS = "templates.note_include,templates.base_path,templates.mapping.daily,concepts.inbox"

BASE_CONFIG = """\
concepts:
  inbox: "100 Inbox/"
templates:
  base_path: "X/900 Support/Templates/"
  mapping:
    daily: "Daily Note.md"
"""


def _read_fields(tmp_path: Path, config_text: str) -> subprocess.CompletedProcess:
    cfg = tmp_path / "vault-config.yaml"
    cfg.write_text(config_text, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--config", str(cfg),
         "--fields", FIELDS, "--format", "json"],
        capture_output=True, text=True,
    )


def test_note_include_absent_is_omitted_and_exits_0(tmp_path):
    proc = _read_fields(tmp_path, BASE_CONFIG)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {
        "templates.base_path": "X/900 Support/Templates/",
        "templates.mapping.daily": "Daily Note.md",
        "concepts.inbox": "100 Inbox/",
    }


def test_note_include_present_is_returned_as_list(tmp_path):
    config = BASE_CONFIG + '  note_include:\n    - "t_*.md"\n    - "Meeting *.md"\n'
    proc = _read_fields(tmp_path, config)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["templates.note_include"] == ["t_*.md", "Meeting *.md"]
    assert result["templates.base_path"] == "X/900 Support/Templates/"
