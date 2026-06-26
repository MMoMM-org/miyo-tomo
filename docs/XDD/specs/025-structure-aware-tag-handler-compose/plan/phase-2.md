---
title: "Phase 2: Deterministic Helper (target_structure.py)"
status: done
version: "1.0"
phase: 2
---

# Phase 2: Deterministic Helper (target_structure.py)

## Phase Context

**GATE**: Read before starting.
- `[ref: SDD/Implementation Examples — target_structure.py]` (traced walkthrough + fallback mapping)
- `[ref: SDD/ADR-3 deterministic helper]`, `[ref: SDD/ADR-9 parse contract]`, `[ref: SDD/CON-2 instance layout]`
- `tomo/scripts/lib/moc_structure.py` — purity-contract precedent (no IO/Kado/LLM, raw-string parser)

**Key Decisions**: pure lib (testable without AI); first-matching-structure-under-marker wins (ADR-9);
single-line + pipe-escape on cells; raw header/separator bytes for the block anchor; cwd-relative only
(NO `_SCRIPT_DIR.parent.parent`).

**Dependencies**: none — independent of Phase 1, **may run in parallel**. `[parallel: true]`

---

## Tasks

Delivers the pure, unit-tested engine that parses the target, validates, assembles rows/items, and picks
the anchor — the heart of the feature.

- [x] **T2.1 Section parser** `[activity: backend-logic]` `[parallel: true]`
  1. Prime: read the helper contract + ADR-9 `[ref: SDD/Complex Logic]`
  2. Test (RED): `parse_section` returns kind=table with columns/header_line/separator_line for a 3-col
     table; kind=list with bullet `-`/`*`/`1.` from the first item; kind=none for prose-only; recognizes
     separator variants `|---|`, `| :-- |`, alignment colons `[ref: PRD/FR-22]`; first-matching structure
     wins when prose precedes the table `[ref: SDD/ADR-9]`.
  3. Implement (GREEN): create `tomo/scripts/lib/target_structure.py` (`# version: 0.1.0`); pure functions,
     raw-string input.
  4. Validate: `./venv/bin/python -m pytest tests/test_target_structure.py -q`; ruff clean.
  - Success: `[ref: PRD/FR-21]` empty table parsed; `[ref: PRD/FR-22]` separator variants; `[ref: SDD/ADR-9]`.

- [x] **T2.2 Assemble + sanitize + anchor selection** `[activity: backend-logic]`
  1. Prime: review the placement matrix + sanitization rule `[ref: SDD/Implementation Examples]`
  2. Test (RED): table_row append → heading+inside anchor, N rows for per_item, 1 row for merged;
     table_row newest_first → block anchor with RAW `header\nseparator` value + placement after; list_item
     append/newest_first → heading + inside/after, cells joined by `join`; `_sanitize` escapes `|` and
     collapses newlines in a synth cell; `_sanitize_line` single-lines list cells; field-empty → empty cell,
     row still well-formed (no fallback).
  3. Implement (GREEN): `assemble(section_lines, output_format, cell_values_per_item) → (block, anchor)`.
  4. Validate: unit tests green; ruff clean.
  - Success: `[ref: PRD/FR-16]` placement matrix; `[ref: PRD/FR-18]` sanitization + positional rows.

- [x] **T2.3 Fallback signalling** `[activity: backend-logic]`
  1. Prime: the fallback matrix `[ref: SDD/Error Handling]`
  2. Test (RED): cell-count≠columns → `Fallback(cell_count_mismatch)`; prose-only section →
     `Fallback(no_structure_under_marker)`; (marker_missing is handled upstream by the reducer guard but the
     helper accepts an empty section and returns no_structure_under_marker). Never returns a malformed row.
  3. Implement (GREEN): return a `Fallback(reason)` sentinel from `assemble`.
  4. Validate: failure-path unit tests green `[ref: Constitution L1 Testing]`.
  - Success: `[ref: PRD/FR-19]` every mismatch yields a typed fallback, never a broken row.

- [x] **T2.4 Phase Validation** `[activity: validate]`
  - Full `tests/test_target_structure.py` green (happy + every fallback trigger + sanitization); ruff clean;
    confirm zero IO/Kado/LLM imports in the module `[ref: SDD/ADR-3]`.
