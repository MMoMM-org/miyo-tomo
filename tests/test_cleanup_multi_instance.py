#!/usr/bin/env python3
# version: 0.1.0
"""test_cleanup_multi_instance.py — registry-aware cleanup-tomo.sh (#39 / D-11).

Post-spec-020 instances live OUTSIDE the repo. cleanup-tomo.sh v0.2 targets a
registered instance by name (~/.tomo/instances.json), defaults an outside-repo
target to a DRY RUN, deletes only with --force, and deregisters after.

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
    """Build a self-contained fake outside-repo instance under tmp_path.

    Layout mirrors a real post-020 install: <root>/{instance,home,begin-tomo.sh,
    tomo-install.json}. Returns the key paths.
    """
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


# ── dry-run is the default for an outside-repo instance ──────────────────────


def test_outside_repo_defaults_to_dry_run(tmp_path):
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))

    res = _run(reg, ["--instance", "tomo-privat"])
    assert res.returncode == 0, res.stderr
    assert "--force" in res.stdout  # tells the user how to actually delete
    # Nothing deleted; registry entry intact.
    assert p["instance"].exists()
    assert p["home"].exists()
    assert p["config"].exists()
    assert _resolve(reg, "tomo-privat").returncode == 0


def test_explicit_dry_run_deletes_nothing(tmp_path):
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))

    res = _run(reg, ["--instance", "tomo-privat", "--dry-run"])
    assert res.returncode == 0, res.stderr
    assert p["instance"].exists()


# ── --force actually deletes + deregisters ───────────────────────────────────


def test_force_deletes_and_deregisters(tmp_path):
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))

    res = _run(reg, ["--instance", "tomo-privat", "--force"])
    assert res.returncode == 0, res.stderr
    assert not p["instance"].exists()
    assert not p["home"].exists()
    assert not p["launcher"].exists()
    assert not p["config"].exists()
    # Deregistered.
    assert _resolve(reg, "tomo-privat").returncode != 0


def test_keep_home_preserves_credentials(tmp_path):
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))

    res = _run(reg, ["--instance", "tomo-privat", "--force", "--keep-home"])
    assert res.returncode == 0, res.stderr
    assert not p["instance"].exists()
    assert p["home"].exists()  # credentials preserved


# ── guard rails ──────────────────────────────────────────────────────────────


def test_unknown_instance_errors(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text('{"schema_version":1,"instances":[]}', encoding="utf-8")
    res = _run(reg, ["--instance", "ghost"])
    assert res.returncode == 1
    assert "Unknown instance" in res.stderr


def test_protected_path_refused(tmp_path):
    """If a target resolves to $HOME, the guard refuses and deletes nothing —
    exercised by pointing HOME at the instance dir (--force would otherwise
    delete it)."""
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))

    res = _run(reg, ["--instance", "tomo-privat", "--force"], home=str(p["instance"]))
    assert res.returncode == 1
    assert "protected path" in res.stderr
    assert p["instance"].exists()  # nothing deleted


def test_list_shows_registered_instance(tmp_path):
    reg = tmp_path / "reg.json"
    p = _make_instance(tmp_path)
    _seed_registry(reg, "tomo-privat", str(p["instance"]))
    res = _run(reg, ["--list"])
    assert res.returncode == 0, res.stderr
    assert "tomo-privat" in res.stdout


def test_missing_files_still_deregisters(tmp_path):
    """A registered instance whose files are already gone still gets
    deregistered (no stale registry entry)."""
    reg = tmp_path / "reg.json"
    ghost_path = tmp_path / "gone" / "instance"
    _seed_registry(reg, "tomo-privat", str(ghost_path))  # path never created
    res = _run(reg, ["--instance", "tomo-privat", "--force"])
    assert res.returncode == 0, res.stderr
    assert _resolve(reg, "tomo-privat").returncode != 0


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
