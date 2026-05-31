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

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
INSTALLER = REPO_ROOT / "scripts" / "install-tomo.sh"
REGISTRY_LIB = REPO_ROOT / "scripts" / "lib" / "instance-registry.sh"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True, exist_ok=True)
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
    pin_home_config: bool = True,
    parent: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run the installer fully isolated. Returns the completed process.

    By default pins --home-dir/--config-file to explicit tmp paths (the T2.1
    isolation contract). Set ``pin_home_config=False`` to exercise the T2.2
    DERIVED layout, where only the parent (--instance-location) is supplied and
    home/config fall out as <parent>/<name>/home and
    <parent>/<name>/tomo-install.json.

    ``parent`` overrides the parent dir (defaults to ``tmp_path/loc``); used to
    share one parent across two installs (cross-instance clobber check).
    """
    vault = _make_vault(tmp_path)
    loc = parent if parent is not None else tmp_path / "loc"
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
    ]
    if pin_home_config:
        args += ["--home-dir", str(home), "--config-file", str(config)]
    args.append("--non-interactive")
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
    # The created workspace (instance/) exists at the isolated path.
    assert (tmp_path / "loc" / "tomo-instance" / "instance").is_dir()


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
    assert (tmp_path / "loc" / "brand-new" / "instance").is_dir()


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
    one --instance-location would produce, and derives home/launcher at the
    correct instance ROOT level.

    The registry stores the INSTANCE dir path including the `/instance` suffix
    (the ADR-2 convention that T2.3's registry_upsert writes), structurally
    distinct from the --instance-location (loc/) that _run_install passes. The
    update route must (a) build the instance at the registered path and (b)
    reconcile the instance ROOT = dirname(registered_path) so home/ and
    begin-tomo.sh land one level up — NOT two (off-by-one dirname bug).

    Runs with pin_home_config=False so HOME_DIR/CONFIG_FILE DERIVE from the
    reconciled root; passing --home-dir/--config-file would pin them and hide
    the derivation bug this test guards.
    """
    registry = tmp_path / "instances.json"
    # Registry stores <root>/instance — the real convention.
    instance_root = tmp_path / "registered-location" / "kept"
    registered_path = instance_root / "instance"
    _seed_registry(registry, "kept", str(registered_path))

    result = _run_install(
        tmp_path,
        instance_name="kept",
        registry_file=registry,
        extra_args=["--update"],
        pin_home_config=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    # The instance was provisioned at the REGISTERED path (update route)…
    assert (registered_path / "config" / "vault-config.yaml").is_file(), (
        "update did not build at the registered path:\n" + result.stdout
    )
    # …home/ and begin-tomo.sh derive at the reconciled ROOT (…/kept), proving
    # INSTANCE_ROOT = dirname(registered_path) and not one level too shallow.
    assert (instance_root / "home").is_dir(), (
        "home/ not at instance root — off-by-one dirname in update route:\n"
        + result.stdout
    )
    assert (instance_root / "begin-tomo.sh").is_file(), (
        "begin-tomo.sh not at instance root — off-by-one dirname in update "
        "route:\n" + result.stdout
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


# ---------------------------------------------------------------------------
# T2.2 — self-contained per-instance path layout (derived from parent)
# ---------------------------------------------------------------------------


def test_derived_layout_produces_self_contained_instance(tmp_path: Path) -> None:
    """create-new with only the parent (--instance-location) supplied derives a
    self-contained <parent>/<name>/ holding instance/, home/, tomo-install.json
    and begin-tomo.sh."""
    registry = tmp_path / "instances.json"
    parent = tmp_path / "parent"

    result = _run_install(
        tmp_path,
        instance_name="alpha",
        registry_file=registry,
        pin_home_config=False,
        parent=parent,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    root = parent / "alpha"
    assert (root / "instance").is_dir(), result.stdout
    assert (root / "home").is_dir(), result.stdout
    assert (root / "tomo-install.json").is_file(), result.stdout
    assert (root / "begin-tomo.sh").is_file(), result.stdout


def test_absent_parent_created_and_note_printed(tmp_path: Path) -> None:
    """The installer itself creates an absent parent dir and prints a note."""
    registry = tmp_path / "instances.json"
    vault = _make_vault(tmp_path)
    # Parent that does NOT exist on disk before the run.
    parent = tmp_path / "will-be-made"
    assert not parent.exists()

    env = os.environ.copy()
    env["TOMO_REGISTRY_FILE"] = str(registry)

    result = subprocess.run(
        [
            "bash",
            str(INSTALLER),
            "--vault",
            str(vault),
            "--profile",
            "miyo",
            "--kado-token",
            "kado_test",
            "--instance-location",
            str(parent),
            "--instance-name",
            "gamma",
            "--non-interactive",
        ],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert parent.is_dir()
    assert (parent / "gamma" / "instance").is_dir()
    # A note about creating the parent must surface to the user.
    combined = (result.stdout + result.stderr).lower()
    assert str(parent) in (result.stdout + result.stderr)
    assert "creat" in combined  # "Created parent directory …"


def test_second_instance_does_not_clobber_first(tmp_path: Path) -> None:
    """Two instances under the SAME parent are isolated — installing the second
    leaves the first's tomo-install.json byte-for-byte unchanged."""
    registry = tmp_path / "instances.json"
    parent = tmp_path / "shared-parent"

    first = _run_install(
        tmp_path,
        instance_name="one",
        registry_file=registry,
        pin_home_config=False,
        parent=parent,
    )
    assert first.returncode == 0, first.stdout + first.stderr
    first_config = parent / "one" / "tomo-install.json"
    assert first_config.is_file()
    before = first_config.read_bytes()

    # NOTE: T2.2 does not yet wire registry_upsert (that is T2.3), so the
    # second install with a fresh name routes to create regardless of the
    # registry. Use a distinct name to avoid the duplicate-name guard.
    second = _run_install(
        tmp_path,
        instance_name="two",
        registry_file=registry,
        pin_home_config=False,
        parent=parent,
    )
    assert second.returncode == 0, second.stdout + second.stderr
    assert (parent / "two" / "tomo-install.json").is_file()

    # The first instance's config is byte-identical — no cross-clobber.
    after = first_config.read_bytes()
    assert after == before, "second install clobbered the first instance's config"


def test_explicit_home_config_override_pins_paths(tmp_path: Path) -> None:
    """--home-dir/--config-file remain explicit overrides (test pinning):
    when passed, HOME_DIR/CONFIG_FILE land exactly there, NOT under the derived
    <parent>/<name>/."""
    registry = tmp_path / "instances.json"
    parent = tmp_path / "parent"
    pinned_home = tmp_path / "pinned-home"
    pinned_config = tmp_path / "pinned.json"

    result = _run_install(
        tmp_path,
        instance_name="delta",
        registry_file=registry,
        pin_home_config=False,
        parent=parent,
        extra_args=[
            "--home-dir",
            str(pinned_home),
            "--config-file",
            str(pinned_config),
        ],
    )

    assert result.returncode == 0, result.stdout + result.stderr
    # Pinned paths win.
    assert pinned_config.is_file()
    assert (pinned_home / ".claude").is_dir()
    # Derived config/home are NOT written when overrides are present.
    assert not (parent / "delta" / "tomo-install.json").exists()
    assert not (parent / "delta" / "home").exists()
    # The instance dir still lands at the derived <parent>/<name>/instance.
    assert (parent / "delta" / "instance").is_dir()


# ---------------------------------------------------------------------------
# T2.3 — config repoPath + registry_upsert + render_launcher
# ---------------------------------------------------------------------------


def test_config_includes_repo_path_and_tomo_version(tmp_path: Path) -> None:
    """tomo-install.json written by the installer includes repoPath and tomoVersion."""
    registry = tmp_path / "instances.json"
    parent = tmp_path / "parent"

    result = _run_install(
        tmp_path,
        instance_name="cfg-test",
        registry_file=registry,
        pin_home_config=False,
        parent=parent,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    config_path = parent / "cfg-test" / "tomo-install.json"
    assert config_path.is_file()

    import json

    cfg = json.loads(config_path.read_text())
    # repoPath must equal REPO_ROOT (the source repo).
    assert cfg.get("repoPath") == str(REPO_ROOT), (
        f"repoPath missing or wrong: {cfg.get('repoPath')!r}"
    )
    # tomoVersion must be present (can be any non-empty string).
    assert cfg.get("tomoVersion"), "tomoVersion missing from config"


def test_config_still_includes_lifecycle_prefix(tmp_path: Path) -> None:
    """lifecyclePrefix remains in tomo-install.json (Phase 4 removes it — not now)."""
    registry = tmp_path / "instances.json"
    parent = tmp_path / "parent"

    result = _run_install(
        tmp_path,
        instance_name="lc-test",
        registry_file=registry,
        pin_home_config=False,
        parent=parent,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    config_path = parent / "lc-test" / "tomo-install.json"
    assert config_path.is_file()

    import json

    cfg = json.loads(config_path.read_text())
    # lifecyclePrefix must still be present (Phase 4 removes it).
    assert "lifecyclePrefix" in cfg, "lifecyclePrefix was prematurely removed"
    # And it is the ONLY tag-prefix key — no new ones added.
    tag_prefix_keys = [k for k in cfg if "prefix" in k.lower() or "tagprefix" in k.lower()]
    assert tag_prefix_keys == ["lifecyclePrefix"], (
        f"unexpected tag-prefix keys: {tag_prefix_keys}"
    )


def test_launcher_has_no_unrendered_placeholders(tmp_path: Path) -> None:
    """begin-tomo.sh produced by render_launcher contains no {{INSTANCE_*}},
    {{HOME_DIR}}, {{TOMO_REPO_ROOT}}, or {{DEV_NOTIFY_PORT}} placeholders.
    Docker {{ index ... }} Go-template strings are expected and must NOT be checked.
    """
    registry = tmp_path / "instances.json"
    parent = tmp_path / "parent"

    result = _run_install(
        tmp_path,
        instance_name="launcher-test",
        registry_file=registry,
        pin_home_config=False,
        parent=parent,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    launcher = parent / "launcher-test" / "begin-tomo.sh"
    assert launcher.is_file()

    content = launcher.read_text()
    import re

    # These Tomo-specific placeholders must all be gone after render.
    tomo_placeholders = re.findall(
        r"\{\{(INSTANCE_NAME|INSTANCE_PATH|HOME_DIR|TOMO_REPO_ROOT|DEV_NOTIFY_PORT)\}\}",
        content,
    )
    assert not tomo_placeholders, (
        f"Unrendered Tomo placeholders remain in begin-tomo.sh: {tomo_placeholders}"
    )


def test_registry_contains_instance_at_instance_subdir(tmp_path: Path) -> None:
    """After install, the registry file contains the new instance with path ==
    <root>/instance (the ADR-2 convention)."""
    import json

    registry = tmp_path / "instances.json"
    parent = tmp_path / "parent"

    result = _run_install(
        tmp_path,
        instance_name="reg-test",
        registry_file=registry,
        pin_home_config=False,
        parent=parent,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert registry.is_file(), "registry file not created by installer"

    data = json.loads(registry.read_text())
    instances = {e["name"]: e for e in data.get("instances", [])}
    assert "reg-test" in instances, f"reg-test not in registry: {list(instances)}"

    expected_path = str(parent / "reg-test" / "instance")
    assert instances["reg-test"]["path"] == expected_path, (
        f"registry path mismatch: {instances['reg-test']['path']!r} != {expected_path!r}"
    )


@pytest.mark.skipif(os.getuid() == 0, reason="chmod 0500 does not deny root writes — registry failure cannot be simulated as root")
def test_registry_upsert_failure_is_soft(tmp_path: Path) -> None:
    """registry_upsert failure must NOT abort the install (ADR-2: registry is
    a rebuildable index). Point TOMO_REGISTRY_FILE at a path whose PARENT dir
    is unwritable — registry_upsert cannot create the file → non-zero exit
    inside the installer — but install must still exit 0 and the instance dir
    + config must be present. A warning must surface (print_warn → stdout).
    """
    import stat

    # Create a dir we then make unwritable so registry_upsert cannot write
    # the JSON file there.
    locked_dir = tmp_path / "no-write"
    locked_dir.mkdir()
    locked_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)  # r-x — no write bit

    registry = locked_dir / "instances.json"
    parent = tmp_path / "parent"

    try:
        result = _run_install(
            tmp_path,
            instance_name="soft-fail",
            registry_file=registry,
            pin_home_config=False,
            parent=parent,
        )

        # Install must succeed despite the registry failure.
        assert result.returncode == 0, (
            "install aborted on registry failure — must soft-fail:\n"
            + result.stdout
            + result.stderr
        )

        # The instance workspace must still be present.
        assert (parent / "soft-fail" / "instance").is_dir(), (
            "instance dir missing after registry soft-fail"
        )

        # The per-instance config must still be written.
        assert (parent / "soft-fail" / "tomo-install.json").is_file(), (
            "tomo-install.json missing after registry soft-fail"
        )

        # A warning must appear in output (print_warn writes to stdout).
        assert "warn" in result.stdout.lower() or "registry" in result.stdout.lower(), (
            "no registry-failure warning in stdout:\n" + result.stdout
        )

    finally:
        # Restore write bit so pytest can clean up tmp_path.
        locked_dir.chmod(stat.S_IRWXU)
