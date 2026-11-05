#!/usr/bin/env python3
# version: 0.1.0
"""test_note_processes_survive.py — update-tomo.sh leaves config/note-processes/ alone
(spec 044 F7-AC12).

The process files of /note are user-owned: no source file maps to them, so a
sync must neither overwrite, retire nor delete them, with or without --force.
backup then restore is covered in test_backup_restore_instance.py.

Isolation: the instance, its home, the registry (TOMO_REGISTRY_FILE) and HOME
all live in tmp_path; the instance starts empty so the version-gated sync has
files to create, and the test asserts it did. The real ~/.tomo/instances.json,
when present, is compared byte for byte before and after (read only).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
UPDATER = REPO_ROOT / "scripts" / "update-tomo.sh"
REAL_REGISTRY = Path.home() / ".tomo" / "instances.json"
SYNCED_SCRIPT = "scripts/note-process.py"

PROCESS_FILES = {
    "t_meeting.md": "---\ndestination: Atlas/Meetings/\nrequired:\n- Agenda\n---\nAsk first.\n",
    "t_problem.md": "---\noffer: never\n---\n",
    "t_réunion.md": "---\ndestination: Atlas/Réunions/\n---\n",
}


def _registry_bytes() -> bytes | None:
    return REAL_REGISTRY.read_bytes() if REAL_REGISTRY.is_file() else None


@pytest.fixture(autouse=True, scope="module")
def real_registry_untouched():
    before = _registry_bytes()
    yield
    assert _registry_bytes() == before, "~/.tomo/instances.json changed during the tests"


def _make_instance(root: Path) -> tuple[Path, Path]:
    """An empty instance with process files; returns (instance path, config file)."""
    instance = root / "instance"
    home = root / "home"
    (instance / ".claude" / "agents").mkdir(parents=True)
    home.mkdir()
    folder = instance / "config" / "note-processes"
    folder.mkdir(parents=True)
    for name, text in PROCESS_FILES.items():
        (folder / name).write_bytes(text.encode("utf-8"))
    config = {
        "instancePath": str(instance), "instanceName": "t27-survive",
        "instanceLocation": str(root), "homePath": str(home),
        "launcherPath": str(root / "begin-tomo.sh"), "repoPath": str(REPO_ROOT),
        "tomoVersion": "0.0.0", "updatedAt": "2026-01-01T00:00:00Z",
        "lifecyclePrefix": "tomo", "vault": str(root / "vault"), "profile": "miyo",
        "kado": {"host": "127.0.0.1", "port": 23026, "token": "tok"},
        "voice": {"enabled": False, "model": "", "language": ""},
        "ide_bridge": {"enabled": False, "auth_token": "", "port": 23027},
    }
    config_file = root / "tomo-install.json"
    config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return instance, config_file


def _run_update(root: Path, config_file: Path, *extra: str) -> subprocess.CompletedProcess:
    fake_home = root / "fake-home"
    fake_home.mkdir(exist_ok=True)
    env = {**os.environ, "HOME": str(fake_home),
           "TOMO_REGISTRY_FILE": str(root / "registry" / "instances.json")}
    return subprocess.run(
        ["bash", str(UPDATER), "--yolo", "--config-file", str(config_file), *extra],
        capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL, timeout=120)


def _snapshot(folder: Path) -> dict:
    return {p.name: p.read_bytes() for p in folder.iterdir()}


@pytest.mark.parametrize("extra", [(), ("--force",)], ids=["plain", "force"])
def test_update_tomo_leaves_note_processes_unchanged(tmp_path, extra):
    instance, config_file = _make_instance(tmp_path)
    folder = instance / "config" / "note-processes"
    before = _snapshot(folder)

    res = _run_update(tmp_path, config_file, *extra)

    assert res.returncode == 0, f"stdout:\n{res.stdout}\nstderr:\n{res.stderr}"
    synced = instance / SYNCED_SCRIPT
    assert synced.read_bytes() == (REPO_ROOT / "tomo" / SYNCED_SCRIPT).read_bytes(), \
        "the sync did not run, so the test proves nothing"
    assert _snapshot(folder) == before
    assert "note-processes" not in res.stdout + res.stderr
