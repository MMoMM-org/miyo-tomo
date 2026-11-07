#!/usr/bin/env python3
# version: 0.1.0
"""test_container_home_settings.py — install-tomo.sh and update-tomo.sh enable
the "You should know" built-in plugin in the container home (#183).

Verifies, for both scripts:
- a home without settings.json gets one with the plugin enabled
- existing keys in the home settings.json survive the merge
- a user who turned the plugin off keeps it off
- update-tomo.sh leaves an unparseable settings.json untouched and fails

All tests run in an isolated tmpdir with an isolated registry; they never touch
~/.tomo, tomo-home/ or tomo-instance/.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
UPDATER = REPO_ROOT / "scripts" / "update-tomo.sh"
INSTALLER = REPO_ROOT / "scripts" / "install-tomo.sh"
PLUGIN = "cc-plugin-you-should-know@builtin"
USER_SETTINGS = {"theme": "custom:tomo-ai", "model": "opus", "enabledPlugins": {"other@x": True}}


def _env(tmp_path: Path) -> dict:
    env = os.environ.copy()
    env["TOMO_REGISTRY_FILE"] = str(tmp_path / "instances.json")
    return env


def _isolated_update(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "upd"
    instance, home = root / "instance", root / "home"
    instance.mkdir(parents=True)
    (home / ".claude").mkdir(parents=True)
    config = root / "tomo-install.json"
    config.write_text(json.dumps({
        "instancePath": str(instance), "instanceName": "upd",
        "instanceLocation": str(root), "homePath": str(home),
        "launcherPath": str(root / "begin-tomo.sh"), "repoPath": str(REPO_ROOT),
        "tomoVersion": "0.0.0", "updatedAt": "2026-01-01T00:00:00Z",
        "voice": {"enabled": False, "model": "", "language": ""},
        "ide_bridge": {"enabled": False, "auth_token": "", "port": 23027},
    }), encoding="utf-8")
    return home, config


def _run_update(tmp_path: Path, config: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(UPDATER), "--keep-voice", "--yes",
                           "--config-file", str(config)],
                          capture_output=True, text=True, env=_env(tmp_path), timeout=120)


def _run_install(tmp_path: Path, home: Path) -> None:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    loc = tmp_path / "loc"
    loc.mkdir()
    res = subprocess.run(
        ["bash", str(INSTALLER), "--vault", str(vault), "--profile", "miyo",
         "--kado-token", "kado_test", "--instance-location", str(loc),
         "--instance-name", "home-settings", "--home-dir", str(home),
         "--config-file", str(tmp_path / "tomo-install.json"), "--non-interactive"],
        capture_output=True, text=True, env=_env(tmp_path), timeout=300)
    assert res.returncode == 0, res.stdout + res.stderr


def _settings(home: Path) -> dict:
    return json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))


def _write_settings(home: Path, data: dict) -> None:
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".claude" / "settings.json").write_text(json.dumps(data), encoding="utf-8")


# ── update-tomo.sh ───────────────────────────────────────────────────────

def test_update_enables_the_plugin_in_a_home_without_settings(tmp_path):
    home, config = _isolated_update(tmp_path)
    res = _run_update(tmp_path, config)
    assert res.returncode == 0, res.stdout + res.stderr
    assert _settings(home)["enabledPlugins"][PLUGIN] is True


def test_update_keeps_existing_home_settings(tmp_path):
    home, config = _isolated_update(tmp_path)
    _write_settings(home, USER_SETTINGS)
    res = _run_update(tmp_path, config)
    assert res.returncode == 0, res.stdout + res.stderr
    settings = _settings(home)
    assert settings["theme"] == "custom:tomo-ai"
    assert settings["model"] == "opus"
    assert settings["enabledPlugins"] == {"other@x": True, PLUGIN: True}


def test_update_keeps_the_plugin_off_when_the_user_turned_it_off(tmp_path):
    home, config = _isolated_update(tmp_path)
    _write_settings(home, {"enabledPlugins": {PLUGIN: False}})
    res = _run_update(tmp_path, config)
    assert res.returncode == 0, res.stdout + res.stderr
    assert _settings(home)["enabledPlugins"][PLUGIN] is False


def test_update_leaves_an_unparseable_home_settings_untouched(tmp_path):
    home, config = _isolated_update(tmp_path)
    broken = home / ".claude" / "settings.json"
    broken.write_text("{ not json", encoding="utf-8")
    res = _run_update(tmp_path, config)
    assert res.returncode == 1, res.stdout + res.stderr
    assert broken.read_text(encoding="utf-8") == "{ not json"
    assert "home settings.json  not valid JSON" in res.stdout + res.stderr


# ── install-tomo.sh ──────────────────────────────────────────────────────

def test_install_enables_the_plugin_in_a_new_home(tmp_path):
    home = tmp_path / "home"
    _run_install(tmp_path, home)
    assert _settings(home)["enabledPlugins"][PLUGIN] is True


def test_install_keeps_existing_home_settings(tmp_path):
    home = tmp_path / "home"
    _write_settings(home, {**USER_SETTINGS, "enabledPlugins": {PLUGIN: False}})
    _run_install(tmp_path, home)
    settings = _settings(home)
    assert settings["theme"] == "custom:tomo-ai"
    assert settings["model"] == "opus"
    assert settings["enabledPlugins"] == {PLUGIN: False}
