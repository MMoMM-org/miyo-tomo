---
title: "Phase 4: Orchestrator integration (Phase 0 in inbox-orchestrator)"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Orchestrator integration

## Phase Context

**Dependencies**: Phase 1 (image + wizard), Phase 3 (agent works standalone).

**Key files**:
- `tomo/dot_claude/agents/inbox-orchestrator.md` (modify — add Phase 0 step)

**Out of scope this phase**: behaviour changes to Phase A/B/C of the
existing fan-out pipeline. We only insert a new pre-step.

---

## Tasks

- [ ] **T4.1 Insert Phase 0 in inbox-orchestrator workflow** `[activity: agent-design]`

  1. Prime: Read current `inbox-orchestrator.md` end-to-end. Locate the
     "Phase A" heading and document structure. Note version field at top.
  2. Implement: Add a new "Phase 0 (conditional): Voice Transcription" section
     BEFORE Phase A. Content:
     - Read `tomo-install.json`. Check `voice.enabled`. If `false` or
       missing → skip Phase 0 entirely, log "voice disabled, skipping".
     - If `true`: invoke `voice-transcriber` agent via `Agent` tool with
       subagent_type `voice-transcriber`, passing the inbox path.
     - Wait for completion. Parse the JSON summary returned.
     - Log summary to scratch (`tomo-tmp/run-<id>/voice-summary.json`).
     - Continue to Phase A — newly written `.md` files are now visible to
       discovery.
     - On agent error: log warning, continue to Phase A anyway (voice
       failures must not block text inbox processing).
  3. Validate: Phase A discovery still uses the same kado-search; no
     changes needed there. The new transcript files appear naturally
     because they're in the same inbox dir.

- [ ] **T4.2 Bump orchestrator version + update changelog comment** `[activity: agent-design]`

  1. Prime: Existing version comment format: `# version: 0.6.0 (Phase D merged...)`.
  2. Implement: Bump to `0.7.0` with comment `(Phase 0 voice transcription added)`.
  3. Validate: Version comment present, increment is correct.

- [ ] **T4.3 Update orchestrator constraints if needed** `[activity: agent-design]`

  1. Prime: Re-read existing "Constraints (strict)" block — does Phase 0
     introduce any new failure mode the orchestrator should explicitly guard?
  2. Implement: Add (if applicable) a constraint: "NEVER attempt voice
     transcription yourself — always delegate to the `voice-transcriber`
     agent. If voice is disabled, simply skip Phase 0; do not warn or prompt."
  3. Validate: Constraints stay actionable, not aspirational.

- [ ] **T4.4 Sync to instance and restart** `[activity: tooling]`

  1. Prime: Same as Phase 3 T3.5 — instance has its own copy.
  2. Implement: Run `bash scripts/update-tomo.sh` to copy the updated
     orchestrator into the instance. Restart Claude in the instance.
  3. Validate: Updated agent picked up — version comment 0.7.0 visible in
     the instance copy.

- [ ] **T4.5 Integration test: voice ON path** `[activity: validate]`

  Pre-condition: voice enabled, tiny model installed, test vault inbox has
  one audio file (no `.md` sibling) AND one regular `.md` fleeting note.

  - Run `/inbox` in the instance.
  - Verify:
    - Phase 0 logs "voice enabled, invoking voice-transcriber".
    - Voice-transcriber summary shows `{transcribed: 1, skipped: 0, errors: []}`.
    - Sibling transcript `.md` is created.
    - Phase A discovery picks up BOTH the original `.md` and the new transcript.
    - Pass 1 fan-out analyzes both; Suggestions doc lists both items.

- [ ] **T4.6 Integration test: voice OFF path** `[activity: validate]`

  Pre-condition: voice disabled in `tomo-install.json`. Test vault inbox has
  one audio file and one regular `.md`.

  - Run `/inbox`.
  - Verify:
    - Phase 0 logs "voice disabled, skipping".
    - voice-transcriber agent is NOT invoked.
    - No transcript created.
    - Phase A discovery picks up only the regular `.md`.
    - Pass 1 fan-out analyzes only the regular note.
    - Audio file is left untouched.

- [ ] **T4.7 Integration test: voice error path** `[activity: validate]`

  Pre-condition: voice enabled, but model dir intentionally renamed to
  simulate missing model. Test vault inbox has one audio file.

  - Run `/inbox`.
  - Verify:
    - voice-transcriber returns error summary; orchestrator logs warning.
    - Phase A still runs; pipeline doesn't abort.
    - User sees clear error in the run summary, not a silent failure.
  - Restore model dir. Re-run. Verify recovery (transcribe succeeds).

- [ ] **T4.8 Phase Validation** `[activity: validate]`

  - All three integration tests (ON / OFF / error) pass.
  - Pure-text inbox (no audio at all) measures within ±5% of pre-spec
    `/inbox` baseline runtime — no measurable overhead.
  - Run summary clearly shows whether voice ran and what happened.
