#!/usr/bin/env python3
# version: 0.1.0
"""test_tomo_note_view_mod.py — the tomo-note-view mod ships whole (spec 044 T4.5, F4-AC5).

Verifies:
- the mod's files exist in the source tree, with the manifest folder stored as
  dot_claude-plugin/ and no generated .claude-plugin/ or types/ tracked
- plugin.json names the mod, and its version agrees with the `// version:`
  line of register.tsx and the Version line of the WHY doc
- the hooks module reads the view file note-instructions.py writes and
  registers /note-draft
- install-tomo.sh and update-tomo.sh deliver it into an instance as
  .claude/skills/tomo-note-view/.claude-plugin/plugin.json plus its hooks, with
  no dot_claude-plugin/ left and no types/ copied; update refreshes a drifted
  manifest

The installer and updater run fully isolated in tmp_path with an isolated
registry; they never touch ~/.tomo, tomo-instance/ or tomo-privat.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
MOD = REPO_ROOT / "tomo" / "dot_claude" / "skills" / "tomo-note-view"
WHY_DOC = REPO_ROOT / "docs" / "tomo" / "dot_claude" / "skills" / "tomo-note-view.md"
INSTALLER = REPO_ROOT / "scripts" / "install-tomo.sh"
UPDATER = REPO_ROOT / "scripts" / "update-tomo.sh"
SHIPPED = ["dot_claude-plugin/plugin.json", "hooks/hooks.json", "hooks/register.tsx",
           "types/index.d.ts"]
INSTALLED = [".claude-plugin/plugin.json", "hooks/hooks.json", "hooks/register.tsx",
             "types/index.d.ts"]

sys.path.insert(0, str(REPO_ROOT / "tomo" / "scripts"))
from lib import note_meta  # noqa: E402


def _manifest() -> dict:
    return json.loads((MOD / "dot_claude-plugin" / "plugin.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("rel", SHIPPED)
def test_mod_file_exists(rel):
    assert (MOD / rel).is_file(), rel


def test_mod_has_a_plugin_test():
    assert list((MOD / "tests").glob("*.test.tsx")), "no *.test.tsx for claude plugin test"


def test_manifest_names_the_mod_and_its_contract():
    manifest = _manifest()
    assert manifest["name"] == "tomo-note-view"
    assert manifest["types"] == "./types/index.d.ts"
    assert json.loads((MOD / "hooks" / "hooks.json").read_text(encoding="utf-8")) == {
        "modules": ["./register.tsx"]}


def test_versions_agree():
    version = _manifest()["version"]
    register = (MOD / "hooks" / "register.tsx").read_text(encoding="utf-8")
    assert re.search(r"^// version: (\S+)$", register, re.M).group(1) == version
    why = WHY_DOC.read_text(encoding="utf-8")
    assert re.search(r"^> Version: (\S+) ", why, re.M).group(1) == version


def test_hooks_read_the_view_file_the_script_writes():
    register = (MOD / "hooks" / "register.tsx").read_text(encoding="utf-8")
    view = (note_meta.STAGE_ROOT / "view.md").as_posix()
    assert f"'{view}'" in register
    assert "'note-draft'" in register and "'AskUserQuestion'" in register


def test_no_generated_manifest_or_types_are_tracked():
    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", str(MOD.relative_to(REPO_ROOT))],
        capture_output=True, text=True, check=True).stdout.split()
    assert not [p for p in tracked if "/.claude-plugin/" in p or "/dot_claude-plugin/types/" in p]


@pytest.mark.parametrize("rel", [".claude-plugin/types/claude-code/index.d.ts",
                                 "dot_claude-plugin/types/claude-code/index.d.ts"])
def test_generated_types_are_gitignored(rel):
    path = (MOD / rel).relative_to(REPO_ROOT)
    res = subprocess.run(["git", "-C", str(REPO_ROOT), "check-ignore", "-q", str(path)])
    assert res.returncode == 0, f"{path} is not gitignored"


# ── delivery ─────────────────────────────────────────────────────────────


def _assert_delivered(instance: Path) -> None:
    skill = instance / ".claude" / "skills" / "tomo-note-view"
    for src, dst in zip(SHIPPED, INSTALLED):
        assert (skill / dst).read_bytes() == (MOD / src).read_bytes(), dst
    assert not (skill / "dot_claude-plugin").exists()
    assert not (skill / ".claude-plugin" / "types").exists()


def _isolated_update(tmp_path: Path, name: str) -> tuple[Path, Path]:
    root = tmp_path / name
    instance, home = root / "instance", root / "home"
    instance.mkdir(parents=True)
    home.mkdir()
    config = root / "tomo-install.json"
    config.write_text(json.dumps({
        "instancePath": str(instance), "instanceName": name,
        "instanceLocation": str(root), "homePath": str(home),
        "launcherPath": str(root / "begin-tomo.sh"), "repoPath": str(REPO_ROOT),
        "tomoVersion": "0.0.0", "updatedAt": "2026-01-01T00:00:00Z",
        "voice": {"enabled": False, "model": "", "language": ""},
        "ide_bridge": {"enabled": False, "auth_token": "", "port": 23027},
    }), encoding="utf-8")
    return instance, config


def _run_update(tmp_path: Path, config: Path) -> None:
    env = os.environ.copy()
    env["TOMO_REGISTRY_FILE"] = str(tmp_path / "instances.json")
    res = subprocess.run(["bash", str(UPDATER), "--keep-voice", "--yes",
                          "--config-file", str(config)],
                         capture_output=True, text=True, env=env, timeout=120)
    assert res.returncode == 0, res.stdout + res.stderr


def test_update_delivers_the_mod(tmp_path):
    instance, config = _isolated_update(tmp_path, "fresh")
    _run_update(tmp_path, config)
    _assert_delivered(instance)


def test_update_refreshes_a_drifted_manifest(tmp_path):
    instance, config = _isolated_update(tmp_path, "drifted")
    manifest = instance / ".claude" / "skills" / "tomo-note-view" / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text('{"name": "tomo-note-view", "version": "0.0.0"}\n', encoding="utf-8")
    _run_update(tmp_path, config)
    _assert_delivered(instance)


def test_install_delivers_the_mod(tmp_path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    loc = tmp_path / "loc"
    loc.mkdir()
    env = os.environ.copy()
    env["TOMO_REGISTRY_FILE"] = str(tmp_path / "instances.json")
    res = subprocess.run(
        ["bash", str(INSTALLER), "--vault", str(vault), "--profile", "miyo",
         "--kado-token", "kado_test", "--instance-location", str(loc),
         "--instance-name", "note-view", "--home-dir", str(tmp_path / "home"),
         "--config-file", str(tmp_path / "tomo-install.json"), "--non-interactive"],
        capture_output=True, text=True, env=env, timeout=300)
    assert res.returncode == 0, res.stdout + res.stderr
    _assert_delivered(loc / "note-view" / "instance")
