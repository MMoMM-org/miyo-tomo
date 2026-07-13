#!/usr/bin/env python3
# version: 0.1.0
"""test_update_tomo_shim.py — the rendered update-tomo.sh convenience shim.

The shim is rendered beside begin-tomo.sh so an instance updates via
`./update-tomo.sh` instead of the full source-repo path. It bakes in
TOMO_REPO_ROOT and delegates to <repo>/scripts/update-tomo.sh with an explicit
--config-file, passing every argument through.

Verifies:
- render_launcher bakes TOMO_REPO_ROOT into the shim and marks it executable
- the shim exec's the real updater with --config-file <its-dir>/tomo-install.json
  and forwards extra args verbatim
- missing real updater / missing config each fail loudly (exit 1)
"""
from __future__ import annotations

import stat
import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "scripts" / "lib"
RENDER_LAUNCHER = LIB_DIR / "render-launcher.sh"
SHIM_TEMPLATE = LIB_DIR / "update-tomo.sh.launcher.template"

_RENDER_DRIVER = f'set -e\n. "{RENDER_LAUNCHER}"\nrender_launcher "$@"\n'


def _render(dst: Path, repo_root: str, tmp_path: Path) -> subprocess.CompletedProcess:
    # Positional order matches render_launcher: template dst name inst home repo port
    return subprocess.run(
        ["/bin/bash", "-c", _RENDER_DRIVER, "--",
         str(SHIM_TEMPLATE), str(dst),
         "inst", "/inst/path", "/home/dir", repo_root, "9999"],
        capture_output=True, text=True, cwd=str(tmp_path), timeout=15,
    )


def _make_stub_repo(root: Path) -> None:
    """A fake source repo whose scripts/update-tomo.sh echoes its args."""
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    stub = scripts / "update-tomo.sh"
    stub.write_text('#!/bin/bash\necho "DELEGATED $*"\n', encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)


def test_shim_bakes_repo_root_and_is_executable(tmp_path):
    dst = tmp_path / "update-tomo.sh"
    res = _render(dst, "/Users/alice/repos/Tomo", tmp_path)
    assert res.returncode == 0, res.stderr
    body = dst.read_text(encoding="utf-8")
    assert 'TOMO_REPO_ROOT="/Users/alice/repos/Tomo"' in body
    assert "{{" not in body  # no unsubstituted placeholders
    assert dst.stat().st_mode & stat.S_IXUSR


def test_shim_delegates_with_config_and_passes_args(tmp_path):
    repo = tmp_path / "repo"
    _make_stub_repo(repo)
    inst = tmp_path / "inst"
    inst.mkdir()
    (inst / "tomo-install.json").write_text("{}", encoding="utf-8")
    shim = inst / "update-tomo.sh"
    assert _render(shim, str(repo), tmp_path).returncode == 0

    run = subprocess.run(
        ["/bin/bash", str(shim), "--yolo", "--dry-run"],
        capture_output=True, text=True, timeout=15,
    )
    assert run.returncode == 0, run.stderr
    expected_cfg = str(inst / "tomo-install.json")
    assert run.stdout.strip() == f"DELEGATED --config-file {expected_cfg} --yolo --dry-run"


def test_shim_fails_when_real_updater_missing(tmp_path):
    inst = tmp_path / "inst"
    inst.mkdir()
    (inst / "tomo-install.json").write_text("{}", encoding="utf-8")
    shim = inst / "update-tomo.sh"
    # repo_root points at an empty dir → no scripts/update-tomo.sh
    empty_repo = tmp_path / "empty"
    empty_repo.mkdir()
    assert _render(shim, str(empty_repo), tmp_path).returncode == 0

    run = subprocess.run(["/bin/bash", str(shim)], capture_output=True, text=True, timeout=15)
    assert run.returncode == 1
    assert "not found in source repo" in run.stderr


def test_shim_fails_when_config_missing(tmp_path):
    repo = tmp_path / "repo"
    _make_stub_repo(repo)
    inst = tmp_path / "inst"
    inst.mkdir()  # no tomo-install.json
    shim = inst / "update-tomo.sh"
    assert _render(shim, str(repo), tmp_path).returncode == 0

    run = subprocess.run(["/bin/bash", str(shim)], capture_output=True, text=True, timeout=15)
    assert run.returncode == 1
    assert "tomo-install.json not found" in run.stderr
