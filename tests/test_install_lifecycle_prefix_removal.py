#!/usr/bin/env python3
# version: 0.1.0
"""test_install_lifecycle_prefix_removal.py — T4.1 (ADR-6) tests.

Asserts that the install wizard has NO lifecycle tag-prefix step after
Phase 4 cleanup:
  (a) --help contains no --prefix flag
  (b) a non-interactive isolated install writes tomo-install.json with no
      lifecyclePrefix key
  (c) the generated vault-config.yaml has no tag_prefix / lifecycle.tag_prefix

GUARDRAIL: every install is run with full isolation flags
  --instance-location <TMPDIR> --instance-name <iso-name>
  --non-interactive
so the test NEVER touches the user's real tomo-instance.

Spec: docs/XDD/specs/020-multi-instance-install/ — Phase 4 T4.1, ADR-6
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
INSTALLER = REPO_ROOT / "scripts" / "install-tomo.sh"


# ---------------------------------------------------------------------------
# helpers (minimal subset — full harness lives in test_install_multi_instance)
# ---------------------------------------------------------------------------


def _make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True, exist_ok=True)
    return vault


def _run_isolated_install(tmp_path: Path, instance_name: str) -> subprocess.CompletedProcess:
    """Run the installer with full isolation. Never touches the real instance."""
    vault = _make_vault(tmp_path)
    registry = tmp_path / "instances.json"
    parent = tmp_path / "loc"
    parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["TOMO_REGISTRY_FILE"] = str(registry)

    return subprocess.run(
        [
            "bash",
            str(INSTALLER),
            "--vault", str(vault),
            "--profile", "miyo",
            "--kado-token", "kado_test",
            "--instance-location", str(parent),
            "--instance-name", instance_name,
            "--non-interactive",
        ],
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# T4.1-a: --help contains no --prefix flag (ADR-6 F6-AC1)
# ---------------------------------------------------------------------------


def test_help_has_no_prefix_flag() -> None:
    """--help output must contain no --prefix flag after T4.1 removal."""
    result = subprocess.run(
        ["bash", str(INSTALLER), "--help"],
        capture_output=True,
        text=True,
    )
    # --help exits 0
    assert result.returncode == 0, result.stderr
    assert "--prefix" not in result.stdout, (
        "--prefix flag still present in --help output after T4.1 removal"
    )


# ---------------------------------------------------------------------------
# T4.1-b: tomo-install.json must have no lifecyclePrefix key (ADR-6 F6-AC1)
# ---------------------------------------------------------------------------


def test_install_json_has_no_lifecycle_prefix(tmp_path: Path) -> None:
    """Non-interactive isolated install must produce a tomo-install.json with
    NO lifecyclePrefix key — and no other prefix-bearing key."""
    result = _run_isolated_install(tmp_path, "t41-json")
    assert result.returncode == 0, result.stdout + result.stderr

    config_path = tmp_path / "loc" / "t41-json" / "tomo-install.json"
    assert config_path.is_file(), "tomo-install.json not produced by install"

    cfg = json.loads(config_path.read_text())
    assert "lifecyclePrefix" not in cfg, (
        "lifecyclePrefix key still present in tomo-install.json after T4.1 removal"
    )
    # No other prefix-shaped key should be present either.
    prefix_keys = [k for k in cfg if "prefix" in k.lower()]
    assert not prefix_keys, (
        f"Unexpected prefix-related keys remain in tomo-install.json: {prefix_keys}"
    )


# ---------------------------------------------------------------------------
# T4.1-c: vault-config.yaml must have no tag_prefix / lifecycle block (ADR-6 F6-AC1)
# ---------------------------------------------------------------------------


def test_vault_config_has_no_tag_prefix(tmp_path: Path) -> None:
    """The generated vault-config.yaml must contain no tag_prefix field and no
    lifecycle: block (lifecycle: only held tag_prefix — removing tag_prefix
    makes the block empty; the empty block must also be removed)."""
    result = _run_isolated_install(tmp_path, "t41-yaml")
    assert result.returncode == 0, result.stdout + result.stderr

    yaml_path = tmp_path / "loc" / "t41-yaml" / "instance" / "config" / "vault-config.yaml"
    assert yaml_path.is_file(), "vault-config.yaml not produced by install"

    content = yaml_path.read_text()
    assert "tag_prefix" not in content, (
        "tag_prefix still present in vault-config.yaml after T4.1 removal"
    )
    assert "lifecycle:" not in content, (
        "lifecycle: block still present in vault-config.yaml — "
        "empty mapping must be removed together with tag_prefix"
    )
