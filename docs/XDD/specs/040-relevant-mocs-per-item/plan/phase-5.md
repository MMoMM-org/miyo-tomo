---
title: "Phase 5: Owner-facing documentation"
status: pending
version: "1.0"
phase: 5
---

# Phase 5: Owner-facing documentation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/S2]`
- `[ref: SDD/Cross-Cutting Concepts; Security and privacy]`
- `[ref: SDD/Constraints; CON-7]`

**Key Decisions**:
- Owner-facing text describes behaviour, not executor internals.

**Dependencies**: Phase 1 (shape fixed). Can run alongside Phase 4.

---

## Tasks

The owner can read what MOC data reaches the model and how the exclude tag now behaves.

- [ ] **T5.1 PRIVACY.md and the inbox reference doc** `[activity: technical-writing]` `[parallel: true]`

  1. Prime: `PRIVACY.md:26-32`; `docs/XDD/reference/tier-2/workflows/inbox-processing.md:68-74`; `docs/XDD/reference/tier-3/inbox/inbox-analysis.md:10`; `docs/troubleshooting.md:504`; `docs/ai/memory/domain.md:10-18` `[ref: PRD/S2-AC1, S2-AC2]`
  2. Test: n/a (document). Checklist: PRIVACY says MOC names reach every item's analysis and headings/callouts only for MOCs it chose; the reference doc describes names, detail, the run-id check and that `MiYo/Tomo/exclude/moc` removes a MOC from inbox link candidates (superseding spec 021 ADR-13 B-moc for the inbox); stale "~10KB/subagent" corrected; link check finds no broken relative links
  3. Implement: edit the files
  4. Validate: link check script (scratchpad `check_links.py` or equivalent) clean
  5. Success: `[ref: PRD/S2-AC1, S2-AC2]`

- [ ] **T5.2 Backlog and memory** `[activity: technical-writing]` `[parallel: true]`

  1. Prime: `docs/XDD/backlog.md`; `docs/ai/memory/memory.md`, `domain.md`, `tools.md`
  2. Test: n/a. Checklist: backlog row for #173 points to spec 040; memory notes the shared-ctx read contract (names + selector, never `--field mocs`) and the exclude-tag change
  3. Implement: edit the files (memory via `/memory-add` routing)
  4. Validate: memory index ≤ 200 lines
  5. Success: the next session finds the new contract without reading this spec
