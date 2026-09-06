---
title: "Phase 1: Item key foundation"
status: completed
version: "1.0"
phase: 1
---

# Phase 1: Item key foundation

## Phase Context

**GATE**: read these before starting.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-2, ADR-5]`
- `[ref: SDD/Application Data Models]` — the `ItemKey` contract
- `[ref: SDD/Constraints; CON-6]` — the filesystem folds case
- `[ref: PRD/Feature 2]` — same-named notes handled independently
- `[ref: PRD/Business Rules 1-5]`

**Key Decisions**:
- The key **is** the path, verbatim — no slug, no hash, no transformation of the value itself.
- `stem` is not renamed. It stays, and means a bare filename again.
- Only the *filename* needs an encoding, and it must survive a case-insensitive filesystem.
- `sanitize_stem` must **not** be used for it — it is lossy by design and would map distinct
  paths onto one name, re-creating the collision this spec removes.

**Dependencies**: none. This phase is the foundation.

**Visible effect**: none. Nothing calls the new module yet and no behaviour changes. That is
intended — see the sequencing rule in `plan/README.md`.

---

## Tasks

Establishes an item identity that is unique across the whole inbox subtree, and the schema
surface that carries it. Deliberately inert: Phase 2 wires it in.

- [x] **T1.1 `lib/item_key.py` — derive and encode** `[activity: domain-modeling]`

  1. **Prime**: Read `[ref: SDD/Application Data Models]` and `[ref: SDD/Implementation Examples]`.
     Read `tomo/scripts/lib/attachment_index.py` as the shape to follow — a pure library under
     `lib/` with no pipeline imports. Read `tomo/scripts/lib/obsidian_filename.py` to see why
     `sanitize_stem` is the wrong tool here.
  2. **Test** (RED):
     - `derive("100 Inbox/Places/Dresden.md")` returns the path unchanged
     - `to_filename` is stable — same key, same name, across calls
     - two keys differing **only in letter case** produce different filenames `[ref: SDD/CON-6]`
     - two keys differing anywhere produce different filenames
     - the readable half of the name contains the note's stem, so a human can identify the file
     - a path with characters awkward in a filename still yields a usable name
       `[ref: PRD/Edge Cases]`
     - an empty or malformed key raises rather than silently producing a name that could collide
  3. **Implement**: `tomo/scripts/lib/item_key.py` with `derive()` and `to_filename()`.
     `to_filename` = readable part + `-` + 8 hex characters of a digest over the **exact** key.
  4. **Validate**: unit tests pass; `ruff` clean; the module imports nothing from the pipeline.
  5. **Success**:
     - [x] Two same-named notes in different folders cannot produce one filename
           `[ref: PRD/AC Feature 2]`
     - [x] The case-collision test fails if the digest is taken over a lowercased key —
           prove it by mutation `[ref: SDD/ADR-5]`

- [x] **T1.2 Schemas carry `item_key`** `[activity: data-architecture]` `[parallel: true]`

  1. **Prime**: Read `[ref: SDD/Data Storage Changes]`. Note that every affected schema sets
     `additionalProperties: false`, so a payload carrying a field the schema does not declare is
     rejected whole — the schema must land **before or with** its producer
     `[ref: SDD/Implementation Gotchas]`.
  2. **Test** (RED):
     - a payload with `item_key` validates against each modified schema
     - a payload **without** `item_key` is rejected — the field is required, not optional
     - `stem` remains required and its description still says "bare filename"
     - a payload with both fields, where `item_key` contains slashes, validates — no pattern
       forbids them
  3. **Implement**: add `item_key` (required string, `minLength: 1`) to
     `item-result.schema.json`, `state-entry.schema.json`, `suggestions-doc.schema.json`,
     `suggestions-wire.schema.json`, `routing-plan.schema.json`.
  4. **Validate**: schema tests pass; every existing fixture that must keep validating still does.
  5. **Success**:
     - [x] All five schemas accept and require `item_key` `[ref: SDD/Data Storage Changes]`
     - [x] `stem`'s declared meaning is unchanged `[ref: SDD/ADR-2]`

- [x] **T1.3 `validate-result.py` requires the key** `[activity: backend]` `[parallel: true]`

  1. **Prime**: Read `tomo/scripts/validate-result.py`, particularly `REQUIRED_TOP` (`:29`).
  2. **Test** (RED):
     - an analyst result missing `item_key` is rejected with a clear message
     - a result carrying both `item_key` and `stem` passes
     - the rejection names the field, so a failing analyst run is diagnosable
  3. **Implement**: add `item_key` to `REQUIRED_TOP`.
  4. **Validate**: unit tests pass; `ruff` clean.
  5. **Success**:
     - [x] A result without the key cannot reach the reducer unnoticed
           `[ref: SDD/Building Block View]`

- [x] **T1.4 Phase Validation** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - Confirm the phase is genuinely inert: no pipeline script imports `lib/item_key.py` yet, and
    a run over an unchanged inbox produces the same output as before this phase.
  - Mutation-prove T1.1's case test: take the digest over a lowercased key, confirm **that
    specific test** fails, restore. A green suite after a mutation that did not apply proves
    nothing — verify the edit actually landed before trusting the result.
  - Bump `# version:` on every modified file.
