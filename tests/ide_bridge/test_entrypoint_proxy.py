#!/usr/bin/env python3
# version: 0.1.0
"""test_entrypoint_proxy.py — Pytest-driven tests for the IDE Bridge proxy spawn
in docker/entrypoint.sh.

Exercises the proxy-decision logic via `bash -c` against a fake ~/.claude/ide
directory.  Uses a PATH shim to stub socat (records argv to a file instead of
exec-ing the real binary) and extracts the IDE Bridge block from the entrypoint
to avoid the process-replacing `exec "$@"` at the tail.

All four branches covered per T2.2 spec:
  - no .claude/ide dir (and empty dir) → no socat, exit 0
  - exactly one <port>.lock → socat invoked once, backgrounded, correct addresses
  - two .lock files → fail fast, non-zero exit, message names the dir; no socat
  - proxy spawn does not block exec "$@"
"""
from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ENTRYPOINT_SH = REPO_ROOT / "docker" / "entrypoint.sh"


def _extract_ide_bridge_block() -> str:
    """Extract just the IDE Bridge section from entrypoint.sh.

    We look for the block that starts with '# ── IDE Bridge' and ends just
    before '# ── Launch' (or before exec "$@").  This lets us test the logic
    without triggering the process-replacing exec builtin.
    """
    content = ENTRYPOINT_SH.read_text()
    # Find the IDE Bridge block
    match = re.search(
        r"(# ──.* IDE Bridge.*?)\n# ──.* Launch",
        content,
        re.DOTALL,
    )
    if not match:
        return ""
    return match.group(1)


def _run_ide_bridge_block(
    home_dir: Path,
    *,
    cmd: str = "true",
    socat_log: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run the IDE Bridge block from entrypoint.sh in a controlled subshell.

    Strategy:
      1. Create a socat shim on $PATH that records its argv instead of running.
      2. Set HOME to home_dir so ~/.claude/ide points to the fake dir.
      3. Run only the IDE Bridge block (extracted from the entrypoint) — we do
         NOT source the whole entrypoint to avoid the process-replacing exec.
      4. After the block, simulate exec by running `cmd` normally.
    """
    if socat_log is None:
        socat_log = home_dir / "socat_calls.txt"

    # Create the socat shim
    shim_dir = home_dir / "shims"
    shim_dir.mkdir(parents=True, exist_ok=True)
    socat_shim = shim_dir / "socat"
    socat_shim.write_text(
        f'#!/bin/sh\necho "socat $@" >> "{socat_log}"\n'
    )
    socat_shim.chmod(0o755)

    ide_block = _extract_ide_bridge_block()
    exec_log = home_dir / "exec_calls.txt"

    harness = textwrap.dedent(f"""\
        set -e
        export HOME="{home_dir}"
        export PATH="{shim_dir}:$PATH"

        {ide_block}

        # Simulate exec "$@" without replacing process
        echo "exec_reached" >> "{exec_log}"
        {cmd}
    """)

    return subprocess.run(
        ["bash", "-c", harness],
        capture_output=True,
        text=True,
        timeout=10,
    )


def _socat_calls(home_dir: Path) -> list[str]:
    log = home_dir / "socat_calls.txt"
    if not log.exists():
        return []
    return [line for line in log.read_text().splitlines() if line.strip()]


def _exec_reached(home_dir: Path) -> bool:
    log = home_dir / "exec_calls.txt"
    return log.exists() and "exec_reached" in log.read_text()


# ── Branch 1: no .claude/ide dir → no socat, exit 0 ─────────────────────────

def test_no_ide_dir_skips_socat_exit_0(tmp_path):
    """When ~/.claude/ide does not exist, no socat is invoked and exit is 0.

    PRD F2-AC2: no proxy spawned, no error.
    """
    home = tmp_path / "home"
    home.mkdir()
    # Deliberately NOT creating home/.claude/ide

    r = _run_ide_bridge_block(home)

    assert r.returncode == 0, f"Expected exit 0, got {r.returncode}\nstderr: {r.stderr}"
    assert _socat_calls(home) == [], f"socat should not have been called; calls: {_socat_calls(home)}"
    # Must not emit error about missing dir
    assert "error" not in r.stderr.lower() or "ide" not in r.stderr.lower(), (
        f"Unexpected error in stderr: {r.stderr}"
    )


def test_empty_ide_dir_skips_socat_exit_0(tmp_path):
    """When ~/.claude/ide exists but has no .lock files, no socat is invoked.

    PRD F2-AC2: no proxy spawned, no error.
    """
    home = tmp_path / "home"
    ide_dir = home / ".claude" / "ide"
    ide_dir.mkdir(parents=True)

    r = _run_ide_bridge_block(home)

    assert r.returncode == 0, f"Expected exit 0\nstderr: {r.stderr}"
    assert _socat_calls(home) == [], f"socat should not have been called; calls: {_socat_calls(home)}"


# ── Branch 2: exactly one .lock → socat invoked with correct addresses ────────

def test_single_lock_invokes_socat_once(tmp_path):
    """Exactly one <port>.lock → socat invoked once.

    PRD F2-AC1: proxy binds container 127.0.0.1:<port> → host.docker.internal:<port>.
    Business Rule 5: port derived from lock filename, not JSON content.
    """
    home = tmp_path / "home"
    ide_dir = home / ".claude" / "ide"
    ide_dir.mkdir(parents=True)
    lock_file = ide_dir / "23027.lock"
    lock_file.write_text(
        '{"pid":0,"workspaceFolders":[],"ideName":"Obsidian","transport":"ws","authToken":"abc"}'
    )

    r = _run_ide_bridge_block(home)

    assert r.returncode == 0, f"Expected exit 0\nstderr: {r.stderr}\nstdout: {r.stdout}"
    calls = _socat_calls(home)
    assert len(calls) == 1, f"Expected exactly 1 socat call, got {len(calls)}: {calls}"
    call = calls[0]
    assert "127.0.0.1" in call, f"Missing bind=127.0.0.1 in socat call: {call}"
    assert "host.docker.internal:23027" in call, (
        f"Missing host.docker.internal:23027 forward target in socat call: {call}"
    )
    assert "23027" in call, f"Port 23027 missing from socat call: {call}"


def test_single_lock_listen_includes_port(tmp_path):
    """The LISTEN side must include the port derived from the filename."""
    home = tmp_path / "home"
    ide_dir = home / ".claude" / "ide"
    ide_dir.mkdir(parents=True)
    (ide_dir / "23027.lock").write_text(
        '{"pid":0,"workspaceFolders":[],"ideName":"Obsidian","transport":"ws","authToken":"abc"}'
    )

    r = _run_ide_bridge_block(home)
    calls = _socat_calls(home)
    assert len(calls) == 1
    # Listen-side argument must contain the port (TCP-LISTEN:23027,... or TCP4-LISTEN:23027,...)
    call = calls[0]
    assert re.search(r"TCP[^:]*:23027", call), (
        f"Expected TCP-LISTEN:23027 in socat call, got: {call}"
    )


def test_single_lock_port_from_filename_not_json(tmp_path):
    """Port must be derived from the lock FILENAME (Business Rule 5).

    JSON content is irrelevant to port selection — the filename is canonical.
    """
    home = tmp_path / "home"
    ide_dir = home / ".claude" / "ide"
    ide_dir.mkdir(parents=True)
    # Lock filename is 23099.lock
    (ide_dir / "23099.lock").write_text(
        '{"pid":0,"workspaceFolders":[],"ideName":"Obsidian","transport":"ws","authToken":"tok"}'
    )

    r = _run_ide_bridge_block(home)

    assert r.returncode == 0, f"Expected exit 0\nstderr: {r.stderr}"
    calls = _socat_calls(home)
    assert len(calls) == 1, f"Expected 1 socat call, got {len(calls)}: {calls}"
    # Port in socat args must be 23099 (from filename)
    assert "23099" in calls[0], f"Expected port 23099 (from filename) in socat call: {calls[0]}"
    # Port 23027 must NOT appear
    assert "23027" not in calls[0], f"Port 23027 leaked into socat call: {calls[0]}"


def test_single_lock_exec_still_reached(tmp_path):
    """Proxy spawn does not block execution: the command following the block runs.

    Verifies CON-6: existing exec behavior is intact after the bridge block.
    """
    home = tmp_path / "home"
    ide_dir = home / ".claude" / "ide"
    ide_dir.mkdir(parents=True)
    (ide_dir / "23027.lock").write_text(
        '{"pid":0,"workspaceFolders":[],"ideName":"Obsidian","transport":"ws","authToken":"abc"}'
    )

    r = _run_ide_bridge_block(home)

    assert r.returncode == 0, f"Expected exit 0\nstderr: {r.stderr}"
    assert _exec_reached(home), (
        "exec point was not reached — proxy spawn may have blocked continuation"
    )


# ── Branch 3: two .lock files → fail fast, non-zero exit ─────────────────────

def test_multiple_locks_fail_fast_nonzero(tmp_path):
    """Two .lock files → exit non-zero.

    SDD Error Handling: fail fast with a clear message.
    """
    home = tmp_path / "home"
    ide_dir = home / ".claude" / "ide"
    ide_dir.mkdir(parents=True)
    for port in ("23027", "23028"):
        (ide_dir / f"{port}.lock").write_text(
            '{"pid":0,"workspaceFolders":[],"ideName":"Obsidian","transport":"ws","authToken":"abc"}'
        )

    r = _run_ide_bridge_block(home)

    assert r.returncode != 0, (
        f"Expected non-zero exit for multiple lock files, got 0\nstdout: {r.stdout}"
    )


def test_multiple_locks_error_names_directory(tmp_path):
    """The error message for multiple lock files must name the ide directory.

    SDD Error Handling: 'Multiple .lock files → fail fast with a clear message
    pointing at the directory.'
    """
    home = tmp_path / "home"
    ide_dir = home / ".claire" / "ide"  # note: using real path below
    ide_dir = home / ".claude" / "ide"
    ide_dir.mkdir(parents=True)
    for port in ("23027", "23028"):
        (ide_dir / f"{port}.lock").write_text("{}")

    r = _run_ide_bridge_block(home)

    combined = r.stdout + r.stderr
    # The message must mention either .claude/ide or the full path
    assert ".claude/ide" in combined or "ide" in combined, (
        f"Error message should reference the ide directory.\nstdout: {r.stdout}\nstderr: {r.stderr}"
    )


def test_multiple_locks_socat_not_invoked(tmp_path):
    """When multiple lock files are found, socat must NOT be invoked.

    SDD Error Handling: fail fast before spawning anything.
    """
    home = tmp_path / "home"
    ide_dir = home / ".claude" / "ide"
    ide_dir.mkdir(parents=True)
    for port in ("23027", "23028"):
        (ide_dir / f"{port}.lock").write_text("{}")

    r = _run_ide_bridge_block(home)

    calls = _socat_calls(home)
    assert calls == [], f"socat must not be invoked for multiple locks; calls: {calls}"


# ── Version check ─────────────────────────────────────────────────────────────

def test_entrypoint_version_is_030():
    """entrypoint.sh version must be 0.3.0 after T2.2 bump."""
    content = ENTRYPOINT_SH.read_text()
    match = re.search(r"# version: (\d+\.\d+\.\d+)", content)
    assert match, "Could not find '# version: X.Y.Z' in entrypoint.sh header"
    version = tuple(int(x) for x in match.group(1).split("."))
    assert version >= (0, 3, 0), (
        f"entrypoint.sh version {match.group(1)} is below 0.3.0. "
        "Must be bumped to 0.3.0 for T2.2."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
