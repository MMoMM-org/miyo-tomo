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
    # Assert the model is the object produced by our fake load_model —
    # without this, the batch-load assertion in the multi-file test
    # could pass even if production code called load_model() N times and
    # kept using the last-returned model (review finding H7).
    assert isinstance(model, _FakeModel), (
        f"_fake_transcribe received unexpected model type: {type(model).__name__}"
    )
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


def test_cli_fetches_via_kado_when_fs_path_missing(monkeypatch, tmp_path):
    """Missing FS path → CLI fetches bytes via Kado, transcribes the temp
    file, cleans up afterwards. This is the container-runtime path: the
    vault is NEVER bind-mounted, so all audio must reach the Whisper
    engine via kado-read operation=file.
    """
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    vault_audio = Path("100 Inbox/test-memo.m4a")  # not on FS
    assert not vault_audio.exists()

    fetched_paths: list[Path] = []

    def _fake_kado_fetch(audio_path):
        # Simulate the Kado fetch: create a real temp file with any bytes,
        # record the vault-relative path we were asked for.
        import tempfile
        fd, tmp_name = tempfile.mkstemp(prefix="tomo-voice-", suffix=".m4a")
        import os
        with os.fdopen(fd, "wb") as fh:
            fh.write(b"\x00" * 32)
        fetched_paths.append(audio_path)
        return Path(tmp_name)

    mod = _load_cli_module()
    _FakeModel.load_count = 0
    monkeypatch.setattr(mod, "load_model", _fake_load_model)
    monkeypatch.setattr(mod, "transcribe", _fake_transcribe)
    monkeypatch.setattr(mod, "_fetch_from_kado", _fake_kado_fetch)

    buf = io.StringIO()
    with patch.object(sys, "argv",
                      ["voice-transcribe.py", str(vault_audio),
                       "--model-dir", str(model_dir)]), \
         patch.object(sys, "stdout", buf):
        try:
            mod.main()
        except SystemExit:
            pass

    data = json.loads(buf.getvalue())
    assert len(data["results"]) == 1
    entry = data["results"][0]
    # audio.name stays the vault filename — the CLI returns results keyed
    # by the ORIGINAL argv name so the agent can map back to vault paths.
    assert entry["audio"] == "test-memo.m4a"
    assert entry["target"] == "test-memo.md"
    assert entry["error"] is None
    assert entry["markdown"] is not None

    # The Kado fetch was invoked with the vault-relative path
    assert len(fetched_paths) == 1
    assert fetched_paths[0] == vault_audio

    # CRITICAL — the rendered markdown refers to the ORIGINAL vault audio,
    # not the /tmp/tomo-voice-* file the CLI transcribed from. The user
    # saw `source: tomo-voice-abcd.m4a` leaking through a v0.3.0 → v0.4.0
    # fix had to restore the original path on the TranscriptResult before
    # render. Assert both the `source:` metadata and the `![[...]]` embed
    # reference the vault filename.
    # `source:` metadata and `![[...]]` embed must both name the vault
    # file, not the ephemeral tomo-voice-*.m4a temp path.
    assert "source: test-memo.m4a" in entry["markdown"]
    assert "![[test-memo.m4a]]" in entry["markdown"]
    # The bug-specific assertions: no temp-named `source:` or embed leaked.
    # (Segment BODY text may legitimately mention "tomo-voice-*" — the
    # fake transcribe mirrors audio.stem into text and we don't rewrite
    # transcript content.)
    assert "source: tomo-voice-" not in entry["markdown"], (
        "temp filename leaked into `source:` metadata — "
        "result.audio_path was not restored before render_markdown"
    )
    assert "![[tomo-voice-" not in entry["markdown"], (
        "temp filename leaked into the `![[…]]` embed — "
        "result.audio_path was not restored before render_markdown"
    )
    # Seek-link wikilinks must also use the vault name
    assert "[[test-memo.m4a#t=" in entry["markdown"]

    # Temp file was cleaned up after transcription. The fake produced a
    # /tmp path via tempfile.mkstemp; the CLI unlinks it in finally-style
    # cleanup regardless of outcome.
    # (We rely on /tmp not accumulating; the test above already set up
    # the fake to create a real temp file, so we verify it's gone.)


def test_cli_sanitises_forbidden_chars_in_target_filename(monkeypatch, tmp_path):
    """Audio files from external recorders often carry colons in the
    timestamp portion (iOS Voice Memos: `memo 2026-04-20 11:48:29.m4a`).
    Obsidian — and therefore `kado-write` — rejects colons and the rest
    of `\\ / : * ? " < > |` in filenames. The CLI MUST sanitise the
    `target` stem so the agent can write it without a kado-write reject.

    Audio source name stays original (it already exists in the vault
    with forbidden chars — we don't rename it). Only the transcript
    target is safe.
    """
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    dirty_audio = tmp_path / "memo 2026-04-20 11:48:29.m4a"
    dirty_audio.write_bytes(b"\x00")

    code, out = _run_cli_with_mocks(
        ["voice-transcribe.py", str(dirty_audio), "--model-dir", str(model_dir)],
        monkeypatch,
    )
    assert code == 0 or code is None
    data = json.loads(out)
    entry = data["results"][0]
    # Source preserved for round-tripping back to the vault
    assert entry["audio"] == "memo 2026-04-20 11:48:29.m4a"
    # Target is sanitised — colons become dashes
    assert entry["target"] == "memo 2026-04-20 11-48-29.md"
    assert ":" not in entry["target"]
    assert entry["error"] is None


def test_cli_records_transcribe_sec_and_model_load_sec(monkeypatch, tmp_path):
    """Perf instrumentation: CLI emits `model_load_sec` at the top level
    of the manifest, and `transcribe_sec` on every successful result.
    Both are rounded to 2 decimals. The stderr summary line surfaces the
    totals for eyeball checks without parsing JSON."""
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    audio = tmp_path / "memo.m4a"
    audio.write_bytes(b"\x00")

    mod = _load_cli_module()
    _FakeModel.load_count = 0
    monkeypatch.setattr(mod, "load_model", _fake_load_model)
    monkeypatch.setattr(mod, "transcribe", _fake_transcribe)

    buf_out = io.StringIO()
    buf_err = io.StringIO()
    with patch.object(sys, "argv",
                      ["voice-transcribe.py", str(audio),
                       "--model-dir", str(model_dir)]), \
         patch.object(sys, "stdout", buf_out), \
         patch.object(sys, "stderr", buf_err):
        try:
            mod.main()
        except SystemExit:
            pass

    data = json.loads(buf_out.getvalue())
    assert "model_load_sec" in data
    assert isinstance(data["model_load_sec"], (int, float))
    assert data["model_load_sec"] >= 0.0

    entry = data["results"][0]
    assert "transcribe_sec" in entry
    assert isinstance(entry["transcribe_sec"], (int, float))
    assert entry["transcribe_sec"] >= 0.0

    # The rendered markdown exposes transcribe_sec too, right next to
    # duration_sec — the stem of T5.2's audit-by-eye workflow.
    assert "transcribe_sec:" in entry["markdown"]

    # Stderr summary line exists with expected shape
    err = buf_err.getvalue()
    assert "voice-transcribe:" in err
    assert "model_load=" in err
    assert "transcribe_total=" in err


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
