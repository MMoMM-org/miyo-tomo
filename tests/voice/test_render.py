#!/usr/bin/env python3
# version: 0.1.0
"""test_render.py — Unit tests for voice_render.py.

Pure-function tests: given a stub TranscriptResult, assert that the rendered
markdown matches the shape specified in PRD § F3 of XDD 009 exactly.

Runs without faster-whisper installed — no engine dependency.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# Load voice_render + voice_transcriber dataclasses from scripts/lib/.
# These modules must be import-safe without faster-whisper — render is pure
# and only touches dataclass instances.
import lib.voice_render as vr  # noqa: E402
from lib.voice_transcriber import Segment, TranscriptResult  # noqa: E402


def make_result(segments: list[tuple[float, float, str]]) -> TranscriptResult:
    return TranscriptResult(
        audio_path=Path("/tmp/memo.m4a"),
        model_name="faster-whisper-tiny",
        language="de",
        duration_sec=12.4,
        segments=[Segment(s, e, t) for (s, e, t) in segments],
    )


def test_render_has_metadata_block_before_separator():
    result = make_result([(0.0, 3.0, "Hallo Welt.")])
    out = vr.render_markdown(result)
    meta, _, _ = out.partition("---")
    assert "source: memo.m4a" in meta
    assert "model: faster-whisper-tiny" in meta
    assert "language: de" in meta
    assert "duration_sec: 12" in meta
    assert "transcribed:" in meta


def test_render_has_audio_embed_after_separator():
    result = make_result([(0.0, 3.0, "Hallo Welt.")])
    out = vr.render_markdown(result)
    _, sep, body = out.partition("---")
    assert sep == "---"
    assert "![[memo.m4a]]" in body


def test_render_one_callout_per_segment():
    result = make_result([
        (0.0, 3.0, "Erster Satz."),
        (3.0, 7.5, "Zweiter Satz."),
        (7.5, 12.4, "Dritter Satz."),
    ])
    out = vr.render_markdown(result)
    callout_lines = [ln for ln in out.splitlines() if ln.startswith("> [!voice]")]
    assert len(callout_lines) == 3


def test_render_callout_timestamp_is_mmss():
    result = make_result([
        (0.0, 3.0, "Start."),
        (65.5, 70.0, "Nach einer Minute."),
        (3600.0, 3605.0, "Nach einer Stunde — segment start in mm:ss."),
    ])
    out = vr.render_markdown(result)
    assert "> [!voice] 00:00" in out
    assert "> [!voice] 01:05" in out
    # 3600 sec = 60:00 — mm:ss format doesn't roll into hours. That's a
    # conscious choice: voice memos rarely exceed an hour and mm:ss maps
    # directly to Obsidian's audio-seek fragment (#t=<sec>).
    assert "> [!voice] 60:00" in out


def test_render_callout_content_is_next_line():
    result = make_result([(10.0, 15.0, "Der Inhalt der Notiz.")])
    out = vr.render_markdown(result)
    lines = out.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("> [!voice]"):
            assert lines[i + 1] == "> Der Inhalt der Notiz."
            return
    raise AssertionError("callout line not found")


def test_render_trailing_newline():
    result = make_result([(0.0, 1.0, "x")])
    out = vr.render_markdown(result)
    assert out.endswith("\n"), "rendered markdown must end with a newline"


def test_render_empty_segment_list_still_produces_metadata_and_embed():
    result = make_result([])
    out = vr.render_markdown(result)
    assert "source: memo.m4a" in out
    assert "![[memo.m4a]]" in out
    # No callouts — that's fine, represents a fully-silent memo
    assert "> [!voice]" not in out


def test_render_timestamp_is_iso8601_second_precision():
    # When a fixed `now` is injected, the `transcribed:` field is fully
    # deterministic — useful both for snapshot tests and to guard the
    # exact ISO-8601 format (review finding M12).
    import re
    from datetime import datetime

    fixed = datetime(2026, 4, 22, 15, 30, 45)
    result = make_result([(0.0, 1.0, "x")])
    out = vr.render_markdown(result, now=fixed)

    assert "transcribed: 2026-04-22T15:30:45" in out

    # Regression guard on the format itself — microseconds, timezone
    # suffix, or a date-only variant would all break downstream tools
    # that consume the transcript metadata.
    match = re.search(r"^transcribed: (.+)$", out, re.MULTILINE)
    assert match is not None
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", match.group(1))


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
