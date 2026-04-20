# Specification: 009-voice-memo-transcription

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-20 |
| **Current Phase** | PRD |
| **Last Updated** | 2026-04-20 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | draft | First cut — needs user review |
| solution.md | pending | Open: Whisper engine choice (whisper.cpp vs faster-whisper), Docker footprint |
| plan/ | pending | |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-20 | Local-only transcription | User privacy; Tomo is already local-first, no reason to route voice memos through cloud |
| 2026-04-20 | Whisper as engine | De-facto standard for open-source transcription; strong German support at medium+ sizes |
| 2026-04-20 | Markdown output with callout-per-segment | Integrates with existing Obsidian callout rendering; preserves segment timestamps for audio-seek |
| 2026-04-20 | Audio file stays in vault | User can replay via embed (`![[memo.m4a#t=3]]`); Tomo doesn't delete source media |
| 2026-04-20 | Transcribe BEFORE Pass 1 analysis | Transcript becomes a regular fleeting note — reuses existing inbox pipeline (classification, MOC match, etc.) |

## Context

The inbox today only handles `.md` files. Users who capture fleeting thoughts as
voice memos on iOS/Android have to manually transcribe before processing —
friction that causes backlog (voice memos pile up untranscribed).

This spec adds a transcription pre-step: when `/inbox` runs, audio files in the
inbox get transcribed locally via Whisper into sibling markdown files (with
segment timestamps as Obsidian callouts). The original audio stays put for
playback-on-demand. Downstream Pass 1 / Pass 2 processing is unchanged — the
transcript is just another fleeting note.

Tomo runs in Docker, so Whisper must fit the container footprint. whisper.cpp
(small C++ binary + GGML model file) is the leading candidate; faster-whisper
(Python, CTranslate2 backend) is the alternative.

## Open Questions

- Audio formats to support (minimum: `.m4a`, `.mp3`, `.wav`; stretch: `.ogg`, `.opus`, `.flac`)?
- Whisper model default (tiny/base/small/medium/large)? Medium is the German sweet spot but costs ~1.5 GB in the image.
- Model downloaded at install time or first-use?
- GPU acceleration path (Metal via llama.cpp style) or CPU-only baseline?
- Interaction with existing `from-X/` inbox subdirs (do voice memos arrive via a specific sender)?
