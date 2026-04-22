#!/usr/bin/env python3
# version: 0.1.0
"""test_transcriber.py — Unit tests for voice_transcriber.py.

Covers the wrapping logic with a mocked faster_whisper.WhisperModel. The
full end-to-end test (engine loaded, real audio transcribed) is opt-in
via the `voice_model` pytest marker — it needs a model dir and the
faster_whisper dep installed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.voice_transcriber import (  # noqa: E402
    Segment,
    TranscriptResult,
    transcribe,
)


class FakeSegment:
    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text


def _fake_info(model_size="tiny", language="de", duration=9.5):
    return SimpleNamespace(
        model_name_or_size=model_size,
        language=language,
        duration=duration,
    )


def test_transcribe_produces_transcript_result_shape():
    model = MagicMock()
    model.transcribe.return_value = (
        iter([FakeSegment(0.0, 2.5, "Hallo.  "), FakeSegment(2.5, 5.0, " Welt. ")]),
        _fake_info(),
    )
    result = transcribe(model, Path("/vault/memo.m4a"), language="de")

    assert isinstance(result, TranscriptResult)
    assert result.audio_path == Path("/vault/memo.m4a")
    assert result.language == "de"
    assert result.duration_sec == 9.5
    assert len(result.segments) == 2
    # Text is stripped per segment (leading/trailing whitespace from
    # Whisper's output)
    assert result.segments[0].text == "Hallo."
    assert result.segments[1].text == "Welt."


def test_transcribe_model_name_composed_from_info():
    model = MagicMock()
    model.transcribe.return_value = (iter([]), _fake_info(model_size="medium"))
    result = transcribe(model, Path("/vault/memo.m4a"))
    assert result.model_name == "faster-whisper-medium"


def test_transcribe_falls_back_when_info_lacks_model_size():
    # Genuine worst case: neither info NOR the model object expose the size.
    model = MagicMock(spec=[])  # no attrs at all
    model.transcribe = MagicMock(
        return_value=(iter([]), SimpleNamespace(language="en", duration=1.0))
    )
    result = transcribe(model, Path("/vault/memo.m4a"))
    assert result.model_name == "faster-whisper"


def test_transcribe_uses_tomo_model_size_stash_when_info_is_bare():
    # faster-whisper 1.2.x: TranscriptionInfo has no model_name and the
    # WhisperModel object doesn't expose its source path. load_model()
    # stashes the size on the model as `_tomo_model_size`; transcribe
    # falls back to it when the info is bare.
    model = MagicMock()
    model._tomo_model_size = "medium"
    model.transcribe.return_value = (
        iter([]),
        SimpleNamespace(language="de", duration=3.0),
    )
    result = transcribe(model, Path("/vault/memo.m4a"))
    assert result.model_name == "faster-whisper-medium"


def test_transcribe_passes_vad_and_language_to_model():
    model = MagicMock()
    model.transcribe.return_value = (iter([]), _fake_info())
    transcribe(model, Path("/vault/memo.m4a"), language="en")

    call_kwargs = model.transcribe.call_args.kwargs
    assert call_kwargs["vad_filter"] is True
    assert call_kwargs["vad_parameters"] == {"min_silence_duration_ms": 500}
    assert call_kwargs["temperature"] == 0.0
    assert call_kwargs["language"] == "en"
    # beam_size=1 explicit: faster-whisper's default is 5 which is slow on
    # CPU and contradicts our deterministic (temperature=0) intent.
    assert call_kwargs["beam_size"] == 1


def test_default_cpu_threads_respects_env_override(monkeypatch):
    from lib.voice_transcriber import _default_cpu_threads

    monkeypatch.setenv("TOMO_VOICE_CPU_THREADS", "3")
    assert _default_cpu_threads() == 3


def test_default_cpu_threads_falls_back_to_half_cores(monkeypatch):
    from lib.voice_transcriber import _default_cpu_threads

    monkeypatch.delenv("TOMO_VOICE_CPU_THREADS", raising=False)
    n = _default_cpu_threads()
    assert n >= 1
    cores = os.cpu_count() or 4
    assert n == max(1, cores // 2)


def test_default_cpu_threads_ignores_invalid_env(monkeypatch):
    from lib.voice_transcriber import _default_cpu_threads

    monkeypatch.setenv("TOMO_VOICE_CPU_THREADS", "not-a-number")
    n = _default_cpu_threads()
    # Falls back to the computed default, not 0 (which would re-introduce
    # the ctranslate2 oversubscription bug).
    assert n >= 1


def test_segment_dataclass_is_plain_data():
    seg = Segment(1.0, 2.0, "hi")
    assert seg.start == 1.0
    assert seg.end == 2.0
    assert seg.text == "hi"


# ── Opt-in: live model integration ──────────────────────────────
# Only runs when TOMO_TEST_MODEL_DIR points at a downloaded model dir AND
# faster_whisper is installed (typically inside the Docker container).
live_test_skip_reason = (
    "set TOMO_TEST_MODEL_DIR to an existing faster-whisper model "
    "directory + install faster_whisper to run"
)


@pytest.mark.voice_model
@pytest.mark.skipif(
    not os.environ.get("TOMO_TEST_MODEL_DIR"),
    reason=live_test_skip_reason,
)
def test_live_load_and_transcribe(tmp_path):
    from lib.voice_transcriber import load_model, transcribe as live_transcribe

    model_dir = Path(os.environ["TOMO_TEST_MODEL_DIR"])
    fixture = TESTS_DIR / "fixtures" / "hello-world.wav"
    if not fixture.exists():
        pytest.skip(f"fixture missing: {fixture}")

    model = load_model(model_dir)
    # load_model must stash the size so transcribe can surface it in the
    # rendered markdown (faster-whisper 1.2.x TranscriptionInfo doesn't).
    assert getattr(model, "_tomo_model_size", "") == \
        model_dir.name.removeprefix("faster-whisper-")

    result = live_transcribe(model, fixture, language=None)
    assert len(result.segments) > 0
    joined = " ".join(s.text.lower() for s in result.segments)
    assert "test" in joined or "hello" in joined or "hallo" in joined
    # Regression guard for the bug the user found in the first live run.
    assert result.model_name.startswith("faster-whisper-"), \
        f"model_name should carry size suffix; got {result.model_name!r}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
