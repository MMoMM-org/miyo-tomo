#!/usr/bin/env python3
# version: 0.2.0
"""test_begin_tomo_ide.py — Pytest-driven tests for the IDE Bridge banner and
socat drift rebuild in scripts/lib/begin-tomo.sh.template (T3.1).

Strategy:
  1. Render the template via sed (same placeholders install-tomo.sh uses) into a
     tmpdir script, with instance/home paths fully inside tmp_path so no writes
     happen outside the test sandbox.
  2. Stub docker and jq on PATH — shims record calls and return controlled output.
  3. Extract just the relevant blocks from the rendered script so we avoid side-
     effects (docker run at the tail, docker info pre-flight, etc.).
  4. Drive each scenario independently.

Coverage targets:
  - F6-AC1: configured + reachable  → banner "Context: connected" (green)
  - F6-AC2: not configured / disabled → banner "Context: not configured" (dim)
  - F6-AC3: configured + unreachable → non-blocking warning, launch continues
  - F3-AC2: image label tomo.has_socat missing/empty → rebuild branch taken
  - ADR-3:  probe respects ≤3s bound, never blocks launch
"""
from __future__ import annotations

import os
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE = REPO_ROOT / "scripts" / "lib" / "begin-tomo.sh.template"


def _render_template(tmp_path: Path, *,
                     ide_enabled: bool = False,
                     ide_port: int = 23027) -> tuple[Path, dict]:
    """Render begin-tomo.sh.template with test-local paths into tmp_path.

    Returns (rendered_path, placeholders) where placeholders maps template keys
    to the values actually used (all paths inside tmp_path).

    Creates fake tomo-install.json in fake-repo so CONFIG_FILE check succeeds.
    The jq shim handles all actual reads; the file only needs to exist.
    """
    instance_path = str(tmp_path / "tomo-instance")
    home_dir = str(tmp_path / "tomo-home")
    fake_repo = str(tmp_path / "fake-repo")

    placeholders = {
        "{{INSTANCE_PATH}}": instance_path,
        "{{INSTANCE_NAME}}": "tomo-test",
        "{{HOME_DIR}}": home_dir,
        "{{TOMO_REPO_ROOT}}": fake_repo,
        "{{DEV_NOTIFY_PORT}}": "9999",
    }

    content = TEMPLATE.read_text()
    for ph, val in placeholders.items():
        content = content.replace(ph, val)

    out = tmp_path / "begin-tomo.sh"
    out.write_text(content)
    out.chmod(0o755)

    # Create the directories the script checks for
    Path(instance_path).mkdir(parents=True, exist_ok=True)
    Path(home_dir).mkdir(parents=True, exist_ok=True)
    Path(fake_repo).mkdir(parents=True, exist_ok=True)

    # Create a minimal tomo-install.json so CONFIG_FILE existence check passes.
    # The jq shim intercepts all reads — this file just needs to exist.
    # CONFIG_FILE is `$(dirname "$INSTANCE_PATH")/tomo-install.json` (host-side,
    # sibling of the instance dir), so the fixture must live next to the
    # instance dir — NOT under TOMO_REPO_ROOT — or the `[ -f "$CONFIG_FILE" ]`
    # gate skips the IDE-bridge config read and the banner shows "not configured".
    enabled_str = "true" if ide_enabled else "false"
    (Path(instance_path).parent / "tomo-install.json").write_text(
        f'{{"ide_bridge": {{"enabled": {enabled_str}, "port": {ide_port}}}}}'
    )

    return out, placeholders


def _make_docker_shim(shim_dir: Path, *,
                      inspect_voice_label: str,
                      inspect_socat_label: str,
                      inspect_rc: int = 0) -> None:
    """Create a docker stub.

    - `docker info` → exit 0
    - `docker image inspect` with tomo.voice_enabled → inspect_voice_label
    - `docker image inspect` with tomo.has_socat    → inspect_socat_label / exit inspect_rc
    - `docker build` → exit 0, prints "docker-build-ok"
    - everything else → exit 0
    """
    shim_dir.mkdir(parents=True, exist_ok=True)
    docker_shim = shim_dir / "docker"
    docker_shim.write_text(
        textwrap.dedent(f"""\
            #!/bin/sh
            case "$1" in
                info)
                    exit 0 ;;
                image)
                    shift
                    if [ "$1" = "inspect" ]; then
                        shift
                        # Walk args looking for the format string
                        fmt=""
                        for a; do
                            case "$a" in
                                *tomo.has_socat*) fmt="socat" ;;
                                *tomo.voice_enabled*) fmt="voice" ;;
                            esac
                        done
                        case "$fmt" in
                            socat)
                                printf '%s\\n' '{inspect_socat_label}'
                                exit {inspect_rc} ;;
                            voice)
                                printf '%s\\n' '{inspect_voice_label}'
                                exit {inspect_rc} ;;
                            *)
                                exit {inspect_rc} ;;
                        esac
                    fi
                    exit 0 ;;
                build)
                    echo "docker-build-ok"
                    exit 0 ;;
                ps|stop|rm|run)
                    exit 0 ;;
            esac
            exit 0
        """)
    )
    docker_shim.chmod(0o755)


def _make_jq_shim(shim_dir: Path, *,
                  ide_enabled: str,
                  ide_port: str = "23027",
                  voice_triple: str = "false\t\tauto",
                  default_mode: str = "default",
                  tomo_version: str = "0.99.0") -> None:
    """Create a jq stub returning controlled values for keys begin-tomo reads.

    Handles both single-call patterns (.ide_bridge fields) and per-call patterns.
    """
    shim_dir.mkdir(parents=True, exist_ok=True)
    jq_shim = shim_dir / "jq"
    jq_shim.write_text(
        textwrap.dedent(f"""\
            #!/bin/sh
            # jq stub — all args passed as "$@"
            # The expression is always $2 (after -r or -e flag)
            expr=""
            for a; do
                case "$a" in
                    -r|-e) ;;
                    *) expr="$a"; break ;;
                esac
            done
            case "$expr" in
                *ide_bridge*'@tsv'*)
                    printf '%s\\t%s\\n' '{ide_enabled}' '{ide_port}' ;;
                *'@tsv'*)
                    printf '%s\\n' '{voice_triple}' ;;
                *defaultMode*)
                    printf '%s\\n' '{default_mode}' ;;
                *tomoVersion*)
                    printf '%s\\n' '{tomo_version}' ;;
                *ide_bridge*enabled*)
                    printf '%s\\n' '{ide_enabled}' ;;
                *ide_bridge*port*)
                    printf '%s\\n' '{ide_port}' ;;
                *)
                    printf '%s\\n' 'null' ;;
            esac
            exit 0
        """)
    )
    jq_shim.chmod(0o755)


def _extract_banner_blocks(rendered: Path) -> str:
    """Extract the minimal set of blocks needed to test the banner and rebuild.

    Returns a runnable bash snippet that:
    - defines hardcoded path variables (INSTANCE_PATH, TOMO_REPO_ROOT, etc.)
    - defines color vars + print_* helpers
    - reads voice config (needed for VOICE_ENABLED)
    - reads IDE Bridge config from CONFIG_FILE
    - defines _probe_ide_bridge() function
    - runs the image inspect + rebuild logic
    - runs the launch banner (Voice + IDE lines)
    - stops before the docker run
    """
    content = rendered.read_text()

    # 1. Hardcoded variable declarations (rendered paths — required for TOMO_REPO_ROOT etc.)
    vars_match = re.search(
        r"(# ── Hardcoded values.*?)\n# ── Colors",
        content, re.DOTALL,
    )
    hardcoded_vars = vars_match.group(1) if vars_match else ""

    # 2. Color definitions + print helpers (up to CLI Flags)
    colors_match = re.search(
        r"(# ── Colors.*?)\n# ── CLI Flags",
        content, re.DOTALL,
    )
    colors = colors_match.group(1) if colors_match else ""

    # 3. Voice config read block + IDE Bridge config read + probe function
    #    (goes from Voice section to Docker image section — now includes IDE Bridge block)
    voice_match = re.search(
        r"(# ── Voice transcription build state.*?)\n# ── Docker image",
        content, re.DOTALL,
    )
    voice_and_ide = voice_match.group(1) if voice_match else ""

    # 4. Docker image + build_image function + inspect + rebuild logic
    image_match = re.search(
        r"(# ── Docker image.*?)\n# ── Auth",
        content, re.DOTALL,
    )
    image = image_match.group(1) if image_match else ""

    # 5. Launch banner — the "# ── Launch" section until docker run
    launch_match = re.search(
        r"(# ── Launch ─.*?\n.*?)(?=\ndocker run)",
        content, re.DOTALL,
    )
    if launch_match:
        launch = launch_match.group(1)
    else:
        # Fallback: grab from Launch marker to end, strip docker run
        launch_match2 = re.search(r"# ── Launch ─.*", content, re.DOTALL)
        launch = launch_match2.group(0) if launch_match2 else ""
        launch = re.sub(r"\ndocker run.*", "\n# docker run suppressed", launch, flags=re.DOTALL)

    # Also need the CONFIG_FILE variable (set in the "Version check" section).
    # Match the WHOLE line, not a quote-delimited fragment: the value nests a
    # double quote (`CONFIG_FILE="$(dirname "$INSTANCE_PATH")/..."`), so a
    # `"[^"]+"` window stops at the inner quote and yields an unbalanced
    # `CONFIG_FILE="$(dirname "` fragment that breaks the assembled snippet.
    config_var_match = re.search(
        r"^CONFIG_FILE=.*$",
        content,
        re.MULTILINE,
    )
    config_var = config_var_match.group(0) if config_var_match else ""
    # And FORCE_REBUILD default
    force_rebuild = "FORCE_REBUILD=false"

    return "\n".join(filter(None, [
        "set -e",
        hardcoded_vars,
        colors,
        force_rebuild,
        config_var,
        voice_and_ide,
        image,
        launch,
    ]))


def _run_snippet(snippet: str, shim_dir: Path,
                 env_extra: dict | None = None) -> subprocess.CompletedProcess:
    """Run a bash snippet with stub tools prepended to PATH."""
    env = dict(os.environ)
    env["PATH"] = f"{shim_dir}:{env['PATH']}"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", "-c", snippet],
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


def _inject_probe_stub(snippet: str, reachable: bool) -> str:
    """Replace the real _probe_ide_bridge() function body with a controlled stub.

    The stub must come AFTER the function is initially defined in the snippet, so
    we append a redefining override at the end of the script preamble — i.e. after
    all function definitions but before the code that calls the probe. We do this
    by appending an override right before the '# ── Docker image' section.
    """
    result_cmd = "return 0" if reachable else "return 1"
    stub = textwrap.dedent(f"""\
        # Probe stub (injected by test) — overrides _probe_ide_bridge defined above
        _probe_ide_bridge() {{
            {result_cmd}
        }}
    """)
    # Inject just before the Docker image section so it overrides the real function
    marker = "# ── Docker image"
    if marker in snippet:
        return snippet.replace(marker, stub + "\n" + marker, 1)
    # Fallback: append at the end of any function definitions
    return snippet + "\n" + stub


# ── F6-AC1: configured + reachable → "connected" ─────────────────────────────

def test_banner_configured_reachable(tmp_path):
    """F6-AC1: .ide_bridge.enabled=true + probe succeeds → 'connected' in banner."""
    rendered, phs = _render_template(tmp_path)
    shim_dir = tmp_path / "shims"

    _make_jq_shim(shim_dir, ide_enabled="true", ide_port="23027",
                  voice_triple="0\t\tauto")
    _make_docker_shim(shim_dir, inspect_voice_label="0",
                      inspect_socat_label="1", inspect_rc=0)

    snippet = _extract_banner_blocks(rendered)
    snippet = _inject_probe_stub(snippet, reachable=True)

    result = _run_snippet(snippet, shim_dir)
    assert result.returncode == 0, (
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "connected" in combined, (
        f"Expected 'connected'. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "not configured" not in combined
    assert "unreachable" not in combined.lower()


# ── F6-AC2: not configured → "not configured" (dim) ──────────────────────────

def test_banner_not_configured(tmp_path):
    """F6-AC2: .ide_bridge absent or enabled=false → 'not configured' in banner."""
    rendered, phs = _render_template(tmp_path)
    shim_dir = tmp_path / "shims"

    _make_jq_shim(shim_dir, ide_enabled="false", voice_triple="0\t\tauto")
    _make_docker_shim(shim_dir, inspect_voice_label="0",
                      inspect_socat_label="1", inspect_rc=0)

    snippet = _extract_banner_blocks(rendered)
    snippet = _inject_probe_stub(snippet, reachable=False)

    result = _run_snippet(snippet, shim_dir)
    assert result.returncode == 0, (
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    # Positive guard: the IDE banner line itself must have rendered.
    # Without this, a missing IDE block would produce "not configured" vacuously
    # (unset IDE_BRIDGE_ENABLED → false branch → dim output) and the test would
    # pass having never exercised the config read path.
    assert "Context:" in combined, (
        f"Context banner line absent — IDE config block may not have run.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "not configured" in combined, (
        f"Expected 'not configured'. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "connected" not in combined


# ── F6-AC3: configured + unreachable → warning, launch continues ──────────────

def test_banner_configured_unreachable_non_blocking(tmp_path):
    """F6-AC3: configured + probe fails → warning + exit 0 (non-blocking)."""
    rendered, phs = _render_template(tmp_path)
    shim_dir = tmp_path / "shims"

    _make_jq_shim(shim_dir, ide_enabled="true", ide_port="23027",
                  voice_triple="0\t\tauto")
    _make_docker_shim(shim_dir, inspect_voice_label="0",
                      inspect_socat_label="1", inspect_rc=0)

    snippet = _extract_banner_blocks(rendered)
    snippet = _inject_probe_stub(snippet, reachable=False)

    result = _run_snippet(snippet, shim_dir)
    assert result.returncode == 0, (
        f"Expected exit 0 (non-blocking). Got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    # Warning must be visible (unreachable annotation or ⚠ symbol)
    has_warning = (
        "unreachable" in combined.lower()
        or "Hashi unreachable" in combined
        or "⚠" in combined
    )
    assert has_warning, (
        f"Expected unreachable warning. stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    # Banner line "configured (Hashi unreachable)" must still appear (with warning annotation)
    assert "configured (Hashi unreachable)" in combined, (
        f"Expected 'configured (Hashi unreachable)' (with warning). stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ── F3-AC2: image has no tomo.has_socat label → rebuild ──────────────────────

def test_socat_label_missing_triggers_rebuild(tmp_path):
    """F3-AC2: tomo.has_socat absent (empty string) on existing image → rebuild taken."""
    rendered, phs = _render_template(tmp_path)
    shim_dir = tmp_path / "shims"

    _make_jq_shim(shim_dir, ide_enabled="false", voice_triple="0\t\tauto")
    # Image exists (rc=0), voice label matches, socat label is empty → rebuild
    _make_docker_shim(shim_dir,
                      inspect_voice_label="0",
                      inspect_socat_label="",
                      inspect_rc=0)

    snippet = _extract_banner_blocks(rendered)
    # No probe stub needed — rebuild happens before probe
    snippet = "# rebuild test — no probe stub\n" + snippet

    result = _run_snippet(snippet, shim_dir)

    combined = result.stdout + result.stderr
    # The rebuild prints "docker-build-ok" or "Rebuilding"
    assert "docker-build-ok" in combined or "Rebuilding" in combined, (
        f"Expected rebuild output for missing socat label.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ── F3-AC2: image has tomo.has_socat=1 → no rebuild ─────────────────────────

def test_socat_label_present_skips_rebuild(tmp_path):
    """When tomo.has_socat=1 label present and voice matches → no rebuild."""
    rendered, phs = _render_template(tmp_path)
    shim_dir = tmp_path / "shims"

    _make_jq_shim(shim_dir, ide_enabled="false", voice_triple="0\t\tauto")
    _make_docker_shim(shim_dir,
                      inspect_voice_label="0",
                      inspect_socat_label="1",
                      inspect_rc=0)

    snippet = _extract_banner_blocks(rendered)
    snippet = "# no probe stub\n" + snippet
    result = _run_snippet(snippet, shim_dir)

    combined = result.stdout + result.stderr
    assert "docker-build-ok" not in combined, (
        f"Expected no rebuild when socat label=1. stdout:\n{result.stdout}"
    )
    # Positive assertion: the no-rebuild branch must have executed and printed
    # "Image exists: ...". Without this, a failed extraction (empty image block)
    # would pass vacuously — docker never called, build never triggered, test green.
    assert "Image exists" in combined, (
        f"Expected 'Image exists' from no-rebuild branch.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert result.returncode == 0, (
        f"Expected clean exit. stderr:\n{result.stderr}"
    )


# ── ADR-3: probe must not hang / must respect ≤3s bound ──────────────────────

def _find_free_port() -> int:
    """Bind to port 0, capture the assigned port, then close the socket.

    The returned port is guaranteed free at the instant of return — no process
    is listening, so a /dev/tcp connect attempt will get connection-refused
    immediately rather than hanging or succeeding.
    """
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_probe_timeout_does_not_block(tmp_path):
    """ADR-3: real probe on a guaranteed-closed port returns unreachable within 5s.

    Uses a port that was free at test start (connection-refused on connect) so
    the fail path of _probe_ide_bridge() is exercised — not a trivial success
    case that would leave the timeout/kill code paths uncovered.

    Asserts:
    - elapsed time < 5s (probe respects ADR-3 ≤3s bound)
    - exit code 0 (probe failure is non-blocking — launch continues)
    - banner shows the configured-but-unreachable warning (probe actually ran
      and returned false, not a stub)
    """
    import time

    free_port = _find_free_port()

    rendered, phs = _render_template(tmp_path)
    shim_dir = tmp_path / "shims"

    _make_jq_shim(shim_dir, ide_enabled="true", ide_port=str(free_port),
                  voice_triple="0\t\tauto")
    _make_docker_shim(shim_dir,
                      inspect_voice_label="0",
                      inspect_socat_label="1",
                      inspect_rc=0)

    # No probe stub — drive the real _probe_ide_bridge() implementation
    # against the closed port to exercise the failure + kill/wait path.
    snippet = _extract_banner_blocks(rendered)

    start = time.monotonic()
    result = _run_snippet(snippet, shim_dir)
    elapsed = time.monotonic() - start

    assert elapsed < 5.0, (
        f"Probe took {elapsed:.1f}s — exceeded 5s safety margin (ADR-3: ≤3s).\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # Launch must continue — probe failure is non-blocking
    assert result.returncode == 0, (
        f"Snippet exited {result.returncode} — probe blocked/killed launch.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    # Probe must have returned unreachable → warning banner (not "connected" clean)
    assert "unreachable" in combined.lower() or "⚠" in combined, (
        f"Expected unreachable warning (probe ran and returned false on closed port).\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ── Regression: voice banner unchanged (CON-6) ───────────────────────────────

def test_voice_banner_unchanged(tmp_path):
    """CON-6: voice banner line still renders correctly after IDE changes."""
    rendered, phs = _render_template(tmp_path)
    shim_dir = tmp_path / "shims"

    # Voice enabled with model large-v3
    _make_jq_shim(shim_dir, ide_enabled="false",
                  voice_triple="true\tlarge-v3\tauto")
    _make_docker_shim(shim_dir,
                      inspect_voice_label="1",  # matches voice enabled
                      inspect_socat_label="1",
                      inspect_rc=0)

    # Create the .download-complete marker so ENABLED banner renders cleanly
    instance_path = phs["{{INSTANCE_PATH}}"]
    model_dir = Path(instance_path) / "voice" / "models" / "faster-whisper-large-v3"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / ".download-complete").touch()

    # Write a fake voice/config.json (the voice block reads this)
    voice_dir = Path(instance_path) / "voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    (voice_dir / "config.json").write_text(
        '{"enabled": true, "model": "large-v3", "language": "auto"}'
    )

    snippet = _extract_banner_blocks(rendered)
    snippet = "# no probe stub\n" + snippet
    result = _run_snippet(snippet, shim_dir)

    combined = result.stdout + result.stderr
    assert "ENABLED" in combined or "Voice" in combined, (
        f"Voice banner missing after IDE changes.\nstdout: {result.stdout}\nstderr:{result.stderr}"
    )


def test_docker_run_adds_host_gateway_mapping():
    """#48: docker run must map host.docker.internal:host-gateway.

    The container statusline probe targets host.docker.internal:<port>; without
    this --add-host the name only resolves on Docker Desktop and would fail-RED
    on Linux even when Hashi is up. Static-source check — the suite stubs the
    probe and never reaches a live `docker run`.
    """
    content = TEMPLATE.read_text()
    assert "--add-host" in content and "host.docker.internal:host-gateway" in content, (
        "begin-tomo.sh.template docker run must pass "
        "--add-host host.docker.internal:host-gateway (#48)."
    )


if __name__ == "__main__":
    import sys
    raise SystemExit(pytest.main([__file__, "-v"] + sys.argv[1:]))
