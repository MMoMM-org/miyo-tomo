#!/usr/bin/env python3
# version: 0.1.0
"""test_cli.py — Tests for scripts/voice-transcribe.py (batch CLI).

Two layers of coverage:

1. Argparse + exit code contract — runs the CLI as a subprocess (no engine
   needed; we hit the model-dir-missing and usage-error paths).

2. JSON manifest shape — imports the CLI module directly, monkey-patches
   load_model + transcribe to return stubbed TranscriptResult objects, and
   asserts the JSON emitted on stdout matches the SDD contract.

No faster_whisper dependency required.
"""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
CLI_PATH = SCRIPTS_DIR / "voice-transcribe.py"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.voice_transcriber import Segment, TranscriptResult  # noqa: E402


def _load_cli_module():
    """Import the hyphenated CLI script as a module for direct testing."""
    spec = importlib.util.spec_from_file_location(
        "voice_transcribe_cli", CLI_PATH
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Subprocess-level contract ────────────────────────────────

def test_cli_prints_help_and_exits_zero():
    r = subprocess.run(
        [sys.executable, str(CLI_PATH), "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0
    assert "voice-transcribe" in r.stdout.lower() or "usage" in r.stdout.lower()


def test_cli_errors_when_no_audio_paths_given():
    r = subprocess.run(
        [sys.executable, str(CLI_PATH), "--model-dir", "/nonexistent"],
        capture_output=True, text=True, timeout=10,
    )
    # argparse exits 2 on usage errors
    assert r.returncode == 2


def test_cli_errors_when_model_dir_flag_missing(tmp_path):
    # --model-dir is required — there is no hardcoded default. Agents
    # must build the path explicitly from voice/config.json .model.
    audio = tmp_path / "memo.m4a"
    audio.write_bytes(b"\x00")
    r = subprocess.run(
        [sys.executable, str(CLI_PATH), str(audio)],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 2
    assert "model-dir" in r.stderr.lower() or "required" in r.stderr.lower()


def test_cli_exits_3_when_model_dir_missing(tmp_path):
    audio = tmp_path / "memo.m4a"
    audio.write_bytes(b"\x00" * 16)
    missing_model = tmp_path / "no-such-model"
    r = subprocess.run(
        [
            sys.executable, str(CLI_PATH),
            str(audio),
            "--model-dir", str(missing_model),
        ],
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 3

    # Scan every stderr line and assert at least one parses as our error
    # JSON — brittle "last line" matching breaks if a future warning or
    # argparse preamble prints ahead of the JSON blob.
    found = None
    for line in r.stderr.strip().splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("error") == "model_dir_missing":
            found = obj
            break
    assert found is not None, (
        f"no model_dir_missing JSON line in stderr: {r.stderr!r}"
    )


# ── JSON manifest shape (mocked engine) ──────────────────────

class _FakeModel:
    """Stand-in for faster_whisper.WhisperModel — counts load invocations."""
    load_count = 0


def _fake_load_model(model_dir):
    _FakeModel.load_count += 1
    return _FakeModel()


def _fake_transcribe(model, audio_path, language=None):
    # Deterministic stub: one-segment result, text mirrors filename stem.
    return TranscriptResult(
        audio_path=audio_path,
        model_name="faster-whisper-tiny",
        language=language or "auto",
        duration_sec=3.0,
        segments=[Segment(0.0, 2.5, f"transcript of {audio_path.stem}")],
    )


def _run_cli_with_mocks(argv, monkeypatch):
    """Run the CLI's main() in-process with patched model+transcribe."""
    mod = _load_cli_module()
    _FakeModel.load_count = 0
    monkeypatch.setattr(mod, "load_model", _fake_load_model)
    monkeypatch.setattr(mod, "transcribe", _fake_transcribe)

    # Capture stdout in a string buffer
    buf = io.StringIO()
    with patch.object(sys, "argv", argv), patch.object(sys, "stdout", buf):
        try:
            mod.main()
        except SystemExit as e:
            return e.code, buf.getvalue()
    return 0, buf.getvalue()


def test_cli_emits_json_manifest_for_single_file(monkeypatch, tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    audio = tmp_path / "memo-1.m4a"
    audio.write_bytes(b"\x00")

    code, out = _run_cli_with_mocks(
        ["voice-transcribe.py", str(audio), "--model-dir", str(model_dir)],
        monkeypatch,
    )
    assert code == 0 or code is None
    data = json.loads(out)
    assert data["model_dir"] == str(model_dir)
    assert len(data["results"]) == 1
    entry = data["results"][0]
    assert entry["audio"] == "memo-1.m4a"
    assert entry["target"] == "memo-1.md"
    assert entry["error"] is None
    assert "memo-1" in entry["markdown"]


def test_cli_loads_model_once_for_batch(monkeypatch, tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    audios = []
    for i in range(3):
        p = tmp_path / f"memo-{i}.m4a"
        p.write_bytes(b"\x00")
        audios.append(str(p))

    code, out = _run_cli_with_mocks(
        ["voice-transcribe.py", *audios, "--model-dir", str(model_dir)],
        monkeypatch,
    )
    assert code == 0 or code is None
    data = json.loads(out)
    assert len(data["results"]) == 3
    # The batch contract: ONE model load per CLI invocation
    assert _FakeModel.load_count == 1


def test_cli_includes_error_entry_for_missing_audio(monkeypatch, tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    real = tmp_path / "real.m4a"
    real.write_bytes(b"\x00")
    bogus = tmp_path / "bogus.m4a"  # not created

    code, out = _run_cli_with_mocks(
        ["voice-transcribe.py", str(real), str(bogus),
         "--model-dir", str(model_dir)],
        monkeypatch,
    )
    assert code == 0 or code is None
    data = json.loads(out)
    assert len(data["results"]) == 2

    real_entry = next(r for r in data["results"] if r["audio"] == "real.m4a")
    bogus_entry = next(r for r in data["results"] if r["audio"] == "bogus.m4a")

    assert real_entry["error"] is None
    assert real_entry["markdown"] is not None

    assert bogus_entry["error"] is not None
    assert bogus_entry["error"]["code"] == "audio_not_found"
    assert bogus_entry["markdown"] is None


def test_cli_catches_transcription_exceptions_per_file(monkeypatch, tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    audio = tmp_path / "memo.m4a"
    audio.write_bytes(b"\x00")

    def exploding_transcribe(model, audio_path, language=None):
        raise RuntimeError("boom")

    mod = _load_cli_module()
    _FakeModel.load_count = 0
    monkeypatch.setattr(mod, "load_model", _fake_load_model)
    monkeypatch.setattr(mod, "transcribe", exploding_transcribe)

    buf = io.StringIO()
    with patch.object(sys, "argv",
                      ["voice-transcribe.py", str(audio),
                       "--model-dir", str(model_dir)]), \
         patch.object(sys, "stdout", buf):
        code = None
        try:
            mod.main()
        except SystemExit as e:
            code = e.code

    # Per-file error must NOT abort the batch
    assert code in (None, 0)
    data = json.loads(buf.getvalue())
    entry = data["results"][0]
    assert entry["markdown"] is None
    assert entry["error"]["code"] == "transcription_error"
    assert "boom" in entry["error"]["detail"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
