---
title: "Voice Memo Transcription — Implementation Plan"
status: draft
version: "1.0"
---

# Implementation Plan

## Context Priming

**Specification**:
- `docs/XDD/specs/009-voice-memo-transcription/README.md`
- `docs/XDD/specs/009-voice-memo-transcription/requirements.md`
- `docs/XDD/specs/009-voice-memo-transcription/solution.md`

**Key Design Decisions**:
- Engine: **faster-whisper** (CPU-only, int8, VAD on)
- Model: host-mounted at `tomo-instance/voice/models/faster-whisper-<size>/`
- Wizard: stateful (always runs, defaults to no-op when already configured)
- Pipeline: new `voice-transcriber` agent runs as **Phase 0** in `inbox-orchestrator`
- Output: plain-text metadata block + `---` + audio embed + per-segment callouts
- No frontmatter imposed — joins existing inbox convention

**Build/Runtime Footprint**:
- ffmpeg: ~60 MB, always installed
- faster-whisper + ctranslate2: ~200 MB, installed only when `VOICE_ENABLED=1`
- Medium model: 1.5 GB on host, mounted in (not in image)

## Implementation Phases

- [ ] [Phase 1: Install wizard + Dockerfile + model download](phase-1.md)
- [ ] [Phase 2: Python modules + CLI script (standalone)](phase-2.md)
- [ ] [Phase 3: voice-transcriber agent (standalone)](phase-3.md)
- [ ] [Phase 4: Orchestrator integration (Phase 0 in inbox-orchestrator)](phase-4.md)
- [ ] [Phase 5: End-to-end live test + docs](phase-5.md)

## Phase Dependencies

```
Phase 1 (wizard + image) ──┐
                            ├──→ Phase 4 (orchestrator) ──→ Phase 5 (E2E + docs)
Phase 2 (modules) ──→ Phase 3 (agent) ──┘
```

Phases 1 and 2 can run in parallel. Phase 3 depends on Phase 2. Phase 4
depends on 1 + 3. Phase 5 is final integration + sign-off.

## Acceptance for Spec Completion

- All 5 phase READMEs marked `status: done`
- `/inbox` with audio file in vault produces transcribed `.md` and proceeds
  through Pass 1 unchanged
- `/inbox` without audio files has no measurable overhead vs pre-spec baseline
- Disabling voice via wizard removes faster-whisper from image; subsequent
  `/inbox` runs ignore audio silently
- Re-enabling restores full functionality
- Performance target met: 5-min memo ≤ 5 min wall on M-series CPU with medium
