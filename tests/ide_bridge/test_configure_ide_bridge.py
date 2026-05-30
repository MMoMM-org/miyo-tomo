#!/usr/bin/env python3
# version: 0.3.3
"""test_configure_ide_bridge.py — Pytest-driven tests for the IDE Bridge wizard lib.

Drives `scripts/lib/configure-ide-bridge.sh` via subprocess with controlled
stdin and asserts the exported globals (IDE_BRIDGE_ENABLED, IDE_BRIDGE_TOKEN,
IDE_BRIDGE_PORT). Uses tmp_path for all file writes; never touches a real install.

Mirrors the test structure of tests/voice/test_configure_voice.py.
"""
from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path
import stat

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIGURE_SH = REPO_ROOT / "scripts/lib/configure-ide-bridge.sh"

# Real Hashi token format: hashi_<8-4-4-4-12 hex UUID>
VALID_TOKEN = "hashi_a1b2c3d4-e5f6-7890-abcd-ef1234567890"
VALID_TOKEN_2 = "hashi_deadbeef-dead-beef-dead-beefdeadbeef"

# Keep bare-UUID constants for tests that exercise the lock-file write path
# (write_ide_lock is opaque to token format — it stores whatever string it receives)
VALID_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
VALID_UUID_2 = "deadbeef-dead-beef-dead-beefdeadbeef"


def _run_wizard(
    current_enabled: str,
    current_token: str,
    current_port: str,
    home_dir: Path,
    stdin_text: str,
    non_interactive: str = "false",
):
    """Invoke configure_ide_bridge() and capture the resulting globals.

    Sources configure-ide-bridge.sh in a subshell, runs the wizard with the
    given stdin, then echoes the globals so we can parse them back.
    """
    home_dir.mkdir(parents=True, exist_ok=True)

    script = textwrap.dedent(f"""\
        print_step() {{ echo "[step] $1"; }}
        print_ok()   {{ echo "[ok]   $1"; }}
        print_warn() {{ echo "[warn] $1"; }}
        print_err()  {{ echo "[err]  $1" >&2; }}

        . "{CONFIGURE_SH}"
        configure_ide_bridge "{current_enabled}" "{current_token}" \\
                             "{current_port}" "{home_dir}" "{non_interactive}"
        echo "RESULT_ENABLED=$IDE_BRIDGE_ENABLED"
        echo "RESULT_TOKEN=$IDE_BRIDGE_TOKEN"
        echo "RESULT_PORT=$IDE_BRIDGE_PORT"
    """)

    r = subprocess.run(
        ["bash", "-c", script],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return r


def _parse(r):
    out = {}
    for line in r.stdout.splitlines():
        if line.startswith("RESULT_"):
            k, _, v = line.partition("=")
            out[k.removeprefix("RESULT_")] = v
    return out


# ── Test 1: non-interactive fresh install ────────────────────────────────────

def test_non_interactive_fresh_install_defaults_disabled(tmp_path):
    r = _run_wizard("false", "", "", tmp_path / "home", "", non_interactive="true")
    assert r.returncode == 0, f"stderr: {r.stderr}"
    result = _parse(r)
    assert result["ENABLED"] == "false"
    # No lock file should be written
    lock_dir = tmp_path / "home" / ".claude" / "ide"
    assert not lock_dir.exists() or not list(lock_dir.glob("*.lock"))


# ── Test 2: non-interactive preserves existing enabled config ─────────────────

def test_non_interactive_preserves_enabled_state(tmp_path):
    r = _run_wizard(
        "true", VALID_TOKEN, "23027",
        tmp_path / "home", "",
        non_interactive="true",
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    result = _parse(r)
    assert result["ENABLED"] == "true"
    assert result["TOKEN"] == VALID_TOKEN
    assert result["PORT"] == "23027"


# ── Test 3: fresh enable with valid hashi_ token and default port ─────────────

def test_fresh_enable_valid_token_default_port(tmp_path):
    """hashi_<uuid> accepted verbatim (including prefix) — RED before fix."""
    # y → enable, then hashi_ token, then empty (accept default port 23027)
    stdin = f"y\n{VALID_TOKEN}\n\n"
    r = _run_wizard("false", "", "", tmp_path / "home", stdin)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    result = _parse(r)
    assert result["ENABLED"] == "true"
    assert result["TOKEN"] == VALID_TOKEN   # prefix must be preserved
    assert result["PORT"] == "23027"


# ── Test 3b: bare UUID (no prefix) REJECTED ───────────────────────────────────

def test_bare_uuid_rejected(tmp_path):
    """Bare UUID without hashi_ prefix is REJECTED — RED before fix."""
    # y → enable, bare UUID (should be rejected), then valid hashi_ token, then empty port
    stdin = f"y\n{VALID_UUID}\n{VALID_TOKEN}\n\n"
    r = _run_wizard("false", "", "", tmp_path / "home", stdin)
    assert r.returncode == 0, f"stdout: {r.stdout}\nstderr: {r.stderr}"
    result = _parse(r)
    # Bare UUID must not be accepted; only the hashi_ token should persist
    assert result["TOKEN"] == VALID_TOKEN
    assert result["ENABLED"] == "true"
    assert result["TOKEN"] != VALID_UUID  # strict: bare UUID must NOT be accepted
    # Error must be reported for the bare UUID
    assert "Invalid" in r.stderr or "invalid" in r.stderr


# ── Test 4: other invalid tokens rejected, does not persist garbage ───────────

def test_invalid_token_rejected(tmp_path):
    """not-a-hashi / wrong-prefix / hashi_not-a-uuid all rejected."""
    # y → enable, three bad tokens, then valid hashi_ token, then empty port
    stdin = f"y\nnot-a-hashi\nwrong_{VALID_UUID}\nhashi_not-a-uuid\n{VALID_TOKEN}\n\n"
    r = _run_wizard("false", "", "", tmp_path / "home", stdin)
    assert r.returncode == 0, f"stdout: {r.stdout}\nstderr: {r.stderr}"
    result = _parse(r)
    # Must not accept any of the garbage tokens
    assert result["TOKEN"] == VALID_TOKEN
    assert result["ENABLED"] == "true"
    # Error must be reported (at least once)
    assert "Invalid" in r.stderr or "invalid" in r.stderr


# ── Test 5: token with leading/trailing whitespace → trimmed then accepted ────

def test_token_whitespace_trimmed_and_accepted(tmp_path):
    """Whitespace around hashi_<uuid> is trimmed then accepted — RED before fix."""
    # y → enable, then hashi_ token with surrounding spaces, then empty port
    stdin = f"y\n  {VALID_TOKEN}  \n\n"
    r = _run_wizard("false", "", "", tmp_path / "home", stdin)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    result = _parse(r)
    assert result["TOKEN"] == VALID_TOKEN   # trimmed; prefix preserved
    assert result["ENABLED"] == "true"


# ── Test 6: invalid port rejected ─────────────────────────────────────────────

def test_port_non_numeric_rejected(tmp_path):
    # y → enable, valid hashi_ token, non-numeric port, then valid port
    stdin = f"y\n{VALID_TOKEN}\nabc\n23027\n"
    r = _run_wizard("false", "", "", tmp_path / "home", stdin)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    result = _parse(r)
    assert result["PORT"] == "23027"
    assert "Invalid" in r.stderr or "invalid" in r.stderr


def test_port_out_of_range_high_rejected(tmp_path):
    # y → enable, valid hashi_ token, port too high (70000), then valid port
    stdin = f"y\n{VALID_TOKEN}\n70000\n23027\n"
    r = _run_wizard("false", "", "", tmp_path / "home", stdin)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    result = _parse(r)
    assert result["PORT"] == "23027"
    assert "Invalid" in r.stderr or "invalid" in r.stderr


def test_port_zero_rejected(tmp_path):
    # y → enable, valid hashi_ token, port 0 (out of range), then valid port
    stdin = f"y\n{VALID_TOKEN}\n0\n23027\n"
    r = _run_wizard("false", "", "", tmp_path / "home", stdin)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    result = _parse(r)
    assert result["PORT"] == "23027"
    assert "Invalid" in r.stderr or "invalid" in r.stderr


# ── Test 7: already-enabled state dispatch ────────────────────────────────────

def test_already_enabled_K_keeps(tmp_path):
    r = _run_wizard("true", VALID_TOKEN, "23027", tmp_path / "home", "K\n")
    assert r.returncode == 0, f"stderr: {r.stderr}"
    result = _parse(r)
    assert result["ENABLED"] == "true"
    assert result["TOKEN"] == VALID_TOKEN
    assert result["PORT"] == "23027"


def test_already_enabled_d_disables(tmp_path):
    r = _run_wizard("true", VALID_TOKEN, "23027", tmp_path / "home", "d\n")
    assert r.returncode == 0, f"stderr: {r.stderr}"
    result = _parse(r)
    assert result["ENABLED"] == "false"
    # Token and port are preserved in globals (caller writes config)
    assert result["TOKEN"] == VALID_TOKEN
    assert result["PORT"] == "23027"


def test_already_enabled_c_updates_token_and_port(tmp_path):
    # c → change, new hashi_ token, new port
    stdin = f"c\n{VALID_TOKEN_2}\n23028\n"
    r = _run_wizard("true", VALID_TOKEN, "23027", tmp_path / "home", stdin)
    assert r.returncode == 0, f"stderr: {r.stderr}"
    result = _parse(r)
    assert result["ENABLED"] == "true"
    assert result["TOKEN"] == VALID_TOKEN_2
    assert result["PORT"] == "23028"


# ── Test 8: write_ide_bridge_config round-trips via jq ───────────────────────

def test_write_ide_bridge_config_writes_all_fields(tmp_path):
    """write_ide_bridge_config merges the ide_bridge block into a JSON file."""
    target = tmp_path / "tomo-install.json"
    target.write_text('{"kado": {"port": 23026}}')

    script = textwrap.dedent(f"""\
        print_step() {{ :; }}
        print_ok()   {{ :; }}
        print_warn() {{ :; }}
        print_err()  {{ :; }}
        . "{CONFIGURE_SH}"
        IDE_BRIDGE_ENABLED=true
        IDE_BRIDGE_TOKEN="{VALID_UUID}"
        IDE_BRIDGE_PORT=23027
        write_ide_bridge_config "{target}"
    """)
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, f"stderr: {r.stderr}"

    data = json.loads(target.read_text())
    ib = data["ide_bridge"]
    assert ib["schema_version"] == 1
    assert ib["enabled"] is True
    assert ib["auth_token"] == VALID_UUID
    assert ib["port"] == 23027
    # Existing keys must survive the merge
    assert data["kado"]["port"] == 23026

    # Double-check each field via jq -e (mirrors the bash jq assertions)
    for jq_expr, expected in [
        (".ide_bridge.schema_version", "1"),
        (".ide_bridge.enabled", "true"),
        (f'.ide_bridge.auth_token == "{VALID_UUID}"', "true"),
        (".ide_bridge.port", "23027"),
    ]:
        r2 = subprocess.run(
            ["jq", "-r", jq_expr, str(target)],
            capture_output=True, text=True, timeout=5,
        )
        assert r2.returncode == 0, f"jq failed on {jq_expr}: {r2.stderr}"
        assert r2.stdout.strip() == expected, f"jq {jq_expr}: got {r2.stdout.strip()!r}"


def test_write_ide_bridge_config_disabled_flag(tmp_path):
    """write_ide_bridge_config writes enabled=false correctly."""
    target = tmp_path / "tomo-install.json"
    target.write_text("{}")

    script = textwrap.dedent(f"""\
        print_step() {{ :; }}
        print_ok()   {{ :; }}
        print_warn() {{ :; }}
        print_err()  {{ :; }}
        . "{CONFIGURE_SH}"
        IDE_BRIDGE_ENABLED=false
        IDE_BRIDGE_TOKEN="{VALID_UUID}"
        IDE_BRIDGE_PORT=23027
        write_ide_bridge_config "{target}"
    """)
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, f"stderr: {r.stderr}"

    data = json.loads(target.read_text())
    assert data["ide_bridge"]["enabled"] is False


# ── Test 9: write_ide_lock creates correct lock file ─────────────────────────

def test_write_ide_lock_fields_and_permissions(tmp_path):
    """write_ide_lock writes 5-field JSON; dir is 0700; file is NOT 0600."""
    home = tmp_path / "home"

    script = textwrap.dedent(f"""\
        print_step() {{ :; }}
        print_ok()   {{ :; }}
        print_warn() {{ :; }}
        print_err()  {{ :; }}
        . "{CONFIGURE_SH}"
        write_ide_lock "{home}" "23027" "{VALID_UUID}"
    """)
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, f"stderr: {r.stderr}"

    lock_file = home / ".claude" / "ide" / "23027.lock"
    assert lock_file.exists(), "lock file was not created"

    # Verify all 5 fields via jq -e
    for jq_expr, expected in [
        (".pid", "0"),
        (".workspaceFolders | length", "0"),
        ('.ideName', "Obsidian"),
        ('.transport', "ws"),
        (f'.authToken == "{VALID_UUID}"', "true"),
    ]:
        r2 = subprocess.run(
            ["jq", "-r", jq_expr, str(lock_file)],
            capture_output=True, text=True, timeout=5,
        )
        assert r2.returncode == 0, f"jq failed on {jq_expr}: {r2.stderr}"
        assert r2.stdout.strip() == expected, f"jq {jq_expr}: got {r2.stdout.strip()!r}"

    # Directory must be 0700
    ide_dir = home / ".claude" / "ide"
    dir_mode = stat.S_IMODE(ide_dir.stat().st_mode)
    assert dir_mode == 0o700, f"ide dir mode: {oct(dir_mode)}"

    # Lock file must NOT be 0600 (ADR-4)
    file_mode = stat.S_IMODE(lock_file.stat().st_mode)
    assert file_mode != 0o600, f"lock file should not be 0600 but got {oct(file_mode)}"


# ── Test 10: disable path — lock gone, config preserved ──────────────────────

def test_disable_removes_lock_preserves_config(tmp_path):
    """d-path: remove_ide_lock deletes the lock file; write_ide_bridge_config
    still writes auth_token and port into the JSON (disabled but preserved)."""
    home = tmp_path / "home"
    target = tmp_path / "tomo-install.json"
    target.write_text("{}")

    # 1. First create a lock file (write_ide_lock is token-format-agnostic)
    script_create = textwrap.dedent(f"""\
        print_step() {{ :; }}
        print_ok()   {{ :; }}
        print_warn() {{ :; }}
        print_err()  {{ :; }}
        . "{CONFIGURE_SH}"
        write_ide_lock "{home}" "23027" "{VALID_TOKEN}"
    """)
    r = subprocess.run(["bash", "-c", script_create], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, f"create lock stderr: {r.stderr}"
    lock_file = home / ".claude" / "ide" / "23027.lock"
    assert lock_file.exists()

    # 2. Disable flow: wizard sets ENABLED=false, caller calls remove_ide_lock
    stdin = "d\n"
    r2 = _run_wizard("true", VALID_TOKEN, "23027", home, stdin)
    assert r2.returncode == 0, f"wizard stderr: {r2.stderr}"
    result = _parse(r2)
    assert result["ENABLED"] == "false"
    assert result["TOKEN"] == VALID_TOKEN
    assert result["PORT"] == "23027"

    # 3. Call remove_ide_lock (what the caller would do)
    script_remove = textwrap.dedent(f"""\
        print_step() {{ :; }}
        print_ok()   {{ :; }}
        print_warn() {{ :; }}
        print_err()  {{ :; }}
        . "{CONFIGURE_SH}"
        remove_ide_lock "{home}" "23027"
    """)
    r3 = subprocess.run(["bash", "-c", script_remove], capture_output=True, text=True, timeout=10)
    assert r3.returncode == 0, f"remove lock stderr: {r3.stderr}"
    assert not lock_file.exists(), "lock file should have been removed"

    # 4. write_ide_bridge_config with ENABLED=false still preserves token+port
    script_write = textwrap.dedent(f"""\
        print_step() {{ :; }}
        print_ok()   {{ :; }}
        print_warn() {{ :; }}
        print_err()  {{ :; }}
        . "{CONFIGURE_SH}"
        IDE_BRIDGE_ENABLED=false
        IDE_BRIDGE_TOKEN="{VALID_TOKEN}"
        IDE_BRIDGE_PORT=23027
        write_ide_bridge_config "{target}"
    """)
    r4 = subprocess.run(["bash", "-c", script_write], capture_output=True, text=True, timeout=10)
    assert r4.returncode == 0, f"write config stderr: {r4.stderr}"

    data = json.loads(target.read_text())
    ib = data["ide_bridge"]
    assert ib["enabled"] is False
    assert ib["auth_token"] == VALID_TOKEN
    assert ib["port"] == 23027


# ── Edge: fresh install decline stays disabled ────────────────────────────────

def test_fresh_install_decline_stays_disabled(tmp_path):
    r = _run_wizard("false", "", "", tmp_path / "home", "n\n")
    assert r.returncode == 0, f"stderr: {r.stderr}"
    result = _parse(r)
    assert result["ENABLED"] == "false"


# ── Edge: write_ide_bridge_config rejects non-existent target ────────────────

def test_write_ide_bridge_config_missing_target_returns_error(tmp_path):
    """write_ide_bridge_config returns 2 and prints to stderr when target absent.

    This guards the install/update callers against a data-loss class where a
    missing tomo-install.json would silently produce no output file.
    """
    missing = tmp_path / "does-not-exist.json"

    script = textwrap.dedent(f"""\
        print_step() {{ :; }}
        print_ok()   {{ :; }}
        print_warn() {{ :; }}
        print_err()  {{ :; }}
        . "{CONFIGURE_SH}"
        IDE_BRIDGE_ENABLED=false
        IDE_BRIDGE_TOKEN="{VALID_UUID}"
        IDE_BRIDGE_PORT=23027
        write_ide_bridge_config "{missing}"
    """)
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=10)
    assert r.returncode == 2
    assert "target does not exist" in r.stderr


# ── T1.2 tests: install smoke + lock-gen focused test ────────────────────────

INSTALL_SH = REPO_ROOT / "scripts/install-tomo.sh"


@pytest.mark.skipif(
    __import__("shutil").which("docker") is None,
    reason="docker not available in this environment",
)
def test_install_smoke_ide_bridge_block_exists(tmp_path):
    """Isolated install smoke: assert tomo-install.json contains .ide_bridge block.

    RED before T1.2 wiring (key absent); GREEN after (key present).
    Uses all four isolation flags so the test never touches the real instance.
    """
    import shutil

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    home_dir = tmp_path / "home"
    cfg_file = tmp_path / "cfg.json"

    r = subprocess.run(
        [
            "bash",
            str(INSTALL_SH),
            "--vault", str(vault_dir),
            "--non-interactive",
            "--instance-location", str(tmp_path),
            "--instance-name", "tomo-instance",
            "--home-dir", str(home_dir),
            "--config-file", str(cfg_file),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, f"install-tomo.sh failed:\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    assert cfg_file.exists(), "cfg.json was not created"

    # Assert the .ide_bridge block exists via jq -e
    r2 = subprocess.run(
        ["jq", "-e", ".ide_bridge", str(cfg_file)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert r2.returncode == 0, (
        f"jq -e '.ide_bridge' failed — block absent in {cfg_file.read_text()}"
    )


def test_write_ide_lock_path_and_content(tmp_path):
    """write_ide_lock produces <home>/.claude/ide/<port>.lock with workspaceFolders
    populated from the 4th arg (container instance path).

    RED before the 4th-arg change (old signature emits []); GREEN after.
    Drives the lib functions directly via bash subprocess — install-free.
    """
    home = tmp_path / "home"
    workspace = str(tmp_path / "tomo-instance")

    script = textwrap.dedent(f"""\
        print_step() {{ :; }}
        print_ok()   {{ :; }}
        print_warn() {{ :; }}
        print_err()  {{ :; }}
        . "{CONFIGURE_SH}"
        write_ide_lock "{home}" "23027" "{VALID_UUID}" "{workspace}"
    """)
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, f"stderr: {r.stderr}"

    lock_file = home / ".claude" / "ide" / "23027.lock"
    assert lock_file.exists(), f"Expected lock at {lock_file}"

    data = json.loads(lock_file.read_text())
    assert data["authToken"] == VALID_UUID
    assert data["ideName"] == "Obsidian"
    assert data["transport"] == "ws"
    assert data["pid"] == 0
    assert data["workspaceFolders"] == [workspace], (
        f"Expected workspaceFolders=[{workspace!r}], got {data['workspaceFolders']!r}"
    )


def test_write_ide_lock_empty_workspace_backward_safe(tmp_path):
    """Omitting the 4th arg OR passing explicit empty string yields workspaceFolders: [].

    Covers both backward-compatible cases:
    - No 4th arg: callers that haven't been updated yet
    - Explicit empty string: callers that pass "" when IDE Bridge is disabled
    """
    home = tmp_path / "home"

    for label, script_body in [
        ("no-4th-arg", f'write_ide_lock "{home}" "23027" "{VALID_UUID}"'),
        ("explicit-empty", f'write_ide_lock "{home}" "23027" "{VALID_UUID}" ""'),
    ]:
        # Remove any lock from a prior iteration
        lock_file = home / ".claude" / "ide" / "23027.lock"
        if lock_file.exists():
            lock_file.unlink()

        script = textwrap.dedent(f"""\
            print_step() {{ :; }}
            print_ok()   {{ :; }}
            print_warn() {{ :; }}
            print_err()  {{ :; }}
            . "{CONFIGURE_SH}"
            {script_body}
        """)
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=10)
        assert r.returncode == 0, f"[{label}] stderr: {r.stderr}"
        assert lock_file.exists(), f"[{label}] Expected lock at {lock_file}"

        data = json.loads(lock_file.read_text())
        assert data["workspaceFolders"] == [], (
            f"[{label}] Expected workspaceFolders=[], got {data['workspaceFolders']!r}"
        )
        assert data["authToken"] == VALID_UUID
        assert data["pid"] == 0
        assert data["ideName"] == "Obsidian"
        assert data["transport"] == "ws"


def test_write_ide_bridge_config_in_install_context(tmp_path):
    """write_ide_bridge_config persists .ide_bridge into an existing JSON file.

    Simulates the post-install config write: a skeleton tomo-install.json
    (with a voice block) gains an ide_bridge block after calling the helper.
    """
    cfg = tmp_path / "tomo-install.json"
    cfg.write_text('{"voice": {"enabled": false, "model": "", "language": ""}}')

    script = textwrap.dedent(f"""\
        print_step() {{ :; }}
        print_ok()   {{ :; }}
        print_warn() {{ :; }}
        print_err()  {{ :; }}
        . "{CONFIGURE_SH}"
        IDE_BRIDGE_ENABLED=false
        IDE_BRIDGE_TOKEN=""
        IDE_BRIDGE_PORT=23027
        write_ide_bridge_config "{cfg}"
    """)
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, f"stderr: {r.stderr}"

    data = json.loads(cfg.read_text())
    assert "ide_bridge" in data, f"ide_bridge key missing from {data}"
    ib = data["ide_bridge"]
    assert ib["enabled"] is False
    assert ib["port"] == 23027
    assert "auth_token" in ib
    # Existing voice block must survive
    assert "voice" in data


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
