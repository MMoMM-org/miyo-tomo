#!/usr/bin/env python3
# version: 0.3.0
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

import os
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


def _default_cpu_threads() -> int:
    """Half the logical CPU count, minimum 1.

    faster-whisper / ctranslate2's `cpu_threads=0` default asks the runtime
    to use ALL logical cores. On Apple Silicon that includes efficiency
    cores, which oversubscribes the performance cores and hurts
    throughput. Half-of-total is a reasonable proxy for performance-core
    count across Intel + Apple Silicon Macs and Linux hosts.

    Override by setting TOMO_VOICE_CPU_THREADS in the environment —
    useful for tuning on servers or constrained containers.
    """
    override = os.environ.get("TOMO_VOICE_CPU_THREADS")
    if override:
        try:
            n = int(override)
            if n >= 1:
                return n
        except ValueError:
            pass
    cores = os.cpu_count() or 4
    return max(1, cores // 2)


def load_model(model_dir: Path):
    """Load a faster-whisper model from an on-disk CT2 directory.

    CPU-only, int8 quantization — matches the Docker runtime profile.
    `cpu_threads` is set explicitly to half the logical cores instead
    of the library's `cpu_threads=0` default (which uses all cores and
    oversubscribes on M-series CPUs); `num_workers=1` keeps the batch
    loop's sequential assumptions intact.

    Deferred import keeps this module safe to load in environments where
    faster_whisper isn't installed (e.g. running render tests on the host).

    We also stash the model size on the returned object as `_tomo_model_size`.
    faster-whisper 1.2.x exposes neither `model_size_or_path` on the model
    nor a reliable `model_name`/`model_name_or_size` on TranscriptionInfo,
    so without this the rendered transcript would drop the size suffix
    (e.g. "faster-whisper" instead of "faster-whisper-medium").
    """
    from faster_whisper import WhisperModel  # type: ignore

    model = WhisperModel(
        str(model_dir),
        device="cpu",
        compute_type="int8",
        cpu_threads=_default_cpu_threads(),
        num_workers=1,
    )
    model._tomo_model_size = model_dir.name.removeprefix("faster-whisper-")
    return model


def transcribe(model, audio_path: Path, language: str | None = None) -> TranscriptResult:
    """Transcribe one audio file via an already-loaded model.

    - `beam_size=1` overrides faster-whisper's default of 5. Greedy decode
      is ~30-40% faster on CPU with negligible quality loss at medium+ sizes
      and matches the "deterministic" intent of `temperature=0.0`.
    - VAD is on with a 500 ms min-silence threshold to skip dead air.
    - Temperature is 0 for deterministic output (same audio → same transcript).
      Note: this disables faster-whisper's compression-ratio fallback chain,
      which is intentional — we prefer reproducibility over occasional
      recovery on hard audio.
    """
    segments_iter, info = model.transcribe(
        str(audio_path),
        language=language,
        beam_size=1,
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
    # Strip the prefix at the FINAL assembly point rather than trusting
    # each source's shape. A future faster-whisper release could populate
    # `model_name_or_size` with the already-prefixed form
    # ("faster-whisper-medium") and our `f"faster-whisper-{size}"` would
    # double-prefix to "faster-whisper-faster-whisper-medium"
    # (review finding L3).
    if isinstance(model_size, str) and model_size.startswith("faster-whisper-"):
        model_size = model_size[len("faster-whisper-"):]

    return TranscriptResult(
        audio_path=audio_path,
        model_name=f"faster-whisper-{model_size}" if model_size else "faster-whisper",
        language=info.language,
        duration_sec=info.duration,
        segments=segments,
    )
