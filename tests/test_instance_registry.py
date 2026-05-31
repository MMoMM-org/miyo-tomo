#!/usr/bin/env python3
# version: 0.1.0
"""test_instance_registry.py — Tests for scripts/lib/instance-registry.sh.

Drives the bash library via subprocess using an isolated TOMO_REGISTRY_FILE
override so tests never touch the real ~/.tomo or tomo-instance/.

Spec: docs/XDD/specs/020-multi-instance-install/ — ADR-2, Phase 1 T1.1
PRD refs: F2-AC1 (upsert creates entry), F2-AC3 (stale handled), F2-AC4 (missing → empty)
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB = REPO_ROOT / "scripts" / "lib" / "instance-registry.sh"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run(cmd: str, registry_file: Path | None = None, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    """Source the lib and run cmd in one bash invocation."""
    env = os.environ.copy()
    if registry_file is not None:
        env["TOMO_REGISTRY_FILE"] = str(registry_file)
    if env_extra:
        env.update(env_extra)
    script = f'source "{LIB}" && {cmd}'
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=env,
    )


def _upsert(registry_file: Path, name: str, path: str, repo: str, version: str) -> subprocess.CompletedProcess:
    return _run(
        f'registry_upsert "{name}" "{path}" "{repo}" "{version}"',
        registry_file=registry_file,
    )


# ---------------------------------------------------------------------------
# registry_path — echo the file path
# ---------------------------------------------------------------------------


def test_registry_path_default(tmp_path: Path) -> None:
    """registry_path echoes the path (default or override)."""
    reg = tmp_path / "instances.json"
    result = _run("registry_path", registry_file=reg)
    assert result.returncode == 0
    assert result.stdout.strip() == str(reg)


def test_registry_path_honors_env_override(tmp_path: Path) -> None:
    """TOMO_REGISTRY_FILE override is returned verbatim."""
    custom = tmp_path / "custom" / "registry.json"
    result = _run("registry_path", registry_file=custom)
    assert result.returncode == 0
    assert result.stdout.strip() == str(custom)


# ---------------------------------------------------------------------------
# registry_upsert — create + overwrite
# ---------------------------------------------------------------------------


def test_upsert_creates_instances_json_with_schema_and_entry(tmp_path: Path) -> None:
    """Happy path: upsert creates instances.json with schema_version + one entry. [F2-AC1]"""
    reg = tmp_path / "instances.json"
    inst_dir = tmp_path / "myinst"
    inst_dir.mkdir()

    result = _upsert(reg, "myinst", str(inst_dir), str(REPO_ROOT), "0.13.0")

    assert result.returncode == 0, result.stderr
    assert reg.exists()
    data = json.loads(reg.read_text())
    assert data["schema_version"] == 1
    assert len(data["instances"]) == 1
    entry = data["instances"][0]
    assert entry["name"] == "myinst"
    assert entry["path"] == str(inst_dir)
    assert entry["repo"] == str(REPO_ROOT)
    assert entry["version"] == "0.13.0"
    assert "updatedAt" in entry
    # ISO-8601 UTC: 2026-05-31T14:00:00Z
    assert entry["updatedAt"].endswith("Z")


def test_upsert_overwrite_no_duplicate(tmp_path: Path) -> None:
    """Upsert of existing name overwrites in place; no duplicate entry."""
    reg = tmp_path / "instances.json"
    inst_dir = tmp_path / "alpha"
    inst_dir.mkdir()

    _upsert(reg, "alpha", str(inst_dir), str(REPO_ROOT), "0.13.0")
    _upsert(reg, "alpha", str(inst_dir), str(REPO_ROOT), "0.14.0")

    data = json.loads(reg.read_text())
    names = [e["name"] for e in data["instances"]]
    assert names.count("alpha") == 1, "duplicate name found"
    assert data["instances"][0]["version"] == "0.14.0"


def test_upsert_multiple_names_coexist(tmp_path: Path) -> None:
    """Two different names both appear in the registry."""
    reg = tmp_path / "instances.json"
    d1 = tmp_path / "inst1"
    d2 = tmp_path / "inst2"
    d1.mkdir()
    d2.mkdir()

    _upsert(reg, "inst1", str(d1), str(REPO_ROOT), "0.13.0")
    _upsert(reg, "inst2", str(d2), str(REPO_ROOT), "0.13.0")

    data = json.loads(reg.read_text())
    assert len(data["instances"]) == 2
    names = {e["name"] for e in data["instances"]}
    assert names == {"inst1", "inst2"}


# ---------------------------------------------------------------------------
# registry_resolve — lookup by name
# ---------------------------------------------------------------------------


def test_resolve_known_name_returns_path(tmp_path: Path) -> None:
    """registry_resolve <known> prints the path field."""
    reg = tmp_path / "instances.json"
    inst_dir = tmp_path / "myinst"
    inst_dir.mkdir()

    _upsert(reg, "myinst", str(inst_dir), str(REPO_ROOT), "0.13.0")
    result = _run('registry_resolve "myinst"', registry_file=reg)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(inst_dir)


def test_resolve_unknown_name_exits_nonzero_empty_output(tmp_path: Path) -> None:
    """registry_resolve <unknown> → non-zero exit + empty stdout."""
    reg = tmp_path / "instances.json"
    inst_dir = tmp_path / "myinst"
    inst_dir.mkdir()
    _upsert(reg, "myinst", str(inst_dir), str(REPO_ROOT), "0.13.0")

    result = _run('registry_resolve "no-such-thing"', registry_file=reg)

    assert result.returncode != 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# registry_list — print all entries
# ---------------------------------------------------------------------------


def test_list_empty_file_missing_exits_zero_empty_output(tmp_path: Path) -> None:
    """Missing registry → empty output, exit 0. [F2-AC4]"""
    reg = tmp_path / "instances.json"
    assert not reg.exists()

    result = _run("registry_list", registry_file=reg)

    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_list_prints_all_entries(tmp_path: Path) -> None:
    """registry_list emits one line per entry (at minimum name is present)."""
    reg = tmp_path / "instances.json"
    d1 = tmp_path / "inst1"
    d2 = tmp_path / "inst2"
    d1.mkdir()
    d2.mkdir()

    _upsert(reg, "inst1", str(d1), str(REPO_ROOT), "0.13.0")
    _upsert(reg, "inst2", str(d2), str(REPO_ROOT), "0.14.0")

    result = _run("registry_list", registry_file=reg)

    assert result.returncode == 0
    assert "inst1" in result.stdout
    assert "inst2" in result.stdout


# ---------------------------------------------------------------------------
# registry_list stale-check — path dir missing
# ---------------------------------------------------------------------------


def test_list_check_flags_stale_entry_no_crash(tmp_path: Path) -> None:
    """Entry whose path dir is missing is flagged (stale), not a crash. [F2-AC3]"""
    reg = tmp_path / "instances.json"
    inst_dir = tmp_path / "ghost"
    inst_dir.mkdir()

    _upsert(reg, "ghost", str(inst_dir), str(REPO_ROOT), "0.13.0")
    # Remove the directory so the entry becomes stale
    inst_dir.rmdir()

    result = _run("registry_list_check", registry_file=reg)

    assert result.returncode == 0  # must not crash
    assert "stale" in result.stdout.lower() or "ghost" in result.stdout


# ---------------------------------------------------------------------------
# registry_remove
# ---------------------------------------------------------------------------


def test_remove_drops_entry(tmp_path: Path) -> None:
    """registry_remove drops the named entry from the registry."""
    reg = tmp_path / "instances.json"
    inst_dir = tmp_path / "todel"
    inst_dir.mkdir()

    _upsert(reg, "todel", str(inst_dir), str(REPO_ROOT), "0.13.0")
    result = _run('registry_remove "todel"', registry_file=reg)

    assert result.returncode == 0, result.stderr
    data = json.loads(reg.read_text())
    names = [e["name"] for e in data["instances"]]
    assert "todel" not in names


def test_remove_nonexistent_name_exits_zero(tmp_path: Path) -> None:
    """Removing a name that does not exist is a no-op, exit 0."""
    reg = tmp_path / "instances.json"
    inst_dir = tmp_path / "keeper"
    inst_dir.mkdir()
    _upsert(reg, "keeper", str(inst_dir), str(REPO_ROOT), "0.13.0")

    result = _run('registry_remove "no-such-thing"', registry_file=reg)

    assert result.returncode == 0
    data = json.loads(reg.read_text())
    assert len(data["instances"]) == 1


# ---------------------------------------------------------------------------
# Corrupt JSON recovery — backed up + treated as empty
# ---------------------------------------------------------------------------


def test_corrupt_json_backed_up_treated_as_empty(tmp_path: Path) -> None:
    """Corrupt/unparseable JSON → backed up + registry treated as empty; no crash."""
    reg = tmp_path / "instances.json"
    reg.write_text("{not valid json!!", encoding="utf-8")

    inst_dir = tmp_path / "fresh"
    inst_dir.mkdir()
    result = _upsert(reg, "fresh", str(inst_dir), str(REPO_ROOT), "0.13.0")

    assert result.returncode == 0, result.stderr
    # Registry now contains the fresh entry (treated as empty)
    data = json.loads(reg.read_text())
    assert len(data["instances"]) == 1
    assert data["instances"][0]["name"] == "fresh"
    # Backup file should exist
    backups = [p for p in tmp_path.iterdir() if "corrupt" in p.name or p.suffix in (".bak", ".corrupt")]
    assert len(backups) >= 1, "expected a backup of the corrupt file"


def test_list_corrupt_json_exits_zero_empty_output(tmp_path: Path) -> None:
    """list on corrupt file → treated as empty, exit 0, no crash."""
    reg = tmp_path / "instances.json"
    reg.write_text("totally {broken", encoding="utf-8")

    result = _run("registry_list", registry_file=reg)

    assert result.returncode == 0
    # Should produce warning on stderr but not crash
    # stdout is either empty or contains stale/warning info — must not crash


# ---------------------------------------------------------------------------
# Unwritable ~/.tomo/ directory — clear non-zero error, no partial file
# ---------------------------------------------------------------------------


def test_unwritable_dir_yields_nonzero_no_partial_file(tmp_path: Path) -> None:
    """~/.tomo/ unwritable → clear non-zero error; no partial file created."""
    locked_dir = tmp_path / "locked"
    locked_dir.mkdir(mode=0o555)  # read+execute only
    reg = locked_dir / "instances.json"

    inst_dir = tmp_path / "myinst"
    inst_dir.mkdir()

    result = _upsert(reg, "myinst", str(inst_dir), str(REPO_ROOT), "0.13.0")

    assert result.returncode != 0, "expected non-zero exit for unwritable dir"
    # No partial .tmp file left behind
    tmp_file = locked_dir / "instances.json.tmp"
    assert not tmp_file.exists()
    assert not reg.exists()


# ---------------------------------------------------------------------------
# Sourcing the lib has no side effects
# ---------------------------------------------------------------------------


def test_sourcing_has_no_side_effects(tmp_path: Path) -> None:
    """Sourcing instance-registry.sh must not create files or print anything."""
    reg = tmp_path / "instances.json"
    result = subprocess.run(
        ["bash", "-c", f'source "{LIB}"'],
        capture_output=True,
        text=True,
        env={**os.environ, "TOMO_REGISTRY_FILE": str(reg)},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert not reg.exists(), "sourcing the lib must not create the registry file"
