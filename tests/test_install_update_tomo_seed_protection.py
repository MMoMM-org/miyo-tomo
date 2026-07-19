#!/usr/bin/env python3
# version: 0.1.0
"""test_install_update_tomo_seed_protection.py — CON-4 create-only seed protection
for config/garden-audit-exclusions.yaml.

Verifies:
- update-tomo on a fresh instance CREATES config/garden-audit-exclusions.yaml
- update-tomo on an instance with a user-edited file PRESERVES it unchanged
  (seed is create-only — never overwritten by update)
- the file is never listed in the retire/delete sweep output

All tests operate in an isolated tmpdir and never touch the real instance at
~/.tomo or tomo-instance/. install-tomo.sh test isolation follows the same
pattern as test_install_multi_instance.py.

Spec: docs/XDD/specs/030-garden-audit/ — Phase 1 CON-4
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
UPDATER = REPO_ROOT / "scripts" / "update-tomo.sh"
REGISTRY_LIB = REPO_ROOT / "scripts" / "lib" / "instance-registry.sh"

SEED_DEST_REL = "config/garden-audit-exclusions.yaml"
SEED_SOURCE = REPO_ROOT / "tomo" / "config" / "garden-audit-exclusions.yaml"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_minimal_instance(root: Path, name: str) -> tuple[Path, Path]:
    """Create a minimal stub instance at <root>/<name>/.

    Returns (instance_path, config_path). Mirrors the pattern used in
    test_update_multi_instance.py for full isolation.
    """
    inst_root = root / name
    instance_path = inst_root / "instance"
    home_dir = inst_root / "home"
    launcher = inst_root / "begin-tomo.sh"

    for d in (instance_path, home_dir, inst_root / "instance" / ".claude" / "agents"):
        d.mkdir(parents=True, exist_ok=True)

    config = {
        "instancePath": str(instance_path),
        "instanceName": name,
        "instanceLocation": str(inst_root),
        "homePath": str(home_dir),
        "launcherPath": str(launcher),
        "repoPath": str(REPO_ROOT),
        "tomoVersion": "0.0.0",
        "updatedAt": "2026-01-01T00:00:00Z",
        "lifecyclePrefix": "tomo",
        "vault": "/tmp/test-vault",
        "profile": "miyo",
        "kado": {"host": "127.0.0.1", "port": 23026, "token": "tok"},
        "voice": {"enabled": False, "model": "", "language": ""},
        "ide_bridge": {"enabled": False, "auth_token": "", "port": 23027},
    }
    config_path = inst_root / "tomo-install.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    return instance_path, config_path


def _build_env(registry_file: Path) -> dict[str, str]:
    """Return an isolated subprocess env (registry + sandbox-safe TMPDIR)."""
    env = os.environ.copy()
    env["TOMO_REGISTRY_FILE"] = str(registry_file)
    if "TMPDIR" in os.environ:
        env["TMPDIR"] = os.environ["TMPDIR"]
    return env


def _run_update(
    registry_file: Path,
    config_file: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> subprocess.CompletedProcess:
    """Run update-tomo.sh with full isolation.

    Always passes --keep-voice --yes to suppress interactive prompts.
    """
    env = _build_env(registry_file)
    args = ["bash", str(UPDATER), "--keep-voice", "--yes", "--config-file", str(config_file)]
    if dry_run:
        args.append("--dry-run")
    if force:
        args.append("--force")
    return subprocess.run(args, capture_output=True, text=True, env=env, timeout=60)


# ---------------------------------------------------------------------------
# T1 — seed source file exists in the repo
# ---------------------------------------------------------------------------


def test_seed_source_file_exists() -> None:
    """The seed source file tomo/config/garden-audit-exclusions.yaml must exist."""
    assert SEED_SOURCE.exists(), (
        f"Seed source missing: {SEED_SOURCE}\n"
        "Create tomo/config/garden-audit-exclusions.yaml before running tests."
    )


# ---------------------------------------------------------------------------
# T2 — fresh instance: seed is CREATED
# ---------------------------------------------------------------------------


def test_update_creates_seed_on_fresh_instance(tmp_path: Path) -> None:
    """update-tomo on a fresh instance creates config/garden-audit-exclusions.yaml."""
    registry = tmp_path / "instances.json"
    instance_path, config_file = _make_minimal_instance(tmp_path, "fresh")

    seed_dest = instance_path / SEED_DEST_REL
    assert not seed_dest.exists(), "Pre-condition: seed must not exist yet"

    result = _run_update(registry, config_file)

    assert result.returncode == 0, (
        f"update-tomo.sh failed (exit {result.returncode}):\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert seed_dest.exists(), (
        f"Seed was not created at {seed_dest}.\n"
        f"update-tomo stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# T3 — user-edited instance: seed is PRESERVED
# ---------------------------------------------------------------------------


def test_update_preserves_user_edited_seed(tmp_path: Path) -> None:
    """update-tomo on an instance with a user-edited seed NEVER overwrites it."""
    registry = tmp_path / "instances.json"
    instance_path, config_file = _make_minimal_instance(tmp_path, "edited")

    # Pre-create the seed with user content distinct from the shipped default.
    seed_dest = instance_path / SEED_DEST_REL
    seed_dest.parent.mkdir(parents=True, exist_ok=True)
    user_content = "# USER EDITED\nversion: 1\nexclusions:\n  - pattern: MyPrivateNotes\n    reason: personal\n"
    seed_dest.write_text(user_content, encoding="utf-8")

    result = _run_update(registry, config_file)

    assert result.returncode == 0, (
        f"update-tomo.sh failed (exit {result.returncode}):\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    actual = seed_dest.read_text(encoding="utf-8")
    assert actual == user_content, (
        "update-tomo OVERWROTE the user-edited seed — CON-4 violated.\n"
        f"Expected:\n{user_content!r}\nGot:\n{actual!r}"
    )


# ---------------------------------------------------------------------------
# T4 — retire sweep: seed is NEVER listed for deletion
# ---------------------------------------------------------------------------


def test_seed_never_appears_in_retire_sweep(tmp_path: Path) -> None:
    """The retire sweep must not list config/garden-audit-exclusions.yaml for deletion."""
    registry = tmp_path / "instances.json"
    instance_path, config_file = _make_minimal_instance(tmp_path, "retire-check")

    # Pre-create the seed so the retire sweep has something to possibly delete.
    seed_dest = instance_path / SEED_DEST_REL
    seed_dest.parent.mkdir(parents=True, exist_ok=True)
    seed_dest.write_text("version: 1\nexclusions: []\n", encoding="utf-8")

    result = _run_update(registry, config_file, dry_run=True)

    assert result.returncode == 0, (
        f"update-tomo.sh (dry-run) failed:\n{result.stdout}\n{result.stderr}"
    )
    # The dry-run plan must not mark our seed for retirement.
    combined = result.stdout + result.stderr
    # No line mentioning the filename should also contain "retire".
    retire_lines = [
        line for line in combined.splitlines()
        if "garden-audit-exclusions" in line and "retire" in line.lower()
    ]
    assert not retire_lines, (
        "Found retire markers for garden-audit-exclusions:\n" + "\n".join(retire_lines)
    )
