#!/usr/bin/env python3
# version: 0.1.0
"""test_install_gitignore_template.py — installing must not run `git init`.

The instance .gitignore comment names `git init` in backticks inside an unquoted
heredoc, so bash ran it in the caller's working directory on every install. A
nested .git is what caused the 2026-04-20 instance wipe.

The install runs with a temporary HOME, registry, config file and instance
location, from an empty working directory.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install-tomo.sh"


def _install(tmp_path: Path) -> tuple[subprocess.CompletedProcess, Path]:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "TOMO_REGISTRY_FILE": str(tmp_path / "registry.json"),
    }
    result = subprocess.run(
        [
            "bash", str(INSTALL_SH),
            "--vault", str(vault),
            "--profile", "lyt",
            "--non-interactive",
            "--instance-location", str(tmp_path / "instances"),
            "--instance-name", "isolated",
            "--home-dir", str(tmp_path / "tomo-home"),
            "--config-file", str(tmp_path / "tomo-install.json"),
        ],
        capture_output=True, text=True, timeout=60, cwd=cwd, env=env,
    )
    return result, cwd


def test_install_leaves_the_working_directory_alone(tmp_path):
    result, cwd = _install(tmp_path)
    assert result.returncode == 0, result.stderr
    assert list(cwd.iterdir()) == []


def test_gitignore_keeps_the_literal_comment(tmp_path):
    result, _ = _install(tmp_path)
    assert result.returncode == 0, result.stderr
    gitignore = next((tmp_path / "instances").rglob(".gitignore")).read_text()
    assert "If you `git init` here" in gitignore
    assert ".mcp.json" in gitignore
