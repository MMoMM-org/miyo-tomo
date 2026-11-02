#!/usr/bin/env python3
# version: 0.1.0
"""test_install_profile_choice.py — the installer offers only profiles it ships.

The `custom` choice wrote `profile: "custom"` without a profiles/custom.yaml, so
/inbox stopped with `profile not found` (#243). The choice is gone until custom
profiles are built properly (#248).

Every run gets a temporary HOME, registry and config file, and stops at the
profile step or at the end of its scripted stdin, before anything is installed.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install-tomo.sh"


def _run(tmp_path: Path, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True, exist_ok=True)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {
        **os.environ,
        "HOME": str(home),
        "TOMO_REGISTRY_FILE": str(tmp_path / "registry.json"),
    }
    return subprocess.run(
        [
            "bash", str(INSTALL_SH),
            "--vault", str(vault),
            "--instance-location", str(tmp_path / "instances"),
            "--instance-name", "isolated",
            "--home-dir", str(tmp_path / "tomo-home"),
            "--config-file", str(tmp_path / "tomo-install.json"),
            *args,
        ],
        capture_output=True, text=True, timeout=30, input=stdin, env=env,
    )


def _assert_nothing_installed(tmp_path: Path) -> None:
    assert not (tmp_path / "instances").exists()
    assert not (tmp_path / "tomo-install.json").exists()
    assert not (tmp_path / "registry.json").exists()


def test_help_names_only_shipped_profiles(tmp_path):
    r = _run(tmp_path, "--help")
    assert r.returncode == 0, r.stderr
    profile_line = next(l for l in r.stdout.splitlines() if "--profile NAME" in l)
    assert "(miyo, lyt)" in profile_line


def test_menu_does_not_offer_custom(tmp_path):
    r = _run(tmp_path, stdin="1\n")
    assert "1. miyo" in r.stdout
    assert "2. lyt" in r.stdout
    assert "custom" not in r.stdout


def test_menu_selects_a_shipped_profile(tmp_path):
    r = _run(tmp_path, stdin="2\n")
    assert "Profile: lyt" in r.stdout


def test_menu_rejects_the_old_custom_entries(tmp_path):
    for entry in ("3", "custom"):
        r = _run(tmp_path, stdin=f"{entry}\n")
        assert "Invalid choice. Enter 1, 2, miyo, or lyt." in r.stdout + r.stderr
        assert "Profile: " not in r.stdout


def test_custom_flag_fails_before_installing(tmp_path):
    r = _run(tmp_path, "--profile", "custom", "--non-interactive")
    assert r.returncode != 0
    assert "Profile not found" in r.stdout + r.stderr
    _assert_nothing_installed(tmp_path)
