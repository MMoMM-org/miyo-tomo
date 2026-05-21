---
title: "F-47 — Tomo Lifecycle State: Unified Frontmatter Block + byFrontmatter Discovery"
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
| specId | 017-tomo-lifecycle-tags |
| title | F-47 — Tomo Lifecycle State (Unified Frontmatter Block + byFrontmatter Discovery) |
| status | DRAFT |
| phases | 6 |
| totalTasks | 33 |
| parallelTasks | 11 |
| specReferences | 99 inline `[ref: ...]` annotations |
| clarificationsRemaining | 0 |

---

## Specification Compliance Guidelines

### How to Ensure Specification Adherence

1. **Before Each Phase**: Read the Phase Context section + every `[ref: ...]` link before writing tests.
2. **During Implementation**: Reference specific SDD/PRD sections in each task via `[ref: ...]` — don't re-decide locked questions.
3. **After Each Task**: Run Specification Compliance checks per the Validate step.
4. **Phase Completion**: Verify all PRD AC mapped to that phase pass before moving on.

### Deviation Protocol

When implementation requires changes from the specification:
1. Document the deviation with rationale in the relevant phase file.
2. Obtain approval before proceeding.
3. Update SDD when the deviation improves the design.
4. Record all deviations in this plan for traceability.

## Metadata Reference

- `[parallel: true]` — Tasks that can run concurrently
- `[component: tomo|hashi|kokoro]` — For multi-component features (Hashi schema-lock handoff + Kokoro ADR are the cross-repo tasks)
- `[ref: doc/section; lines: X-Y]` — Links to specifications
- `[activity: type]` — Activity hint for specialist agent selection

### Success Criteria

**Validate** = process verification ("did we follow TDD?").
**Success** = outcome verification ("does it work correctly?").

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/017-tomo-lifecycle-tags/requirements.md` — PRD v1.2 (8 features, 30+ Gherkin AC, 4 non-linear scenarios, 4 flow diagrams)
- `docs/XDD/specs/017-tomo-lifecycle-tags/solution.md` — SDD v1.0 (6 ADRs, layered producer/consumer + shared state-machine, Cross-Spec Coordination map)
- `docs/XDD/specs/017-tomo-lifecycle-tags/README.md` — Decisions Log (pre-PRD locks: state machine names, OQ4 no-backward-compat, OQ5 going-forward filename rename only)
- `~/Kouzou/projects/miyo/miyo-constitution.md` — L1/L2 governance (Privacy, Local-first, Architecture L2 Kokoro ADR, Code Quality L2 shared state-machine module, Testing L1 rejection-path coverage)
- `_inbox/from-kado/2026-05-21_kado-to-tomo_frontmatter-write-shipped-plus-bonus.md` — Authoritative Kado 0.11.0 capability list + recommended F-47 hot-path pattern; supersedes the 2026-05-20 write-frontmatter-shipped notice (rolled into this doc) and covers both `kado-write operation=frontmatter` merge semantics AND `kado-search operation=byFrontmatter` query/filter syntax
- `docs/XDD/specs/013-moc-creation-skill/plan/phase-6.md` — F-43 T6.2/T6.4 paused-state notes (Phase 5 unblocks T6.2; Phase 5 also unblocks T6.4)
- `docs/XDD/specs/012-force-atomic-synthesis/solution.md` — XDD 012 fan-doc renderer; Phase 2 task extends it for `doc_type=suggestions-fan`

**Key Design Decisions** (from SDD ADRs, all user-confirmed 2026-05-21):

- **ADR-1**: State machine = pure-data dict-of-dicts in `tomo_lifecycle.py` — auditable in one glance; no class hierarchy.
- **ADR-2**: `KadoClient` extensions are additive methods (`write_frontmatter`, `search_by_frontmatter`); existing call sites untouched.
- **ADR-3**: State-promoter is orchestrator-embedded logic (Bash dispatch + small helper), NOT a new subagent — control flow, not LLM reasoning.
- **ADR-4**: Schema validation via Python `jsonschema` (Draft 7). Dev-mode strict via `TOMO_SCHEMA_STRICT=1`; prod-mode tolerant (warns).
- **ADR-5**: `tag-captured.py` → renamed to `mark-captured.py` AND rewritten to use `kado_client.write_frontmatter()` (eliminates `feedback_frontmatter_newline_guard` bug class).
- **ADR-6**: Each P-phase is independently shippable. P1 (producers) ships additively; P2 (consumers) is the big-bang legacy cut. Privat-Test inbox wipe at P2 start.

**Locked PRD scope**:

- v1.2: **frontmatter-only state** (no mirrored lifecycle tag) — `tomo.state` is single SoT.
- v1.1: **byFrontmatter primary** discovery — Kado 0.11.0 returns paths + frontmatter inline.
- **AC-2.1 wording precision** (clarification, 2026-05-21): PRD AC-2.1 reads "EXACTLY ONE `kado-search byFrontmatter` call". The intent is **one query per state bucket**: ONE call for `tomo.state=pending-*` AND ONE call for `tomo.state=captured` — both via `byFrontmatter`, both server-side path-filtered. This is NOT one combined Kado call; do not attempt to compress them. SDD §Complex Logic step 2 + Plan T3.1 both implement this two-call shape.
- OQ4: **clean cut-over** — no legacy fallback in state-init / orchestrator; Privat-Test reset absorbs migration cost.
- OQ5: **going-forward filename rename only** — no bulk migration of existing `tomo-moc-proposal-*.md`.
- OQ13: **Hashi auto-cleanup on instructions-applied** + manual orphan delete. No Tomo-side cleanup script.

**Implementation Context**:

```bash
# Testing
pytest tests/ -v                                    # full unit suite
pytest tests/test_tomo_lifecycle.py -v              # state machine tests
pytest tests/test_doc_frontmatter.py -v             # schema validation tests
pytest tests/test_kado_client_frontmatter.py -v     # wrapper tests
pytest tests/test_inbox_discovery.py -v             # bucket + drift tests

# Quality
ruff check tomo/scripts/                            # lint
python3 -c "import ast; ast.parse(open('tomo/scripts/state-promoter.py').read())"  # syntax sanity
python3 -m jsonschema -i <fixture.json> tomo/schemas/doc-frontmatter.schema.json   # schema CLI

# Tomo lifecycle
./scripts/update-tomo.sh                            # sync tomo/ → tomo-instance/
./begin-tomo.sh                                     # launch Tomo container (script lives at repo root)
# inside container:
#   /inbox             — Phase A unified discovery + state-promotion + Pass-1
#   /inbox --recover   — drift-recovery mode (treat captured as fresh)
#   /moc-propose ...   — proposal-doc emission with tomo: block

# Schema strict-mode (dev)
export TOMO_SCHEMA_STRICT=1                         # raise on schema validation failure

# Cross-repo handoff (Phase 6)
ls _outbox/for-hashi/                               # outgoing schema-lock handoff
```

**Branch convention**: All F-47 work happens on `feat/017-tomo-lifecycle-tags` (per Constitution L1 Operations + SDD §Cross-Spec Coordination Branch-state coordination). Direct main commits are blocked except for `_outbox/` paths (gitignored exemption per repo `.gitignore`). Each P-phase may also cut a sub-branch off main if the operator prefers tighter merge boundaries (ADR-6 atomicity allows it).

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor: **Prime** (understand context), **Test** (red), **Implement** (green), **Validate** (refactor + verify).

> **Tracking Principle**: Track logical units that produce verifiable outcomes. The TDD cycle is the method, not separate tracked items.

- [x] [Phase 1: State Machine, Schema, and Kado Client Foundation](phase-1.md)
- [ ] [Phase 2: Producer-Side Writes (F-47.P1)](phase-2.md)
- [ ] [Phase 3: Consumer Cut-over — Unified byFrontmatter Discovery (F-47.P2)](phase-3.md)
- [ ] [Phase 4: Drift Recovery + Transcription Stop-Gate (F-47.P3)](phase-4.md)
- [ ] [Phase 5: F-43 MOC-Consumption (F-47.P4)](phase-5.md)
- [ ] [Phase 6: Hashi Schema Handoff + Final Integration & E2E Validation (F-47.P5)](phase-6.md)

---

## Plan Verification

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

## Phase-to-AC Coverage Map

| PRD AC | Phase / Task |
|--------|--------------|
| AC-1.1 (mark-captured writes tomo.state=captured via write_frontmatter) | T2.1 |
| AC-1.2 (suggestions-render emits tomo: block) | T2.2 |
| AC-1.3 (instruction-render emits source_suggestions / source_moc_proposal) | T2.3 |
| AC-1.4 (moc-architect / suggestions-reducer --moc-proposal-mode emits tomo: block) | T2.4, T2.6 |
| AC-1.5 (schema validation gates every producer write) | T1.2, T2.7 |
| AC-2.1 (single byFrontmatter + single listDir per Phase A run) | T3.1 |
| AC-2.2 (non-pending docs not returned — filtered server-side) | T3.1, T3.6 |
| AC-2.3 (empty-inbox hybrid: byFrontmatter + listDir both execute) | T3.1, T3.6 |
| AC-2.4 (filter.path excludes vault-wide pollution) | T1.3, T3.6 |
| AC-3.1 (pending-approval → approved on [x] Approved) | T3.2, T3.3 |
| AC-3.2 (pending-accept → accepted on any [x] Accept) | T3.2, T3.3, T5.2 |
| AC-3.3 (no tick → doc stays pending) | T3.2 |
| AC-3.4 (invalid transition rejected + logged) | T1.1, T3.2 |
| AC-3.5 (malformed body skipped + logged) | T3.2 |
| AC-4.1 (Tomo emits the contract; Hashi accepts state flip) | T6.1 |
| AC-4.2 (missing source path → warning + proceed; instructions trashed last) | T6.1 |
| AC-4.3 (partial-applied count → no cleanup) | T6.1 |
| AC-4.4 (multiple pending-apply docs cleaned independently) | T6.1 |
| AC-4.5 (generic source_* iteration — future doc-types) | T6.1 |
| AC-5.1 (accepted cluster → bundled create_moc + N child updates) | T5.1, T5.2 |
| AC-5.2 (multi-cluster: ticked → bundled, un-ticked → squelch) | T5.2, T5.3 |
| AC-5.3 (Hashi cleanup trashes instructions + proposal-doc) | T6.1, T6.4 |
| AC-5.4 (MOC lands in inbox folder — Obsidian linkable) | T5.2 |
| AC-5a.1 (drift hint when captured > 0 + pending* == 0) | T4.2 |
| AC-5a.2 (--recover treats captured as fresh) | T4.1, T4.2 |
| AC-5a.3 (recovery transparent to downstream cleanup) | T4.2, T6.4 |
| AC-5a.4 (no auto-recovery when --recover absent) | T4.1 |
| AC-5b.1 (media → transcribe → stop-gate exit) | T4.3 |
| AC-5b.2 (re-run /inbox → transcript treated as fresh source) | T4.3, T6.4 |
| AC-5b.3 (un-edited transcript no special handling) | T4.3 |
| AC-5b.4 (media + manual notes same run: only new transcripts deferred) | T4.3 |
| AC-6.1 (kado_client.write_frontmatter wrapper) | T1.3 |
| AC-6.2 (mark-captured uses wrapper) | T2.1 |
| AC-7.1 (state-machine module imported by all producers/consumers) | T1.1, T2.x, T3.2 |
| AC-7.2 (every producer write schema-validated) | T1.2, T2.7 |
| Token-cost measurement vs PRD §7 baselines | T6.3 |
| Cross-repo Kokoro ADR (Architecture L2) | T6.2 |
| Memory + 013/009 resumption markers | T6.5 |
