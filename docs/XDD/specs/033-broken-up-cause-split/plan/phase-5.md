---
title: "Phase 5: Integration, regression and live validation"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: Integration, regression and live validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Quality Requirements]` — all six
- `[ref: SDD/Acceptance Criteria]`
- `[ref: PRD/Success Metrics]`
- `docs/XDD/specs/032-up-source-routing/live-validation.md` — the live-run procedure, including the
  `Atlas/` exclusion that had to be narrowed and restored

**Key Decisions**:
- Byte-identity is proven by **loading the pre-spec modules from git and diffing**, never by
  observing that tests still pass. Spec 032 established the method after a count-based proxy went
  hollow.

**Dependencies**: Phases 1–4.

---

## Tasks

- [x] **T5.1 End-to-end on the live cache** `[activity: validate]`

  1. **Prime**: the measured baseline is 359 entries, 42 flagged, of which 20 are `not-a-moc` and 22
     `unresolved` `[ref: README/decisions log]`.
  2. **Test**: drive the real scan and the real renderer over the live cache.
     - the two checks' counts sum to 42
     - the `not-a-moc` count is 20 and the `unresolved` count is 22 — if either differs, the vault
       changed and the baseline must be re-measured before concluding a defect
     - no advisory finding carries an apply checkbox
     - the report's summary counts match the finding counts
  3. **Validate**: run it; record the numbers.
  4. **Success**: the split holds on production data, not only on fixtures.

- [x] **T5.2 Everything else is byte-identical** `[activity: validate]`

  1. **Prime**: `[ref: CON-3]`. Load the pre-spec modules from git under distinct module names and
     render the same document through both.
  2. **Test**: for a mixed document containing every check, assert that **every block except the
     broken-parent ones** is byte-identical. Scope the assertion to those blocks by index, not by a
     count of changed lines — a whole-report count is a proxy that holds only until the next
     legitimate change, which is exactly how 032's CON-7 guard went hollow.
  3. **Validate**: prove the guard bites by changing an unrelated check's output on purpose and
     confirming red.
  4. **Success**: the guard asserts the invariant it is named after.

- [x] **T5.3 Zero added vault access** `[activity: validate]`

  1. **Prime**: `[ref: CON-1]`. `_check_broken_up` takes no `graph_audit_fn` / `list_dir_fn`, so it
     structurally cannot call out; the new sibling must inherit that property.
  2. **Test**: assert **structurally** — neither check function accepts a vault-callable parameter —
     rather than by counting calls at runtime. A call count passes for the wrong reason on a run
     where the cache happened to be warm.
  3. **Validate**: record the outcome in `docs/evolution/inbox-cost-log.md`, noting the same caveat
     spec 032 recorded: a `tool_use` count measures the model, not the scripts.
  4. **Success**: the property is structural, so it cannot regress silently.

- [x] **T5.4 Live run and the one metric that matters** `[activity: validate]`

  1. **Prime**: `./scripts/update-tomo.sh --yolo` → `/explore-vault` → `/garden-audit`. The bare
     `update-tomo.sh` dies at the voice prompt without copying anything.
  2. **Test**: on the refreshed cache and the real report:
     - the 20 formerly-destructive offers are gone — count the approvable broken-parent fixes before
       and after `[ref: PRD/Success Metrics]`
     - the advisory block reads as advice a person can act on
  3. **Validate**: record the before/after counts.
  4. **Success**: the headline metric is **behavioural** — *no destructive fix is offered for a link
     that works*. Do not tick this task on test evidence alone; 032 kept its equivalent open until a
     real apply was observed, and that discipline is why the defect was found rather than assumed
     absent.

- [ ] **T5.5 Documentation** `[activity: documentation]`

  1. Update the spec README to `Implemented` via `xdd-meta finalize`, with the measured before/after.
  2. Close issue #157 with the numbers, not with a description.
  3. Record the exclusion behaviour change from T3.3 wherever a release note is owed.
  4. **Success**: someone reading #157 in six months sees what changed and by how much.

- [ ] **T5.6 Phase Validation** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - Walk the SDD Quality Requirements table and confirm each row has a passing test.
  - Walk the PRD acceptance criteria and confirm each maps to a green test — including the
    negative ones, which are the easiest to satisfy vacuously.
