---
title: "Phase 3: Audio-peer plumbing & source-set deletion"
status: completed
version: "1.1"
phase: 3
---

# Phase 3: Audio-peer plumbing & source-set deletion

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-2]` — additive audio_peer; analyst captures it
- `[ref: SDD/Runtime View; Complex Logic]` — source-set deletion behind the completion gate
- `[ref: PRD/Feature 3]` — voice source = {audio + transcript} set

**Key Decisions**:
- ADR-1/2: confirmed item carries an optional `audio_peer` path (None when absent), sourced from
  the transcript `source:` frontmatter — the analyst ADDS this extraction (the key is already in
  the loaded frontmatter, written by `voice_render.py`) — no new Kado calls.
- Delete builder emits one `delete_source` per {primary, audio_peer}, behind the existing
  completion gate; `keep_source` suppresses BOTH; no peer → single-file (unchanged).
- `_ensure_md_extension` must NOT be applied to the `.m4a`.

**Dependencies**:
- Phase 1 (`keep_source`), Phase 2 (the source-set render consumes `audio_peer`).

---

## Tasks

Delivers the behavioral core: confirming a voice item proposes deletion of BOTH the transcript and
the audio; keeping the source keeps both; no orphaned audio.

- [x] **T3.1 Analyst emits audio_peer** `[activity: backend]`

  1. Prime: Read `inbox-analyst.md` voice detection (`transcribed:`) and confirm the transcript
     frontmatter carries `source:` (written by `voice_render.py`); the analyst does NOT extract
     `source:` today `[ref: SDD/Code Context; inbox-analyst.md]`.
  2. Test (red): a contract/fixture test asserting that a voice item's analyst output carries the
     `audio_peer` (vault-relative audio path) when the transcript declares `source:`, and omits it
     (None) otherwise `[ref: PRD/AC F3]`.
  3. Implement (green): add `source:` extraction to `inbox-analyst` — the key already exists in
     the transcript frontmatter it loads (written by `voice_render.py`), so this is a new
     extraction step, NOT a new Kado read — and emit it as `audio_peer`. Update the per-item
     output schema if one is enforced.
  4. Validate: contract/fixture test passes.
  5. Success: analyst output carries `audio_peer` for voice items `[ref: SDD/ADR-2]`.

- [ ] **T3.2 Carry audio_peer manifest→confirmed-item→move_note** `[activity: backend]`

  1. Prime: Read `_build_move_note_actions` `[ref: SDD/Code Context; instruction-render.py; lines: 739-772]`.
  2. Test (red): a move_note built from a manifest entry with an audio peer carries the peer
     through to the action context the delete builder reads `[ref: PRD/AC F3]`.
  3. Implement (green): thread `audio_peer` from the manifest entry into the move_note action
     context (do NOT `_ensure_md_extension` the `.m4a`). Confirmed-item carries `audio_peer`.
  4. Validate: move_note build tests pass; the `.m4a` extension is preserved.
  5. Success: audio_peer reaches `_build_delete_source_actions` inputs `[ref: SDD/ADR-1]`.

- [x] **T3.3 Source-set deletion in _build_delete_source_actions** `[activity: backend]`

  1. Prime: Read source (3) move_note-origin block `[ref: SDD/Code Context; instruction-render.py; lines: 1066-1094]`
     and the completion gate `[ref: SDD/Glossary; Completion gate]`.
  2. Test (red): voice item, keep_source=False → emits delete_source for transcript AND audio peer
     (both behind the gate); keep_source=True → emits NEITHER; no audio_peer → exactly one delete
     (unchanged); gate not yet satisfied → defers both; **multi-atomic: two atomics from one
     transcript with an audio_peer → neither the transcript nor the audio delete fires until BOTH
     atomics are rendered, then both fire**; **degraded fail-safe: audio_peer absent when one was
     expected → never emits an audio delete** `[ref: PRD/AC F3; constitution L1 reject path]`.
  3. Implement (green): after the gate passes for an origin stem, also emit a `delete_source` for
     its `audio_peer` (reason e.g. "Audio peer of consumed origin"); `keep_source_stems` suppress
     both; guard `audio_peer is None`.
  4. Validate: delete-builder suite green incl. keep/delete/no-peer/deferred cases.
  5. Success: no orphaned audio; keep suppresses both; propose-only preserved `[ref: PRD/AC F3, F5]`.

- [ ] **T3.4 Version bumps + docs/tomo counterparts** `[activity: backend]` `[parallel: true]`

  1. Prime: version-gated sync rule.
  2. Test: N/A.
  3. Implement: bump `# version:` on edited managed scripts; update `inbox-analyst.md` doc
     counterpart + `docs/tomo/scripts/instruction-render.md` for the audio-peer behavior.
  4. Validate: versions bumped; counterparts updated.
  5. Success: managed artifacts versioned + documented `[ref: SDD/CON-5]`.

- [x] **T3.5 Phase Validation** `[activity: validate]`

  - Run full suite. Add an end-to-end test: a confirmed voice item (keep_source unchecked) yields
    two `delete_source` actions (transcript + audio) and zero Tomo-side deletes — assert no
    `Path.unlink`/Kado-delete call occurs in the render path, not just output shape. Lint clean.
