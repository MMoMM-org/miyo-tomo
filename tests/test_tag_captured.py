#!/usr/bin/env python3
# version: 0.1.0
"""test_tag_captured.py — Regression guard for tag-captured.py.

Ensures non-markdown paths (audio files, binaries, stray text) are
skipped BEFORE the Kado call rather than erroring with
VALIDATION_ERROR. The skip path was added 2026-04-22 after a voice-
disabled /inbox run hit 2× Kado VALIDATION_ERROR on `.m4a` paths that
had been marked `done` by inbox-analyst.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "tag-captured.py"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_script_module():
    spec = importlib.util.spec_from_file_location("tag_captured", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def state_file(tmp_path):
    """Write a state-file mixing .md (done) and .m4a (done) items."""
    path = tmp_path / "inbox-state.jsonl"
    entries = [
        {"stem": "Asahikawa", "path": "100 Inbox/Asahikawa.md", "status": "done",
         "run_id": "test"},
        {"stem": "memo-audio",
         "path": "100 Inbox/Apothekerpfädchen 11__2026-04-20 11:48:29.m4a",
         "status": "done", "run_id": "test"},
        {"stem": "Evergreen Notes", "path": "100 Inbox/Evergreen Notes.md",
         "status": "done", "run_id": "test"},
        {"stem": "welcome", "path": "100 Inbox/welcome.txt",
         "status": "done", "run_id": "test"},
    ]
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return path


def test_non_md_paths_are_skipped_before_kado_call(state_file, monkeypatch,
                                                    capsys, tmp_path):
    mod = _load_script_module()

    # Mock the KadoClient so no real network / vault access is attempted
    # for the .md entries. Our regression guard is about what DOESN'T get
    # passed through — the non-.md entries must never reach read_note().
    paths_read = []
    fake_client = MagicMock()

    def fake_read_note(path):
        paths_read.append(path)
        return {"content": "---\ntags: []\n---\n\nbody\n", "modified": None}

    def fake_write_note(path, content, expected_modified=None):
        return None

    fake_client.read_note.side_effect = fake_read_note
    fake_client.write_note.side_effect = fake_write_note

    monkeypatch.setattr(mod, "KadoClient", lambda: fake_client)

    # Dummy vault-config.yaml so load_tag_prefix doesn't crash
    cfg = tmp_path / "vault-config.yaml"
    cfg.write_text("lifecycle:\n  tag_prefix: TestPrefix\n")

    with monkeypatch.context() as m:
        m.setattr(sys, "argv",
                  ["tag-captured.py", "--state", str(state_file),
                   "--config", str(cfg)])
        rc = mod.main()

    # No errors should have occurred. Exit 0.
    assert rc == 0, f"expected exit 0, got {rc}"

    # Only .md paths hit Kado.
    for p in paths_read:
        assert p.lower().endswith(".md"), (
            f"Non-.md path leaked through to Kado: {p}"
        )

    # Both .md items should have been read.
    assert "100 Inbox/Asahikawa.md" in paths_read
    assert "100 Inbox/Evergreen Notes.md" in paths_read

    # Neither of the non-md items should have been read.
    assert not any(".m4a" in p for p in paths_read)
    assert not any(p.endswith(".txt") for p in paths_read)

    # stderr should explicitly log the skips
    err = capsys.readouterr().err
    assert "[skip]" in err
    assert ".m4a" in err or "memo-audio" in err
    assert "welcome" in err
    # And the summary should reflect the split
    assert "skipped_non_md=2" in err
    assert "errors=0" in err


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
