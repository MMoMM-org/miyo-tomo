#!/usr/bin/env python3
# version: 0.1.0
"""test_configure_voice.py — Pytest-driven tests for the bash wizard.

Drives `scripts/lib/configure-voice.sh` via subprocess with controlled
stdin and asserts the exported globals (VOICE_ENABLED, VOICE_MODEL,
VOICE_LANGUAGE). Uses a temp dir for `models_base_dir` and a stub
download helper to avoid network.

Review finding H8: the 4 branches (K / c / d / invalid-model) had no
automated coverage; "manual heredoc sanity check" was the only gate.
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIGURE_SH = REPO_ROOT / "scripts/lib/configure-voice.sh"
DOWNLOAD_SH = REPO_ROOT / "scripts/download-whisper-model.sh"


def _run_wizard(
    current_enabled: str,
    current_model: str,
    current_lang: str,
    models_base_dir: Path,
    stdin_text: str,
    non_interactive: str = "false",
    stub_download: bool = True,
):
    """Invoke configure_voice() and capture the resulting globals.

    Sources configure-voice.sh in a subshell, runs the wizard with the
    given stdin, then echoes the globals so we can parse them back.
    """
    models_base_dir.mkdir(parents=True, exist_ok=True)

    # Stub download-whisper-model.sh so we never hit HuggingFace.
    # configure_voice derives the script path from $(dirname BASH_SOURCE)/..
    # so we place our stubbed lib in a sibling dir structure.
    #
    # Instead of patching the real repo layout, copy configure-voice.sh
    # into a tmp tree with a stub download-whisper-model.sh alongside.
    if stub_download:
        tmp_scripts = models_base_dir.parent / "scripts"
        tmp_lib = tmp_scripts / "lib"
        tmp_lib.mkdir(parents=True, exist_ok=True)
        (tmp_lib / "configure-voice.sh").write_text(CONFIGURE_SH.read_text())
        stub = tmp_scripts / "download-whisper-model.sh"
        stub.write_text(textwrap.dedent("""\
            #!/bin/bash
            # Stub — pretend the download succeeded.
            set -e
            SIZE="$1"
            DEST="$2"
            mkdir -p "$DEST"
            touch "$DEST/model.bin"
            touch "$DEST/.download-complete"
            echo "✓ (stub) Downloaded $SIZE to $DEST"
        """))
        stub.chmod(0o755)
        source_path = tmp_lib / "configure-voice.sh"
    else:
        source_path = CONFIGURE_SH

    script = textwrap.dedent(f"""\
        print_step() {{ echo "[step] $1"; }}
        print_ok()   {{ echo "[ok]   $1"; }}
        print_warn() {{ echo "[warn] $1"; }}
        print_err()  {{ echo "[err]  $1" >&2; }}

        . "{source_path}"
        configure_voice "{current_enabled}" "{current_model}" \\
                        "{current_lang}" "{models_base_dir}" "{non_interactive}"
        echo "RESULT_ENABLED=$VOICE_ENABLED"
        echo "RESULT_MODEL=$VOICE_MODEL"
        echo "RESULT_LANGUAGE=$VOICE_LANGUAGE"
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


def test_non_interactive_fresh_install_defaults_disabled(tmp_path):
    r = _run_wizard("false", "", "", tmp_path / "models", "", non_interactive="true")
    assert r.returncode == 0
    result = _parse(r)
    assert result["ENABLED"] == "false"
    assert result["MODEL"] == ""


def test_non_interactive_preserves_enabled_state(tmp_path):
    r = _run_wizard("true", "medium", "de", tmp_path / "models", "",
                    non_interactive="true")
    assert r.returncode == 0
    result = _parse(r)
    assert result["ENABLED"] == "true"
    assert result["MODEL"] == "medium"
    assert result["LANGUAGE"] == "de"


def test_K_keeps_current_state(tmp_path):
    # Currently enabled. User picks K (default).
    r = _run_wizard("true", "small", "en", tmp_path / "models", "K\n")
    assert r.returncode == 0
    result = _parse(r)
    assert result["ENABLED"] == "true"
    assert result["MODEL"] == "small"
    assert result["LANGUAGE"] == "en"


def test_d_disables_with_no_cleanup(tmp_path):
    # Currently enabled with medium model already on disk.
    models = tmp_path / "models"
    (models / "faster-whisper-medium").mkdir(parents=True)
    (models / "faster-whisper-medium" / "model.bin").touch()
    # "d" disables, "n" declines cleanup.
    r = _run_wizard("true", "medium", "de", models, "d\nn\n")
    assert r.returncode == 0
    result = _parse(r)
    assert result["ENABLED"] == "false"
    # Model files left alone since user declined cleanup.
    assert (models / "faster-whisper-medium" / "model.bin").exists()


def test_d_disables_and_removes_model_dirs(tmp_path):
    models = tmp_path / "models"
    (models / "faster-whisper-medium").mkdir(parents=True)
    (models / "faster-whisper-medium" / "model.bin").touch()
    # "d" disables, "y" confirms cleanup.
    r = _run_wizard("true", "medium", "de", models, "d\ny\n")
    assert r.returncode == 0
    result = _parse(r)
    assert result["ENABLED"] == "false"
    assert not (models / "faster-whisper-medium").exists()


def test_c_changes_model_and_downloads(tmp_path):
    # Currently enabled with medium — switch to small. Stub download
    # writes a sentinel, so we can verify the download path triggered.
    models = tmp_path / "models"
    # "c" → change, then new model "small", then new lang "en"
    r = _run_wizard("true", "medium", "de", models, "c\nsmall\nen\n")
    assert r.returncode == 0, f"stderr: {r.stderr}"
    result = _parse(r)
    assert result["ENABLED"] == "true"
    assert result["MODEL"] == "small"
    assert result["LANGUAGE"] == "en"
    assert (models / "faster-whisper-small" / ".download-complete").exists()


def test_invalid_model_name_falls_back_to_default(tmp_path):
    # Fresh install, user enters an invalid model name — wizard prints
    # an error and keeps the default ("medium").
    models = tmp_path / "models"
    r = _run_wizard("false", "", "", models, "y\nLARGE-XL\nde\n")
    assert r.returncode == 0, f"stderr: {r.stderr}"
    result = _parse(r)
    assert result["ENABLED"] == "true"
    # Wizard rejected LARGE-XL and kept the default, which is "medium"
    # for a fresh install.
    assert result["MODEL"] == "medium"
    assert "Invalid model" in r.stdout or "Invalid model" in r.stderr


def test_fresh_install_decline_stays_disabled(tmp_path):
    # Fresh install, user says "n" to enabling. Nothing downloaded.
    r = _run_wizard("false", "", "", tmp_path / "models", "n\n")
    assert r.returncode == 0
    result = _parse(r)
    assert result["ENABLED"] == "false"
    # Stub download should not have been called.
    assert not list((tmp_path / "models").glob("faster-whisper-*"))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
