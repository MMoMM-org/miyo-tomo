#!/usr/bin/env python3
# version: 0.1.0
"""test_update_tomo_sync_gaps.py — update-tomo.sh delivers what install-tomo.sh
delivers, and retires what the source tree dropped.

Verifies:
- skill support files beyond SKILL.md (e.g. obsidian-bases/references/) are
  created on a fresh instance and refreshed when they drift
- every file removed from the source tree that the retire lists name is deleted
  from an instance that still holds it
- every versioned runtime Python file carries a `# version:` header, so the
  version gate can see its changes

All tests run in an isolated tmpdir with an isolated registry; they never touch
~/.tomo or tomo-instance/.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
UPDATER = REPO_ROOT / "scripts" / "update-tomo.sh"
SKILLS_SRC = REPO_ROOT / "tomo" / "dot_claude" / "skills"

SKILL_SUPPORT_REL = "obsidian-bases/references/FUNCTIONS_REFERENCE.md"

STALE_FILES = [
    ".claude/commands/tomo-tag-handler-wizard.md",
    ".claude/skills/tomo-daily-log-wizard.md",
    ".claude/skills/tomo-trackers-wizard.md",
    ".claude/scripts/file-suggestion-v2.sh",
    "scripts/state-scanner.py",
]


def _make_minimal_instance(root: Path, name: str) -> tuple[Path, Path]:
    """Create a stub instance at <root>/<name>/; return (instance_path, config_path)."""
    inst_root = root / name
    instance_path = inst_root / "instance"
    home_dir = inst_root / "home"
    for d in (instance_path, home_dir):
        d.mkdir(parents=True, exist_ok=True)

    config = {
        "instancePath": str(instance_path),
        "instanceName": name,
        "instanceLocation": str(inst_root),
        "homePath": str(home_dir),
        "launcherPath": str(inst_root / "begin-tomo.sh"),
        "repoPath": str(REPO_ROOT),
        "tomoVersion": "0.0.0",
        "updatedAt": "2026-01-01T00:00:00Z",
        "voice": {"enabled": False, "model": "", "language": ""},
        "ide_bridge": {"enabled": False, "auth_token": "", "port": 23027},
    }
    config_path = inst_root / "tomo-install.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return instance_path, config_path


def _run_update(tmp_path: Path, config_file: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["TOMO_REGISTRY_FILE"] = str(tmp_path / "instances.json")
    args = ["bash", str(UPDATER), "--keep-voice", "--yes", "--config-file", str(config_file)]
    result = subprocess.run(args, capture_output=True, text=True, env=env, timeout=60)
    assert result.returncode == 0, (
        f"update-tomo.sh failed (exit {result.returncode}):\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    return result


def test_skill_support_file_created_on_fresh_instance(tmp_path: Path) -> None:
    instance_path, config_file = _make_minimal_instance(tmp_path, "fresh")
    dst = instance_path / ".claude" / "skills" / SKILL_SUPPORT_REL

    _run_update(tmp_path, config_file)

    assert dst.read_bytes() == (SKILLS_SRC / SKILL_SUPPORT_REL).read_bytes()


def test_drifted_skill_support_file_is_refreshed(tmp_path: Path) -> None:
    instance_path, config_file = _make_minimal_instance(tmp_path, "drifted")
    dst = instance_path / ".claude" / "skills" / SKILL_SUPPORT_REL
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("stale reference content\n", encoding="utf-8")

    _run_update(tmp_path, config_file)

    assert dst.read_bytes() == (SKILLS_SRC / SKILL_SUPPORT_REL).read_bytes()


@pytest.mark.parametrize("rel", STALE_FILES)
def test_removed_source_file_is_retired(tmp_path: Path, rel: str) -> None:
    instance_path, config_file = _make_minimal_instance(tmp_path, "stale")
    stale = instance_path / rel
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("left over from an old install\n", encoding="utf-8")

    _run_update(tmp_path, config_file)

    assert not stale.exists(), f"{rel} survived update-tomo — missing from a RETIRED_* list"


def test_runtime_python_files_carry_version_header() -> None:
    scripts = REPO_ROOT / "tomo" / "scripts"
    missing = [
        str(p.relative_to(REPO_ROOT))
        for p in sorted([*scripts.glob("*.py"), *scripts.glob("lib/*.py")])
        # Mirrors get_version(): first `# version:` line anywhere in the file.
        if not any(line.startswith("# version:") for line in p.read_text(encoding="utf-8").splitlines())
    ]
    assert not missing, f"version-gated files without '# version:' header (never re-synced): {missing}"
