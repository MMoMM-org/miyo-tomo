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
- `claude plugin validate` and `claude plugin test` pass on an
  installed-layout copy (skipped when ~/.local/bin/claude is absent or the
  environment refuses it; a failing plugin test fails)
- install-tomo.sh and update-tomo.sh deliver it into an instance as
  .claude/skills/tomo-note-view/.claude-plugin/plugin.json plus its hooks, with
  no dot_claude-plugin/ left and no types/ copied; update refreshes a drifted
  manifest; generated types planted in a throwaway copy of the source tree
  never reach the instance

The installer and updater run fully isolated in tmp_path with an isolated
registry; they never touch ~/.tomo, tomo-instance/ or tomo-privat.
"""
from __future__ import annotations

import json
import os
import re
import shutil
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


PLANTED_TYPES = "dot_claude-plugin/types/claude-code/index.d.ts"


def _source_copy_with_planted_types(tmp_path: Path) -> Path:
    """A throwaway repo copy (docker/, scripts/, tomo/) whose mod holds generated types."""
    root = tmp_path / "repo"
    for part in ("docker", "scripts", "tomo"):
        shutil.copytree(REPO_ROOT / part, root / part,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    planted = root / "tomo" / "dot_claude" / "skills" / "tomo-note-view" / PLANTED_TYPES
    planted.parent.mkdir(parents=True)
    planted.write_text("// generated by the engine\n", encoding="utf-8")
    return root


def _assert_no_types(instance: Path) -> None:
    skill = instance / ".claude" / "skills" / "tomo-note-view"
    assert (skill / ".claude-plugin" / "plugin.json").is_file()
    assert not (skill / ".claude-plugin" / "types").exists()
    assert not (skill / "dot_claude-plugin").exists()


def _isolated_update(tmp_path: Path, name: str, repo: Path = REPO_ROOT) -> tuple[Path, Path]:
    root = tmp_path / name
    instance, home = root / "instance", root / "home"
    instance.mkdir(parents=True)
    home.mkdir()
    config = root / "tomo-install.json"
    config.write_text(json.dumps({
        "instancePath": str(instance), "instanceName": name,
        "instanceLocation": str(root), "homePath": str(home),
        "launcherPath": str(root / "begin-tomo.sh"), "repoPath": str(repo),
        "tomoVersion": "0.0.0", "updatedAt": "2026-01-01T00:00:00Z",
        "voice": {"enabled": False, "model": "", "language": ""},
        "ide_bridge": {"enabled": False, "auth_token": "", "port": 23027},
    }), encoding="utf-8")
    return instance, config


def _run_update(tmp_path: Path, config: Path, updater: Path = UPDATER) -> None:
    env = os.environ.copy()
    env["TOMO_REGISTRY_FILE"] = str(tmp_path / "instances.json")
    res = subprocess.run(["bash", str(updater), "--keep-voice", "--yes",
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


def test_update_never_syncs_generated_types(tmp_path):
    repo = _source_copy_with_planted_types(tmp_path)
    instance, config = _isolated_update(tmp_path, "typed", repo)
    _run_update(tmp_path, config, repo / "scripts" / "update-tomo.sh")
    _assert_no_types(instance)


def _run_install(tmp_path: Path, installer: Path = INSTALLER) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    loc = tmp_path / "loc"
    loc.mkdir()
    env = os.environ.copy()
    env["TOMO_REGISTRY_FILE"] = str(tmp_path / "instances.json")
    res = subprocess.run(
        ["bash", str(installer), "--vault", str(vault), "--profile", "miyo",
         "--kado-token", "kado_test", "--instance-location", str(loc),
         "--instance-name", "note-view", "--home-dir", str(tmp_path / "home"),
         "--config-file", str(tmp_path / "tomo-install.json"), "--non-interactive"],
        capture_output=True, text=True, env=env, timeout=300)
    assert res.returncode == 0, res.stdout + res.stderr
    return loc / "note-view" / "instance"


def test_install_delivers_the_mod(tmp_path):
    _assert_delivered(_run_install(tmp_path))


def test_install_never_ships_generated_types(tmp_path):
    repo = _source_copy_with_planted_types(tmp_path)
    _assert_no_types(_run_install(tmp_path, repo / "scripts" / "install-tomo.sh"))


# ── the mod's own checks under the engine ────────────────────────────────

CLAUDE = Path.home() / ".local" / "bin" / "claude"
_ENV_ERRORS = ("EPERM", "Operation not permitted", "sandbox", "EACCES")


def _installed_layout(tmp_path: Path) -> Path:
    """Copy the mod as an instance holds it: dot_claude-plugin/ → .claude-plugin/."""
    dst = tmp_path / "tomo-note-view"
    shutil.copytree(MOD, dst, ignore=shutil.ignore_patterns(".claude-plugin"))
    (dst / "dot_claude-plugin").rename(dst / ".claude-plugin")
    shutil.rmtree(dst / ".claude-plugin" / "types", ignore_errors=True)
    return dst


def _engine(args: list[str]) -> subprocess.CompletedProcess:
    """Run the claude binary; skip when it is absent or the environment refuses it."""
    if not (CLAUDE.exists() and os.access(CLAUDE, os.X_OK)):
        pytest.skip(f"{CLAUDE} is absent or not executable")
    try:
        res = subprocess.run([str(CLAUDE), *args], capture_output=True, text=True, timeout=300)
    except PermissionError as exc:
        pytest.skip(f"claude could not start here: {exc}")
    output = res.stdout + res.stderr
    if res.returncode != 0 and any(word in output for word in _ENV_ERRORS) \
            and "(fail)" not in output and "✘ Validation" not in output:
        pytest.skip(f"claude refused by the environment: {output[-300:]}")
    return res


def test_claude_plugin_validate_passes(tmp_path):
    res = _engine(["plugin", "validate", str(_installed_layout(tmp_path))])
    assert res.returncode == 0, res.stdout + res.stderr
    assert "Validation passed" in res.stdout + res.stderr


def test_claude_plugin_test_passes(tmp_path):
    res = _engine(["plugin", "test", str(_installed_layout(tmp_path))])
    output = res.stdout + res.stderr
    assert res.returncode == 0, output
    assert re.search(r"^\s*0 fail$", output, re.M), output
    assert re.search(r"^\s*([1-9]\d*) pass$", output, re.M), output
