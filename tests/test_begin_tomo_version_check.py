#!/usr/bin/env python3
# version: 0.1.0
"""test_begin_tomo_version_check.py — Tests for T3.3: non-fatal update-availability check.

Covers:
A. _version_compare unit cases (exhaustive, bash-3.2 portability)
B. Version-check block routing:
   - behind: warn showing installed vs available, offer update-tomo.sh --instance
   - current/ahead: silent, proceed
   - broken (missing source file, unknown versions): non-fatal, proceed
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "scripts" / "lib"
RENDER_LAUNCHER = LIB_DIR / "render-launcher.sh"
TEMPLATE = LIB_DIR / "begin-tomo.sh.template"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_version_compare(template: Path = TEMPLATE) -> str:
    """Extract the _version_compare function body from the template via sed.

    Mirrors the pattern in test_begin_tomo_identity.py's _sanitize_via_bash.
    """
    result = subprocess.run(
        ["sed", "-n", "/^_version_compare()/,/^}/p", str(template)],
        capture_output=True, text=True, check=True,
    )
    func = result.stdout
    assert func.strip(), f"Failed to extract _version_compare from {template}"
    return func


def _version_compare(a: str, b: str) -> str:
    """Run _version_compare against real bash using env vars (avoids dash-flag parsing).

    Returns one of: "behind", "ahead", "equal", "unknown".
    Always returns 0 (set -e safe) — we assert returncode == 0 to verify that.
    """
    func = _extract_version_compare()
    script = func + '\n_version_compare "$_VC_A" "$_VC_B"\n'
    env = {**os.environ, "_VC_A": a, "_VC_B": b}
    result = subprocess.run(
        ["bash", "-s"],
        input=script,
        capture_output=True, text=True, timeout=10,
        env=env,
    )
    assert result.returncode == 0, (
        f"_version_compare must always return 0 (set -e safe)\n"
        f"  a={a!r} b={b!r}\n"
        f"  stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    return result.stdout.strip()


def _render(tmp_path: Path, instance_name: str = "my-instance") -> str:
    """Render the template with sample values, return file content."""
    dst = tmp_path / "begin-tomo.sh"
    driver = f"""
set -e
. "{RENDER_LAUNCHER}"
render_launcher "$@"
"""
    result = subprocess.run(
        ["/bin/bash", "-c", driver, "--",
         str(TEMPLATE), str(dst), instance_name,
         "/data/tomo-instance", "/home/user", "/src/Tomo", "9999"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"render_launcher failed\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    return dst.read_text(encoding="utf-8")


def _run_check_with_stdin(
    tmp_path: Path,
    instance_version: str,
    source_version: str,
    missing_source: bool = False,
    answer: str = "n",
) -> tuple[int, str]:
    """Return (returncode, stdout) for the check block, feeding `answer` to stdin.

    The check script is written to a tmp file so bash reads it via argv[0] and
    only the prompt answer travels through stdin.  The yes-branch is stubbed:
    instead of calling the real update-tomo.sh + exec, it echoes "WOULD_UPDATE"
    so tests can assert on it without needing the real script to exist.
    """
    source_file = tmp_path / "project-context.md"
    if not missing_source:
        source_file.write_text(f"# version: {source_version}\n", encoding="utf-8")

    install_root = tmp_path / "install-root"
    install_root.mkdir(exist_ok=True)
    instance_path = install_root / "instance"
    instance_path.mkdir(exist_ok=True)
    config_file = install_root / "tomo-install.json"
    config_file.write_text(
        f'{{"tomoVersion": "{instance_version}"}}\n', encoding="utf-8"
    )

    func = _extract_version_compare()

    check_script = f"""#!/bin/bash
set -e

INSTANCE_PATH="{instance_path}"
INSTANCE_NAME="test-inst"
TOMO_REPO_ROOT="/nonexistent/Tomo"

C_RESET="" C_BOLD="" C_DIM="" C_CYAN="" C_GREEN="" C_YELLOW="" C_RED=""
print_warn() {{ printf "  WARN: %s\\n" "$1"; }}

{func}

SOURCE_VERSION_FILE="{source_file}"
CONFIG_FILE="$(dirname "$INSTANCE_PATH")/tomo-install.json"

INSTANCE_VERSION="unknown"
if [ -f "$CONFIG_FILE" ] && command -v jq > /dev/null 2>&1; then
    INSTANCE_VERSION="$(jq -r '.tomoVersion // "unknown"' "$CONFIG_FILE")"
fi

if [ -f "$SOURCE_VERSION_FILE" ]; then
    SOURCE_VERSION="$(grep -m1 '^# version:' "$SOURCE_VERSION_FILE" 2>/dev/null | sed 's/^# version: *//' || echo 'unknown')"
    _vc_result="$(_version_compare "$INSTANCE_VERSION" "$SOURCE_VERSION")"
    if [ "$_vc_result" = "behind" ]; then
        echo ""
        print_warn "Instance ($INSTANCE_VERSION) is behind source ($SOURCE_VERSION)"
        printf "  Run: bash %s/scripts/update-tomo.sh --instance %s\\n" "$TOMO_REPO_ROOT" "$INSTANCE_NAME"
        echo ""
        read -rp "  Update now? [y/N] " ans
        case "$ans" in
          [yY]*) echo "WOULD_UPDATE"; exit 0 ;;
          *) : ;;
        esac
    fi
fi

echo "LAUNCH_PROCEEDS"
"""
    # Write script to a file so bash reads it as argv[0]; stdin carries only the
    # prompt answer.  This is the correct way to test `read -rp` prompts.
    script_file = tmp_path / "check_block.sh"
    script_file.write_text(check_script, encoding="utf-8")
    script_file.chmod(0o755)

    result = subprocess.run(
        ["bash", str(script_file)],
        input=answer + "\n",
        capture_output=True, text=True, timeout=15,
        env=os.environ.copy(),
    )
    return result.returncode, result.stdout


# ── A. _version_compare unit tests ──────────────────────────────────────────

class TestVersionCompare:
    def test_version_compare_equal(self):
        assert _version_compare("1.2.3", "1.2.3") == "equal"

    def test_version_compare_behind(self):
        assert _version_compare("1.2.3", "1.3.0") == "behind"

    def test_version_compare_ahead(self):
        assert _version_compare("1.3.0", "1.2.3") == "ahead"

    def test_version_compare_multidigit(self):
        # THE TRAP: lexical compare would give "0.9.0" > "0.10.0" (wrong)
        assert _version_compare("0.9.0", "0.10.0") == "behind"

    def test_version_compare_major(self):
        assert _version_compare("1.0.0", "0.99.99") == "ahead"

    def test_version_compare_unknown_a(self):
        assert _version_compare("unknown", "1.2.3") == "unknown"

    def test_version_compare_unknown_b(self):
        assert _version_compare("1.2.3", "unknown") == "unknown"

    def test_version_compare_both_unknown(self):
        assert _version_compare("unknown", "unknown") == "unknown"

    def test_version_compare_empty_a(self):
        assert _version_compare("", "1.2.3") == "unknown"

    def test_version_compare_empty_b(self):
        assert _version_compare("1.2.3", "") == "unknown"

    def test_version_compare_differing_field_counts(self):
        # 1.2 vs 1.2.0 — treat missing fields as 0
        assert _version_compare("1.2", "1.2.0") == "equal"

    def test_version_compare_always_returns_zero(self):
        """_version_compare must ALWAYS return exit code 0 (set -e safe)."""
        func = _extract_version_compare()
        for a, b in [("unknown", "1.0"), ("", ""), ("1.0.0", "1.0.0"), ("0.9", "0.10")]:
            script = func + f'\n_version_compare "{a}" "{b}"\n'
            result = subprocess.run(
                ["bash", "-s"],
                input=script, capture_output=True, text=True, timeout=10,
                env=os.environ.copy(),
            )
            assert result.returncode == 0, (
                f"_version_compare({a!r}, {b!r}) returned non-zero: {result.returncode}"
            )


# ── B. Version-check block routing tests ────────────────────────────────────

class TestVersionCheckBlock:
    def test_check_behind_warns_and_offers_update(self, tmp_path):
        """When installed < available: warn shows installed vs available + offer mentions update-tomo.sh --instance."""
        rc, stdout = _run_check_with_stdin(
            tmp_path, instance_version="1.0.0", source_version="1.1.0", answer="n"
        )
        assert rc == 0, f"Check block crashed: {stdout}"
        assert "1.0.0" in stdout, f"Installed version not shown in warning: {stdout}"
        assert "1.1.0" in stdout, f"Source version not shown in warning: {stdout}"
        assert "update-tomo.sh" in stdout, f"update-tomo.sh not mentioned: {stdout}"
        assert "--instance" in stdout, f"--instance flag not in update offer: {stdout}"
        assert "LAUNCH_PROCEEDS" in stdout, "Launch must proceed after declining update"

    def test_check_current_silent(self, tmp_path):
        """When installed == available: no warning, launch proceeds silently."""
        rc, stdout = _run_check_with_stdin(
            tmp_path, instance_version="1.1.0", source_version="1.1.0"
        )
        assert rc == 0, f"Check block crashed: {stdout}"
        assert "WARN" not in stdout, f"Unexpected warning for up-to-date install: {stdout}"
        assert "LAUNCH_PROCEEDS" in stdout, "Launch must proceed when current"

    def test_check_ahead_silent(self, tmp_path):
        """When installed > available (ahead): no warning, launch proceeds silently."""
        rc, stdout = _run_check_with_stdin(
            tmp_path, instance_version="1.2.0", source_version="1.1.0"
        )
        assert rc == 0, f"Check block crashed: {stdout}"
        assert "WARN" not in stdout, f"Unexpected warning when instance is ahead: {stdout}"
        assert "LAUNCH_PROCEEDS" in stdout, "Launch must proceed when ahead"

    def test_check_missing_source_nonfatal(self, tmp_path):
        """Missing SOURCE_VERSION_FILE must be non-fatal — launch proceeds."""
        rc, stdout = _run_check_with_stdin(
            tmp_path,
            instance_version="1.0.0", source_version="1.1.0",
            missing_source=True,
        )
        assert rc == 0, f"Check block crashed on missing source file: {stdout}"
        assert "LAUNCH_PROCEEDS" in stdout, "Launch must proceed when source file is missing"

    def test_check_behind_answer_yes_fires_update(self, tmp_path):
        """Answer y when behind: WOULD_UPDATE is echoed (update path fires), not LAUNCH_PROCEEDS."""
        rc, stdout = _run_check_with_stdin(
            tmp_path, instance_version="1.0.0", source_version="1.1.0", answer="y"
        )
        assert rc == 0, f"Check block crashed on yes-answer: {stdout}"
        assert "WOULD_UPDATE" in stdout, (
            f"Yes-branch (update path) did not fire for answer='y': {stdout}"
        )
        assert "LAUNCH_PROCEEDS" not in stdout, (
            "LAUNCH_PROCEEDS must not appear when update path fires (exit 0 after WOULD_UPDATE)"
        )

    def test_check_behind_answer_empty_proceeds(self, tmp_path):
        """Empty answer (EOF / just Enter) when behind: falls through, launch proceeds."""
        rc, stdout = _run_check_with_stdin(
            tmp_path, instance_version="1.0.0", source_version="1.1.0", answer=""
        )
        assert rc == 0, f"Check block crashed on empty answer: {stdout}"
        assert "LAUNCH_PROCEEDS" in stdout, (
            "Launch must proceed when answer is empty (EOF)"
        )


# ── C. Template structure tests ──────────────────────────────────────────────

class TestTemplateStructure:
    def test_version_is_0_16_0(self):
        """Template must carry version 0.16.0 after the exposeAuthPort/--no-auth-port bump."""
        content = TEMPLATE.read_text(encoding="utf-8")
        assert "# version: 0.16.0" in content, (
            f"Template version not bumped to 0.16.0. Found: "
            f"{[ln for ln in content.splitlines() if '# version:' in ln]}"
        )

    def test_config_file_uses_instance_path(self):
        """CONFIG_FILE in version-check block must derive from INSTANCE_PATH, not TOMO_REPO_ROOT."""
        content = TEMPLATE.read_text(encoding="utf-8")
        assert 'dirname "$INSTANCE_PATH"' in content, (
            "CONFIG_FILE must use dirname $INSTANCE_PATH, not TOMO_REPO_ROOT"
        )

    def test_version_compare_function_in_template(self):
        """_version_compare function must be present in the template."""
        content = TEMPLATE.read_text(encoding="utf-8")
        assert "_version_compare()" in content, (
            "_version_compare function not found in template"
        )

    def test_no_vc_result_blocks_launch(self):
        """Template must NOT use non-zero exit from _version_compare (set -e guard)."""
        content = TEMPLATE.read_text(encoding="utf-8")
        # Should use result=$(_version_compare ...) pattern, not if _version_compare
        # (the latter would fail with set -e if function returned non-zero)
        assert 'result=$(_version_compare' in content or '_vc_result=$(_version_compare' in content, (
            "_version_compare result must be captured, not used directly in if condition"
        )

    def test_auth_port_flag_and_config_present(self):
        """--no-auth-port flag, exposeAuthPort config read, and conditional
        AUTH_FLAGS must all be present in the template."""
        content = TEMPLATE.read_text(encoding="utf-8")
        assert "--no-auth-port)" in content, "--no-auth-port flag case missing"
        assert "exposeAuthPort" in content, "exposeAuthPort config read missing"
        assert "AUTH_FLAGS=()" in content, "conditional empty AUTH_FLAGS missing"

    def test_auth_port_does_not_use_jq_alternative_operator(self):
        """REGRESSION: jq's `//` returns the right side when the left is null OR
        false, so `.exposeAuthPort // true` mis-reads an explicit `false` as
        `true` and the toggle silently never disables the port."""
        content = TEMPLATE.read_text(encoding="utf-8")
        # Target the jq invocation specifically (not the explanatory comment,
        # which deliberately spells out the anti-pattern).
        assert "jq -r '.exposeAuthPort'" in content, (
            "expected the raw jq read `jq -r '.exposeAuthPort'`"
        )
        assert "jq -r '.exposeAuthPort //" not in content, (
            "jq `//` alternative operator must NOT be used on the boolean "
            "exposeAuthPort — it mis-reads explicit false as true"
        )

    def test_defaultmode_uses_instance_config_not_repo_root(self):
        """defaultMode block must NOT set CONFIG_FILE to TOMO_REPO_ROOT path.

        The repo root has no tomo-install.json in the new multi-instance layout.
        CONFIG_FILE must be hoisted from instance path before the defaultMode block.
        """
        content = TEMPLATE.read_text(encoding="utf-8")
        # The stale repo-root assignment must be gone
        assert 'CONFIG_FILE="$TOMO_REPO_ROOT/tomo-install.json"' not in content, (
            "Stale CONFIG_FILE=$TOMO_REPO_ROOT/tomo-install.json found — defaultMode silently fails"
        )
        # CONFIG_FILE must derive from INSTANCE_PATH (set once, hoisted)
        assert 'CONFIG_FILE="$(dirname "$INSTANCE_PATH")/tomo-install.json"' in content, (
            "CONFIG_FILE must be set from $(dirname $INSTANCE_PATH)/tomo-install.json"
        )
        # Exactly one CONFIG_FILE assignment in the file
        assignment_count = content.count('CONFIG_FILE=')
        assert assignment_count == 1, (
            f"Expected exactly 1 CONFIG_FILE= assignment, found {assignment_count}"
        )


# ── D. Auth-port toggle behaviour ────────────────────────────────────────────

def _run_auth_port_block(tmp_path: Path, config_json: str | None) -> str:
    """Extract the real exposeAuthPort config block from the template and run it.

    Starts from EXPOSE_AUTH_PORT=true / AUTH_PORT_CLI_SET=false (no CLI flag) and
    echoes the resulting EXPOSE_AUTH_PORT. config_json=None omits the config file.
    """
    content = TEMPLATE.read_text(encoding="utf-8")
    start = content.index("# ── Auth-port exposure from tomo-install.json")
    end = content.index('if [ "$SHOW_HELP" = "true" ]; then', start)
    block = content[start:end]
    assert "exposeAuthPort" in block, "Failed to extract the auth-port config block"

    config_file = tmp_path / "tomo-install.json"
    if config_json is not None:
        config_file.write_text(config_json, encoding="utf-8")

    script = (
        "set -e\n"
        "EXPOSE_AUTH_PORT=true\n"
        "AUTH_PORT_CLI_SET=false\n"
        f'CONFIG_FILE="{config_file}"\n'
        f"{block}\n"
        'echo "$EXPOSE_AUTH_PORT"\n'
    )
    result = subprocess.run(
        ["/bin/bash", "-s"], input=script,
        capture_output=True, text=True, timeout=10, env=os.environ.copy(),
    )
    assert result.returncode == 0, f"auth-port block crashed: {result.stderr}"
    return result.stdout.strip()


class TestAuthPortToggle:
    def test_config_absent_field_keeps_port_exposed(self, tmp_path):
        """No exposeAuthPort field → default true (port exposed)."""
        assert _run_auth_port_block(tmp_path, '{"defaultMode":"default"}') == "true"

    def test_config_false_disables_port(self, tmp_path):
        """exposeAuthPort:false → EXPOSE_AUTH_PORT=false (regression guard for jq `//`)."""
        assert _run_auth_port_block(tmp_path, '{"exposeAuthPort":false}') == "false"

    def test_config_true_keeps_port_exposed(self, tmp_path):
        """exposeAuthPort:true → stays true (port exposed)."""
        assert _run_auth_port_block(tmp_path, '{"exposeAuthPort":true}') == "true"

    def test_no_config_file_keeps_port_exposed(self, tmp_path):
        """Missing config file → default true (port exposed)."""
        assert _run_auth_port_block(tmp_path, None) == "true"
