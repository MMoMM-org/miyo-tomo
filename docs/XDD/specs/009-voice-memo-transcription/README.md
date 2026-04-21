# Specification: 009-voice-memo-transcription

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-20 |
| **Current Phase** | CODE-COMPLETE — pending host validation (T5.1 / T5.2) |
| **Last Updated** | 2026-04-21 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | ready | v0.2 — all open questions answered 2026-04-20 |
| solution.md | ready | v0.2 — batch-CLI pattern (2026-04-21) |
| plan/ | code-complete | Phases 1-5 implementation merged into `feat/xdd-009-voice-transcription`. T3.6 / T4.5-T4.8 / T5.1-T5.2 / T5.7 live tests pending host Tomo session. |

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
| 2026-04-20 | Engine: faster-whisper | Python-native API fits existing scripts/lib pattern; built-in VAD trims silence (faster); CPU-only confirmed — speed matters more than without GPU; pip install simpler than compile-from-source |
| 2026-04-20 | CPU-only (no GPU passthrough) | Docker Desktop doesn't pass Metal/CUDA by default; keeps setup portable across hosts |
| 2026-04-20 | Model on host, mounted into container | Image stays lean; model swap (medium → large-v3) requires only re-download, no image rebuild. Still "preloaded" at install time per F2a |
| 2026-04-20 | Whisper metadata as plain-text block, NOT frontmatter | User's inbox is zettelkasten-inspired, lean; YAML frontmatter slot stays free for any future inbox-note convention |
| 2026-04-20 | No inbox-note template imposed by this spec | Tomo has atomic-note templates but no inbox template yet — defining it is a separate concern (backlog F-25); transcripts join the existing free-form fleeting-note convention |
| 2026-04-21 | Batch CLI (load model once per `/inbox` run, transcribe all audios, exit) | Amortises ~3–5 s cold-start across N files without a daemon. OS reclaims ~2 GB model RAM on process exit — implicit unload, no lifecycle code. Rejected alternatives: per-file CLI (N× cold-start), long-lived daemon (IPC + idle-timeout complexity for uncertain gain). |

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

Resolved 2026-04-20:
- Engine → **faster-whisper**
- GPU → **CPU-only** (Docker portability)
- Model storage → **host-mounted** at `tomo-instance/voice/models/`

All resolved during SDD + implementation:
- **Install wizard placement** → inline function `configure_voice()` in
  `scripts/lib/configure-voice.sh`, sourced by `install-tomo.sh` and
  `update-tomo.sh`.
- **ffmpeg** → added to `docker/Dockerfile` unconditionally (~60 MB).
- **Model URL** → `Systran/faster-whisper-<size>` on HuggingFace; files
  discovered via the Tree API (integrity via size + LFS SHA-256 for
  `model.bin`).
- **VAD config** → defaulted to `vad_filter=True`,
  `min_silence_duration_ms=500` in `scripts/lib/voice_transcriber.py`.
  Not exposed to vault-config for MVP — YAGNI.
- **Agent integration** → new `voice-transcriber` agent invoked by
  `inbox-orchestrator` as Phase 0a (before Phase 0b resume detection).

## Completion Summary (2026-04-21)

**Shipped** (branch `feat/xdd-009-voice-transcription`, 6 commits):

| Area | Artefact | Status |
|---|---|---|
| Install wizard | `scripts/lib/configure-voice.sh` v0.2.0 | ✅ |
| Model download | `scripts/download-whisper-model.sh` v0.2.0 (HF Tree API + size/sha256 verification + `.download-complete` sentinel) | ✅ |
| Docker | ffmpeg unconditional + `ARG VOICE_ENABLED=0` gates `faster-whisper>=1.0,<2` pip install + `VOLUME /tomo/voice` | ✅ |
| Launcher | `begin-tomo.sh.template` v0.7.0 — `--build-arg` + `tomo.voice_enabled` image label + drift auto-rebuild + `-v voice:/tomo/voice:ro` when enabled | ✅ |
| Python modules | `scripts/lib/voice_transcriber.py` v0.1.0, `scripts/lib/voice_render.py` v0.1.0 | ✅ |
| Batch CLI | `scripts/voice-transcribe.py` v0.1.0 — variadic audio paths, JSON manifest stdout, exit 0/2/3 | ✅ |
| Agent | `tomo/dot_claude/agents/voice-transcriber.md` v0.1.0 (sonnet/low) | ✅ |
| Orchestrator | `inbox-orchestrator.md` v0.6.0 → v0.7.0 — Phase 0a voice + Phase 0b resume (renamed) | ✅ |
| Tests | 20 pytest tests (7 render + 6 transcriber + 7 CLI), 19 pass + 1 opt-in `voice_model` skipped | ✅ |

**Host-side sandbox validation** (pre-merge, without running Tomo):
- Wizard state transitions (fresh / keep / change / disable) across
  non-interactive and interactive paths.
- HF download + checksum verification with tiny model (83 MB, 6 files,
  sha256 on `model.bin`).
- `.download-complete` sentinel detection → triggers clean re-download
  on partial state.
- `pytest -m voice_model` with faster-whisper 1.2.1 + tiny model:
  `test_live_load_and_transcribe` PASS (transcribed fixture
  word-for-word).
- Batch CLI multi-file smoke: 2 files in ~1.05 s wall-clock (one model
  load amortised across both).
- All 5 touched shell scripts syntax-checked.

**Pending — live Tomo validation** (host only):
- T3.6 standalone agent invocation in a running Tomo session.
- T4.5 / T4.6 / T4.7 orchestrator integration — voice ON / voice OFF /
  voice error recovery.
- T5.1 real voice memo end-to-end on medium model + Obsidian callout
  playback verification.
- T5.2 5-min memo performance measurement (target ≤ 5 min wall on
  M-series CPU).

**Known limits**:
- Non-LFS HF files (config.json, tokenizer.json, vocabulary.txt) are
  size-verified only, not sha256-verified. Git-blob-sha1 would require
  extra plumbing; re-download on corruption is cheap enough.
- Model rerun detection relies on a sentinel file, not on content
  hash. A hand-corrupted file with intact sentinel would not be
  detected on next `/inbox`. Acceptable — users don't hand-edit
  CT2 weights.
- `voice.language` omitted or `"auto"` sends nothing to the CLI →
  Whisper auto-detect. Not tested against a multi-language memo.
