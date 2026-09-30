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
     in `tomo/schemas/suggestions-wire.schema.json` — there were **21** when this
     task ran; T1.1b marks two more, so a reader arriving later finds **23**
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

  **This task was expected to produce a finding, not just a file, and it did.**
  The expectation rested on 21 marked schema fields against a parser whose controls
  were merely *estimated* at "about seven" — a gap wide enough that something had
  to be unaccounted for. Both figures have since been measured and neither is what
  it was, so the original arithmetic is retired rather than restated: the marked
  count is now 23, and the parser side is 34 distinct label literals, which is a
  different unit and not comparable to it.

  What the task actually surfaced is recorded in the deviation table and the
  backlog rather than resolved silently — including two fields the schema-side join
  was blind to, which added T1.1b to this very phase. That is the clearest evidence
  for why this phase is first.

- [x] **T1.1b The schema stops under-reporting, and the join gains a key** `[activity: data-architecture]`

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
     - [x] `selected` and `anchor` carry the marker, so the schema-side join sees
           them `[ref: PRD/F4]`
     - [x] Every row carries `parser_label`; its absence is permitted only at
           `editable: false` `[ref: PRD/F4]`
     - [x] Each constraint `parser_label` adds has a rejection test whose bite was
           demonstrated by executed ablation
     - [x] No `note` value references a task, phase, feature or spec id, proved by
           a **committed** test whose bite was demonstrated — not by a manual read
     - [x] A **committed** test pins the marked-field count at 23, catching a
           deleted marker, which T1.2's join structurally cannot
     - [x] The plan's counts are corrected — 23 marked fields, and a measured
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
  3. Implement: `tests/test_038_decision_inventory_join.py`, joining to rows
     through **`parser_label`** — the array T1.1b added for exactly this. Do not
     join on prose, and do not join on `wire_field`: D24's is `null`.

     **Schema side**: walk the wire schema for descriptions beginning
     `Editable — `. Floor the enumeration at **23**.

     **Parser side**: extract the literals with Python's stdlib `ast`, filtering
     by **what is being compared**, not by which function it sits in. Harvest
     string constants where the other operand is one of the parser's control
     subjects — `text_lower`, `key`, `label`, `cb_text`, `text`, `stripped` — in
     the shapes `"x" in text_lower`, `key == "x"`, `key in ("x", "y")` and
     `label.startswith("x")`. Floor the harvest at **61**.

     **These numbers are measured, not estimated** (2026-09-30). The subject
     filter harvests **61** literals; the inventory carries **34**. Do not
     "correct" either number to make them agree — they are not supposed to.

     Every harvested literal must be **either** in some row's `parser_label`
     **or** in an explicit justified-absence list carrying a stated reason. That
     is the consumer's own pattern and it fails **closed**: a newly added control
     literal is in neither, so the test goes red with nobody remembering anything.
     Owner ruling 2026-09-30.

     The **31** currently-absent literals fall into three groups, so express the
     list as rules plus a few specifics rather than 31 hand-written entries:
     structural markers (anything starting with `#` or `**`, plus field-line
     labels like `- Source:`), option values that are not control labels
     (`keep`, `preserve`, `behalten`, `related`), and **read-only field keys** —
     `summary`, `classification`, `source`, `type`, `attachments`. That last group
     is the reassuring one: the harvest is correctly finding non-editable fields,
     including the dead `classification` branch this phase recorded in the backlog.

     Rejected alternatives, recorded so they are not revisited: a hand-written
     literal list (a control added to the parser and not to the list fails
     nothing, which makes this criterion theatre); regex over the source (misreads
     multi-line calls, fails confusingly rather than loudly); scoping the walk to
     named control-recognition functions (**measured**: still ~70 literals, so
     function scope is not what removes the noise); and an advisory parser side
     that only checks rows against the source (concedes the direction ADR-7 built
     the two-sided join for).

     **A row with `editable: false` is exempt from the parser-side join** — that
     is what a retired control is, and without the exemption the test would reject
     exactly the row the column exists to carry `[ref: PRD/F4]`.
  4. Validate: full suite green; both mutations (remove a row; add an `Editable`
     field to the schema without a row) turn it red — **run them, do not assert
     that they would** `[ref: plan/README.md; the standing warning]`.
  5. Success:
     - [ ] A schema field marked `Editable` with no row fails the test `[ref: PRD/F4]`
     - [ ] A parser-recognised control with no row fails the test `[ref: PRD/F4]`
     - [ ] A retired control's row survives at `editable: false` and does **not**
           fail the parser-side join — the one case where a row legitimately has
           no control `[ref: PRD/F4]`
     - [ ] **The exemption cannot go stale**: a row at `editable: false` whose
           parser control still exists fails the test. Without this, a row marked
           retired while its control is alive stays exempt, and the consumer is
           told to delete a control that still works — the exact opposite of what
           the column exists to say `[ref: PRD/F4]`
     - [ ] **The join cannot pass vacuously**: the test pins a floor on its own
           schema-side enumeration, so a reworded marker fails loudly instead of
           matching nothing and satisfying every assertion below it
     - [ ] Every failure mode above demonstrated by executed mutation, named in
           the task report by node id

     Two notes on the criteria above, both from the TDD guardian's audit:

     - **Criteria 3 and 4 are exercised on synthetic rows, and the docstring must
       say so.** No row currently has `editable: false`, so both the exemption and
       its staleness guard can only run against fabricated data. Name what each
       fixture models: one row retired with its control genuinely gone, which must
       pass the join; one row retired while its control is still live, which must
       fail it. They model future rows that do not exist yet, and that is the
       point of writing them now rather than when the first control is retired.
     - **The schema-side floor here is not redundant with T1.1b's exact count.**
       `test_wire_schema_marks_exactly_23_editable_fields` asserts `== 23` and
       catches a marker being **deleted**. This test's `>= 23` floor catches the
       enumeration **silently matching nothing** after a reword. Different
       mutations, different files, either deletable alone. Both must remain.

  **Where these two extra criteria came from.** Both are the consumer's, read off
  their own guard during Phase 1. Their fourth test keeps their justified-absence
  list honest — an entry that *does* have a control fails — and ours had no mirror
  of it. And their detection guard pins `expect(editableFields.length)
  .toBeGreaterThanOrEqual(8)` under a comment naming the risk outright: *"If Tomo
  rewords 'Editable — …' the filter above silently matches nothing and every
  assertion below passes vacuously."* That is this spec's signature failure mode,
  anticipated by the consumer, in the test we are mirroring.

  **Two known limitations to state in the test's own docstring, not to fix:**
  - It catches a *missing* row, not a *wrong* one. A row whose `wire_field` names
    the wrong path passes. The consumer's join catches that from the other side
    `[ref: SDD/ADR-7 trade-offs]`.
  - It catches a newly added **literal-matched** control, not a pattern-matched
    one. Owner ruling 2026-09-30. Concretely: `RE_DAILY_LOG_LINE` matches one line
    and yields time, position and content together, so `"—"` keys D14, D15 and D16
    identically. A fourth decision added to that same line would find `"—"`
    already has rows and the join would stay green. State that sentence, not the
    general form — it names the exact mutation that slips through.
  - **Four row labels cannot be harvested by any AST filter**, measured
    2026-09-30: `—` lives inside a regex rather than a comparison;
    `after_last_line` and `before_first_line` are set-membership against a
    module-level constant; `force atomic note` is compared through
    `cb.group(1).lower()`, a call chain rather than a plain name. All four are
    already in rows, and the join requires harvested-literal → row, not the
    reverse, so they cause no failure. They are simply **not guarded** by the
    parser-side direction. Say that in the docstring; do not contort the
    extraction to reach them.

- [ ] **T1.3 Phase validation** `[activity: validate]`

  - Run the full suite and `ruff`. Confirm the inventory validates against its own
    schema. Report every discrepancy T1.1 surfaced as a list, with a recommendation
    for each: in scope for this spec, or a backlog entry. **Do not resolve them in
    this phase** — they are input to a scope decision, not work to absorb quietly.
  - Success: suite green; `ruff` clean; the discrepancy list exists and each item
    has a recommendation `[ref: PRD/F4]`.
