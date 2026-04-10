---
title: "Phase 3 — Inbox Processing"
status: draft
version: "1.0"
---

# Implementation Plan

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:
- `docs/specs/tier-1/pkm-intelligence-architecture.md` — Root architecture
- `docs/specs/tier-2/workflows/inbox-processing.md` — 2-pass workflow
- `docs/specs/tier-3/inbox/` — All inbox specs (analysis, suggestions, instructions, cleanup, state lifecycle)
- `docs/specs/tier-3/templates/token-vocabulary.md` — Token resolution system

**Key Design Decisions**:
- **ADR-1**: 2-pass model — suggestions first (direction), instructions second (details)
- **ADR-2**: State machine via tags — `#MiYo-Tomo/<state>` on each document
- **ADR-3**: MVP execution boundary — Tomo writes only to inbox folder
- **ADR-4**: Run-to-run discovery — check applied→confirmed→captured priority order
- **ADR-5**: Token resolution order — generated→config→metadata→content→custom

---

## Implementation Phases

- [ ] [Phase 1: Python Scripts](phase-1.md)
- [ ] [Phase 2: Agent Definitions](phase-2.md)
- [ ] [Phase 3: Command + Skills](phase-3.md)
- [ ] [Phase 4: Integration Validation](phase-4.md)

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | :white_check_mark: |
| Every task produces a verifiable deliverable | :white_check_mark: |
| Dependencies are explicit with no circular references | :white_check_mark: |
| Parallel opportunities are marked with `[parallel: true]` | :white_check_mark: |
| All phase files exist and are linked from this manifest as `[Phase N: Title](phase-N.md)` | :white_check_mark: |
