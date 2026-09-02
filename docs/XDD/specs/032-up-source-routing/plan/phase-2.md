---
title: "Phase 2: Carry it to the finding"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Carry it to the finding

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-2]` — the check describes reality; it does not choose
- `[ref: SDD/Interface Specifications; BrokenUpFindingDetail]`
- `[ref: PRD/Feature 1]`, `[ref: PRD/Business rule 1]`
- Source to read: `garden-audit.py:86-100` (`_finding`, `detail` is the carrier), `:150-169` (`_check_broken_up`, source-agnostic today); `tomo/schemas/garden-audit-doc.schema.json`, `garden-audit-wire.schema.json`

**Key Decisions**:
- The finding gains **two** fields, not a new finding type. `detail` already carries `up_target`; this is the same mechanism.
- The check stays **cache-only** — it reads two more cache keys and makes no call `[ref: CON-5]`.

**Dependencies**: Phase 1 (the cache must carry `up_value`).

---

## Tasks

Makes the declaration site visible to everything downstream, without changing any behaviour yet.

- [ ] **T2.1 Finding detail carries site and value** `[activity: backend-logic]`

  1. **Prime**: Read `_check_broken_up` at `garden-audit.py:150-169`. It currently passes `{"up_target": ...}` as `detail`.
  2. **Test** (RED):
     - a frontmatter-sourced broken entry produces a finding whose detail carries `up_source == "frontmatter"` and the observed `up_value` `[ref: PRD/AC-F1.2]`
     - an inline-sourced broken entry carries `up_source == "inline"` and `up_value is None` `[ref: PRD/AC-F1.1]`
     - a cache entry **without** the `up_value` key produces a finding whose detail also lacks it — the absence must survive the hop, not be filled in with `None` `[ref: SDD/ADR-3]`
     - a note with no declaration produces no finding, unchanged `[ref: PRD/AC-F1.3]`
     - the check issues no Kado call `[ref: CON-5]`
     - `up_target` and every other finding field are unchanged `[ref: CON-7]`
  3. **Implement**: extend the `detail` dict passed to `_finding`. Propagate the key's **absence** rather than defaulting it.
  4. **Validate**: unit tests pass; `ruff` clean; `# version:` bumped.
  5. **Success**:
     - [ ] The declaration site reaches the finding `[ref: PRD/Feature 1]`
     - [ ] A missing `up_value` stays missing — the sentinel test in Phase 3 depends on it `[ref: SDD/Implementation Gotchas]`

- [ ] **T2.2 Schema declarations** `[activity: data-architecture]` `[parallel: true]`

  1. **Prime**: Both garden-audit schemas describe `detail` per check. Check whether `detail` is open or closed for `broken_up` before assuming a field can simply appear.
  2. **Test** (RED):
     - a finding carrying the two new detail fields validates against `garden-audit-doc.schema.json`
     - the same for `garden-audit-wire.schema.json`
     - a finding **without** them still validates — they must not be required, or every pre-change artefact breaks `[ref: CON-7]`
     - `up_value` accepts a list, a scalar and `null` — the shape is not constrained beyond that `[ref: SDD/Application Data Models]`
  3. **Implement**: declare `up_source` (enum plus null) and `up_value` (unconstrained) in both schemas.
  4. **Validate**: schema tests pass. Schemas sync bytewise — no version bump `[ref: CON-8]`.
  5. **Success**: both channels accept the enriched finding, and legacy artefacts still validate

- [ ] **T2.3 Digest impact check** `[activity: validate]`

  1. **Prime**: the garden-audit wire has its own digest with **per-field exclusions**, unlike the suggestions digest. Confirm which fields it covers before adding to `detail`.
  2. **Test** (RED):
     - adding `up_source`/`up_value` to a finding does **not** make an otherwise unedited document read as user-edited
     - a genuine user edit is still detected
  3. **Implement**: if the digest covers `detail` wholesale, add the two fields to its exclusion set — they are Tomo-written, not user-editable, and a Tomo-written field that shifts the digest would read as an edit.
  4. **Validate**: digest tests pass.
  5. **Success**: Tomo-written fields never masquerade as user edits `[ref: SDD/Cross-Cutting Concepts]`

- [ ] **T2.4 Phase Validation** `[activity: validate]`

  - Full suite green. Confirm end to end that a frontmatter-sourced broken parent produces a finding carrying both fields, through both the doc and the wire channel. `ruff` clean.
