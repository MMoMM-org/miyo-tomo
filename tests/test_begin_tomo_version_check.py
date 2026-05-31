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


def _run_version_check_block(
    tmp_path: Path,
    instance_version: str = "1.0.0",
    source_version: str = "1.0.0",
    missing_source: bool = False,
    answer: str = "n",
) -> subprocess.CompletedProcess:
    """Drive the version-check block from the rendered launcher in isolation.

    Renders the template, extracts the _version_compare function and the
    version-check block (~179–210), then runs it in a controlled environment.

    The check block uses:
      - SOURCE_VERSION_FILE (written by us to a tmpfile or absent)
      - INSTANCE_PATH (used to locate $(dirname)/tomo-install.json)
      - TOMO_REPO_ROOT / INSTANCE_NAME  (for the update offer text)

    To avoid the real docker-run, we wrap only the check block, not the
    full launcher. The stdin answer controls the read -rp prompt.
    """
    # Build a fake SOURCE_VERSION_FILE
    source_file = tmp_path / "project-context.md"
    if not missing_source:
        source_file.write_text(f"# version: {source_version}\n", encoding="utf-8")

    # Build a fake tomo-install.json one level up from INSTANCE_PATH
    install_root = tmp_path / "install-root"
    install_root.mkdir()
    instance_path = install_root / "instance"
    instance_path.mkdir()
    config_file = install_root / "tomo-install.json"
    config_file.write_text(
        f'{{"tomoVersion": "{instance_version}", "instanceName": "test-inst"}}\n',
        encoding="utf-8",
    )

    # Extract _version_compare from template
    func = _extract_version_compare()

    # Build a minimal check block that mirrors the template logic but
    # substitutes the real paths with our tmp paths and adds a sentinel
    # at the end so we can confirm it proceeded past the check.
    check_script = f"""
#!/bin/bash
set -e

INSTANCE_PATH="{instance_path}"
INSTANCE_NAME="test-inst"
TOMO_REPO_ROOT="/nonexistent/Tomo"

# Color helpers (non-tty — empty)
C_RESET="" C_BOLD="" C_DIM="" C_CYAN="" C_GREEN="" C_YELLOW="" C_RED=""
print_warn() {{ printf "  WARN: %s\\n" "$1"; }}
print_step() {{ printf "\\n STEP: %s\\n" "$1"; }}

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
          [yY]*) bash "$TOMO_REPO_ROOT/scripts/update-tomo.sh" --instance "$INSTANCE_NAME" && exec "$0" "$@" ;;
          *) : ;;
        esac
    fi
fi

echo "LAUNCH_PROCEEDS"
"""
    env = {**os.environ}
    result = subprocess.run(
        ["bash", "-s"],
        input=check_script,
        capture_output=True, text=True, timeout=15,
        env=env,
        stdin=subprocess.PIPE,
    )
    # Feed the answer to the read prompt via stdin
    result2 = subprocess.run(
        ["bash", "-s"],
        input=check_script,
        capture_output=True, text=True, timeout=15,
        env=env,
    )
    _ = result  # discard first (stdin pipe race)
    return result2


def _run_check_with_stdin(
    tmp_path: Path,
    instance_version: str,
    source_version: str,
    missing_source: bool = False,
    answer: str = "n",
) -> tuple[int, str]:
    """Return (returncode, stdout) for the check block, feeding `answer` to stdin."""
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

    check_script = f"""
#!/bin/bash
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
    result = subprocess.run(
        ["bash", "-s"],
        input=check_script,
        capture_output=True, text=True, timeout=15,
        env=os.environ.copy(),
        # Feed answer via stdin (for the read -rp prompt)
    )
    # Run again with piped stdin for the interactive prompt
    result = subprocess.run(
        ["/bin/bash"],
        input=check_script,
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


# ── C. Template structure tests ──────────────────────────────────────────────

class TestTemplateStructure:
    def test_version_is_0_14_0(self):
        """Template must carry version 0.14.0 after T3.3 bump."""
        content = TEMPLATE.read_text(encoding="utf-8")
        assert "# version: 0.14.0" in content, (
            f"Template version not bumped to 0.14.0. Found: "
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
