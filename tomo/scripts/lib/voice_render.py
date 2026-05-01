#!/usr/bin/env python3
# version: 0.5.0
"""voice_render.py — Deterministic markdown renderer for transcripts.

Consumes a TranscriptResult and produces markdown matching PRD § F3 of
XDD 009:

  source: <filename>
  transcribed: <iso8601>
  recorded: <iso8601>          # optional, parsed from filename timestamp
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

import re
from datetime import datetime

from .voice_transcriber import TranscriptResult


# Trailing `__YYYY-MM-DD HH:MM:SS` (or `HH-MM-SS` after Obsidian sanitisation
# strips `:`) carried by external recorders (iOS Voice Memos, Otter, etc).
# Surfacing this as `recorded:` gives downstream consumers (inbox-analyst
# date-source priority) an event-date field that is independent of whatever
# maintenance timestamp the host PKM might add later (Obsidian Linter's
# `Updated:` field, Templater hooks, etc.).
_FILENAME_TIMESTAMP_RE = re.compile(
    r"__"
    r"(?P<date>\d{4}-\d{2}-\d{2})"
    r"[ _T-]+"
    r"(?P<hh>\d{2})[:\-](?P<mm>\d{2})[:\-](?P<ss>\d{2})"
    r"$"
)


def _extract_recorded_iso(stem: str) -> str | None:
    """Extract a `recorded:` ISO-8601 timestamp from a filename stem.

    Recognises the trailing pattern `__YYYY-MM-DD HH:MM:SS` (or `HH-MM-SS`).
    Returns a second-precision ISO-8601 string, or `None` when no match —
    callers omit the `recorded:` line in that case (purely additive).
    """
    m = _FILENAME_TIMESTAMP_RE.search(stem)
    if not m:
        return None
    return f"{m.group('date')}T{m.group('hh')}:{m.group('mm')}:{m.group('ss')}"


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
    recorded_iso = _extract_recorded_iso(result.audio_path.stem)
    lines: list[str] = [
        f"source: {audio_name}",
        f"transcribed: {ts}",
    ]
    if recorded_iso is not None:
        # Event-date field, distinct from `transcribed:` (processing time).
        # The inbox-analyst Step 8 date-source scan prefers `recorded:` over
        # maintenance timestamps like Obsidian Linter's `Updated:` field.
        lines.append(f"recorded: {recorded_iso}")
    lines.extend([
        f"model: {result.model_name}",
        f"language: {result.language}",
        f"duration_sec: {int(result.duration_sec)}",
    ])
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
