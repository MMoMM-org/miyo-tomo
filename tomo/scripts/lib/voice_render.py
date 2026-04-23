#!/usr/bin/env python3
# version: 0.4.0
"""voice_render.py — Deterministic markdown renderer for transcripts.

Consumes a TranscriptResult and produces markdown matching PRD § F3 of
XDD 009:

  source: <filename>
  transcribed: <iso8601>
  model: <faster-whisper-XYZ>
  language: <lang>
  duration_sec: <int>

  ---

  ![[<filename>]]

  > [!voice] mm:ss
  > <segment text>

  > [!voice] mm:ss
  > <segment text>

Pure function — no I/O, no engine imports.
"""
from __future__ import annotations

from datetime import datetime

from .voice_transcriber import TranscriptResult


def _mmss(seconds: float) -> str:
    """Format seconds as mm:ss (minutes may exceed 59 for long memos).

    We intentionally do not roll into hh:mm:ss — voice memos rarely run past
    an hour and mm:ss maps directly to Obsidian's audio-seek fragment.
    """
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def render_markdown(
    result: TranscriptResult,
    now: datetime | None = None,
    transcribe_sec: float | None = None,
) -> str:
    """Render a transcript to markdown.

    Fully deterministic when `now` is passed; defaults to `datetime.now()`
    so callers don't need to thread a clock through. Tests should pass a
    fixed value to assert the exact ISO-8601 format.

    `transcribe_sec` is the wall-clock time the Whisper engine spent on
    this file (not model-load, not I/O). When present, it's surfaced as
    a top-level metadata field so T5.2-style performance audits can read
    the number directly off the rendered note.
    """
    ts = (now or datetime.now()).isoformat(timespec="seconds")
    audio_name = result.audio_path.name
    lines: list[str] = [
        f"source: {audio_name}",
        f"transcribed: {ts}",
        f"model: {result.model_name}",
        f"language: {result.language}",
        f"duration_sec: {int(result.duration_sec)}",
    ]
    if transcribe_sec is not None:
        lines.append(f"transcribe_sec: {round(float(transcribe_sec), 2)}")
    lines.extend([
        "",
        "---",
        "",
        f"![[{audio_name}]]",
        "",
    ])
    for seg in result.segments:
        # Clickable seek link: Obsidian audio embeds accept the `#t=<seconds>`
        # fragment on wikilinks so a click on "01:05" scrubs the embed above
        # to that point. Alias `|01:05` renders as the visible timestamp;
        # the integer-seconds fragment is what the media-player consumes.
        seek_sec = int(seg.start)
        ts_mmss = _mmss(seg.start)
        lines.append(f"> [!voice] [[{audio_name}#t={seek_sec}|{ts_mmss}]]")
        lines.append(f"> {seg.text}")
        lines.append("")

    return "\n".join(lines) + "\n"
