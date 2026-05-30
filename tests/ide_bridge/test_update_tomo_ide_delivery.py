#!/usr/bin/env python3
# version: 0.1.0
"""test_update_tomo_ide_delivery.py — update-tomo.sh IDE Bridge delivery (T4.1).

Delivery-gap fix: update-tomo.sh must regenerate the begin-tomo.sh launcher AND
copy docker/entrypoint.sh into the container home, version-gated through its
existing plan/execute model. Before this fix an existing user who ran
update-tomo.sh to enable the IDE Bridge got a lock file but a STALE launcher
(no socat drift-rebuild / banner / probe) and a STALE entrypoint (no socat
proxy spawn), so the bridge silently did not work — only install-tomo.sh
shipped these.

Drives update-tomo.sh against an ISOLATED tmp instance via an isolated
--config-file — NEVER the real instance
(memory: feedback_test_scripts_must_never_touch_real_install).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
UPDATE_SCRIPT = REPO_ROOT / "scripts" / "update-tomo.sh"
SRC_ENTRYPOINT = REPO_ROOT / "docker" / "entrypoint.sh"
LAUNCHER_TEMPLATE = REPO_ROOT / "scripts" / "lib" / "begin-tomo.sh.template"

# Stale versions seeded into the tmp instance — older than source so the scan
# must classify them as "update".
OLD_ENTRYPOINT_VERSION = "0.2.0"
OLD_LAUNCHER_VERSION = "0.11.0"

pytestmark = pytest.mark.skipif(
    not UPDATE_SCRIPT.exists(), reason="update-tomo.sh not found"
)


def _file_version(path: Path) -> str:
    for line in path.read_text().splitlines():
        if line.startswith("# version:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def _setup_instance(tmp_path: Path):
    """Build an isolated tmp instance + home + tomo-install.json.

    Returns (config_file, instance_path, home_dir, launcher_path) — every path
    lives inside tmp_path so no run can touch the real instance.
    """
    instance_location = tmp_path / "loc"
    instance_path = instance_location / "tomo-instance"
    home_dir = tmp_path / "home"
    launcher_path = instance_location / "begin-tomo.sh"
    config_file = tmp_path / "tomo-install.json"

    instance_path.mkdir(parents=True, exist_ok=True)
    (instance_path / ".claude").mkdir(parents=True, exist_ok=True)
    home_dir.mkdir(parents=True, exist_ok=True)

    # Seed a STALE entrypoint in the container home.
    (home_dir / "entrypoint.sh").write_text(
        f"#!/bin/bash\n# version: {OLD_ENTRYPOINT_VERSION}\necho stale-entrypoint\n"
    )
    # Seed a STALE launcher at the launcher path.
    launcher_path.write_text(
        f"#!/bin/bash\n# version: {OLD_LAUNCHER_VERSION}\necho stale-launcher\n"
    )

    config = {
        "version": "0.0.0",
        "instanceName": "testinst",
        "instanceLocation": str(instance_location),
        "instancePath": str(instance_path),
        "launcherPath": str(launcher_path),
        "homePath": str(home_dir),
        "vaultPath": str(tmp_path / "vault"),
        "profile": "miyo",
        "profileVersion": "0.0.0",
        "lifecyclePrefix": "tomo",
        "kado": {"host": "127.0.0.1", "port": 23026, "protocol": "http"},
        "voice": {"enabled": False, "model": "", "language": ""},
        "ide_bridge": {"enabled": True, "auth_token": "tok-123", "port": 23027},
        "installedAt": "2026-01-01T00:00:00Z",
        "tomoVersion": "0.0.0",
    }
    config_file.write_text(json.dumps(config, indent=2))

    return config_file, instance_path, home_dir, launcher_path


def _run_update(config_file: Path, *extra_args):
    """Run update-tomo.sh against the isolated config (non-interactive)."""
    return subprocess.run(
        [
            "/bin/bash",
            str(UPDATE_SCRIPT),
            "--config-file", str(config_file),
            "--yolo",  # --keep-voice --yes: no prompts, no voice wizard
            *extra_args,
        ],
        capture_output=True,
        text=True,
        cwd=str(config_file.parent),
    )


def test_update_delivers_entrypoint(tmp_path):
    config_file, _instance_path, home_dir, _launcher = _setup_instance(tmp_path)
    result = _run_update(config_file)
    assert result.returncode == 0, f"update failed:\n{result.stdout}\n{result.stderr}"

    dst = home_dir / "entrypoint.sh"
    assert _file_version(dst) == _file_version(SRC_ENTRYPOINT), \
        "entrypoint version not updated to source"
    assert dst.read_text() == SRC_ENTRYPOINT.read_text(), \
        "entrypoint not byte-identical to source"
    assert os.access(dst, os.X_OK), "entrypoint.sh not executable after update"


def test_update_regenerates_launcher(tmp_path):
    config_file, instance_path, _home_dir, launcher = _setup_instance(tmp_path)
    result = _run_update(config_file)
    assert result.returncode == 0, f"update failed:\n{result.stdout}\n{result.stderr}"

    assert _file_version(launcher) == _file_version(LAUNCHER_TEMPLATE), \
        "launcher version not updated to template"

    body = launcher.read_text()
    # No placeholder must remain — catches any single-placeholder typo in the sed pipeline.
    assert "{{INSTANCE_PATH}}" not in body, "launcher still has unsubstituted {{INSTANCE_PATH}}"
    assert "{{INSTANCE_NAME}}" not in body, "launcher still has unsubstituted {{INSTANCE_NAME}}"
    assert "{{HOME_DIR}}" not in body, "launcher still has unsubstituted {{HOME_DIR}}"
    assert "{{TOMO_REPO_ROOT}}" not in body, "launcher still has unsubstituted {{TOMO_REPO_ROOT}}"
    assert "{{DEV_NOTIFY_PORT}}" not in body, "launcher still has unsubstituted {{DEV_NOTIFY_PORT}}"
    # Concrete substituted values must appear — catches missing/swapped values.
    config = json.loads(config_file.read_text())
    assert str(instance_path) in body, "launcher missing substituted INSTANCE_PATH"
    assert config["instanceName"] in body, "launcher missing substituted INSTANCE_NAME"
    assert str(config_file.parent / "home") in body, "launcher missing substituted HOME_DIR"
    assert os.access(launcher, os.X_OK), "launcher not executable after update"


def test_dry_run_writes_nothing(tmp_path):
    config_file, _instance_path, home_dir, launcher = _setup_instance(tmp_path)
    result = _run_update(config_file, "--dry-run")
    assert result.returncode == 0, f"dry-run failed:\n{result.stdout}\n{result.stderr}"

    combined = result.stdout + result.stderr
    assert "entrypoint" in combined.lower(), "dry-run plan did not mention entrypoint"
    assert "begin-tomo" in combined.lower() or "launcher" in combined.lower(), \
        "dry-run plan did not mention launcher"

    assert _file_version(home_dir / "entrypoint.sh") == OLD_ENTRYPOINT_VERSION, \
        "dry-run modified the entrypoint"
    assert _file_version(launcher) == OLD_LAUNCHER_VERSION, \
        "dry-run modified the launcher"


def test_idempotent_second_run_is_current(tmp_path):
    config_file, _instance_path, home_dir, launcher = _setup_instance(tmp_path)
    first = _run_update(config_file)
    assert first.returncode == 0, f"first update failed:\n{first.stdout}\n{first.stderr}"

    assert _file_version(home_dir / "entrypoint.sh") == _file_version(SRC_ENTRYPOINT)
    assert _file_version(launcher) == _file_version(LAUNCHER_TEMPLATE)

    second = _run_update(config_file)
    assert second.returncode == 0, f"second update failed:\n{second.stdout}\n{second.stderr}"

    combined = second.stdout + second.stderr
    # Execute phase prints nothing for current files; assert the plan did NOT
    # mark either deliverable update/create on the no-op second run.
    assert "↑ update   entrypoint" not in combined, "entrypoint spuriously re-updated"
    assert "+ create   entrypoint" not in combined, "entrypoint spuriously re-created"
    assert "↑ update   begin-tomo.sh" not in combined, "launcher spuriously re-updated"
    assert "+ create   begin-tomo.sh" not in combined, "launcher spuriously re-created"
