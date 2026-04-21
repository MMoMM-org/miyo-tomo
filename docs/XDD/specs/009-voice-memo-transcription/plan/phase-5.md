---
title: "Phase 5: End-to-end live test + docs"
status: code-complete
version: "1.1"
phase: 5
---

# Phase 5: End-to-end live test + docs

## Phase Context

**Dependencies**: Phases 1–4 complete and merged.

**Key files**:
- `README.md` (root — feature mention)
- `docs/XDD/reference/tier-2/workflows/inbox-pass-1.md` (reference doc — note
  Phase 0 addition)
- `tomo/dot_claude/rules/project-context.md` (version bump + capability note)
- `docs/XDD/backlog.md` (mark F-26 as done)

---

## Tasks

- [ ] **T5.1 Real voice memo end-to-end** `[activity: validate]` *(pending — host + live Tomo + real vault)*

  1. Prime: Use the real production setup (medium model, real vault).
  2. Implement: Record a 2–3 minute voice memo in German on phone, sync to
     vault inbox. Run `/inbox`.
  3. Validate:
     - Transcript markdown is generated.
     - Pass 1 classifies the transcript correctly (not "fleeting" garbage).
     - Audio embed playback works in Obsidian (click → seeks to start).
     - Click on a callout timestamp → audio seeks correctly (verify Obsidian
       supports `t=N` fragment in audio embeds; if not, document the limit).

- [ ] **T5.2 Performance measurement** `[activity: validate]` *(pending — host; medium model download required)*

  1. Prime: Performance target = 5-min memo ≤ 5 min wall on M-series CPU
     with medium model.
  2. Implement: Record a 5-minute monologue, time the transcription:
     - `time python3 scripts/voice-transcribe.py <5min.m4a> --model-dir <medium>`
     - Repeat 3 times, take the median.
  3. Validate:
     - Median ≤ 5 min wall-clock → target met, document actual number.
     - If exceeds: investigate (was VAD trimming? was int8 active? CPU
       count?). Adjust SDD performance target with measured reality.

- [x] **T5.3 Update tier-2 inbox-processing reference doc** `[activity: docs]` — Section 4 agents table + new "4b. Optional Pre-Step: Voice Transcription (Phase 0)" added. *(Note: plan originally said `inbox-pass-1.md`; actual filename is `inbox-processing.md`.)*

  1. Prime: Read `docs/XDD/reference/tier-2/workflows/inbox-pass-1.md`.
  2. Implement: Add a "Phase 0: Voice Transcription (optional)" section
     describing the conditional pre-step. Reference spec 009. Note that
     transcripts feed Phase A unchanged.
  3. Validate: Reference doc accurately reflects new pipeline.

- [x] **T5.4 Update README and project-context** `[activity: docs]` — README features + Agents table; project-context v0.7.0 → v0.8.0 + new "Voice Memo Transcription (Optional)" section + agents table update.

  1. Prime: Read root `README.md` and `tomo/dot_claude/rules/project-context.md`.
  2. Implement:
     - README: under features, add "Voice memo transcription (optional, local)".
     - project-context.md: bump version, mention voice capability + how it's
       enabled (`install-tomo.sh` wizard).
  3. Validate: Both files reference the feature accurately.

- [x] **T5.5 Backlog update** `[activity: docs]` — F-26 marked ✅ Done 2026-04-21 with commit trail.

  1. Prime: `docs/XDD/backlog.md` lists F-26 (voice memo transcription)
     as Should.
  2. Implement: Mark F-26 as done with a date and link to spec 009.
  3. Validate: Backlog reflects current truth.

- [~] **T5.6 Spec status flip** `[activity: docs]` *(partial — spec README reflects code-complete state + Completion Summary; final DONE flip waits on T5.1/T5.2 live validation)*

  1. Prime: `docs/XDD/specs/009-voice-memo-transcription/README.md`
     currently in PLAN phase.
  2. Implement: Set Current Phase = `DONE`, set Status = `ready`. Mark all
     phase READMEs as `status: done`. Add a "Completion Summary" section
     in spec README listing what shipped, performance numbers, known limits.
  3. Validate: All status fields consistent. README serves as the canonical
     "this is what we built" reference.

- [ ] **T5.7 Phase Validation** `[activity: validate]` *(pending — blocked on T5.1/T5.2)*

  - Live transcription works end-to-end on a real voice memo.
  - Performance target met (or documented if not).
  - All docs updated; no dangling references to "future" voice work.
  - Spec marked done; backlog cleared of F-26.
  - Branch ready to merge into main.
