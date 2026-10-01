---
title: "Phase 2: The wire carries the decision"
status: in_progress
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
- The version move touches **two** artefacts — the live schema and the shape
  manifest. The vendored `hashi-` copy is **not** touched here: it records what the
  consumer actually vendors, and spec 035's move (`4338481`) updated it only in a
  later commit (`f63b947`), once Hashi had confirmed. Writing the new version there
  now would make the parity report claim the consumer is current while their real
  copy still pins the old one and rejects every document we emit `[ref: SDD/CON-1]`.
- The manifest carries the version at **two internal sites** —
  `nodes["/"].values.schema_version` and the top-level `schema_version`. Both are
  written by `scripts/wire-shape.py --regenerate`; hand-editing one is the
  half-finished move in its most literal form.
- **CON-2's silent fallback cannot originate in code.** Spec 035's ADR-5 made the
  emitter (`suggestions-render.py:507`) and the reader (`suggestion-parser.py:270`)
  both derive the expected version from the schema via `wire_schema_version`, so the
  two can no longer diverge. What survives is a **stale wire file on disk** emitted
  at the old version, and **fixtures** pinning it. A live proof must therefore
  regenerate the run *after* the move rather than reuse an existing wire
  `[ref: SDD/CON-2]`. This is still the most important risk in the spec — its
  mechanism is just not the one this plan first named.
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

- [x] **T2.1 The schema move, both artefacts at once** `[activity: data-architecture]`

  1. Prime: read `tomo/schemas/suggestions-wire.schema.json`, its
     `hashi-` sibling, `tomo/schemas/shapes/suggestions-wire.shape.json`, and
     `tomo/scripts/lib/wire_shape.py`'s `classify()` (`:582-725` — **not**
     `wire_gate.py`, which is 522 lines and merely re-exports it at `:48`) to
     understand why an added property on a closed node forces
     `ACTION_MOVE_VERSION` `[ref: SDD/ADR-1]`.
  2. Test: a test asserting the live schema and the shape manifest agree on
     `schema_version` and on the presence of `attachment_conflicts`, and that the
     manifest agrees with itself across both of its version sites. Make it red by
     moving only one.
  3. Implement: add the top-level `attachment_conflicts[]` array with the five
     fields **and add it to the schema's top-level `required`** — `tag_handler_groups`,
     `proposed_mocs` and `daily_updates` are all required-and-may-be-empty, and
     T2.2's conflict-free-run assertion is only enforceable if this one is too; add
     `attachments` to `suggestions[].items.required` `[ref: SDD/ADR-8]`; move
     `schema_version` `2` → `3` in the live schema **only**; regenerate the shape
     manifest with `scripts/wire-shape.py --regenerate` (the CLI is at
     `scripts/`, not under `tomo/scripts/lib/`). Leave
     `hashi-suggestions-wire.schema.json` untouched — Phase 5 owns it.
     **Fourth artefact, consequent on leaving the vendored copy alone:**
     `tests/test_wire_snapshot_parity.py`'s
     `test_suggestions_comparison_a_is_clean_offline` (`:689`) asserts
     `reportable == []` and **will fail** — measured: the change produces
     **six** reportable entries (`added_enum_value '3'`,
     `removed_enum_value '2'`, `added_property attachment_conflicts`,
     `required_added attachment_conflicts`,
     `node_added /properties/attachment_conflicts/items`,
     `required_added attachments`). Re-measure that expectation to the new
     delta, following the instruction its own docstring carries forward —
     "re-measure and update rather than treat a changed delta as a defect".
     Precedent: this test has already stood at **eight** while awaiting the
     consumer (it went 0 → 8 → 0 across spec 035), under requirements.md's
     Rule 7. **Do NOT reach for `SANCTIONED_ASYMMETRIES`**: its own comment
     restricts it to "a standing cross-repo decision, not a lag awaiting a
     handoff", and `test_wire_snapshot_parity.py:810` pins the mapping to
     exactly `{"hashi-instructions.schema.json"}` on the stated ground that
     an exclusion on this wire "hides drift instead of scoping the
     comparison".
  4. Validate: `scripts/wire-shape.py --check` exits 0 and `--obligations` reports
     no drift once the manifest is regenerated — **measured**: property added +
     version moved + manifest regenerated yields `passed=True, actions=[]`. The
     drift test from step 2 is green; a deliberately half-finished move turns it
     red.
  5. Success:
     - [ ] The live schema and the shape manifest carry `schema_version: "3"`,
           both manifest sites included; the vendored copy still reads `"2"`
           `[ref: PRD/F1]`
     - [ ] `attachment_conflicts` is in the schema's top-level `required`
     - [ ] The vendored-parity expectation is re-measured to the six-entry
           delta, and `SANCTIONED_ASYMMETRIES` is unchanged
     - [ ] A half-finished move fails the gate rather than shipping quietly
           `[ref: SDD/Acceptance Criteria]`
     - [ ] `attachments` is required `[ref: SDD/ADR-8]`
     - [ ] The instructions wire is untouched `[ref: PRD/F1]`

- [ ] **T2.1b The inventory catches up with the field it predicted** `[activity: data-architecture]`

  Moved from Phase 5 (was T5.2) by owner ruling 2026-10-01, and **widened by
  measurement**: T5.2's text covered only the remedy row, but T2.1 added **two**
  editable wire fields, so the marked count went `23` → `25` while 23 rows carry a
  non-null `wire_field`. Phase 1's join is red, correctly, and would have stayed
  red through Phases 3 and 4 — against three phase gates that each demand a green
  suite. Its only prerequisite, the wire field existing, is now satisfied.

  1. Prime: read `tomo/schemas/suggestions-decision-inventory.json` — especially
     **D24**, whose own note already predicted this: "The remedy has no wire field
     yet; expected to gain one once the wire is extended to carry it." Read the new
     `attachment_conflicts` node in `tomo/schemas/suggestions-wire.schema.json` and
     `_assert_schema_side_join` (`tests/test_038_decision_inventory_join.py:317`).
  2. Test: the join test is **already red** — `25 schema field(s) marked Editable
     but only 23 inventory row(s) carry a non-null wire_field`. That is this task's
     RED state and it arrived on its own; do not manufacture another. Observe the
     red → green transition rather than assuming it.
  3. Implement:
     - **D24**: `wire_field` `null` → the remedy's path; rewrite the note so it
       records that the prediction came true rather than still predicting.
     - **A new row** for `attachment_conflicts[].proposed_name`, `editable: true`.
       Its `parser_label` may name the control Phase 4's T4.2 will implement — the
       parser-side join runs literal → row only (`_assert_parser_side_join`), so a
       row whose label is not yet harvestable violates nothing. Verify that claim
       in the code before relying on it.
     - **Both count guards**, updated and not collapsed:
       `FLOOR_SCHEMA_MARKED_FIELDS` (`:117`) `23` → `25`, its explanatory text at
       `:78-79`, and the arithmetic at `:563`/`:568`; and
       `test_wire_schema_marks_exactly_23_editable_fields` in
       `tests/test_038_inventory_schema_validation.py`, renamed to its new number.
     - Check whether the inventory's own top-level `schema_version` (currently `1`)
       is obliged to move for an added row. The file is **vendored by Hashi** —
       state the answer either way rather than leaving it unexamined.
  4. Validate: both `test_038_*` files fully green; `scripts/wire-shape.py --check`
     still exits 0. Then **prove the two guards still bite**: delete one `Editable`
     marker and confirm the `== 25` test fails; reword one and confirm the floor
     test fails. Neither mutation may leave both green `[ref: README/A standing
     warning carried forward from spec 037]`.
  5. Success:
     - [ ] D24 names its wire field, and its note no longer predicts `[ref: PRD/F4]`
     - [ ] `proposed_name` has a row `[ref: PRD/F4]`
     - [ ] The join passes in both directions again
     - [ ] Both count guards updated to `25`, neither removed, **both demonstrated
           still able to fail** by executed mutation
     - [ ] The inventory's `schema_version` question is answered in the commit message

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

  - Run the full suite and `ruff`. **Measured correction to this task as first
    written**: the gate's `ACTION_MOVE_VERSION` + `ACTION_HANDOVER` verdict is
    reachable ONLY while the version has not moved. With T2.1 done the gate returns
    `passed=True, actions=[]`, so chasing the original wording would require leaving
    the move half-finished — the very CON-2 failure this phase exists to prevent.
    Verify instead: `--check` clean on the repo, and `move_version` + `handover`
    reproduced on a **scratch copy** with the version held back, as the
    half-finished-move guard. The handover obligation is recorded for Phase 5 by
    hand — the gate stops emitting it once the move is complete.
  - **Record for Phase 5**: the live-vs-vendored comparison is structural only
    (`snapshot_parity_delta` ignores `description`), so three already-divergent
    descriptions — `candidate_mocs[].selected`, `candidate_mocs[].anchor` and
    `proposed_mocs[].tags` — are invisible to every test in the suite and must ride
    the handoff explicitly alongside the **six** reportable structural
    entries — measured, and two more than a first reading suggests, because
    the version move itself contributes both `added_enum_value '3'` and
    `removed_enum_value '2'`.
  - **Prove the wire path is still taken.** Generate a run **after** the version
    move so its wire carries `"3"`, edit that wire, and confirm Pass 2 rebuilds from
    it. A wire generated before the move carries `"2"`, mismatches, and falls back
    to the markdown with only a stderr warning — so reusing an existing wire would
    demonstrate the opposite of what this step claims, and a green suite proves
    nothing either way `[ref: SDD/CON-2]`. Run against `--instance tomo-instance`
    (**never** `tomo-privat`, which is live).
  - **Sync the instance first, and verify it.** Measured 2026-10-01:
    `tomo-instance/schemas/suggestions-wire.schema.json` still declares `"2"` after
    T2.1, because the instance holds its own copy. Both the emitter and the reader
    inside the instance resolve `wire_schema_version` against *that* copy, so they
    agree with each other at the OLD version — a live run would take the wire path,
    look correct, and prove nothing about the move. Run `scripts/update-tomo.sh`
    and then `grep` the instance's schema to confirm it reads `"3"` before
    generating the run. Schemas are compared **bytewise** there, not gated on a
    `# version:` header (`scripts/update-tomo.sh:308`, `:500-503`), so the sync does
    carry this change — but confirm it rather than assume it.
  - Success: suite green; `ruff` clean; the wire path demonstrably taken after the
    version move `[ref: PRD/F1]`.
