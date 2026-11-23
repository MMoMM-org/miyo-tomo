---
title: "/review: every day read, and the previous reviews taken into account"
status: ready
version: "1.2"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All `[NEEDS CLARIFICATION: ...]` markers have been addressed
- [x] All specification file paths are correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)

- [x] Context priming section is complete
- [x] All implementation phases are defined with linked phase files
- [x] Dependencies between phases are clear (no circular dependencies)
- [x] Parallel work is properly tagged with `[parallel: true]`
- [x] Activity hints provided for specialist selection `[activity: type]`
- [x] Every phase references relevant SDD sections
- [x] Every test references PRD acceptance criteria
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup

---

## Output Schema

### PLAN Status Report

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| specId | string | Yes | Spec identifier (NNN-name format) |
| title | string | Yes | Feature title |
| status | enum: `DRAFT`, `IN_REVIEW`, `COMPLETE` | Yes | Document readiness |
| phases | PhaseStatus[] | Yes | Status of each implementation phase |
| totalTasks | number | Yes | Total tasks across all phases |
| parallelTasks | number | Yes | Tasks marked `[parallel: true]` |
| specReferences | number | Yes | Count of `[ref: ...]` specification links |
| clarificationsRemaining | number | Yes | Count of `[NEEDS CLARIFICATION]` markers |

### PhaseStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| phase | number | Yes | Phase number |
| name | string | Yes | Phase name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| tasks | number | Yes | Task count in this phase |
| file | string | Yes | Path to phase file (phase-N.md) |
| detail | string | No | What needs clarification or what's in progress |

Current report: specId `047-review-chunked-read`, status IN_REVIEW (ready for `/implement`), 9 phases, 44 tasks, 11 marked `[parallel: true]`, clarificationsRemaining 0.

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Complete the Pre-Implementation Specification Gate
2. **During Implementation**: Reference specific SDD sections in each task
3. **After Each Task**: Run Specification Compliance checks
4. **Phase Completion**: Verify all specification requirements are met

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with clear rationale
2. Obtain approval before proceeding
3. Update SDD when the deviation improves the design
4. Record all deviations in this plan for traceability

## Metadata Reference

- `[parallel: true]` - Tasks that can run concurrently
- `[component: component-name]` - For multi-component features
- `[ref: document/section; lines: 1, 2-3]` - Links to specifications, patterns, or interfaces and (if applicable) line(s)
- `[activity: type]` - Activity hint for specialist agent selection
- `[model: routine|hard|frontier]` - Overrides the spec's model tier for this task

### Success Criteria

**Validate** = Process verification ("did we follow TDD?")
**Success** = Outcome verification ("does it work correctly?")

```markdown
# Single-line format
- Success: [Criterion] `[ref: PRD/AC-X.Y]`

# Multi-line format
- Success:
  - [ ] [Criterion 1] `[ref: PRD/AC-X.Y]`
  - [ ] [Criterion 2] `[ref: SDD/Section]`
```

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/047-review-chunked-read/requirements.md` — PRD v1.1 (56 criteria F1-AC1 … F8-AC2; amendments to specs 045/046; Notes for the SDD)
- `docs/XDD/specs/047-review-chunked-read/solution.md` — SDD v1.2 (12 confirmed ADRs, ADR-1/2/4/6/10 amended 2026-11-23; line numbers below are v1.1's and run 2–35 lines low in v1.2 (more toward the end) — the section names govern; Building Block View with the responsibility matrix, lines 374-427; Directory Map 429-505; interfaces 535-677; examples 697-870; walkthroughs (a)–(d) 966-1049; gotchas 1298-1309). Large: read in parts with offset/limit.
- `docs/XDD/specs/047-review-chunked-read/README.md` — Decisions Log (tier Incremental, model tier hard, labels, deletion at write, continue on the stored read)
- `docs/XDD/specs/047-review-chunked-read/research.md` — measured sizes, ~1.85 chars/token, consumer list C1–C10
- `docs/XDD/specs/046-review-template-sections/solution.md` and `close-out.md`; `docs/XDD/specs/045-weekly-monthly-review/solution.md` — the base designs
- `docs/tomo/dot_claude/skills/periodic-review.md` — the skill's WHY layer
- `evals/README.md` — the eval gate (no gated file is changed by this plan)

**Key Design Decisions**:

- **ADR-1 / ADR-3**: `review-read.py` writes a stage (`days/`, `growth/` per creation day, `children/`, `previous/`, `context*.json`, `weeks.json`, `manifest.json` last, a `read_id` on every file) through `lib/review_stage.py`; `review_stage.load` returns today's merged dict so `review-doc.py`'s consumers stay untouched; a stored read is continued without Kado unless `--fresh`, the mapping changed or the manifest is invalid. `lib/review_read_parts.py` is deleted. `context.json` holds growth counts and MOC lists only; the read `report` lives only in `manifest.json` and is never proposer input.
- **ADR-2**: every agent-read file ≤ 32,768 bytes (was 40,960; owner after T1.4) in its line-broken (`indent=1`, text as line arrays, UTF-8) form; a unit ≤ 131,072 bytes of day files plus growth files (was 81,920; owner after T2.5); digest cap `min(8192, 114688 // units)`; carryover cap 12,288; one cutter `review_day.cut_at_boundary`.
- **ADR-4 / ADR-8**: `review-digest.py plan | check` drives one batch (rounds of ≤ `MAX_PARALLEL` 16) of haiku digesters and the sonnet carryover, one retry, then the opus proposer; each digest carries its unit's growth candidates (source = creation day); "not condensed" is named, never a partial read. The skill dispatches every agent from the main session with STRICT rules (one message, `subagent_type`, `run_in_background: false`, no stage reads in the main session).
- **ADR-5 / ADR-6 / ADR-12**: previous notes through the same `PacedReader`, five states; proposals gain `carried` + `carried_ids`, checked in `lib/review_carried.py` (failures always in `errors`), a full section resolved by `overflow`; labels and top lines in `_LABELS`.
- **ADR-9 / ADR-10 / ADR-11**: Pass 2 and wire v4 unchanged; `review_stage.discard` at write, Pass 1 abort, new read; a behaviour baseline e2e (week, month, quarter fingerprints) is written and GREEN on the old flow before any production change.

**Implementation Context**:

```bash
# Testing
./venv/bin/python -m pytest tests/ -q                                   # full suite, ONE invocation, GREEN at every phase validation
./venv/bin/python -m pytest tests/test_review_*.py tests/test_047_*.py tests/test_period.py -q
./venv/bin/python -m pytest tests/test_035_wire_gate.py tests/test_035_wire_manifests.py -q   # wire v4 unchanged

# Quality
./venv/bin/ruff check tomo/scripts scripts tests

# Owner go only (never unannounced)
python3 tomo/scripts/review-read.py --kind quarter --period 2026-Q1 --stem <stem> --measure   # test instance config, no model
scripts/update-tomo.sh --instance tomo-instance --yolo                                      # sync before a live walk
scripts/run-evals.sh --case <review case>                                                   # paid; not a gate for these files
python3 scripts/tomo-session-stats.py --session <jsonl>                                     # cost, time, peak per step
```

Standing rules for every task:
- WHY goes to `docs/tomo/<mirrored-path>.md` first, the runtime prose or code second; `tomo/dot_claude/**` holds imperatives only; runtime skill edits through `tcs-helper:skill-author`, agent files through `tcs-helper:agent-author`.
- Bump `# version:` on every managed file edited (number only).
- Commit after every task on `feature/270-redesign-the-quarterly-read-chunked-data`; stage explicit paths only; never `git stash/reset/restore/clean/checkout`; never a `CLAUDE_ALLOW_*` override.
- No eval-gated file changes (CON-6): `settings.json`, `synthesis-conductor.md`, `suggestion-conductor.md`, `suggest-handling/SKILL.md`, `commands/inbox.md` stay byte-identical. If one must change, stop and bring it to the owner (full-suite eval run before merge).
- RED proofs by reverting the fix (or applying the mutation the test docstring names); coverage greps are never truncated.
- `tomo-privat` is LIVE: never synced, never read, never written. Live runs only with `--instance tomo-instance` on the test vault, only on the owner's go; nothing edits the test vault directly; its deliberate daily gap stays broken; no journal text is quoted in any record.
- Perf, cost and paid runs only on the owner's go; restart the container session after any agent or skill sync.
- New modules ≤ 300 lines of dense logic; the near-limit files of CON-5 get call sites and small extensions only.
- Every task that edits a versioned file bumps its `# version:` again, even when an earlier task of this spec already bumped it; the target versions in the SDD Directory Map are the end state, not one bump.
- A task that creates a new `tests/test_review_*.py` file (or another review file the SDD map does not name yet) adds it to spec 047's `solution.md` Directory Map in the same commit, so `tests/test_review_sdd_map.py` stays green (owner 2026-11-23). The plan itself does not edit `solution.md`.
- Code review: the per-task review chain of `/implement` (spec-compliance review, then code-quality review, for every task) is the code review of this plan; no extra phase-level review task is added. Phase validations stay: full pytest in ONE invocation, ruff, and the phase's criteria traced to node ids (owner 2026-11-23).

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: Behaviour baseline and early smoke checks](phase-1.md)
- [x] [Phase 2: Stage layout, limits and the loader](phase-2.md)
- [ ] [Phase 3: Previous notes](phase-3.md)
- [ ] [Phase 4: Condensing — units, digests, carryover, plan and check](phase-4.md)
- [ ] [Phase 5: Carried items, their checks and the top lines](phase-5.md)
- [ ] [Phase 6: Agents, skill dispatch and STRICT rules](phase-6.md)
- [ ] [Phase 7: Privacy, deletion, measurement and documentation](phase-7.md)
- [ ] [Phase 8: Baseline e2e on the new flow](phase-8.md)
- [ ] [Phase 9: Live walk on the test instance and close-out](phase-9.md)

**Phase dependencies:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9, linear, no cycles. Inside phases: T1.1 ∥ T1.2 → T1.3; T1.4 and T1.5 (owner go) run any time in Phase 1, independent of T1.1–T1.3, and their outcomes must be recorded before Phase 2 starts (T1.5 may lower the ADR-2 numbers; T1.4 decides the nested-write fallback used in T4.3). T2.1 ∥ T2.2 → T2.3 → T2.4 (one switch-over commit: read and load side together) → T2.5 (owner go). T3.1 may start once T2.1 is done (it needs `cut_at_boundary`), T3.2 needs T2.4 and T3.1. T4.1 → T4.2 → T4.3 → T4.4. T5.1 ∥ T5.2 ∥ T5.5 → T5.3 (needs T5.2's `resolve_sources`) → T5.4. T6.1 → T6.2 → T6.3 → T6.4 (T6.3 needs T6.2: T6.2 re-creates the step-5 proposal pins in `tests/test_047_agents.py` before T6.3 removes them from the skill tests). T7.1 ∥ T7.2 ∥ T7.3 ∥ T7.4. T8.1 → T8.2. T9.1 → T9.2 → T9.3 → T9.4.

**Between Phase 2 and Phase 6** the runtime skill still describes the old step 5; the test instance is not synced before T9.1, so no live run sees the half-built flow. The baseline e2e (T1.3) stays GREEN through Phases 2–7 because the walk drives the scripts, not the skill.

### Deviation 2026-11-23 (owner, after the T1.5 measurement)

T1.5 measured 2026-Q1: days max 8,303 B, ISO-week sums max 46,747 B (indent=1) — the ADR-2 day, week and digest limits hold. But `growth.created` (746 created notes with their links) was ≈ 157.7 KB indented, 4× the 40,960-byte ceiling, and `report` ≈ 39.5 KB. Decided: (1) vault growth goes per creation day to `growth/<date>.json`, counts in its unit's 81,920-byte budget (a week pushed over splits by the same rule), and reaches the proposer only as the digests' growth candidates, whose sources are the creation days (today's growth group rule, `review_doc.py:274-275`); (2) `context.json` keeps only `created_count`, `mocs_changed`, `mocs_linked_by_new`; (3) the read `report` stays in `manifest.json` only, scripts render from it as before, no agent reads it. SDD v1.2 amends ADR-1, ADR-2, ADR-4, ADR-6, ADR-10. Tasks changed (ids stable): T2.2, T2.3 (adds the `review_period._growth` `day` key), T2.4, T2.5, T4.1, T4.2, T4.3, T4.4, T6.2, T6.4, T7.2, T8.1. No PRD criterion or owning task moves.

Second pass, same day (owner, after T1.4; SDD v1.3): `FILE_CEILING` 32,768 bytes (Read cut a 40,965-byte poorly tokenizing file at its 25k-token cap); a Kado per-path denial is a `FORBIDDEN` `KadoToolError`, caught per previous-note call as `refused`, while `KadoAuthError` still stops the read. Tasks changed: T2.2, T2.3 (ceiling), T3.1, T3.3 (denial), T8.1 (fingerprint `diff()` parent-key form).

### Criteria → task map (one owning task per PRD criterion)

Model-behaviour criteria (marked †) are owned by the task that writes the agent rule and its prompt pin; their evidence is completed by a recorded live-walk row in T9.2 and traced in T9.4.

| Criteria | Owning task | Collaborators |
|---|---|---|
| F1-AC1 | T2.2 | T4.2 (digest `days` = unit days), T6.2 (digester reads all), T9.2 |
| F1-AC2 | T2.2 | T2.3 (same `read_day` entry), T8.1 |
| F1-AC3 † | T6.2 | T5.4 (two-day rule over all days), T9.2 |
| F1-AC4 † | T6.2 | T9.2 |
| F1-AC5 † | T6.2 | T5.4 (`double-placement`), T9.2 |
| F1-AC6 | T2.4 | T4.3 (only period days dispatched) |
| F1-AC7 | T2.1 | T2.3 (32 KB re-cut) |
| F2-AC1 | T8.1 | T1.3 (old-flow fingerprint) |
| F2-AC2 | T8.1 | T1.3 (old-flow instruction sets) |
| F2-AC3 | T2.3 | T6.2 (proposer marks over the whole period) |
| F2-AC4 | T2.4 | — |
| F2-AC5 | T2.4 | T3.2 |
| F2-AC6 | T3.2 | T2.4 |
| F3-AC1 | T3.1 | T3.2 |
| F3-AC2 | T3.1 | T3.2 |
| F3-AC3 | T3.1 | T3.2 |
| F3-AC4 | T3.1 | — |
| F3-AC5 | T3.1 | — |
| F3-AC6 | T5.2 | T6.3 (run report), T9.2 |
| F3-AC7 | T3.1 | — |
| F3-AC8 | T3.1 | T6.3 (no setup question) |
| F3-AC9 | T3.1 | T1.4 (Kado denial shape) |
| F3-AC10 | T3.1 | T5.2 (line "read in part") |
| F3-AC11 | T5.2 | — |
| F4-AC1 † | T6.2 | T5.3 (`coverage`), T9.2 |
| F4-AC2 † | T6.2 | T5.3 (day rule per mark), T9.2 |
| F4-AC3 † | T6.2 | T5.3 (`carried-theme-done`), T9.2 |
| F4-AC4 † | T6.2 | T5.3 (group/mark rule), T9.2 |
| F4-AC5 | T5.4 | T3.1 (off-limits text read as a source) |
| F4-AC6 | T5.3 | — |
| F4-AC7 | T5.3 | — |
| F4-AC8 † | T6.2 | T9.2 |
| F4-AC9 | T3.1 | T8.2 |
| F4-AC10 | T5.3 | T5.4 (`over-cap` after `overflow`) |
| F4-AC11 † | T6.2 | T9.2 |
| F5-AC1 | T5.2 | — |
| F5-AC2 | T5.4 | — |
| F5-AC3 | T5.3 | — |
| F5-AC4 | T5.5 | T8.1 |
| F5-AC5 | T5.5 | T8.1 |
| F5-AC6 | T8.2 | — |
| F6-AC1 | T4.3 | T5.2 (top line), T8.2 |
| F6-AC2 | T4.3 | T5.2 (top line), T8.2 |
| F6-AC3 | T6.3 | T8.2 |
| F6-AC4 | T2.4 | T4.3 (plan dispatches only what is not passed), T6.3 (the line), T8.2, T9.2 |
| F6-AC5 | T2.3 | T2.4, T8.2 |
| F6-AC6 | T6.3 | T2.4 (`replace --abort` discards), T8.2 |
| F6-AC7 | T3.1 | T8.2 |
| F6-AC8 | T4.3 | T6.3 (stop wording), T8.2 |
| F7-AC1 | T2.3 | T2.4, T7.2 |
| F7-AC2 | T7.1 | — |
| F7-AC3 | T7.1 | — |
| F7-AC4 | T7.2 | — |
| F7-AC5 | T6.2 | T7.2 |
| F8-AC1 | T7.3 | T9.2 |
| F8-AC2 | T9.4 | — |

Count: F1 7, F2 6, F3 11, F4 11, F5 6, F6 8, F7 5, F8 2 = 56; each criterion has exactly one owning task.

### SDD component → task map

| Component (SDD Directory Map / Building Block View) | Change | Task(s) |
|---|---|---|
| `tomo/dot_claude/skills/periodic-review/SKILL.md` | MODIFY 0.2.13 → 0.3.0 | T6.3 (a minimal step-4 key rename in T2.4 only if a contract test requires it) |
| `tomo/dot_claude/agents/review-digester.md` | NEW | T6.2 |
| `tomo/dot_claude/agents/review-carryover.md` | NEW | T6.2 |
| `tomo/dot_claude/agents/review-proposer.md` | NEW | T6.2 |
| `tomo/schemas/review-digest.schema.json` | NEW | T4.1 |
| `tomo/schemas/review-carryover.schema.json` | NEW | T4.1 |
| `tomo/schemas/review-proposals.schema.json` | MODIFY | T5.1 |
| `tomo/config/vault-example.yaml` | MODIFY (comment) | T7.1 |
| `tomo/scripts/review-read.py` | MODIFY → 0.4.0 | T2.4, T3.2 |
| `tomo/scripts/review-digest.py` | NEW | T4.3 |
| `tomo/scripts/review-doc.py` | MODIFY → 0.8.0 | T2.4, T4.4, T5.4 |
| `tomo/scripts/lib/review_stage.py` | NEW | T2.3, T4.4 (`condensed`/`carryover` in `load`) |
| `tomo/scripts/lib/review_weeks.py` | NEW | T2.2 |
| `tomo/scripts/lib/review_previous.py` | NEW | T3.1 |
| `tomo/scripts/lib/review_digest.py` | NEW | T4.2 |
| `tomo/scripts/lib/review_carried.py` | NEW | T5.3 |
| `tomo/scripts/lib/review_read_parts.py` | DELETE | T2.4 |
| `tomo/scripts/lib/review_period.py` | MODIFY → 0.6.0 | T2.3 (`growth.created` entries keep `day`), T3.2 |
| `tomo/scripts/lib/review_doc.py` | MODIFY → 0.6.0 | T4.4 (`Sources` leaves out failed units), T5.2, T5.4 |
| `tomo/scripts/lib/review_sections.py` | MODIFY → 0.3.0 | T5.4 |
| `tomo/scripts/lib/review_day.py` | MODIFY → 0.3.3 | T2.1 |
| `lib/review_children.py`, `lib/review_habits.py`, `lib/review_doc_parse.py` (code unchanged) | entries to `children/`; habits over loader days; parse regression | T2.3, T2.4, T5.5 |
| `lib/review_mapping.py`, `lib/review_section_plan.py`, `review-session.py`, `review-instructions.py` (unchanged, boundary) | regression only | T5.4, T8.1, T8.2 |
| `lib/run_id.py`, `lib/review_md.py`, `lib/review_reader.py` (reused) | — | T2.3, T3.1 |
| `docs/tomo/...` mirrors for every new/changed script, lib, agent and the skill | NEW / MODIFY / DELETE | in the task that changes the file (first step), swept in T7.4 |
| `PRIVACY.md`, `docs/setup.md`, `README.md`, `docs/usage.md`, `docs/XDD/backlog.md` | MODIFY | T7.1 |
| `scripts/tomo-session-stats.py` (F8-AC1 owner; not in the file table) | verify, extend only where a field is missing | T7.3 |
| `tests/review_doc_fingerprint.py` | NEW | T1.1 |
| `tests/test_047_baseline_e2e.py` | NEW, first | T1.3, T8.1, T8.2 |
| `tests/review_privacy_fixture.py` | MODIFY | T1.2, T4.4 |
| `tests/review_e2e_walk.py` | MODIFY | T1.2, T4.4, T8.1 |
| `tests/test_review_stage.py` (replaces `test_review_read_parts.py`, DELETE) | NEW | T2.3, T2.4 |
| `tests/test_review_weeks.py` | NEW | T2.2 |
| `tests/test_review_previous.py` | NEW | T3.1 |
| `tests/test_review_digest.py` | NEW | T4.2, T4.3 |
| `tests/test_review_carried.py` | NEW | T5.3 |
| `tests/test_047_skill_contract.py` | NEW | T6.3 |
| `tests/test_047_agents.py` | NEW | T6.2 |
| tests changed by design (`test_review_read.py`, `test_046_t4_5_*`, `test_046_t4_4_skill_sections.py`, `test_review_skill*.py`, `test_review_doc.py`, `test_review_doc_parse.py`, `test_review_privacy.py`, `test_review_privacy_docs.py`, `test_review_e2e*.py`, `test_review_period_golden.py`, `test_046_close_out_gaps.py`, `test_045_close_out_gaps.py`, `test_review_integration.py`) | MODIFY | T2.4, T3.2, T5.2, T5.5, T6.3, T7.1, T7.2 |
| `tests/test_review_sdd_map.py` | MODIFY (reads spec 047's map) | T1.1, T7.4 |
| `tests/test_review_doc_fingerprint.py`, `tests/test_review_digest_schemas.py`, `tests/test_review_proposals_carried_schema.py` (new, not yet in the SDD map) | NEW; added to spec 047's Directory Map by the creating task | T1.1, T4.1, T5.1 |
| `docs/XDD/specs/047-review-chunked-read/solution.md` Directory Map (Tests block) | MODIFY by the creating task | T1.1, T2.4, T4.1, T5.1 |
| `tests/test_review_why_docs.py` | MODIFY | T7.4 |
| plugin eval case `review-no-stage-read` (Quality Requirements) | NEW | T6.4 |

### ADR → task map

| ADR | Tasks |
|---|---|
| ADR-1 Stage layout and the loader | T2.3, T2.4 (amended: `growth/`, report in manifest only) |
| ADR-2 Size limits | T1.4 (Read smoke → 32 KB ceiling), T1.5, T2.1, T2.2, T2.3, T2.5 (amended: budget includes growth) |
| ADR-3 Read id, manifest, continuing | T2.3, T2.4 |
| ADR-4 Digest/carryover contracts, `review-digest.py` | T4.1, T4.2, T4.3, T4.4, T6.2 (amended: growth candidates) |
| ADR-5 Previous notes | T1.4 (Kado denial shape: `FORBIDDEN` tool error), T3.1, T3.2 |
| ADR-6 Carried field, checks, labels | T5.1, T5.2, T5.3, T5.4, T6.2 (amended: growth group input) |
| ADR-7 Three agents | T1.4 (nested write smoke), T6.1, T6.2 |
| ADR-8 Dispatch, rounds, STRICT | T4.3 (rounds), T6.3, T6.4, T9.2 |
| ADR-9 Pass 2 and wire unchanged | T5.5, T8.1, T8.2 |
| ADR-10 Privacy and deletion | T2.3, T2.4, T7.1, T7.2 (amended: `growth/`) |
| ADR-11 Behaviour baseline first | T1.1, T1.2, T1.3, T8.1 |
| ADR-12 Top lines | T5.2 |

---

## Plan Verification

Before this plan is ready for implementation, verify:

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ✅ |
| Every task produces a verifiable deliverable | ✅ |
| All PRD acceptance criteria map to specific tasks | ✅ |
| All SDD components have implementation tasks | ✅ |
| Dependencies are explicit with no circular references | ✅ |
| Parallel opportunities are marked with `[parallel: true]` | ✅ |
| Each task has specification references `[ref: ...]` | ✅ |
| Project commands in Context Priming are accurate | ✅ |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | ✅ |
