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
| requirements.md | ready | v0.2 — all open questions answered 2026-04-20 |
| solution.md | pending | Open: Whisper engine (whisper.cpp vs faster-whisper), install wizard hook, ffmpeg staging |
| plan/ | pending | |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-20 | Local-only transcription | User privacy; Tomo is already local-first, no reason to route voice memos through cloud |
| 2026-04-20 | Whisper as engine | De-facto standard for open-source transcription; strong German support at medium+ sizes |
| 2026-04-20 | Markdown output with callout-per-segment | Integrates with existing Obsidian callout rendering; preserves segment timestamps for audio-seek |
| 2026-04-20 | Audio file stays in vault | User can replay via embed (`![[memo.m4a#t=3]]`); Tomo doesn't delete source media |
| 2026-04-20 | Transcribe BEFORE Pass 1 analysis | Transcript becomes a regular fleeting note — reuses existing inbox pipeline (classification, MOC match, etc.) |
| 2026-04-20 | Install-time opt-in wizard | Feature adds ~1.5 GB to image with medium model — opt-in keeps Docker lean for text-only users |
| 2026-04-20 | Default model: medium | Best German quality at reasonable footprint; user can override to tiny/base/small/large-v3 at install |
| 2026-04-20 | Segment-level timestamps only (no word-level) | Keeps output compact; users can replay audio from segment start |
| 2026-04-20 | Warn at 20 min, no hard limit | Meeting memos legitimately run 60+ min; hard cap would block real use cases |
| 2026-04-20 | All common audio formats via ffmpeg | m4a/mp3/wav/ogg/opus/flac/aac — ffmpeg decodes transparently, whitelist drives only discovery |
| 2026-04-20 | Same inbox, no voice subdir | Simpler UX — audio sits next to .md fleeting notes |

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

## Open Questions (for SDD)

- **Engine**: whisper.cpp (C++, smaller footprint, ggml models) vs
  faster-whisper (Python, CTranslate2, faster on CPU)? Both viable; need
  to benchmark image size and M-series speed.
- **GPU/Metal acceleration**: whisper.cpp supports Metal on macOS hosts
  via Core ML or direct Metal. Docker Desktop doesn't pass GPU through by
  default — likely CPU-only inside container. Confirm at SDD time.
- **Install wizard UX**: new wizard skill under `/tomo-setup` or inline
  prompts in `install-tomo.sh`? Existing patterns: `tomo-trackers-wizard`,
  `tomo-daily-log-wizard`. Voice is install-time, not vault-time, so it
  probably belongs in `install-tomo.sh` directly.
- **Model storage path inside image**: `/opt/whisper/models/ggml-<size>.bin`
  or under instance home? Affects Dockerfile layering and update flow.
- **ffmpeg in image**: already present? If not, needs install step.
