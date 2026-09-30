---
title: "Phase 1: The inventory, and what it reveals"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: The inventory, and what it reveals

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/F4]` — the inventory's nine acceptance criteria
- `[ref: PRD/Secondary Persona: The consumer's build pipeline]` — the only consumer of this artefact
- `[ref: PRD/Secondary User Journey (build-time)]` — the flow this phase enables
- `[ref: SDD/ADR-7]` — hand-written, guarded by a two-sided join test, and why not a registry
- `[ref: SDD/Building Block View; C11, C12]`

**Key Decisions**:
- The file is **hand-written**. A declarative registry would make drift impossible
  rather than merely detected, and is explicitly rejected for this spec: it is a
  refactor across the reducer and the parser, inside a spec already carrying four
  deliverables and a wire version move `[ref: SDD/ADR-7]`.
- The join runs in **both** directions. One direction only would have missed 037.
- `editable: false` exists for **retired** controls — a row that outlives its
  control, so the consumer is told to remove theirs rather than keep one writing a
  field we no longer honour.

**Dependencies**: none. This phase is independent of Phases 2–4 and is
deliberately first — see the manifest's note on build order.

---

## Tasks

Delivers the artefact that makes a missing editable decision a build failure
instead of a defect report, and — as a side effect that is the real reason it is
first — an inventory of what the suggestions markdown actually offers today.

- [ ] **T1.1 Enumerate what the markdown offers, and write it down** `[activity: domain-modeling]`

  1. Prime: read `suggestion-parser.py`'s control recognition (`parse_section`'s
     decision checkboxes ~`:812-822`, `_walk_attachment_conflicts` `:2268`,
     `_walk_tag_handler_decisions` `:2135`, `parse_tag_handler_keep_source` `:2212`)
     and the field-line handling below it. Then read every `Editable` description
     in `tomo/schemas/suggestions-wire.schema.json` — there are **21**
     `[ref: SDD/ADR-7]`.
  2. Test: none yet — this task's output is data, and T1.2 is the test that
     constrains it. Writing the test first here would mean asserting the contents
     of a file whose contents are the open question.
  3. Implement: `tomo/schemas/suggestions-decision-inventory.json` with one row
     per editable decision: `id` (stable, opaque, never changes when wording
     changes), `markdown_control` (prose, for humans), `wire_field` (dotted path
     or `null`), `editable`, optional `note`. Plus
     `tomo/schemas/suggestions-decision-inventory.schema.json` so a malformed row
     fails our own tests before it can reach the consumer `[ref: PRD/F4]`.
  4. Validate: the file validates against its own schema; `ruff` clean; ids are
     unique and none is derived from prose.
  5. Success:
     - [ ] One row per editable decision the markdown offers `[ref: PRD/F4]`
     - [ ] The attachment-conflict remedy appears with `wire_field: null`, which
           is the 037 state and the row the format exists for `[ref: PRD/F4]`
     - [ ] No read-only decision appears `[ref: PRD/F4]`
     - [ ] A malformed row fails Tomo's tests `[ref: PRD/F4]`

  **Expect this task to produce a finding, not just a file.** 21 schema fields
  against ~7 recognised controls means some editable wire fields have no markdown
  control and some controls may have no row anyone knew about. Record every
  discrepancy in the task's report rather than resolving it silently — it may
  change Phases 2–4, and it is the reason this phase is first.

- [ ] **T1.2 The two-sided join test** `[activity: testing]`

  1. Prime: read the consumer's own guard as the model —
     `test/unit/ui/suggestions-view/editable-field-coverage.test.ts` in the Hashi
     repo (**read-only**; never edit anything there). Ours is its mirror
     `[ref: SDD/ADR-7]`.
  2. Test: the test *is* the deliverable. It must fail in both directions: a
     schema field marked `Editable` with no inventory row, and a
     parser-recognised control with no inventory row. Build both failures
     deliberately and watch them fail before making them pass.
  3. Implement: `tests/test_038_decision_inventory_join.py`. Enumerate the schema
     side by walking the schema for `Editable` descriptions; enumerate the parser
     side from the label literals and field names the parser matches on. **A row
     with `editable: false` is exempt from the parser-side join** — that is what a
     retired control is, and without the exemption the test would reject exactly
     the row the column exists to carry `[ref: PRD/F4]`.
  4. Validate: full suite green; both mutations (remove a row; add an `Editable`
     field to the schema without a row) turn it red — **run them, do not assert
     that they would** `[ref: plan/README.md; the standing warning]`.
  5. Success:
     - [ ] A schema field marked `Editable` with no row fails the test `[ref: PRD/F4]`
     - [ ] A parser-recognised control with no row fails the test `[ref: PRD/F4]`
     - [ ] A retired control's row survives at `editable: false` and does **not**
           fail the parser-side join — the one case where a row legitimately has
           no control `[ref: PRD/F4]`
     - [ ] Both failure modes demonstrated by executed mutation, named in the
           task report by node id

  **Known limitation to state in the test's own docstring, not to fix:** this
  catches a *missing* row, not a *wrong* one. A row whose `wire_field` names the
  wrong path passes. The consumer's join catches that from the other side
  `[ref: SDD/ADR-7 trade-offs]`.

- [ ] **T1.3 Phase validation** `[activity: validate]`

  - Run the full suite and `ruff`. Confirm the inventory validates against its own
    schema. Report every discrepancy T1.1 surfaced as a list, with a recommendation
    for each: in scope for this spec, or a backlog entry. **Do not resolve them in
    this phase** — they are input to a scope decision, not work to absorb quietly.
  - Success: suite green; `ruff` clean; the discrepancy list exists and each item
    has a recommendation `[ref: PRD/F4]`.
