#!/usr/bin/env python3
# version: 0.1.0
"""test_begin_tomo_identity.py — Tests for T3.2: TOMO_INSTANCE_NAME env + sanitized hostname.

Covers:
A. _sanitize_hostname unit cases (via bash -c sourcing the helper function)
B. Rendered launcher carries -e TOMO_INSTANCE_NAME, sanitized --hostname,
   and the unchanged Hashi label miyo.tomo.instance-name=<raw>
C. tomo-statusline.sh identity block: TOMO_INSTANCE_NAME preferred over basename
"""
from __future__ import annotations

import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "scripts" / "lib"
RENDER_LAUNCHER = LIB_DIR / "render-launcher.sh"
TEMPLATE = LIB_DIR / "begin-tomo.sh.template"
STATUSLINE = REPO_ROOT / "tomo" / "scripts" / "tomo-statusline.sh"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _render(tmp_path: Path, instance_name: str = "my-instance") -> str:
    """Render the template with the given instance_name, return file content."""
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


def _sanitize_via_bash(raw: str) -> str:
    """Exercise _sanitize_hostname by extracting the REAL function from the template.

    Uses sed to pull the function body directly from begin-tomo.sh.template so
    these tests track the actual implementation through future edits — not a copy.

    The raw value is passed via the _RAW env var (not as a positional arg) to avoid
    bash treating dash-prefixed values like '---hello' as flag arguments.
    """
    # Extract _sanitize_hostname from the template (lines from the function header
    # to the first column-0 closing brace).
    extract = subprocess.run(
        ["sed", "-n", "/^_sanitize_hostname()/,/^}/p", str(TEMPLATE)],
        capture_output=True, text=True, check=True,
    )
    func = extract.stdout
    assert func.strip(), f"Failed to extract _sanitize_hostname from {TEMPLATE}"
    # Pass the raw value via env var to avoid bash interpreting dash-prefixed
    # strings (e.g. '---') as options when they appear in the arg list.
    script = func + '\n_sanitize_hostname "$_RAW"\n'
    import os
    env = {**os.environ, "_RAW": raw}
    result = subprocess.run(
        ["bash", "-s"],
        input=script,
        capture_output=True, text=True, timeout=10,
        env=env,
    )
    assert result.returncode == 0, (
        f"_sanitize_hostname failed\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    return result.stdout.strip()


# ── A. Sanitize unit tests ───────────────────────────────────────────────────

class TestSanitizeHostname:
    def test_spaces_become_dashes(self):
        assert _sanitize_via_bash("My Vault!") == "My-Vault"

    def test_dots_colons_become_dashes(self):
        assert _sanitize_via_bash("a.b:c") == "a-b-c"

    def test_multi_dash_collapsed(self):
        assert _sanitize_via_bash("a--b---c") == "a-b-c"

    def test_leading_junk_stripped(self):
        assert _sanitize_via_bash("---hello") == "hello"

    def test_trailing_junk_stripped(self):
        assert _sanitize_via_bash("hello---") == "hello"

    def test_all_special_falls_back_to_tomo(self):
        # "..." → "---" → collapsed/stripped → empty → "tomo"
        assert _sanitize_via_bash("...") == "tomo"

    def test_all_dashes_falls_back_to_tomo(self):
        assert _sanitize_via_bash("---") == "tomo"

    def test_empty_falls_back_to_tomo(self):
        assert _sanitize_via_bash("") == "tomo"

    def test_alphanumeric_unchanged(self):
        assert _sanitize_via_bash("myinstance") == "myinstance"

    def test_alphanumeric_with_dash_unchanged(self):
        assert _sanitize_via_bash("my-instance") == "my-instance"

    def test_mixed_junk_produces_clean_hostname(self):
        # "My Vault!" → "My-Vault-" → "My-Vault"
        result = _sanitize_via_bash("My Vault!")
        assert result == "My-Vault"


# ── B. Rendered launcher content tests ──────────────────────────────────────

class TestRenderedLauncherIdentity:
    def test_tomo_instance_name_env_present(self, tmp_path):
        """Rendered launcher must pass -e TOMO_INSTANCE_NAME=$INSTANCE_NAME to docker run.

        The template keeps $INSTANCE_NAME as a shell variable reference —
        INSTANCE_NAME="<value>" is baked at the top, so it expands at runtime.
        """
        content = _render(tmp_path, "my-instance")
        assert '-e "TOMO_INSTANCE_NAME=$INSTANCE_NAME"' in content, (
            "-e TOMO_INSTANCE_NAME not found in rendered launcher"
        )

    def test_tomo_instance_name_env_raw_baked(self, tmp_path):
        """INSTANCE_NAME is baked at the top of the rendered launcher as the raw value."""
        content = _render(tmp_path, "My Vault!")
        # The variable assignment at the top carries the raw name
        assert 'INSTANCE_NAME="My Vault!"' in content, (
            "Raw INSTANCE_NAME not baked into launcher header"
        )
        # And the env line references the variable (not a second copy)
        assert '-e "TOMO_INSTANCE_NAME=$INSTANCE_NAME"' in content, (
            "-e TOMO_INSTANCE_NAME not found in rendered launcher"
        )

    def test_hostname_uses_sanitized_var(self, tmp_path):
        """--hostname references the SANITIZED_HOSTNAME variable, not a static string."""
        content = _render(tmp_path, "my-instance")
        assert '--hostname "$SANITIZED_HOSTNAME"' in content, (
            "--hostname must reference SANITIZED_HOSTNAME variable"
        )

    def test_hostname_not_static_tomo(self, tmp_path):
        """--hostname must no longer be the hardcoded string 'tomo'."""
        content = _render(tmp_path, "prod")
        assert '--hostname tomo' not in content, (
            "Old static --hostname tomo must be replaced"
        )

    def test_sanitize_hostname_function_present(self, tmp_path):
        """_sanitize_hostname function must be defined in the rendered launcher."""
        content = _render(tmp_path, "my-instance")
        assert '_sanitize_hostname()' in content, (
            "_sanitize_hostname function not found in rendered launcher"
        )
        assert 'SANITIZED_HOSTNAME="$(_sanitize_hostname "$INSTANCE_NAME")"' in content, (
            "SANITIZED_HOSTNAME computation not found"
        )

    def test_hashi_label_uses_instance_name_var(self, tmp_path):
        """Hashi contract: miyo.tomo.instance-name label uses $INSTANCE_NAME variable."""
        content = _render(tmp_path, "my-instance")
        assert '--label "miyo.tomo.instance-name=$INSTANCE_NAME"' in content, (
            "Hashi label miyo.tomo.instance-name not found or corrupted"
        )

    def test_tomo_instance_dir_still_present(self, tmp_path):
        """TOMO_INSTANCE_DIR env must still be passed (backward compat)."""
        content = _render(tmp_path, "my-instance")
        assert '-e "TOMO_INSTANCE_DIR=' in content, (
            "TOMO_INSTANCE_DIR env var was removed"
        )


# ── C. Statusline identity tests ─────────────────────────────────────────────

def _run_statusline(env_overrides: dict) -> subprocess.CompletedProcess:
    """Run tomo-statusline.sh with given env vars, feeding empty JSON on stdin."""
    import os
    env = {**os.environ, **env_overrides}
    # Remove vars we want absent
    for key in list(env.keys()):
        if env[key] is None:
            del env[key]
    env = {k: v for k, v in env.items() if v is not None}
    return subprocess.run(
        ["/bin/bash", str(STATUSLINE)],
        input='{}',
        capture_output=True, text=True, timeout=10,
        env=env,
        cwd=str(TESTS_DIR),  # no .mcp.json here → kado shows no_config, that's fine
    )


class TestStatuslineInstanceIdentity:
    def test_prefers_tomo_instance_name_when_set(self):
        """When TOMO_INSTANCE_NAME is set, INSTANCE_LABEL equals it."""
        result = _run_statusline({
            "TOMO_INSTANCE_NAME": "work-vault",
            "TOMO_INSTANCE_DIR": "/data/tomo-instance",
        })
        assert result.returncode == 0, f"statusline crashed: {result.stderr}"
        assert "work-vault" in result.stdout, (
            f"TOMO_INSTANCE_NAME not reflected in statusline output: {result.stdout!r}"
        )

    def test_falls_back_to_basename_when_name_unset(self):
        """When TOMO_INSTANCE_NAME is absent, basename of TOMO_INSTANCE_DIR is used."""
        result = _run_statusline({
            "TOMO_INSTANCE_NAME": None,   # will be excluded
            "TOMO_INSTANCE_DIR": "/data/my-dir-name",
        })
        assert result.returncode == 0, f"statusline crashed: {result.stderr}"
        assert "my-dir-name" in result.stdout, (
            f"Basename fallback not reflected in statusline output: {result.stdout!r}"
        )

    def test_empty_label_when_both_unset(self):
        """When both TOMO_INSTANCE_NAME and TOMO_INSTANCE_DIR are absent,
        the 友 prefix section is not rendered."""
        result = _run_statusline({
            "TOMO_INSTANCE_NAME": None,
            "TOMO_INSTANCE_DIR": None,
        })
        assert result.returncode == 0, f"statusline crashed: {result.stderr}"
        # The 友 section only appears when INSTANCE_LABEL is non-empty
        assert "友" not in result.stdout, (
            f"Unexpected 友 section in output without instance vars: {result.stdout!r}"
        )
