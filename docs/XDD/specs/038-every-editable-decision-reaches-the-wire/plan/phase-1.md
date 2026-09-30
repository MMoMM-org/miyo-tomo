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

- [x] **T1.1 Enumerate what the markdown offers, and write it down** `[activity: domain-modeling]`

  1. Prime: read `suggestion-parser.py`'s control recognition (`parse_section`'s
     decision checkboxes ~`:812-822`, `_walk_attachment_conflicts` `:2268`,
     `_walk_tag_handler_decisions` `:2135`, `parse_tag_handler_keep_source` `:2212`)
     and the field-line handling below it. Then read every `Editable` description
     in `tomo/schemas/suggestions-wire.schema.json` — there are **21**
     `[ref: SDD/ADR-7]`.
  2. Test: write `tomo/schemas/suggestions-decision-inventory.schema.json` first,
     then `tests/test_038_inventory_schema_validation.py` against it — a
     conforming row validates, and a row that is malformed in each way the schema
     claims to forbid fails. **Demonstrate both directions by running them**, not
     by asserting them `[ref: PRD/F4]`.

     What is *not* testable at this point is **which rows exist** — that is the
     open question this task answers, and T1.2's join test is what constrains it.
     The distinction is the whole point: a test for "what makes a row valid" is
     available now; a test for "which rows there are" is not.
  3. Implement: `tomo/schemas/suggestions-decision-inventory.json` with one row
     per editable decision: `id` (stable, opaque, never changes when wording
     changes), `markdown_control` (prose, for humans), `wire_field` (dotted path
     or `null`), `editable`, optional `note`. The schema from step 2 is already
     guarding the shape, so the inventory is never authored against an unverified
     structure `[ref: PRD/F4]`.
  4. Validate: the file validates against its own schema; `ruff` clean; ids are
     unique and none is derived from prose.
  5. Success:
     - [x] One row per editable decision the markdown offers `[ref: PRD/F4]`
     - [x] The attachment-conflict remedy appears with `wire_field: null`, which
           is the 037 state and the row the format exists for `[ref: PRD/F4]`
     - [x] No read-only decision appears `[ref: PRD/F4]`
     - [x] A malformed row fails Tomo's tests, proved by an executed test named
           by node id — not by the schema's mere existence `[ref: PRD/F4]`

  **Expect this task to produce a finding, not just a file.** 23 schema fields
  against 34 distinct `parser_label` literals means some editable wire fields have
  no markdown control and some controls may have no row anyone knew about. Record
  every discrepancy in the task's report rather than resolving it silently — it
  may change Phases 2–4, and it is the reason this phase is first.

- [ ] **T1.1b The schema stops under-reporting, and the join gains a key** `[activity: data-architecture]`

  1. Prime: read the `candidate_mocs[].selected` and `.anchor` descriptions in
     `tomo/schemas/suggestions-wire.schema.json`, and the format the other 21 use
     — `"Editable — <prose>"`. Read `build_from_wire`'s `candidate_mocs` loop,
     which honours `selected` (it skips unselected entries) and `anchor`. Read the
     inventory and its schema as T1.1 left them.
  2. Test: `parser_label`'s constraints get rejection tests in
     `tests/test_038_inventory_schema_validation.py`, one per constraint, each
     demonstrated by executed ablation. That file's docstring claims **every**
     declared constraint has its own rejection test, and T1.1's re-review made the
     claim true exhaustively across all 18 keywords. Adding a constrained property
     without its tests falsifies it again `[ref: PRD/F4]`.
  3. Implement:
     a. Prepend the `Editable — ` marker to `candidate_mocs[].selected` and
        `.anchor`. Both are honoured by the rebuild path but carry no marker, so
        ADR-7's schema-side join is structurally blind to them — the blind spot
        this spec exists to end. Owner ruling 2026-09-30.
     b. Add `parser_label` to the inventory schema and every row: the literal the
        parser matches on. It is **many-to-one** — `time`, `position` and
        `content` come from one log-entry line, and the three `accepted` fields
        share one checkbox. A row at `editable: false` has no control by
        definition, so the schema must permit the label's absence, or the field
        breaks the exemption `editable: false` exists to carry. Owner ruling
        2026-09-30.
     c. Rewrite D22/D23/D24's `note` self-contained: no task, phase, feature or
        spec identifiers. The file is vendored by a consumer who cannot resolve
        them. D22/D23's current text stops being true the moment (a) lands.
  4. Validate: full suite and `ruff`. **15 test files reference
     `suggestions-wire.schema`** — if any pins description text or hashes the file,
     report it rather than working around it. Then, concretely:
     - A **committed** test asserts `suggestions-wire.schema.json` carries exactly
       **23** `Editable`-marked descriptions. This is not redundant with T1.2's
       join: the join requires *marked field → row*, so **removing** a marker is
       silent — the requirement simply disappears, the orphaned row still
       satisfies the parser-side direction, and nothing fails. This assertion is
       the only thing that catches a deleted marker. Do not remove it later as
       duplicate coverage.
     - A **committed** test asserts no `note` value carries a task, phase, feature
       or spec identifier. Prove it bites by inserting such a string and watching
       it fail. A manual read would be "a rule someone has to remember", which is
       the mechanism `[ref: SDD/ADR-7]` names as what failed in 037 — and this file
       is hand-maintained, so the next row added is exactly where jargon returns.
     - The inventory validates against its schema, which is what catches a row
       missing `parser_label` where one is required.
     - Report the **count of distinct `parser_label` values**. That measured number
       replaces the plan's "~7 recognised controls" estimate — a count, not an
       estimate.
     - Execute the ablations from step 2 and report which constraint each test
       proved, by pytest node id.
  5. Success:
     - [ ] `selected` and `anchor` carry the marker, so the schema-side join sees
           them `[ref: PRD/F4]`
     - [ ] Every row carries `parser_label`; its absence is permitted only at
           `editable: false` `[ref: PRD/F4]`
     - [ ] Each constraint `parser_label` adds has a rejection test whose bite was
           demonstrated by executed ablation
     - [ ] No `note` value references a task, phase, feature or spec id, proved by
           a **committed** test whose bite was demonstrated — not by a manual read
     - [ ] A **committed** test pins the marked-field count at 23, catching a
           deleted marker, which T1.2's join structurally cannot
     - [ ] The plan's counts are corrected — 23 marked fields, and a measured
           count of distinct `parser_label` values replaces "~7 recognised
           controls"

  **Two backlog entries this task also writes**, to `docs/XDD/backlog.md`:
  - `classification` is parsed but **unreachable from the review surface**: no
    renderer emits the line, and field lines are emitted literally rather than
    from a generic emitter, so the value is always `None`. It is not an editable
    decision and owes no wire field. Recorded so the next reader does not
    re-derive it.
  - The `type` field line has no `suggestions-wire` counterpart and was not
    traced. Open question, lower confidence than `classification`.

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
