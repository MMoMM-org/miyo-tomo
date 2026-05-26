---
title: "Phase 4: Drift Recovery + Transcription Stop-Gate (F-47.P3)"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: Drift Recovery + Transcription Stop-Gate (F-47.P3)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/§3 Non-Linear Scenarios N3, N4; lines: 119-130]` — drift and transcription mid-flow
- `[ref: PRD/§6.4 Drift Recovery diagram; lines: 593-628]`
- `[ref: PRD/Feature 5a; AC-5a.1..AC-5a.4]` — drift detection + --recover
- `[ref: PRD/Feature 5b; AC-5b.1..AC-5b.4]` — media transcription stop-gate
- `[ref: PRD/§3 N2 + AC of Feature 4 contract framing]` — parallel-instructions warning
- `[ref: SDD/Complex Logic step 1 + step 4; lines: 841-865]` — transcription pre-check + drift detection algorithm
- `[ref: SDD/CLI command changes; lines: 484-496]` — `/inbox --recover` + media stop-gate

**Key Decisions**:
- **Drift = hint, not action** (PRD §3 N3): `/inbox` surfaces the drift state; user invokes `--recover` to act on it. Silent re-Pass-1 risks duplicates if the drift signal is actually a steady-state residual.
- **Transcription = two-run gate** (PRD AC-5b.1): media → transcribe → exit. The new transcript is NOT picked up by the same `/inbox` run. User edits between transcribe and capture.
- **`--recover` semantics**: treat docs with `tomo.state=captured` as fresh sources for Pass-1 dispatch. `mark-captured.py` re-asserts the tag idempotently (no-op write per Phase 1 schema + Phase 2 wrapper).
- **Parallel-instructions warning** (PRD §3 N2): emitted when `pendingApply.count + transitions_applied > 1` — explicit text listing all paths so user can grep them in Obsidian.

**Dependencies**:
- **Hard**: Phase 3 (orchestrator A2.5 + inbox-discovery.py + state-promoter.py) must be merged. The drift flag and `--recover` mode hook into A2.5d/A2.5c paths from T3.1/T3.3.
- T4.1 (–recover flag) blocks T4.2 (drift hint references the flag).
- T4.3 (transcription stop-gate) is independent of drift work; can run in parallel with T4.1+T4.2.

---

## Tasks

This phase makes `/inbox` resilient to two off-happy-path scenarios: (a) user deletes a workflow doc mid-flow leaving stranded captured sources (drift), (b) user drops audio files and needs a two-run gate to review the transcript before processing. Both behaviours flow through the existing Phase A2.5 wiring from Phase 3 — Phase 4 fills in the UX text + control flow.

- [x] **T4.1 `inbox.md` — `--recover` flag** `[activity: agent-prompt-update]`

  1. Prime: Read `tomo/dot_claude/commands/inbox.md` entry-point and confirm how it currently dispatches `inbox-orchestrator`. Read PRD AC-5a.2 (recover treats captured as fresh) `[ref: PRD/Feature 5a]`. Read SDD Complex Logic step 4 (drift block when `--recover` set, override `newSources = capturedHits.paths`) `[ref: SDD/Complex Logic; lines: 859-865]`.
  2. Test: N/A (command file). Manual smoke: invoke `/inbox --recover` against a drift inbox (3 captured, 0 pending) — orchestrator overrides newSources with captured paths and runs Pass-1 against them; resulting `<ts>_suggestions.md` produced; captured tags re-asserted idempotently.
  3. Implement: In `tomo/dot_claude/commands/inbox.md`, document the `--recover` flag (purpose: drift-recovery; behaviour: treat captured as fresh sources; no-op if no captured docs exist). Pass `--recover` through to `inbox-orchestrator.md` as an env var (`TOMO_INBOX_RECOVER=1`) or argv. Update `inbox-orchestrator.md` Phase A2.5c bucket logic: if `TOMO_INBOX_RECOVER` is set, replace `newSources` with `capturedHits.paths` before drift-check + Phase B branching. Bump `# version:` on both files.
  4. Validate: Run `./scripts/update-tomo.sh`; restart Claude; smoke test per step 2. Verify `mark-captured` second-write against an already-captured doc is a no-op via merge-mode (write payload identical, no state change, no exception, `lifecycle.transition` event still logged as idempotent).
  5. Success: `/inbox --recover` reroutes captured docs into Pass-1; `tomo.state=captured` stays valid across re-assert `[ref: PRD/AC-5a.2, AC-5a.3, AC-5a.4]` `[ref: SDD/CLI command changes; lines: 485-489]`.

- [x] **T4.2 Drift hint surfacing + UX text** `[activity: agent-prompt-update]` `[parallel: true]`

  1. Prime: Read PRD AC-5a.1 exact hint text wording (`"⚠ N captured notes have no associated workflow doc..."`) `[ref: PRD/Feature 5a; AC-5a.1]`. Read PRD §6.4 drift recovery diagram for the surfaced-hint scenario. Read PRD §10 "Design note" — drift is a hint, not an action.
  2. Test: N/A (agent prompt text). Manual smoke: arrange a drift inbox (3 captured, 0 pending), invoke `/inbox` WITHOUT `--recover`. Expected: discovery JSON has `drift=true`; orchestrator prints the verbatim hint with `N=3` and the `--recover` command line on a single line; exits without dispatching Pass-1 against captured docs; captured docs untouched.
  3. Implement: In `inbox-orchestrator.md` Phase A2.5d, when `discovery.drift == true` and `TOMO_INBOX_RECOVER` is NOT set, emit the verbatim PRD-locked hint text (include the count and the exact `--recover` command line — user must not need to remember the flag, per SDD §Quality Requirements/Usability). Suppress the hint when `--recover` IS set (it's already being acted on). Document the wording-lock as a STRICT comment so future LLM edits don't paraphrase.
  4. Validate: Manual smoke per step 2; grep `inbox-orchestrator.md` for the verbatim PRD hint string — confirm exact match; `./scripts/update-tomo.sh`; restart Claude.
  5. Success: Drift surfaces as one-line hint with verbatim count + flag command `[ref: PRD/AC-5a.1]` `[ref: SDD/Quality Requirements/Usability]`. No auto-recovery when `--recover` absent `[ref: PRD/AC-5a.4]`.

- [x] **T4.3 Transcription stop-gate (voice-transcriber.md + orchestrator A2.5a)** `[activity: agent-prompt-update]`

  1. Prime: Read `tomo/dot_claude/agents/voice-transcriber.md` — current behaviour around transcript output. Read PRD AC-5b.1..AC-5b.4 + §3 N4 for the locked two-run-gate contract `[ref: PRD/Feature 5b]`. Read SDD Runtime View step 3 transcription pre-check `[ref: SDD/Runtime View/Primary Flow; lines: 767-768]`. Confirm voice-transcriber currently produces `<stem>.md` files in the inbox folder.
  2. Test: N/A (agent prompts + orchestrator). Manual smoke matrix: (a) inbox contains one `.mp3` + zero `.md` → `/inbox` runs transcription, produces `<stem>.md` WITHOUT `tomo:` block, exits with stop-gate message; (b) inbox contains one `.mp3` + one manual `.md` → transcription runs for the `.mp3`, Pass-1 runs for the manual `.md`, the new transcript is NOT picked up in the same run (deferred); (c) re-run after (a) → transcript flows through Pass-1 normally, gets `tomo.state=captured`; (d) zero media files → A2.5a is a no-op, normal discovery continues.
  3. Implement:
     - In `inbox-orchestrator.md` Phase A2.5a, add: enumerate `.mp3 .m4a .wav .ogg .flac` files in inbox via `listDir`. If any present, dispatch voice-transcriber per file (sequential or per existing voice flow). After transcription completes, **stop** with the verbatim PRD message `"N transcript(s) created. Review/edit them, then re-run /inbox to process."` — exit Phase A here. Manual `.md` notes from the same run go through Pass-1 only if they pre-existed (per AC-5b.4) — implementation detail: in (b), Pass-1 runs against `newSources = listDir.allMd − newlyTranscribedStems`. The newly produced transcripts are added to a per-run skip-list and excluded from this run's newSources bucket.
     - In `voice-transcriber.md`, STRICT-confirm it writes the transcript `.md` to the inbox **WITHOUT** a `tomo:` block (transcripts must look like fresh sources on the next run — AC-5b.2).
     - Bump `# version:` on both.
  4. Validate: Run `./scripts/update-tomo.sh`; restart Claude; smoke tests (a)-(d) above. Verify the transcript `.md` has zero `tomo` keys in its frontmatter immediately after transcription. Verify the second `/inbox` run captures it as `tomo.state=captured`.
  5. Success: Two-run gate behaves per AC-5b.1..AC-5b.4 `[ref: PRD/Feature 5b]` `[ref: PRD/§6.1/§3 N4]`.

- [x] **T4.4 Parallel-instructions warning text** `[activity: agent-prompt-update]` `[parallel: true]`

  1. Prime: Read PRD §3 N2 for the locked warning text. Read SDD Complex Logic step 6 (parallel-instructions warning) `[ref: SDD/Complex Logic; lines: 877-880]`. Read PRD §6.3 final summary message for verbatim format. Read SDD Quality Requirements/Usability — must list ALL pending-apply paths.
  2. Test: N/A (orchestrator output). Manual smoke: prepare inbox with 1 pre-existing `pending-apply` instructions doc + 1 fresh source. Run `/inbox`. Expected stderr summary includes the warning `"⚠ You now have N instructions docs pending Hashi-apply (<paths>)..."` listing both the pre-existing path and the path of any newly-produced instructions doc (if any). Verify path-list is fully enumerated, not truncated.
  3. Implement: In `inbox-orchestrator.md` Phase A summary step (end-of-run), compute `total_pending_apply = pendingApply.count + newly_produced_instructions.count`. If `total_pending_apply > 1`, emit warning text with full path list (one path per line). Tie the wording verbatim to PRD §6.3 final summary block.
  4. Validate: Smoke per step 2; grep prompt for the verbatim text; `./scripts/update-tomo.sh`; restart Claude.
  5. Success: User sees all pending-apply paths in the summary so they can grep them in Obsidian `[ref: SDD/Quality Requirements/Usability; lines: 1112-1113]` `[ref: PRD/§3 N2]`.

- [x] **T4.5 Phase 4 Validation** `[activity: validate]`

  Run full `pytest tests/ -v` — expect no test changes in this phase (work is in agent prompts + orchestrator prose). Run `ruff check tomo/scripts/`. Manual smoke matrix:
  1. Drift inbox (3 captured, 0 pending), no `--recover`: hint emitted verbatim with count=3 + recover command; no Pass-1 dispatched against captured.
  2. Same inbox with `--recover`: captured docs → Pass-1 → suggestions doc produced; captured tags idempotently re-asserted.
  3. One `.mp3` only: transcription produces `<stem>.md` without `tomo:` block; stop-gate message; exit.
  4. One `.mp3` + one manual `.md`: transcription for mp3, Pass-1 for the manual md only (transcript deferred to next run).
  5. Re-run after (3) or (4): transcript flows through Pass-1 normally with `tomo.state=captured` at end.
  6. Pre-existing pending-apply + fresh source → end-of-run warning lists both pending-apply paths.

  Document any deviation from PRD wording (verbatim mismatch with hint or warning text) — wording is **locked** per PRD §6.3 + AC-5a.1.
