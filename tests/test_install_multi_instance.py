#!/usr/bin/env python3
# version: 0.1.0
"""test_install_multi_instance.py — Tests for the registry-driven instance
selection front-end in scripts/install-tomo.sh (Phase 2, T2.1).

Drives the installer via subprocess in --non-interactive mode with FULL
isolation flags so the test never touches the user's real
$REPO_ROOT/tomo-instance, tomo-home, or tomo-install.json. The registry is
isolated via TOMO_REGISTRY_FILE pointing into the test's tmpdir.

Scope: the SELECTION front-end only — does the installer route a fresh name
to "create", route a duplicate name to rejection, and proceed on a clean
first install. Path-layout and config-write/registry-upsert are T2.2/T2.3.

Spec: docs/XDD/specs/020-multi-instance-install/ — Phase 2 T2.1
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
INSTALLER = REPO_ROOT / "scripts" / "install-tomo.sh"
REGISTRY_LIB = REPO_ROOT / "scripts" / "lib" / "instance-registry.sh"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    return vault


def _seed_registry(registry_file: Path, name: str, path: str) -> None:
    """Pre-populate the isolated registry with one entry via the real lib."""
    path_dir = Path(path)
    path_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TOMO_REGISTRY_FILE"] = str(registry_file)
    script = (
        f'source "{REGISTRY_LIB}" && '
        f'registry_upsert "{name}" "{path}" "{REPO_ROOT}" "0.0.0"'
    )
    res = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, env=env
    )
    assert res.returncode == 0, res.stderr


def _run_install(
    tmp_path: Path,
    *,
    instance_name: str,
    registry_file: Path,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Run the installer fully isolated. Returns the completed process."""
    vault = _make_vault(tmp_path)
    loc = tmp_path / "loc"
    home = tmp_path / "home"
    config = tmp_path / "tomo-install.json"
    loc.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["TOMO_REGISTRY_FILE"] = str(registry_file)

    args = [
        "bash",
        str(INSTALLER),
        "--vault",
        str(vault),
        "--profile",
        "miyo",
        "--kado-token",
        "kado_test",
        "--instance-location",
        str(loc),
        "--instance-name",
        instance_name,
        "--home-dir",
        str(home),
        "--config-file",
        str(config),
        "--non-interactive",
    ]
    if extra_args:
        args.extend(extra_args)

    return subprocess.run(args, capture_output=True, text=True, env=env)


# ---------------------------------------------------------------------------
# No registry → first-instance create proceeds
# ---------------------------------------------------------------------------


def test_no_registry_first_install_proceeds(tmp_path: Path) -> None:
    """Empty/missing registry → install routes to create and completes."""
    registry = tmp_path / "instances.json"
    assert not registry.exists()

    result = _run_install(
        tmp_path, instance_name="tomo-instance", registry_file=registry
    )

    assert result.returncode == 0, result.stdout + result.stderr
    # The created instance directory exists at the isolated path.
    assert (tmp_path / "loc" / "tomo-instance").is_dir()


# ---------------------------------------------------------------------------
# One registered instance + create-new with a NEW name → routed to create
# ---------------------------------------------------------------------------


def test_create_new_name_with_existing_registry_proceeds(tmp_path: Path) -> None:
    """A registry with one entry + a fresh --instance-name → create proceeds."""
    registry = tmp_path / "instances.json"
    _seed_registry(registry, "existing-one", str(tmp_path / "existing-dir"))

    result = _run_install(
        tmp_path, instance_name="brand-new", registry_file=registry
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "loc" / "brand-new").is_dir()


# ---------------------------------------------------------------------------
# create-new with a DUPLICATE name, --non-interactive → non-zero + stderr
# ---------------------------------------------------------------------------


def test_duplicate_name_non_interactive_rejected(tmp_path: Path) -> None:
    """--instance-name that already exists, no --update → non-zero + clear stderr,
    and no heavy work (no instance dir created for the duplicate name)."""
    registry = tmp_path / "instances.json"
    _seed_registry(registry, "dupe", str(tmp_path / "dupe-dir"))

    result = _run_install(
        tmp_path, instance_name="dupe", registry_file=registry
    )

    assert result.returncode != 0
    assert "dupe" in result.stderr
    # Front-end rejected before creating anything under the isolated location.
    assert not (tmp_path / "loc" / "dupe").exists()


# ---------------------------------------------------------------------------
# --update on a known name → resolves the existing instance (update route)
# ---------------------------------------------------------------------------


def test_update_known_name_builds_at_registered_path(tmp_path: Path) -> None:
    """--update --instance-name <known> resolves the REGISTERED path, not the
    one --instance-location would produce.

    The registry entry lives under registered-location/, structurally distinct
    from the --instance-location (loc/) that _run_install passes. The update
    route must target the registered path; if the create route ran instead it
    would build under loc/kept and this test would fail.
    """
    registry = tmp_path / "instances.json"
    registered_path = tmp_path / "registered-location" / "kept"
    _seed_registry(registry, "kept", str(registered_path))

    result = _run_install(
        tmp_path,
        instance_name="kept",
        registry_file=registry,
        extra_args=["--update"],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    # The instance was provisioned at the REGISTERED path (update route)…
    assert (registered_path / "config" / "vault-config.yaml").is_file(), (
        "update did not build at the registered path:\n" + result.stdout
    )
    # …and NOT at the --instance-location path (which the create route uses).
    assert not (tmp_path / "loc" / "kept").exists(), (
        "create route ran instead of update — instance built under "
        "--instance-location"
    )


# ---------------------------------------------------------------------------
# --update on an UNKNOWN name → non-zero + stderr (nothing to update)
# ---------------------------------------------------------------------------


def test_update_unknown_name_rejected(tmp_path: Path) -> None:
    """--update with a name not in the registry → non-zero + clear stderr."""
    registry = tmp_path / "instances.json"
    _seed_registry(registry, "real", str(tmp_path / "real-dir"))

    result = _run_install(
        tmp_path,
        instance_name="ghost",
        registry_file=registry,
        extra_args=["--update"],
    )

    assert result.returncode != 0
    assert "ghost" in result.stderr
