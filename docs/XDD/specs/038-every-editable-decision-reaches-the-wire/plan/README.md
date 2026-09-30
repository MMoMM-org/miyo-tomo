---
title: "Every editable decision reaches the wire"
status: draft
version: "1.0"
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

| Field | Value |
|-------|-------|
| specId | 038-every-editable-decision-reaches-the-wire |
| title | Every editable decision reaches the wire |
| status | `IN_REVIEW` |
| totalTasks | 23 |
| parallelTasks | 3 |
| specReferences | 125 |
| clarificationsRemaining | 0 |

### PhaseStatus

| Phase | Name | Status | Tasks | File |
|-------|------|--------|-------|------|
| 1 | The inventory, and what it reveals | `in_progress` | 4 | `phase-1.md` |
| 2 | The wire carries the decision | `pending` | 5 | `phase-2.md` |
| 3 | Refusal, before anything can be typed | `pending` | 5 | `phase-3.md` |
| 4 | The name becomes a value | `pending` | 4 | `phase-4.md` |
| 5 | Integration, the live path, and one handoff | `pending` | 5 | `phase-5.md` |

---

## Specification Compliance Guidelines

1. **Before each phase**: read the phase file's GATE section in full. Every phase
   references the SDD sections it depends on.
2. **During implementation**: cite the `[ref: ...]` in the code's docstring where
   a decision is non-obvious, and write the WHY into `docs/tomo/<mirrored-path>.md`
   as you go — not at the end.
3. **After each task**: the two-stage review chain (spec compliance, then code
   quality) runs per task, not per phase.
4. **Phase completion**: every PRD criterion the phase claims must map to a test
   that was **executed**, named by node id. "A test exists" is a weaker guarantee
   than usual on this spec — see the note on unbiteable mutations below.

### Deviation Protocol

1. Document the deviation with rationale in the phase file.
2. Obtain approval before proceeding.
3. Update the SDD when the deviation improves the design.
4. Record every deviation here for traceability.

#### Recorded deviations

| Date | Task | Deviation | Rationale |
|------|------|-----------|-----------|
| 2026-09-30 | T1.1 | T1.1 gains a test of its own: the inventory's JSON Schema is written first, then `tests/test_038_inventory_schema_validation.py`, before the inventory is authored. The task previously declared "Test: none yet". | The TDD guardian blocked the task on an internal contradiction: T1.1 claimed no test while carrying "a malformed row fails Tomo's tests" as a success criterion, which `[ref: PRD/F4]` requires. T1.2's join test proves *completeness*, never *row validity*, so as originally sequenced that PRD criterion was owned by no test in the plan. The guardian's distinction is the one that resolves it — a test for "what makes a row valid" is available immediately, a test for "which rows exist" is not. Approved by the owner 2026-09-30. |
| 2026-09-30 | — | The schema's `Editable` field count corrected from 23 to 21 in this file, `solution.md` ADR-7, and twice in `phase-1.md`. | Measured, not recalled: a walk over every schema description containing `Editable` returns 21, and returns 21 at `main`, so the schema had not drifted — the figure was wrong when written. Corrected before T1.1 was dispatched so no implementer is primed to count until it reaches a number that does not exist. Commit `de8da00`. |
| 2026-09-30 | T1.1b (new) | A task is added to Phase 1, between T1.1 and T1.2: mark `candidate_mocs[].selected` and `.anchor` `Editable` in the wire schema, add a `parser_label` key to the inventory, make the D22/D23/D24 notes self-contained, and correct the plan's two control counts. Phase 1 goes from 3 tasks to 4; the spec from 22 to 23. | Two owner rulings on T1.1's findings, both 2026-09-30. **First:** `build_from_wire` honours `selected` (it skips unselected entries) and `anchor`, yet neither description carries the `Editable` marker — so ADR-7's schema-side join is permanently blind to two fields the wire acts on, which is the exact blind spot this spec exists to close. **Second:** the parser-side join needs a key, and neither available field can serve — `wire_field` is `null` on D24, and `markdown_control` is prose whose provenance was deliberately stripped as consumer-facing. Without `parser_label` the mapping would live as a hand-written dict in the test, which is "a rule someone has to remember" — the mechanism ADR-7 names as what failed in 037. Both must land before T1.2 writes its join, and they share two files, so they ship as one task rather than three review cycles. |

### A standing warning carried forward from spec 037

Spec 037 produced **nine** instances of a named mutation that could not bite — a
test asserting something already true, or a claim about which test catches which
fault that nobody had run. Three of those survived two reviews and propagated into
plan text, docstrings and WHY docs.

So on this spec: **a claim about which test catches which fault is a measurable
claim.** Run the mutation before writing it down, and re-run any such claim a
reviewer or implementer reports. This is cheap and it is the single highest-yield
check available here.

## Metadata Reference

- `[parallel: true]` — tasks that can run concurrently
- `[ref: document/section; lines: N-M]` — links to specifications
- `[activity: type]` — activity hint for specialist selection

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/038-every-editable-decision-reaches-the-wire/requirements.md` — the PRD, 38 acceptance criteria across F1–F4, S1, C1–C2
- `docs/XDD/specs/038-every-editable-decision-reaches-the-wire/solution.md` — the SDD, 8 confirmed ADRs, 13 components
- `docs/XDD/specs/038-every-editable-decision-reaches-the-wire/README.md` — the decisions log; nine owner rulings, none to be re-derived
- `docs/XDD/backlog.md` — the originating entry, and the 2026-09-30 embed finding this spec must not contradict

**Key Design Decisions**:

- **ADR-1** — 037's ADR-5 is superseded. The suggestions wire moves `2` → `3`, and the move is a functioning gate, not bookkeeping: a mismatch makes Pass 2 fall back to the markdown **silently**.
- **ADR-2** — The conflict is a **top-level** `attachment_conflicts[]` array. Nesting it per suggestion reopens the multi-owner divergence 037 closed.
- **ADR-4** — The markdown keeps its inline shape; the parser trusts the backtick text unconditionally. An untouched document is byte-identical.
- **ADR-5** — A typed name is **rejected**, never sanitised. `sanitize_stem` is not reused on this path, and the check is its own module so one rule serves both read paths.
- **ADR-6** — A refused name **holds** the owning note, unlike `keep_in_inbox`. The owner asked to rename and we refused; that is `collision`-shaped, not choice-shaped.
- **ADR-7** — The inventory is hand-written, guarded by a join test in **both** directions.

**Implementation Context**:

```bash
# Tests (host; never inside the container)
./venv/bin/python -m pytest tests/ -q

# Lint
./venv/bin/python -m ruff check tomo/scripts/

# A single phase's tests
./venv/bin/python -m pytest tests/test_038_*.py -q
```

**Standing constraints for every task** — these are not advisory:

- **Never** `git stash`, `git reset --hard`, `git add -A`, or `git checkout --`.
  No `CLAUDE_ALLOW_DESTRUCTIVE_*` variables. Use `git worktree` for RED evidence
  and remove it with `rm -rf` plus `git worktree prune`; `--force` is blocked here.
- **`tomo-privat` is a LIVE environment — never touch it.** Any live work is
  `--instance tomo-instance`.
- Do **not** run `/capture-insight`, and do **not** write into any Obsidian vault.
- `/Volumes/Moon/Coding/MiYo/Hashi` is **read-only**. Never edit anything there.
- Bump `# version: X.Y.Z` on every edited file under `tomo/scripts/`.
- Write the `docs/tomo/<mirrored-path>.md` WHY entry **as you go**. A task was
  failed in spec 037 for omitting them.
- Commit messages end with the session's attribution lines.

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor:
**Prime** (understand context), **Test** (red), **Implement** (green),
**Validate** (refactor + verify).

- [ ] [Phase 1: The inventory, and what it reveals](phase-1.md)
- [ ] [Phase 2: The wire carries the decision](phase-2.md)
- [ ] [Phase 3: Refusal, before anything can be typed](phase-3.md)
- [ ] [Phase 4: The name becomes a value](phase-4.md)
- [ ] [Phase 5: Integration, the live path, and one handoff](phase-5.md)

### Why this order, and one thing it deliberately inverts

**The inventory is built first, though the owner ruled it ships last.** Those are
different decisions and both hold. The owner's ruling was about *delivery* — one
coordinated release, no partial handoff. Build order is free, and the consumer's
argument for going early was sound on its own terms: *"its value is the rows
neither of us knows about."*

Building it in Phase 1 collects that value without shipping early. The schema
already marks **21** fields `Editable` while the parser recognises about seven
controls, so the join test is expected to fail on its first run — and what it
reveals may change the scope of Phases 2–4. Finding that out first is strictly
better than finding it out last.

**Phase 3 precedes Phase 4** — refusal lands before anything can type a bad name.
The check is a pure function on a string, so it is fully testable before the
markdown can produce a typed name, and this ordering means no commit on the branch
ever has an unguarded owner-typed string reaching a destination.

**Dependencies**: Phase 1 is independent of everything. Phase 2 → Phase 4 (the
wire must carry `proposed_name` before both surfaces can be proven to converge).
Phase 3 → Phase 4 (the guard exists before the input does). Phase 5 depends on all.

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ⬜ |
| Every task produces a verifiable deliverable | ⬜ |
| All PRD acceptance criteria map to specific tasks | ⬜ |
| All SDD components have implementation tasks | ⬜ |
| Dependencies are explicit with no circular references | ⬜ |
| Parallel opportunities are marked with `[parallel: true]` | ⬜ |
| Each task has specification references `[ref: ...]` | ⬜ |
| Project commands in Context Priming are accurate | ⬜ |
| All phase files exist and are linked from this manifest | ⬜ |
