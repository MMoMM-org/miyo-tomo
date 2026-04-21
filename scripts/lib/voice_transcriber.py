#!/usr/bin/env python3
# version: 0.1.1
"""voice_transcriber.py — Thin wrapper over faster_whisper.WhisperModel.

Exposes:
  - Segment, TranscriptResult dataclasses (pure data, no engine import)
  - load_model(model_dir) → WhisperModel (int8 cpu-only)
  - transcribe(model, audio_path, language=None) → TranscriptResult

The dataclasses must be importable WITHOUT faster_whisper installed — the
render module and tests depend on them. The engine is only imported when
load_model() / transcribe() is actually called.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Segment:
    start: float  # seconds
    end: float
    text: str


@dataclass
class TranscriptResult:
    audio_path: Path
    model_name: str
    language: str
    duration_sec: float
    segments: list[Segment] = field(default_factory=list)


def load_model(model_dir: Path):
    """Load a faster-whisper model from an on-disk CT2 directory.

    CPU-only, int8 quantization — matches the Docker runtime profile.
    Deferred import keeps this module safe to load in environments where
    faster_whisper isn't installed (e.g. running render tests on the host).

    We also stash the model size on the returned object as `_tomo_model_size`.
    faster-whisper 1.2.x exposes neither `model_size_or_path` on the model
    nor a reliable `model_name`/`model_name_or_size` on TranscriptionInfo,
    so without this the rendered transcript would drop the size suffix
    (e.g. "faster-whisper" instead of "faster-whisper-medium").
    """
    from faster_whisper import WhisperModel  # type: ignore

    model = WhisperModel(str(model_dir), device="cpu", compute_type="int8")
    model._tomo_model_size = model_dir.name.removeprefix("faster-whisper-")
    return model


def transcribe(model, audio_path: Path, language: str | None = None) -> TranscriptResult:
    """Transcribe one audio file via an already-loaded model.

    VAD is on with a 500 ms min-silence threshold to skip dead air.
    Temperature is 0 for deterministic output (same audio → same transcript).
    """
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        temperature=0.0,
    )
    segments = [Segment(s.start, s.end, s.text.strip()) for s in segments_iter]

    # Model-size resolution, preferring least-surprising sources:
    # 1. TranscriptionInfo.model_name / model_name_or_size (some versions).
    # 2. `_tomo_model_size` stashed by our load_model() (1.2.x fallback).
    # 3. Empty — render will degrade gracefully to "faster-whisper".
    model_size = (
        getattr(info, "model_name_or_size", None)
        or getattr(info, "model_name", None)
        or getattr(model, "_tomo_model_size", None)
        or ""
    )

    return TranscriptResult(
        audio_path=audio_path,
        model_name=f"faster-whisper-{model_size}" if model_size else "faster-whisper",
        language=info.language,
        duration_sec=info.duration,
        segments=segments,
    )
