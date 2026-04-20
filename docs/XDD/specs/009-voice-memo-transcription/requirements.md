---
title: "Voice Memo Transcription in Inbox"
status: draft
version: "0.2"
---

# Product Requirements Document

## Product Overview

### Vision

Let Tomo transcribe voice memos in the inbox locally via Whisper, so voice
captures become regular fleeting notes that flow through the existing 2-pass
inbox pipeline — no manual transcription step, no cloud.

### Problem Statement

Today's `/inbox` only handles `.md` files. Users who capture thoughts as voice
memos on iOS/Android accumulate audio files that either:

- Get transcribed manually (friction → backlog) or
- Never get processed (intent lost)

Cloud transcription (OpenAI API, AssemblyAI) would solve the UX but violates
Tomo's local-first/privacy-first principle — personal voice memos shouldn't
leave the user's machine.

### Value Proposition

- **Zero-friction voice capture:** drop an audio file in the inbox → next
  `/inbox` run transcribes it and processes the transcript like any other
  fleeting note.
- **Local-only:** transcription runs in the Docker container; audio never
  touches external servers.
- **Audio-text co-location:** the original audio stays in the vault; the
  transcript references it with `![[memo.m4a]]` so users can replay on
  demand.
- **Seekable transcript:** segment-level timestamps as callouts let users
  jump to the exact audio moment (`![[memo.m4a#t=N]]`).
- **Pipeline reuse:** transcribed notes go through existing Pass 1 (MOC
  matching, classification) and Pass 2 (instructions) — no parallel flow.

## User Personas

### Primary: Voice-first capturer

- Records thoughts on iOS Voice Memos / Android Recorder while walking, driving,
  or away from desk.
- Currently has 20+ unprocessed `.m4a` files sitting in vault because
  transcription is a chore.
- Wants captures to flow through the same `/inbox` review he uses for text
  notes — not a parallel workflow.

### Secondary: Meeting-note capturer

- Records short (<5 min) meeting summaries or brainstorm voice memos.
- Needs the transcript to keep rough structure (segment breaks) so he can
  navigate, but doesn't need word-perfect accuracy.

## User Journey Map

### Primary Journey: voice memo → inbox note

1. User records a voice memo on phone, syncs it to the vault inbox folder
   (e.g. via Obsidian sync, iCloud, Syncthing).
2. User runs `/inbox`.
3. Tomo discovers audio files in the inbox alongside `.md` files.
4. For each audio file, Tomo runs local Whisper → produces sibling `.md`:
   `memo.m4a` → `memo.md` with segment-timestamped callouts referencing the audio.
5. Newly-created transcripts enter Pass 1 fan-out just like hand-typed
   fleeting notes: classified, MOC-matched, daily-log candidates evaluated.
6. User reviews suggestions in the standard Pass 1 output; approves or edits.
7. Pass 2 generates instructions; user applies via existing flow.
8. If user wants to replay a moment mid-review, they click the embed in the
   transcript — Obsidian seeks to the timestamp.

### Edge Journey: already-transcribed audio

- If `memo.md` already exists alongside `memo.m4a`, Tomo skips transcription
  (idempotent) and processes the existing `.md` through the normal flow.

## Feature Requirements

### Must Have

#### F1 — Audio discovery in inbox
- `/inbox` discovery step finds audio files in the **same inbox directory** as
  `.md` files (no separate voice subdir).
- Supported formats whitelist: `.m4a .mp3 .wav .ogg .opus .flac .aac`
  (ffmpeg decodes all of these transparently — whitelist only drives discovery).
- Symlinks followed (same as existing inbox scan).
- Discovery is skipped entirely if voice feature is disabled (see F2a).

#### F2 — Local Whisper transcription
- Transcription runs inside the Docker container — no network calls.
- Whisper model is multilingual (user language ≠ only English).
- Output captures segment-level timestamps (start/end per segment).
  Word-level timing is NOT generated (MVP).

#### F2a — Install-time opt-in
- `install-tomo.sh` asks the user: "Enable voice memo transcription? [y/n]"
  - If **no**: no Whisper binary, no model, no image bloat. Inbox audio
    discovery is silently skipped. User can enable later via install --update.
  - If **yes**: asks "Which Whisper model? [tiny / base / small / medium
    (recommended) / large-v3]". Default: `medium` (German sweet spot).
- Selected choices persist in `tomo-install.json` under `voice: { enabled,
  model }`.
- Install step then pre-downloads the selected GGML model into the Docker
  image (fat-image, zero-latency first use).
- Re-running install with a different choice updates the image accordingly.

#### F3 — Markdown transcript with timestamped callouts
- For each audio file `X.<ext>`, Tomo writes sibling `X.md` with:
  - Frontmatter identifying it as a transcript (source: audio file name, model used, date)
  - First line: audio embed `![[X.<ext>]]` for playback
  - One Obsidian callout per segment, header = `mm:ss` start timestamp
  - Segment body = transcribed text
- Markdown is a valid fleeting note that the existing Pass 1 pipeline can classify.

#### F4 — Idempotent
- If `X.md` already exists alongside `X.<ext>`, skip transcription.
- If `X.<ext>` has been processed before (has a status tag indicating inbox
  lifecycle), skip.

#### F5 — Audio file preserved
- The original audio file is NOT deleted, moved, or modified.
- Cleanup (archive / delete) is a user decision handled by existing inbox
  lifecycle — same as text fleeting notes.

### Should Have

#### F6 — Language hint
- Optional `voice.language` field in vault-config (e.g. `de`, `en`) to skip
  Whisper's auto-detect and improve short-memo accuracy.

#### F7 — Skip-list config
- User can exclude patterns (`voice.exclude: ["**/recorded-meetings/**"]`)
  from auto-transcription.

#### F8 — Long-audio warning
- Files longer than `voice.warn_minutes` (default: 20) log a warning before
  transcription starts: "This file is N minutes long — transcription will
  take ~N minutes wall-clock."
- No hard limit — user decides whether to wait or cancel. Rationale: meeting
  memos can legitimately be 60+ min; a hard cap would block real use cases.

### Could Have

#### F9 — Chapter detection from pause length
- Whisper's segment boundaries group words by pause; chapter-level grouping
  (> N seconds silence) could create Obsidian headers instead of just callouts.

#### F10 — Speaker hints in output
- If user says "Marcus:" or "Dana:" aloud, detect and format as dialogue.
  (NOT full diarization — just textual cues.)

### Won't Have (MVP)

- Speaker diarization (multi-speaker separation).
- Cloud fallback (OpenAI, AssemblyAI).
- Real-time / streaming transcription.
- Audio editing / clipping.
- Automatic deletion of source audio.

## Functional Requirements

### Inputs
- Audio file in inbox directory (format per F1)
- vault-config section `voice:` with model + language + exclude (all optional)

### Outputs
- Sibling `.md` file with transcript + embed + frontmatter
- Log entry (stdout / orchestrator log) with file, duration, model, elapsed time

### Behaviour
- Audio file found → transcribe → write markdown → proceed to Pass 1 discovery
- Audio with pre-existing `.md` → skip transcription silently
- Audio > configurable max duration (default 30 min?) → warn but still process
- Transcription failure → write error marker file (`X.transcribe-error.md`),
  leave audio in place, surface in `/inbox` summary

### Acceptance criteria
- Given a `.m4a` in the inbox, when `/inbox` runs, then:
  - A sibling `.md` is created
  - The `.md` has the audio embedded as first line
  - Segments are formatted as callouts with `mm:ss` timestamps
  - The `.md` is picked up by Pass 1 fan-out alongside other fleeting notes
- Given an audio with a pre-existing transcript `.md`, when `/inbox` runs,
  then Whisper is NOT invoked again.
- Given no audio files in inbox, when `/inbox` runs, then behaviour matches
  pre-spec (no overhead).

## Non-Functional Requirements

- **Privacy:** zero outbound network calls during transcription.
- **Performance:** 5-minute voice memo completes transcription in under
  real-time (≤5 min wall-clock) on typical M2/M3 Apple Silicon with
  `medium` model.
- **Footprint:** selected model adds ≤ 2 GB to the Docker image; smaller
  models acceptable as default.
- **Reproducibility:** same audio + same model = same transcript (modulo
  Whisper's inherent stochasticity at `temperature=0`).
- **Error surface:** transcription failures don't block processing of other
  inbox items.

## Out of Scope

- Transcription of audio files OUTSIDE the inbox (user-initiated "transcribe
  this file X" commands — separate command if ever needed).
- Post-transcription LLM polishing (cleanup, summarization) — Pass 1 already
  handles classification; additional polish can come later as a separate
  skill.
- Audio pre-processing (noise reduction, volume normalization).
- Support for video files — `.mp4`/`.mov` with audio tracks. Stretch via
  ffmpeg demux, but not MVP.

## Success Metrics

- User's voice-memo backlog clears within 2 `/inbox` sessions of rollout.
- Zero cloud calls observable in Tomo audit log during transcription.
- Transcript fleeting notes have the same Pass 1 acceptance rate (±10%) as
  hand-typed fleeting notes, indicating transcript quality is sufficient
  for the pipeline.

## Answered Questions (2026-04-20)

1. **Model default:** `medium` — German/multilingual sweet spot. (User-choice at install, default pre-selected.)
2. **Audio max duration:** warn-only at 20 min, no hard limit.
3. **Audio formats:** whitelist all common ones (`.m4a .mp3 .wav .ogg .opus .flac .aac`) — ffmpeg decodes all transparently, negligible implementation cost.
4. **Timestamp granularity:** segment-level only.
5. **Inbox location:** same inbox directory — audio files sit next to `.md` fleeting notes.
6. **Model download:** fat image — pre-downloaded during install, zero first-use latency.
7. **Install-time opt-in:** YES — feature is optional; install wizard asks enable + model. Keeps Docker image lean for users who don't capture voice.
