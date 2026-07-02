#!/usr/bin/env python3
# version: 0.2.0
"""test_cleanup_multi_instance.py — registry-aware cleanup-tomo.sh (#39 / D-11).

v0.3 separates two operations:
  registry-only  — deregister from ~/.tomo/instances.json; never touch files.
  delete-disk    — also remove files; needs --force to skip the confirm.
Non-interactive runs default to the SAFE registry-only action. Interactive runs
(a TTY) get an r/d/N menu — not exercised here (subprocess has no TTY, so these
tests deterministically hit the non-interactive branch).

SAFETY: every test drives the script in --instance mode against a FAKE instance
built under the test's tmp_path, with the registry isolated via
TOMO_REGISTRY_FILE. Tests NEVER exercise the legacy no--instance path (which
targets the real repo-root instance) and never reference real filesystem paths.

Spec: docs/XDD/specs/020-multi-instance-install/ ; issue #39.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
CLEANUP = REPO_ROOT / "scripts" / "cleanup-tomo.sh"
REGISTRY_LIB = REPO_ROOT / "scripts" / "lib" / "instance-registry.sh"


def _make_instance(tmp_path: Path, name: str = "tomo-privat") -> dict:
    root = tmp_path / name
    inst = root / "instance"
    home = root / "home"
    (inst / ".claude").mkdir(parents=True)
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / ".credentials.json").write_text("{}", encoding="utf-8")
    launcher = root / "begin-tomo.sh"
    launcher.write_text("#!/bin/bash\n", encoding="utf-8")
    config = root / "tomo-install.json"
    config.write_text(json.dumps({
        "instancePath": str(inst),
        "homePath": str(home),
        "launcherPath": str(launcher),
    }), encoding="utf-8")
    return {"root": root, "instance": inst, "home": home,
            "launcher": launcher, "config": config}


def _seed_registry(registry_file: Path, name: str, inst_path: str) -> None:
    env = {**os.environ, "TOMO_REGISTRY_FILE": str(registry_file)}
    script = (
        f'source "{REGISTRY_LIB}" && '
        f'registry_upsert "{name}" "{inst_path}" "{REPO_ROOT}" "0.10.0"'
    )
    res = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)
    assert res.returncode == 0, res.stderr


def _resolve(registry_file: Path, name: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "TOMO_REGISTRY_FILE": str(registry_file)}
    return subprocess.run(
        ["bash", "-c", f'source "{REGISTRY_LIB}" && registry_resolve "{name}"'],
        capture_output=True, text=True, env=env,
    )


def _run(registry_file: Path, args: list[str], home: str | None = None):
    env = {**os.environ, "TOMO_REGISTRY_FILE": str(registry_file)}
    if home is not None:
        env["HOME"] = home
    return subprocess.run(
        ["bash", str(CLEANUP), *args], capture_output=True, text=True, env=env,
    )


# ── registry-only: deregister, never touch files ────────────────────────────


def test_registry_only_deregisters_keeps_files(tmp_path):
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))

    res = _run(reg, ["--instance", "tomo-privat", "--registry-only"])
    assert res.returncode == 0, res.stderr
    # Files untouched; entry gone; user told to delete manually.
    assert p["instance"].exists() and p["home"].exists() and p["config"].exists()
    assert _resolve(reg, "tomo-privat").returncode != 0
    assert "Delete these yourself" in res.stdout
    assert str(p["instance"]) in res.stdout


def test_noninteractive_default_is_registry_only(tmp_path):
    """No action flag + no TTY (subprocess) → safe registry-only, files kept."""
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))

    res = _run(reg, ["--instance", "tomo-privat"])
    assert res.returncode == 0, res.stderr
    assert p["instance"].exists()
    assert _resolve(reg, "tomo-privat").returncode != 0
    assert "registry-only" in res.stdout


# ── delete-disk: only with --force (non-interactive) ─────────────────────────


def test_delete_disk_force_removes_and_deregisters(tmp_path):
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))

    res = _run(reg, ["--instance", "tomo-privat", "--delete-disk", "--force"])
    assert res.returncode == 0, res.stderr
    assert not p["instance"].exists()
    assert not p["home"].exists()
    assert not p["launcher"].exists()
    assert not p["config"].exists()
    assert _resolve(reg, "tomo-privat").returncode != 0


def test_delete_disk_without_force_noninteractive_errors(tmp_path):
    """--delete-disk with no --force and no TTY must refuse and change nothing."""
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))

    res = _run(reg, ["--instance", "tomo-privat", "--delete-disk"])
    assert res.returncode == 1
    assert "without --force" in res.stderr
    assert p["instance"].exists()                       # nothing deleted
    assert _resolve(reg, "tomo-privat").returncode == 0  # still registered


def test_keep_home_with_delete_disk(tmp_path):
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))

    res = _run(reg, ["--instance", "tomo-privat", "--delete-disk", "--force", "--keep-home"])
    assert res.returncode == 0, res.stderr
    assert not p["instance"].exists()
    assert p["home"].exists()


# ── guard rails ──────────────────────────────────────────────────────────────


def test_protected_path_refused(tmp_path):
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))

    res = _run(reg, ["--instance", "tomo-privat", "--delete-disk", "--force"],
               home=str(p["instance"]))
    assert res.returncode == 1
    assert "protected path" in res.stderr
    assert p["instance"].exists()


def test_mutually_exclusive_flags(tmp_path):
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))
    res = _run(reg, ["--instance", "tomo-privat", "--registry-only", "--delete-disk"])
    assert res.returncode == 1
    assert "mutually exclusive" in res.stderr


def test_unknown_instance_errors(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text('{"schema_version":1,"instances":[]}', encoding="utf-8")
    res = _run(reg, ["--instance", "ghost", "--registry-only"])
    assert res.returncode == 1
    assert "Unknown instance" in res.stderr


def test_dry_run_changes_nothing(tmp_path):
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))
    res = _run(reg, ["--instance", "tomo-privat", "--delete-disk", "--force", "--dry-run"])
    assert res.returncode == 0, res.stderr
    assert p["instance"].exists()
    assert _resolve(reg, "tomo-privat").returncode == 0  # not deregistered either


def test_list_shows_registered_instance(tmp_path):
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))
    res = _run(reg, ["--list"])
    assert res.returncode == 0, res.stderr
    assert "tomo-privat" in res.stdout


def test_missing_files_registry_only_deregisters(tmp_path):
    reg = tmp_path / "reg.json"
    ghost = tmp_path / "gone" / "instance"
    _seed_registry(reg, "tomo-privat", str(ghost))
    res = _run(reg, ["--instance", "tomo-privat", "--registry-only"])
    assert res.returncode == 0, res.stderr
    assert _resolve(reg, "tomo-privat").returncode != 0


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
