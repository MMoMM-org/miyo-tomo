#!/usr/bin/env python3
# version: 0.1.0
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


def render_markdown(result: TranscriptResult) -> str:
    """Render a transcript to markdown. Deterministic apart from the
    `transcribed:` timestamp (ISO 8601, second precision)."""
    lines: list[str] = [
        f"source: {result.audio_path.name}",
        f"transcribed: {datetime.now().isoformat(timespec='seconds')}",
        f"model: {result.model_name}",
        f"language: {result.language}",
        f"duration_sec: {int(result.duration_sec)}",
        "",
        "---",
        "",
        f"![[{result.audio_path.name}]]",
        "",
    ]
    for seg in result.segments:
        lines.append(f"> [!voice] {_mmss(seg.start)}")
        lines.append(f"> {seg.text}")
        lines.append("")

    return "\n".join(lines) + "\n"
