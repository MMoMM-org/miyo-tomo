#!/usr/bin/env python3
# version: 0.2.0
"""test_update_multi_instance.py — Tests for per-instance update selection in
scripts/update-tomo.sh (Phase 3, T3.1).

Drives update-tomo.sh as a subprocess with full isolation:
- TOMO_REGISTRY_FILE → tmp_path registry (never touches ~/.tomo)
- --config-file or --instance to resolve the target
- Each instance is a minimal stub with tomo-install.json + instance/ workspace

Scope: resolution and isolation — does --instance <name> resolve via the
registry and target ONLY that instance, leaving other instances byte-unchanged?
Includes non-dry-run isolation test against the real tomo/ source tree.

Spec: docs/XDD/specs/020-multi-instance-install/ — Phase 3 T3.1
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


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _seed_registry(registry_file: Path, name: str, instance_path: str) -> None:
    """Pre-populate the isolated registry with one entry via the real lib."""
    Path(instance_path).mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TOMO_REGISTRY_FILE"] = str(registry_file)
    script = (
        f'source "{REGISTRY_LIB}" && '
        f'registry_upsert "{name}" "{instance_path}" "{REPO_ROOT}" "0.0.0"'
    )
    res = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, env=env
    )
    assert res.returncode == 0, res.stderr


def _make_minimal_instance(root: Path, name: str) -> tuple[Path, Path]:
    """Create a minimal stub instance at <root>/<name>/.

    Returns (instance_path, config_path).
    - instance_path = <root>/<name>/instance (the workspace dir; registry path)
    - config_path   = <root>/<name>/tomo-install.json

    The stub tomo-install.json contains the minimum fields update-tomo.sh reads
    during config-resolution. The instance/ dir tree mirrors just enough of the
    real layout that the file-scan phase completes without errors.
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
    config_path.write_text(json.dumps(config, indent=2))

    return instance_path, config_path


def _build_env(registry_file: Path) -> dict[str, str]:
    """Return an isolated subprocess env with the given registry file and a
    sandbox-safe TMPDIR so mktemp inside the script writes to an allowed path
    (macOS uses _CS_DARWIN_USER_TEMP_DIR which ignores TMPDIR; -p overrides it).
    """
    env = os.environ.copy()
    env["TOMO_REGISTRY_FILE"] = str(registry_file)
    if "TMPDIR" in os.environ:
        env["TMPDIR"] = os.environ["TMPDIR"]
    return env


def _run_update(
    registry_file: Path,
    *,
    config_file: Path | None = None,
    instance_name: str | None = None,
    dry_run: bool = True,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Run update-tomo.sh with full isolation.

    Pass either config_file (explicit, test-friendly) or instance_name
    (registry-resolved). Always passes --keep-voice --yes to suppress prompts.
    Set dry_run=False for the execute phase (writes files to instance workspace).
    """
    env = _build_env(registry_file)
    args = ["bash", str(UPDATER), "--keep-voice", "--yes"]
    if dry_run:
        args.append("--dry-run")
    if config_file is not None:
        args += ["--config-file", str(config_file)]
    if instance_name is not None:
        args += ["--instance", instance_name]
    if extra_args:
        args.extend(extra_args)
    return subprocess.run(args, capture_output=True, text=True, env=env)


# ---------------------------------------------------------------------------
# --config-file: explicit path, test-friendly back-compat
# ---------------------------------------------------------------------------


def test_config_file_flag_resolves_and_exits_zero(tmp_path: Path) -> None:
    """--config-file <path> resolves the target config and exits 0 (dry-run)."""
    registry = tmp_path / "instances.json"
    _, config_a = _make_minimal_instance(tmp_path, "alpha")

    result = _run_update(registry, config_file=config_a)

    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Mutual exclusion: --instance + --config-file together → error
# ---------------------------------------------------------------------------


def test_instance_and_config_file_together_rejected(tmp_path: Path) -> None:
    """--instance and --config-file are mutually exclusive → exit 2 + stderr."""
    registry = tmp_path / "instances.json"
    instance_path_a, config_a = _make_minimal_instance(tmp_path, "alpha")
    _seed_registry(registry, "alpha", str(instance_path_a))

    result = _run_update(registry, instance_name="alpha", config_file=config_a)

    assert result.returncode == 2, (
        f"Expected exit 2, got {result.returncode}:\n{result.stdout}{result.stderr}"
    )
    assert "mutually exclusive" in (result.stderr + result.stdout), (
        f"Expected 'mutually exclusive' in output:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# --instance <name>: registry-driven resolution
# ---------------------------------------------------------------------------


def test_instance_flag_resolves_known_name(tmp_path: Path) -> None:
    """--instance <name> resolves via registry and exits 0 (dry-run)."""
    registry = tmp_path / "instances.json"
    instance_path_a, _ = _make_minimal_instance(tmp_path, "alpha")
    _seed_registry(registry, "alpha", str(instance_path_a))

    result = _run_update(registry, instance_name="alpha")

    assert result.returncode == 0, result.stdout + result.stderr


def test_instance_flag_unknown_name_exits_nonzero(tmp_path: Path) -> None:
    """--instance <name> with an unregistered name → non-zero + stderr."""
    registry = tmp_path / "instances.json"
    instance_path_a, _ = _make_minimal_instance(tmp_path, "alpha")
    _seed_registry(registry, "alpha", str(instance_path_a))

    result = _run_update(registry, instance_name="ghost")

    assert result.returncode != 0
    assert "ghost" in (result.stderr + result.stdout)


# ---------------------------------------------------------------------------
# Instance isolation (dry-run): --instance A resolves A, not B
# ---------------------------------------------------------------------------


def test_instance_flag_resolution_dry_run(tmp_path: Path) -> None:
    """--instance A resolves A's config; B's tomo-install.json is byte-unchanged.

    Uses --dry-run, so this tests the resolution path only — not write-isolation.
    See test_instance_flag_write_isolation_non_dry_run for the execute-phase check.
    """
    registry = tmp_path / "instances.json"
    instance_a, config_a = _make_minimal_instance(tmp_path, "alpha")
    instance_b, config_b = _make_minimal_instance(tmp_path, "beta")

    _seed_registry(registry, "alpha", str(instance_a))
    _seed_registry(registry, "beta", str(instance_b))

    before_b = config_b.read_bytes()

    result = _run_update(registry, instance_name="alpha")

    assert result.returncode == 0, result.stdout + result.stderr

    # B's config must be byte-identical — dry-run only touches A's resolution.
    after_b = config_b.read_bytes()
    assert after_b == before_b, (
        "update --instance alpha modified beta's tomo-install.json (dry-run)"
    )


# ---------------------------------------------------------------------------
# Instance isolation (non-dry-run): execute phase writes A only, B untouched
# ---------------------------------------------------------------------------


def test_instance_flag_write_isolation_non_dry_run(tmp_path: Path) -> None:
    """--instance A through the full execute phase writes into A's workspace and
    leaves B's tomo-install.json and instance/ workspace byte-identical.

    Uses the real tomo/ source tree (REPO_ROOT/tomo) so the full file-scan and
    execute phase runs without a stub source tree.

    Verifies:
    - A's tomo-install.json tomoVersion is updated (non-"0.0.0") after the run.
    - B's tomo-install.json is byte-identical to its pre-run state.
    - B's instance/ directory tree is byte-identical (no files written there).

    Mutation check: the before_b snapshot is compared byte-by-byte after; if
    update-tomo.sh wrote anything into B's instance dir, the dir-mtime changes
    and the file comparison catches any file-level writes.
    """
    registry = tmp_path / "instances.json"
    instance_a, config_a = _make_minimal_instance(tmp_path, "alpha")
    instance_b, config_b = _make_minimal_instance(tmp_path, "beta")

    _seed_registry(registry, "alpha", str(instance_a))
    _seed_registry(registry, "beta", str(instance_b))

    # Snapshot B's config and collect every file path inside B's instance dir.
    before_b_config = config_b.read_bytes()
    b_instance_dir = tmp_path / "beta" / "instance"
    before_b_files = {
        str(p.relative_to(b_instance_dir)): p.read_bytes()
        for p in b_instance_dir.rglob("*")
        if p.is_file()
    }

    # Run the full execute phase (no --dry-run) targeting only A.
    result = _run_update(registry, instance_name="alpha", dry_run=False)

    assert result.returncode == 0, (
        f"update --instance alpha (live) failed:\n{result.stdout}\n{result.stderr}"
    )

    # A's tomoVersion must have been refreshed — confirming execute phase ran.
    updated_cfg_a = json.loads(config_a.read_text())
    assert updated_cfg_a.get("tomoVersion") not in ("", "0.0.0", None), (
        f"A's tomoVersion was not updated after live run: {updated_cfg_a.get('tomoVersion')!r}"
    )

    # B's config must be byte-identical — the execute phase must not have touched it.
    after_b_config = config_b.read_bytes()
    assert after_b_config == before_b_config, (
        "update --instance alpha (live) modified beta's tomo-install.json"
    )

    # B's instance/ workspace must have no new files and no modified files.
    after_b_files = {
        str(p.relative_to(b_instance_dir)): p.read_bytes()
        for p in b_instance_dir.rglob("*")
        if p.is_file()
    }
    new_in_b = set(after_b_files) - set(before_b_files)
    assert not new_in_b, (
        f"update --instance alpha wrote new files into beta's instance/: {new_in_b}"
    )
    changed_in_b = {
        f for f in before_b_files if after_b_files.get(f) != before_b_files[f]
    }
    assert not changed_in_b, (
        f"update --instance alpha modified files in beta's instance/: {changed_in_b}"
    )


def test_two_instances_registered_both_selectable(tmp_path: Path) -> None:
    """Both instances can be independently targeted via --instance."""
    registry = tmp_path / "instances.json"
    instance_a, config_a = _make_minimal_instance(tmp_path, "one")
    instance_b, config_b = _make_minimal_instance(tmp_path, "two")

    _seed_registry(registry, "one", str(instance_a))
    _seed_registry(registry, "two", str(instance_b))

    result_a = _run_update(registry, instance_name="one")
    assert result_a.returncode == 0, result_a.stdout + result_a.stderr

    result_b = _run_update(registry, instance_name="two")
    assert result_b.returncode == 0, result_b.stdout + result_b.stderr


# ---------------------------------------------------------------------------
# Default fallback: no --instance, no --config-file → REPO_ROOT default
# ---------------------------------------------------------------------------


def test_no_instance_flag_falls_back_to_default_config(tmp_path: Path) -> None:
    """Without --instance or --config-file, the script falls back to the default
    $REPO_ROOT/tomo-install.json. When that file is absent the script exits 1
    with "No tomo-install.json found" — guarding single-instance back-compat.
    """
    registry = tmp_path / "instances.json"
    # Ensure no tomo-install.json exists at REPO_ROOT for this test.
    default_config = REPO_ROOT / "tomo-install.json"
    if default_config.exists():
        # Real install present — skip rather than assert exit 1 on a live system.
        import pytest  # noqa: PLC0415
        pytest.skip("REPO_ROOT/tomo-install.json exists — single-instance live system")

    result = subprocess.run(
        ["bash", str(UPDATER), "--keep-voice", "--yes", "--dry-run"],
        capture_output=True,
        text=True,
        env={**os.environ, "TOMO_REGISTRY_FILE": str(registry), "TMPDIR": os.environ.get("TMPDIR", "/tmp")},
    )
    assert result.returncode == 1, (
        f"Expected exit 1 (no config), got {result.returncode}:\n{result.stdout}{result.stderr}"
    )
    assert "tomo-install.json" in (result.stdout + result.stderr), (
        f"Expected 'tomo-install.json' in output:\n{result.stdout}{result.stderr}"
    )
