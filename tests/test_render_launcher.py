#!/usr/bin/env python3
# version: 0.1.0
"""test_render_launcher.py — Tests for scripts/lib/render-launcher.sh.

Verifies render_launcher() via subprocess/bash sourcing:
- All 5 placeholders are substituted against the real template
- Output file is executable
- sed-special characters in values (& / |) render literally
- Atomic write: failed render leaves no partial dst and returns non-zero
"""
from __future__ import annotations

import stat
import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "scripts" / "lib"
RENDER_LAUNCHER = LIB_DIR / "render-launcher.sh"
TEMPLATE = LIB_DIR / "begin-tomo.sh.template"

# Minimal bash driver: source the lib then call render_launcher with positional args.
_DRIVER = """\
set -e
. "{lib}"
render_launcher "$@"
"""


def _run(args: list[str], tmpdir: Path) -> subprocess.CompletedProcess:
    """Source render-launcher.sh and call render_launcher with args."""
    driver = _DRIVER.format(lib=str(RENDER_LAUNCHER))
    return subprocess.run(
        ["/bin/bash", "-c", driver, "--"] + args,
        capture_output=True,
        text=True,
        cwd=str(tmpdir),
        timeout=15,
    )


class TestRenderLauncherBasic:
    def test_all_placeholders_substituted(self, tmp_path):
        """render_launcher replaces all 5 named placeholders in the output."""
        dst = tmp_path / "begin-tomo.sh"
        result = _run(
            [
                str(TEMPLATE),
                str(dst),
                "my-instance",
                "/Users/alice/tomo-instance",
                "/Users/alice",
                "/Users/alice/repos/Tomo",
                "9999",
            ],
            tmp_path,
        )
        assert result.returncode == 0, (
            f"render_launcher failed\nstdout={result.stdout}\nstderr={result.stderr}"
        )
        content = dst.read_text(encoding="utf-8")
        # The 5 named Tomo placeholders must all be gone.
        # (The template also contains docker --format '{{ ... }}' expressions
        # which are intentionally NOT substituted and must survive unchanged.)
        for placeholder in (
            "{{INSTANCE_PATH}}",
            "{{INSTANCE_NAME}}",
            "{{HOME_DIR}}",
            "{{TOMO_REPO_ROOT}}",
            "{{DEV_NOTIFY_PORT}}",
        ):
            assert placeholder not in content, (
                f"Placeholder {placeholder!r} still present in output"
            )

    def test_instance_name_substituted(self, tmp_path):
        dst = tmp_path / "begin-tomo.sh"
        _run(
            [str(TEMPLATE), str(dst), "prod-instance", "/data/tomo",
             "/home/user", "/src/Tomo", "9999"],
            tmp_path,
        )
        content = dst.read_text(encoding="utf-8")
        assert 'INSTANCE_NAME="prod-instance"' in content

    def test_instance_path_substituted(self, tmp_path):
        dst = tmp_path / "begin-tomo.sh"
        _run(
            [str(TEMPLATE), str(dst), "myinst", "/data/myinst",
             "/home/user", "/src/Tomo", "9999"],
            tmp_path,
        )
        content = dst.read_text(encoding="utf-8")
        assert 'INSTANCE_PATH="/data/myinst"' in content

    def test_home_dir_substituted(self, tmp_path):
        dst = tmp_path / "begin-tomo.sh"
        _run(
            [str(TEMPLATE), str(dst), "inst", "/data/inst",
             "/Users/bob", "/src/Tomo", "9999"],
            tmp_path,
        )
        content = dst.read_text(encoding="utf-8")
        assert 'HOME_DIR="/Users/bob"' in content

    def test_repo_root_substituted(self, tmp_path):
        dst = tmp_path / "begin-tomo.sh"
        _run(
            [str(TEMPLATE), str(dst), "inst", "/data/inst",
             "/home/user", "/opt/repos/Tomo", "9999"],
            tmp_path,
        )
        content = dst.read_text(encoding="utf-8")
        assert 'TOMO_REPO_ROOT="/opt/repos/Tomo"' in content

    def test_dev_notify_port_substituted(self, tmp_path):
        dst = tmp_path / "begin-tomo.sh"
        _run(
            [str(TEMPLATE), str(dst), "inst", "/data/inst",
             "/home/user", "/src/Tomo", "12345"],
            tmp_path,
        )
        content = dst.read_text(encoding="utf-8")
        assert 'DEV_NOTIFY_PORT="12345"' in content


class TestRenderLauncherExecutable:
    def test_output_is_executable(self, tmp_path):
        """Rendered launcher must have execute bit set."""
        dst = tmp_path / "begin-tomo.sh"
        result = _run(
            [str(TEMPLATE), str(dst), "inst", "/data/inst",
             "/home/user", "/src/Tomo", "9999"],
            tmp_path,
        )
        assert result.returncode == 0
        mode = dst.stat().st_mode
        assert mode & stat.S_IXUSR, f"Output not executable: mode={oct(mode)}"


class TestRenderLauncherSedSpecialChars:
    def test_ampersand_in_value_renders_literally(self, tmp_path):
        """A value containing & must not expand to the matched text in sed."""
        dst = tmp_path / "begin-tomo.sh"
        result = _run(
            [
                str(TEMPLATE),
                str(dst),
                "inst",
                "/Users/x&y/Tomo",   # & is a sed replacement metachar
                "/Users/x&y",
                "/src/Tomo",
                "9999",
            ],
            tmp_path,
        )
        assert result.returncode == 0, (
            f"render_launcher failed\nstderr={result.stderr}"
        )
        content = dst.read_text(encoding="utf-8")
        assert 'INSTANCE_PATH="/Users/x&y/Tomo"' in content, (
            f"& was not rendered literally.\n{content}"
        )

    def test_slash_in_value_renders_literally(self, tmp_path):
        """Values with forward slashes must not break the sed expression."""
        dst = tmp_path / "begin-tomo.sh"
        result = _run(
            [
                str(TEMPLATE),
                str(dst),
                "inst",
                "/deep/nested/path/tomo",
                "/deep/nested/home",
                "/deep/nested/repo",
                "9999",
            ],
            tmp_path,
        )
        assert result.returncode == 0
        content = dst.read_text(encoding="utf-8")
        assert 'INSTANCE_PATH="/deep/nested/path/tomo"' in content

    def test_pipe_in_value_renders_literally(self, tmp_path):
        """A value containing | (sed default delimiter) must render literally."""
        # Use a non-standard name that includes pipe-like chars in path components.
        # We embed | in instance_name since instance_path with | is unusual but valid.
        dst = tmp_path / "begin-tomo.sh"
        result = _run(
            [
                str(TEMPLATE),
                str(dst),
                "inst|v2",   # | in the name
                "/data/inst",
                "/home/user",
                "/src/Tomo",
                "9999",
            ],
            tmp_path,
        )
        assert result.returncode == 0, (
            f"render_launcher failed\nstderr={result.stderr}"
        )
        content = dst.read_text(encoding="utf-8")
        assert 'INSTANCE_NAME="inst|v2"' in content, (
            f"| was not rendered literally.\n{content}"
        )


class TestRenderLauncherAtomic:
    def test_missing_template_returns_nonzero(self, tmp_path):
        """render_launcher must exit non-zero when the template does not exist."""
        dst = tmp_path / "begin-tomo.sh"
        missing = tmp_path / "no-such-template.sh"
        result = _run(
            [str(missing), str(dst), "inst", "/data/inst",
             "/home/user", "/src/Tomo", "9999"],
            tmp_path,
        )
        assert result.returncode != 0, (
            "Expected non-zero exit for missing template"
        )

    def test_missing_template_leaves_no_dst(self, tmp_path):
        """A failed render must not leave a partial dst file behind."""
        dst = tmp_path / "begin-tomo.sh"
        missing = tmp_path / "no-such-template.sh"
        _run(
            [str(missing), str(dst), "inst", "/data/inst",
             "/home/user", "/src/Tomo", "9999"],
            tmp_path,
        )
        assert not dst.exists(), (
            "Partial dst file must not exist after a failed render"
        )
