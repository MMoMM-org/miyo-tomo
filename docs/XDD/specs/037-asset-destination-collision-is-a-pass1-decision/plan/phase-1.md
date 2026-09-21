---
title: "Phase 1: Detection in the reducer"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Detection in the reducer

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-1]` — the check lives in the reducer
- `[ref: SDD/Architecture Decisions; ADR-2]` — generalise the folder cache
- `[ref: SDD/Runtime View; Primary Flow — Pass 1]`
- `[ref: SDD/Cross-Cutting Concepts; Cost]`
- `[ref: PRD/F1]`, `[ref: PRD/S1]`

**Key Decisions**:
- The reducer, not `inbox-triage.py`: triage has no `asset_folder` and never
  computes a destination. The reducer already loads both the folder and a Kado
  client.
- `_vault_folder_notes` is generalised rather than copied. Two near-identical
  folder caches would drift.
- The check fails **open** — a listing that raises is not a collision. Same
  posture as the note pass it sits beside.
- `same_file` is decided on content. The live pair is two different 69-byte
  PNGs; a size comparison would call them identical.

**Dependencies**: none. This phase is the foundation for 2 and 3.

---

## Tasks

Establishes the capability to know that a destination is taken, and whether the
file already there is the same one.

- [ ] **T1.1 The folder cache serves attachments as well as notes** `[activity: domain-modeling]`

  1. Prime: Read `tomo/scripts/suggestions-reducer.py:1966-1996` — `_vault_folder_notes`, its `_folder_cache`, the case-folded keys recomposed through `_dest_join`, and `folder_listing_calls` `[ref: SDD/Required Context Sources]`
  2. Test: a folder listed once serves two lookups without a second call; an attachment name is found in a folder whose `.md` files are ignored; a note lookup keeps its current behaviour unchanged; a name differing only in case is found `[ref: PRD/F1-AC4]`; a listing that raises yields an empty map and still counts its round trip
  3. Implement: parameterise the helper on the file predicate and the join, so the attachment caller passes `_asset_dest_join` and keeps non-`.md` names, while the note caller's arguments are unchanged
  4. Validate: `./venv/bin/python -m pytest tests/ -q`; `ruff` clean; the spec 034 T5.2 tests still pass untouched
  5. Success: one listing per folder regardless of caller `[ref: PRD/F1-AC3]`; the note path is behaviourally identical `[ref: SDD/Constraints, additive only]`; `folder_listing_calls` counts the asset folder `[ref: SDD/Cost]`

- [ ] **T1.2 An occupied destination becomes a recorded conflict** `[activity: domain-modeling]`

  1. Prime: Read `_build_move_asset_actions` for how attachments are deduplicated globally and how `owner_source_items` is accumulated `[ref: render_actions.py:640-728]`; read `load_asset_folder` `[ref: suggestions-reducer.py:1363]`
  2. Test: a free destination raises nothing and leaves the run byte-identical to today `[ref: PRD/F1-AC1]`; an occupied destination produces one conflict naming source, destination and every owning note `[ref: PRD/F1-AC2]`; an attachment embedded by three notes produces **one** conflict carrying three owners; no Kado client produces no conflicts and no error `[ref: PRD/F1-AC5]`; a listing failure produces no conflicts and the run proceeds `[ref: SDD/Error Handling]`
  3. Implement: compute each distinct attachment's destination through `_asset_dest_join` — the same helper Pass 2 uses — and record `attachment_conflicts[]` entries into the suggestions-doc structure
  4. Validate: full suite; `ruff`; assert on a fixture with zero conflicts that the emitted document is unchanged from the pre-change render
  5. Success: every PRD F1 criterion has a named test; the destination is computed by the same helper as Pass 2, so the two cannot disagree `[ref: SDD/Runtime View, step 3]`

- [ ] **T1.3 The conflict knows whether it is the same file** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: Read `KadoClient.read_file_bytes` `[ref: kado_client.py:176]` and the live probe recorded in `README.md` — two 69-byte PNGs with different digests
  2. Test: byte-identical files set `same_file: true`; differing files set `false`; **two files of identical size and different content set `false`** — the regression that a size check would fail `[ref: SDD/Complex Logic]`; a read that raises sets `null` and does not abort `[ref: PRD/S1-AC3]`; a destination occupied by a folder sets `false` `[ref: SDD/Error Handling]`
  3. Implement: read both sides only for a name already known to be taken, compare content, set `same_file`
  4. Validate: full suite; `ruff`; assert that a run with no collisions performs **zero** content reads
  5. Success: content decides, never size `[ref: PRD/S1]`; reads are bounded by collisions, not attachments `[ref: SDD/Cost]`; nothing derived from the content is persisted anywhere `[ref: SDD/Security and privacy]`
