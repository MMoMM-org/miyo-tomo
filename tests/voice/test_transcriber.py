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
    model = MagicMock()
    # Older faster-whisper versions exposed neither attribute — mimic that
    bad_info = SimpleNamespace(language="en", duration=1.0)
    model.transcribe.return_value = (iter([]), bad_info)
    result = transcribe(model, Path("/vault/memo.m4a"))
    assert result.model_name == "faster-whisper"


def test_transcribe_passes_vad_and_language_to_model():
    model = MagicMock()
    model.transcribe.return_value = (iter([]), _fake_info())
    transcribe(model, Path("/vault/memo.m4a"), language="en")

    call_kwargs = model.transcribe.call_args.kwargs
    assert call_kwargs["vad_filter"] is True
    assert call_kwargs["vad_parameters"] == {"min_silence_duration_ms": 500}
    assert call_kwargs["temperature"] == 0.0
    assert call_kwargs["language"] == "en"


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
    result = live_transcribe(model, fixture, language=None)
    assert len(result.segments) > 0
    joined = " ".join(s.text.lower() for s in result.segments)
    assert "test" in joined or "hello" in joined or "hallo" in joined


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
