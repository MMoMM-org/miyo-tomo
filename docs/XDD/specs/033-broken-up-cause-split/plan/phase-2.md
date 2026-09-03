---
title: "Phase 2: Split the check"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Split the check

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-3]`
- `[ref: SDD/Interface Specifications; Finding — the split]`
- `[ref: PRD/Feature 1]`, `[ref: PRD/Feature 2]`, `[ref: PRD/Feature 6]`
- Source to read: `tomo/scripts/garden-audit.py:86-101` (`_finding` — note that `decision` is
  attached **only** when `fixable`), `:148-181` (`_check_broken_up`), `:51-60` (`_TIER`,
  `_FIXABLE`); `tomo/scripts/garden-audit-parser.py:403` and `:603` (both routing sites, gated on
  `check == "broken_up"`)

**Key Decisions**:
- **ADR-1** — the advisory case is a **different check**, not a `broken_up` finding with a different
  tier. This is what makes the destructive path structurally absent rather than merely unused.
- **ADR-3** — a missing `up_broken_reason` is a known state with its own behaviour, never a default.

**Dependencies**: Phase 1 (the field must exist before the check can branch on it).

---

## Tasks

The behavioural change. After this phase the audit emits two checks where it emitted one, and the
advisory one carries no decision block.

- [ ] **T2.1 `_check_broken_up` branches on the reason** `[activity: domain-modeling]`

  1. **Prime**: Read `garden-audit.py:148-181`. Note the ADR-3 membership pattern spec 032 already
     uses there for `up_source` and `up_value` — copy it, do not re-invent it.
  2. **Test** (RED):
     - entry with `up_broken_reason == "unresolved"` → one finding, `check == "broken_up"`
     - entry with `up_broken_reason == "not-a-moc"` → one finding, `check == "parent_not_moc"`
     - a mixed batch → the two counts sum to the number of broken entries, with **no entry
       silently dropped**. Assert the sum, not each branch in isolation — a dropped entry is the
       failure this test exists to catch. `[ref: PRD/F1]`
     - `detail` carries the reason through, using a membership test
     - exclusions are consulted **per check name**, so a path excluded for `broken_up` only is still
       eligible for `parent_not_moc` `[ref: SDD/ADR-4]`
  3. **Implement**: read the reason with the `_MISSING` sentinel; route to the two check names.
  4. **Validate**: `./venv/bin/python -m pytest tests/test_garden_audit_scan.py -q`
  5. **Success**: every broken entry produces exactly one finding, under the right check name.

- [ ] **T2.2 The advisory check carries no decision block** `[activity: domain-modeling]`

  1. **Prime**: `_finding` attaches `decision` only when `check in _FIXABLE` (`:98-100`). Registering
     the tier without touching `_FIXABLE` is the whole mechanism. `[ref: SDD/ADR-1]`
  2. **Test** (RED) — assert over a **whole mixed batch**, not a happy path:
     - no `parent_not_moc` finding has a `decision` key `[ref: PRD/F2 criterion 2]`
     - every one has `tier == "advisory"` and `fixable is False`
     - feeding that batch through both parser routing sites produces **no** confirmed item and **no**
       action for any of them `[ref: PRD/F2 criterion 5]` `[ref: CON-2]`
     - the same batch's `broken_up` findings still route exactly as spec 032 emits them
       `[ref: SDD/ADR-7]`
  3. **Implement**: `_TIER["parent_not_moc"] = "advisory"` only. Phase 3 owns the remaining sites.
  4. **Validate**: `./venv/bin/python -m pytest tests/test_garden_audit_scan.py tests/test_garden_audit_parser.py -q`
  5. **Success**: CON-2 holds because the code path does not exist, not because nothing takes it.

- [ ] **T2.3 A pre-033 cache claims no cause** `[activity: domain-modeling]`

  1. **Prime**: `[ref: SDD/ADR-3]` and its named failure — a `.get()` default classifies every old
     finding as `unresolved`, which keeps offering the destructive fix on exactly the findings this
     spec protects, while the report claims it checked.
  2. **Test** (RED):
     - an entry **without** the key → a `broken_up` finding (today's behaviour), and the detail
       records that the cause is unknown — **not** `"unresolved"` `[ref: PRD/F6 criterion 1]`
     - an entry **with** `up_broken_reason: null` and `up_state: broken` → treated as unknown too,
       and asserted separately from the absent case so the two cannot collapse
     - a batch mixing pre- and post-033 entries → each is handled on its own terms
  3. **Implement**: the sentinel comparison; no default anywhere on the path.
  4. **Validate**: full check suite.
  5. **Success**: reverting the sentinel to `.get("up_broken_reason")` turns a test red — prove it by
     doing so, do not assert it `[ref: SDD/Implementation Gotchas 1]`.

- [ ] **T2.4 Phase Validation** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - Run the real check over the live cache: the two counts must sum to today's 42.
  - Confirm no action is emitted for any advisory finding by driving the real parser, not by reading
    the code.
