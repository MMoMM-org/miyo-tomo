#!/usr/bin/env python3
# version: 0.1.1
"""test_statusline_render.py — Pytest-driven tests for tomo-statusline.sh (T3.2).

Feeds JSON on stdin, stubs the probes (PATH shims or injected env vars),
and asserts the rendered statusline line.

Coverage:
  - PRD F7-AC1: Kado renders as 門:<port> with all 4 states
  - PRD F7-AC2: Hashi renders as 橋:<port> with 3 states (no Tags)
  - PRD F7-AC3: ANSI color codes present for all states
  - CON-6: instance label 友 <name> rendering unchanged

Strategy mirrors test_configure_ide_bridge.py (subprocess + bash).
The statusline script is driven via subprocess with controlled filesystem
state (tmp_path for lock files, tmp .mcp.json for Kado config) and with
cache files pre-seeded so the live probes are bypassed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATUSLINE_SH = REPO_ROOT / "tomo" / "scripts" / "tomo-statusline.sh"

# ANSI escape sequences
ANSI_GREEN = "\033[0;32m"
ANSI_YELLOW = "\033[0;33m"
ANSI_RED = "\033[0;31m"
ANSI_RESET = "\033[0m"

# Minimal stdin JSON (model name + context pct)
_BASE_JSON = '{"model":{"display_name":"Sonnet"},"context_window":{"used_percentage":10}}'


def _run_statusline(
    *,
    json_input: str = _BASE_JSON,
    mcp_json_content: str | None = None,
    lock_files: dict[str, str] | None = None,
    kado_cache_content: str | None = None,
    hashi_cache_content: str | None = None,
    tomo_instance_dir: str = "",
    extra_env: dict[str, str] | None = None,
    tmp_path: Path,
) -> subprocess.CompletedProcess:
    """Run tomo-statusline.sh with controlled environment inside tmp_path.

    Creates all required files in tmp_path (working directory = tmp_path,
    HOME = tmp_path/home, TMPDIR = tmp_path/tmp) so no host filesystem
    state is touched.

    Args:
        json_input: JSON piped on stdin.
        mcp_json_content: raw string written to tmp_path/.mcp.json. When
            None the file does not exist (→ Kado no_config).
        lock_files: mapping of filename → JSON content, written under
            tmp_path/home/.claude/ide/. When empty/None → Hashi no_config.
        kado_cache_content: if set, pre-seed the Kado cache file so the live
            kado_check probe is skipped entirely.
        hashi_cache_content: if set, pre-seed the Hashi cache file so the
            live hashi_check probe is skipped entirely.
        tomo_instance_dir: value for TOMO_INSTANCE_DIR env var.
        extra_env: additional environment overrides.
        tmp_path: pytest tmp_path fixture.

    Returns subprocess.CompletedProcess with stdout/stderr/returncode.
    """
    # Prepare dirs
    home_dir = tmp_path / "home"
    tmp_dir = tmp_path / "tmp"
    home_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Write .mcp.json in cwd (= tmp_path, mimics instance cwd)
    if mcp_json_content is not None:
        (tmp_path / ".mcp.json").write_text(mcp_json_content)

    # Write lock files
    if lock_files:
        ide_dir = home_dir / ".claude" / "ide"
        ide_dir.mkdir(parents=True, exist_ok=True)
        for fname, content in lock_files.items():
            (ide_dir / fname).write_text(content)

    # Pre-seed caches so real network probes never run
    if kado_cache_content is not None:
        cache_path = tmp_dir / "tomo-statusline-kado"
        cache_path.write_text(kado_cache_content)
    if hashi_cache_content is not None:
        cache_path = tmp_dir / "tomo-statusline-hashi"
        cache_path.write_text(hashi_cache_content)

    env = dict(os.environ)
    env["HOME"] = str(home_dir)
    env["TMPDIR"] = str(tmp_dir)
    if tomo_instance_dir:
        env["TOMO_INSTANCE_DIR"] = tomo_instance_dir
    else:
        env.pop("TOMO_INSTANCE_DIR", None)
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        ["bash", str(STATUSLINE_SH)],
        input=json_input,
        capture_output=True,
        text=True,
        timeout=15,
        cwd=str(tmp_path),
        env=env,
    )


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\033\[[0-9;]*m", "", text)


def _has_ansi(text: str) -> bool:
    """Return True if text contains at least one ANSI escape sequence."""
    return bool(re.search(r"\033\[[0-9;]*m", text))


# ── Kado: 門:<port> with all 4 states (F7-AC1) ────────────────────────────────

def _make_mcp_json(port: int = 23026) -> str:
    """Return a minimal .mcp.json string pointing to the given Kado port."""
    return json.dumps({
        "mcpServers": {
            "kado": {
                "url": f"http://127.0.0.1:{port}/mcp",
                "headers": {"Authorization": "Bearer test-token"},
            }
        }
    })


def test_kado_ok_renders_gate_port_check(tmp_path):
    """F7-AC1: Kado ok → 門:23026 ✓ in output (green)."""
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="ok",
        tmp_path=tmp_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "門:23026" in r.stdout, (
        f"Expected '門:23026' in output.\nstdout: {r.stdout!r}"
    )
    assert "✓" in r.stdout, f"Expected ✓. stdout: {r.stdout!r}"
    # Color retained (F7-AC3): ANSI green must be present
    assert ANSI_GREEN in r.stdout, (
        f"Expected ANSI green in Kado ok state.\nstdout: {r.stdout!r}"
    )


def test_kado_unreachable_renders_gate_port_cross(tmp_path):
    """F7-AC1: Kado unreachable → 門:23026 ✗ in output (red)."""
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="unreachable",
        tmp_path=tmp_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "門:23026" in r.stdout, (
        f"Expected '門:23026' in output.\nstdout: {r.stdout!r}"
    )
    assert "✗" in r.stdout, f"Expected ✗. stdout: {r.stdout!r}"
    # Color retained: ANSI red
    assert ANSI_RED in r.stdout, (
        f"Expected ANSI red in Kado unreachable state.\nstdout: {r.stdout!r}"
    )


def test_kado_tags_denied_renders_gate_port_check_tags_cross(tmp_path):
    """F7-AC1: Kado tags_denied → 門:23026 ✓ Tags ✗ in output (yellow)."""
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="tags_denied",
        tmp_path=tmp_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "門:23026" in r.stdout, (
        f"Expected '門:23026' in output.\nstdout: {r.stdout!r}"
    )
    assert "✓" in r.stdout and "✗" in r.stdout, (
        f"Expected both ✓ and ✗ for tags_denied.\nstdout: {r.stdout!r}"
    )
    assert "Tags" in r.stdout, (
        f"Expected 'Tags' label in tags_denied state.\nstdout: {r.stdout!r}"
    )
    # Color retained: ANSI yellow
    assert ANSI_YELLOW in r.stdout, (
        f"Expected ANSI yellow in Kado tags_denied state.\nstdout: {r.stdout!r}"
    )


def test_kado_no_config_renders_gate_port_question(tmp_path):
    """F7-AC1: Kado no_config → 門:<port> ? (yellow, no_config) — port from .mcp.json."""
    # Even when the cache says no_config, the port needs a source.
    # When .mcp.json is absent the port defaults gracefully (e.g. "?" or "0").
    # When .mcp.json is present but cache says no_config, port is still parsed.
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="no_config",
        tmp_path=tmp_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "門:" in r.stdout, (
        f"Expected '門:' prefix in output.\nstdout: {r.stdout!r}"
    )
    assert "?" in r.stdout, (
        f"Expected '?' in Kado no_config state.\nstdout: {r.stdout!r}"
    )
    assert ANSI_YELLOW in r.stdout, (
        f"Expected ANSI yellow in Kado no_config state.\nstdout: {r.stdout!r}"
    )


def test_kado_error_renders_gate_port_cross(tmp_path):
    """F7-AC1: Kado error (treated same as unreachable) → 門:23026 ✗ (red)."""
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="error",
        tmp_path=tmp_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "門:23026" in r.stdout, (
        f"Expected '門:23026' in output.\nstdout: {r.stdout!r}"
    )
    assert "✗" in r.stdout, f"Expected ✗ for error. stdout: {r.stdout!r}"
    assert ANSI_RED in r.stdout, (
        f"Expected ANSI red for error state.\nstdout: {r.stdout!r}"
    )


def test_kado_port_from_mcp_json_url(tmp_path):
    """F7-AC1: Port number shown in 門:<port> is parsed from .mcp.json URL."""
    # Use a non-default port to verify we're reading from the URL
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23999),
        kado_cache_content="ok",
        tmp_path=tmp_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "門:23999" in r.stdout, (
        f"Expected '門:23999' (from .mcp.json port 23999).\nstdout: {r.stdout!r}"
    )


def test_kado_old_label_not_present(tmp_path):
    """CON-6 inverse: old 'Kado' label without port must NOT appear in any state."""
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="ok",
        tmp_path=tmp_path,
    )
    stripped = _strip_ansi(r.stdout)
    # Should not find bare "Kado " prefix — must use 門:<port> format
    assert " Kado " not in stripped and "| Kado" not in stripped, (
        f"Old 'Kado' label found — must use 門:<port> format.\nstdout: {r.stdout!r}"
    )


# ── Hashi: 橋:<port> with 3 states (F7-AC2) ──────────────────────────────────

_LOCK_JSON = json.dumps({
    "pid": 0,
    "workspaceFolders": [],
    "ideName": "Obsidian",
    "transport": "ws",
    "authToken": "test-token-uuid",
})


def test_hashi_configured_reachable_renders_bridge_port_check(tmp_path):
    """F7-AC2: lock present + probe ok → 橋:23027 ✓ (green)."""
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="ok",
        lock_files={"23027.lock": _LOCK_JSON},
        hashi_cache_content="ok:23027",
        tmp_path=tmp_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "橋:23027" in r.stdout, (
        f"Expected '橋:23027' in output.\nstdout: {r.stdout!r}"
    )
    assert "✓" in r.stdout, f"Expected ✓ for Hashi ok. stdout: {r.stdout!r}"
    assert ANSI_GREEN in r.stdout, (
        f"Expected ANSI green for Hashi ok.\nstdout: {r.stdout!r}"
    )


def test_hashi_configured_unreachable_renders_bridge_port_cross(tmp_path):
    """F7-AC2: lock present + probe fails → 橋:23027 ✗ (red)."""
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="ok",
        lock_files={"23027.lock": _LOCK_JSON},
        hashi_cache_content="unreachable:23027",
        tmp_path=tmp_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "橋:23027" in r.stdout, (
        f"Expected '橋:23027' in output.\nstdout: {r.stdout!r}"
    )
    assert "✗" in r.stdout, (
        f"Expected ✗ for Hashi unreachable.\nstdout: {r.stdout!r}"
    )
    assert ANSI_RED in r.stdout, (
        f"Expected ANSI red for Hashi unreachable.\nstdout: {r.stdout!r}"
    )


def test_hashi_not_configured_renders_bridge_question(tmp_path):
    """F7-AC2: no lock file → 橋:<port> ? (yellow, not configured)."""
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="ok",
        # no lock_files → no_config
        tmp_path=tmp_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "橋:" in r.stdout, (
        f"Expected '橋:' prefix (Hashi indicator) in output.\nstdout: {r.stdout!r}"
    )
    assert "?" in r.stdout, (
        f"Expected '?' for Hashi no_config.\nstdout: {r.stdout!r}"
    )
    assert ANSI_YELLOW in r.stdout, (
        f"Expected ANSI yellow for Hashi no_config.\nstdout: {r.stdout!r}"
    )


def test_hashi_no_tags_substate(tmp_path):
    """F7-AC2: Hashi never shows 'Tags' sub-state in any state."""
    for hashi_state in ("ok:23027", "unreachable:23027"):
        r = _run_statusline(
            mcp_json_content=_make_mcp_json(23026),
            kado_cache_content="ok",
            lock_files={"23027.lock": _LOCK_JSON},
            hashi_cache_content=hashi_state,
            tmp_path=tmp_path,
        )
        # Extract only the Hashi portion of the output
        # Look for the 橋 section and verify no "Tags" appears there
        stripped = _strip_ansi(r.stdout)
        bridge_idx = stripped.find("橋:")
        assert bridge_idx >= 0, f"橋: not found for state {hashi_state}"
        # Get the Hashi segment (from 橋 to end of line)
        bridge_segment = stripped[bridge_idx:]
        assert "Tags" not in bridge_segment, (
            f"Hashi must not show Tags sub-state (state={hashi_state}).\n"
            f"bridge segment: {bridge_segment!r}\nstdout: {r.stdout!r}"
        )


# ── Color codes retained for ALL states (F7-AC3) ─────────────────────────────

def test_all_kado_states_have_ansi_color(tmp_path):
    """F7-AC3: all Kado states carry ANSI color, not symbol-only."""
    states_and_colors = [
        ("ok", ANSI_GREEN),
        ("unreachable", ANSI_RED),
        ("error", ANSI_RED),
        ("tags_denied", ANSI_YELLOW),
        ("no_config", ANSI_YELLOW),
    ]
    for state, expected_color in states_and_colors:
        r = _run_statusline(
            mcp_json_content=_make_mcp_json(23026),
            kado_cache_content=state,
            tmp_path=tmp_path,
        )
        assert expected_color in r.stdout, (
            f"Kado state '{state}' missing expected ANSI color.\n"
            f"stdout: {r.stdout!r}"
        )


def test_all_hashi_states_have_ansi_color(tmp_path):
    """F7-AC3: all Hashi states carry ANSI color, not symbol-only."""
    # ok + unreachable — each gets its own sub-directory to avoid state bleed
    for idx, (hashi_cache, expected_color) in enumerate([
        ("ok:23027", ANSI_GREEN),
        ("unreachable:23027", ANSI_RED),
    ]):
        sub = tmp_path / f"sub{idx}"
        sub.mkdir()
        r = _run_statusline(
            mcp_json_content=_make_mcp_json(23026),
            kado_cache_content="ok",
            lock_files={"23027.lock": _LOCK_JSON},
            hashi_cache_content=hashi_cache,
            tmp_path=sub,
        )
        assert expected_color in r.stdout, (
            f"Hashi state '{hashi_cache}' missing expected ANSI color.\n"
            f"stdout: {r.stdout!r}"
        )

    # no_config (no lock file) — fresh sub-directory, no prior state
    no_cfg_sub = tmp_path / "no_cfg"
    no_cfg_sub.mkdir()
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="ok",
        tmp_path=no_cfg_sub,
    )
    assert ANSI_YELLOW in r.stdout, (
        f"Hashi no_config missing ANSI yellow.\nstdout: {r.stdout!r}"
    )


# ── Instance label 友 <name> unchanged (CON-6) ────────────────────────────────

def test_instance_label_renders_unchanged(tmp_path):
    """CON-6: 友 <instance-name> still renders when TOMO_INSTANCE_DIR is set."""
    fake_instance = tmp_path / "my-tomo-instance"
    fake_instance.mkdir()

    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="ok",
        tomo_instance_dir=str(fake_instance),
        tmp_path=tmp_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "友" in r.stdout, f"Expected 友 in output. stdout: {r.stdout!r}"
    assert "my-tomo-instance" in r.stdout, (
        f"Expected instance name in output.\nstdout: {r.stdout!r}"
    )


def test_instance_label_absent_when_no_instance_dir(tmp_path):
    """CON-6: 友 label is absent when TOMO_INSTANCE_DIR is unset."""
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="ok",
        tomo_instance_dir="",
        tmp_path=tmp_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "友" not in r.stdout, (
        f"Expected no 友 without TOMO_INSTANCE_DIR.\nstdout: {r.stdout!r}"
    )


# ── Hashi indicator is genuinely new (RED guard) ──────────────────────────────

def test_hashi_indicator_present_in_output(tmp_path):
    """Positive assertion: 橋 character MUST appear in the output.

    This test is the RED guard — it fails before implementation (no 橋 in
    the old script) and passes only after the 橋 indicator is added.
    """
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="ok",
        lock_files={"23027.lock": _LOCK_JSON},
        hashi_cache_content="ok:23027",
        tmp_path=tmp_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "橋" in r.stdout, (
        f"橋 (Hashi) indicator MISSING from output — implementation not wired.\n"
        f"stdout: {r.stdout!r}"
    )


def test_kado_gate_format_present_in_output(tmp_path):
    """RED guard: 門 character MUST appear (Kado reformatted to 門:<port>).

    This fails before implementation (old script shows 'Kado' not '門:').
    """
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="ok",
        tmp_path=tmp_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert "門" in r.stdout, (
        f"門 (Kado reformatted) MISSING from output — implementation not wired.\n"
        f"stdout: {r.stdout!r}"
    )


# ── M2: multiple lock files → no_config (F7-AC2 "exactly one") ───────────────

def test_hashi_multiple_locks_not_configured(tmp_path):
    """F7-AC2: two lock files present → ambiguous → 橋:? ? (yellow, no_config).

    Drives the live hashi_check path (no hashi_cache_content override) so the
    guard added by M1 is actually exercised. Without the lock_count > 1 guard
    in hashi_check, the function would pick an arbitrary lock and probe it —
    either ok or unreachable — so the ✓ or ✗ assertion below would fail RED.
    """
    r = _run_statusline(
        mcp_json_content=_make_mcp_json(23026),
        kado_cache_content="ok",
        lock_files={
            "23027.lock": _LOCK_JSON,
            "23028.lock": _LOCK_JSON,
        },
        # No hashi_cache_content — live hashi_check runs
        tmp_path=tmp_path,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"

    stripped = _strip_ansi(r.stdout)
    bridge_idx = stripped.find("橋:")
    assert bridge_idx >= 0, f"橋: not found in output.\nstdout: {r.stdout!r}"

    bridge_segment = stripped[bridge_idx:]
    assert "?" in bridge_segment, (
        f"Expected '?' for multiple-locks no_config.\nbridge: {bridge_segment!r}"
    )
    assert "✓" not in bridge_segment, (
        f"Must not show ✓ when multiple locks present.\nbridge: {bridge_segment!r}"
    )
    assert "✗" not in bridge_segment, (
        f"Must not show ✗ when multiple locks present.\nbridge: {bridge_segment!r}"
    )
    # Color retained: ANSI yellow for no_config
    assert ANSI_YELLOW in r.stdout, (
        f"Expected ANSI yellow for multiple-locks no_config.\nstdout: {r.stdout!r}"
    )


if __name__ == "__main__":
    import sys
    raise SystemExit(pytest.main([__file__, "-v"] + sys.argv[1:]))
