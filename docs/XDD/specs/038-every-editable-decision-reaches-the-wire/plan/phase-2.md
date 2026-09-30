---
title: "Phase 2: The wire carries the decision"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: The wire carries the decision

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/F1]` — seven acceptance criteria, each naming which wire and which path
- `[ref: SDD/ADR-1]` — the supersession and the version move
- `[ref: SDD/ADR-2]` — top-level array, not per-suggestion
- `[ref: SDD/ADR-3]` — carry what the consumer cannot derive
- `[ref: SDD/ADR-8]` — `attachments` becomes required
- `[ref: SDD/Runtime View; Primary Flow — Pass 2, wire path]`
- `[ref: SDD/Risks and Technical Debt; Known Technical Issues]`

**Key Decisions**:
- The version move touches **three** artefacts and a half-finished move **fails
  silently** — `load_changed_wire` falls back to the markdown with only a stderr
  warning `[ref: SDD/CON-2]`. This is the single most important risk in the spec.
- The array carries `source`, `destination`, `same_file`, `remedy`,
  `proposed_name`. It does **not** carry the owning notes `[ref: SDD/ADR-3]`.
- `remedy` defaults exactly the way the markdown pre-ticks: `rename` when a free
  name was found, otherwise `keep_in_inbox` `[ref: PRD/F1]`.

**Dependencies**: Phase 1 complete (its discrepancy list may add rows that affect
the inventory's remedy row). Nothing in Phases 3–4.

---

## Tasks

Delivers the fix for the measured data-loss path: a remedy chosen by the owner
survives Pass 2's JSON-only rebuild.

- [ ] **T2.1 The schema move, all three artefacts at once** `[activity: data-architecture]`

  1. Prime: read `tomo/schemas/suggestions-wire.schema.json`, its
     `hashi-` sibling, `tomo/schemas/shapes/suggestions-wire.shape.json`, and
     `tomo/scripts/lib/wire_gate.py`'s `classify()` (`:582-725`) to understand why
     an added property on a closed node forces `ACTION_MOVE_VERSION`
     `[ref: SDD/ADR-1]`.
  2. Test: a test asserting all three artefacts agree on `schema_version` and on
     the presence of `attachment_conflicts`. Make it red by moving only one.
  3. Implement: add the top-level `attachment_conflicts[]` array with the five
     fields; add `attachments` to `suggestions[].items.required`
     `[ref: SDD/ADR-8]`; move `schema_version` `2` → `3` in the live schema and
     the vendored copy; regenerate the shape manifest with `wire_shape.py`'s CLI.
  4. Validate: the wire gate passes; the drift test from step 2 is green; a
     deliberately half-finished move turns it red.
  5. Success:
     - [ ] All three artefacts carry `schema_version: "3"` `[ref: PRD/F1]`
     - [ ] A half-finished move fails the gate rather than shipping quietly
           `[ref: SDD/Acceptance Criteria]`
     - [ ] `attachments` is required `[ref: SDD/ADR-8]`
     - [ ] The instructions wire is untouched `[ref: PRD/F1]`

- [ ] **T2.2 Project the conflict onto the wire** `[activity: backend-api]`

  1. Prime: read `build_wire_payload` (`suggestions-render.py:422`) and `_wire_note`
     (`:293`), and `detect_attachment_conflicts`'s output shape
     (`suggestions-reducer.py:582`, records written at `:2884`).
  2. Test: a conflict run's wire carries the array with the remedy defaulted as the
     markdown pre-ticks; a conflict-free run carries an empty array; an attachment
     embedded by several notes produces **one** entry `[ref: PRD/F1]`.
  3. Implement: project `d.get("attachment_conflicts")` into the payload. The
     source is the same structured record the markdown block already renders from —
     computed once, rendered twice, **no second vault call** `[ref: SDD/Cross-Cutting Concepts; Cost]`.
  4. Validate: `emit_digest` covers the new field automatically (it hashes the
     payload minus itself) — confirm rather than assume.
  5. Success:
     - [ ] The wire carries remedy, source, destination, `same_file`, `proposed_name` `[ref: PRD/F1]`
     - [ ] One entry per attachment however many notes embed it `[ref: PRD/F1]`
     - [ ] The owning notes are **not** carried `[ref: PRD/F1]`
     - [ ] No additional vault interaction `[ref: SDD/Cost]`

- [ ] **T2.3 Read the conflict back from the wire** `[activity: backend-api]`

  1. Prime: read `build_from_wire` (`suggestion-parser.py:325`) and the hardcoded
     `"attachment_conflict_remedies": []` at `:492` with its comment — the comment
     states the premise correctly and stops there, which is the defect in one line.
  2. Test: **three existing tests change together, by design.**
     `tests/test_037_remedy_lost_on_the_wire_path.py`'s strict xfail
     (`test_the_wire_path_carries_the_chosen_remedy_too`) flips to passing, and the
     two tests recording today's wrong answers are **deleted**
     (`test_the_wire_path_returns_an_empty_list_today`,
     `test_losing_the_remedy_silently_produces_the_ignore_outcome`). The file's own
     docstring predicts `4 passed, 1 xfailed` → `3 failed`; that transition is the
     signal the change works `[ref: SDD/Implementation Gotchas]`.
  3. Implement: replace the `[]` with a projection producing the same
     `{source, remedy, proposed_name}` triple the markdown path yields.
  4. Validate: the two baseline tests in that file stay green; remove the xfail
     marker rather than leaving a passing xfail.
  5. Success:
     - [ ] The wire path and the markdown path return identical triples for
           identical decisions `[ref: PRD/F1]`
     - [ ] The strict xfail is **removed**, not left passing `[ref: SDD/Implementation Gotchas]`
     - [ ] The two defect-recording tests are deleted with it

- [ ] **T2.4 Update the golden fixtures** `[activity: testing]`

  1. Prime: read `tests/test_suggestions_wire_golden.py` (hand-built full payload
     dicts, e.g. `:115-236`) and `tests/test_wire_snapshot_parity.py` (`:238`,
     `:262`). These are **mechanical, multi-site, and easy to half-finish**
     `[ref: SDD/Known Technical Issues]`.
  2. Test: the conflict-free golden comparison must show **only** the version
     stamp and an empty `attachment_conflicts` array as differences — capture the
     pre-change payload as the comparison target rather than asserting "unchanged"
     against nothing.
  3. Implement: add the key to every fixture that builds a full payload; update
     the expected `schema_version`.
  4. Validate: full suite green; the offline schema-vs-vendored comparison passes;
     the network upstream comparison is a report and may skip.
  5. Success:
     - [ ] Conflict-free runs differ only by the version stamp and an empty array,
           against a **captured** target `[ref: SDD/Acceptance Criteria]`
     - [ ] No fixture left half-updated — the suite is the check

- [ ] **T2.5 Phase validation** `[activity: validate]`

  - Run the full suite and `ruff`. Verify the wire gate's classification is
    `ACTION_MOVE_VERSION` + `ACTION_HANDOVER` and that the handover obligation is
    recorded for Phase 5 rather than discharged here.
  - **Prove the wire path is still taken.** Generate a run, edit its wire, and
    confirm Pass 2 rebuilds from it — because a mismatched version falls back to
    the markdown *without erroring*, a green suite alone does not prove this
    `[ref: SDD/CON-2]`.
  - Success: suite green; `ruff` clean; the wire path demonstrably taken after the
    version move `[ref: PRD/F1]`.
