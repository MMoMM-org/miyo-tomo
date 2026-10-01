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

- [x] **T2.1b The inventory catches up with the field it predicted** `[activity: data-architecture]`

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
       `:78-79`, and the docstring arithmetic at `:563` ("drops from 23 to 22" →
       `25` to `24`); and `test_wire_schema_marks_exactly_23_editable_fields` in
       `tests/test_038_inventory_schema_validation.py`, renamed to its new number.
       **`FLOOR_SCHEMA_MARKED_FIELDS` is not a loose floor** — despite the name and
       the `>=` comparison, `test_injection_e_reworded_marker_breaches_the_floor`
       opens with the premise `marked_before == FLOOR_SCHEMA_MARKED_FIELDS` and its
       failure message says so outright: "a schema change moved the count out from
       under this injection; pick a fixture that actually sits on the floor, rather
       than loosen the pin". The floor must equal the exact marked count or that
       injection stops testing anything, so a floor left lagging at `23` does not
       merely under-constrain — it breaks the injection's premise. Verified by
       reading `:563-580`.
     - **Arithmetic, verified 2026-10-01** so it is not re-derived: 23 rows are
       backed now; D24 moving off `null` makes 24; one new row makes **25**, which
       equals the marked count. No existing row names `attachment_conflicts`, so
       exactly one row is added, not two.
     - The inventory's own `schema_version` **stays `1`** — settled 2026-10-01, not
       a judgement call: `suggestions-decision-inventory.schema.json` declares
       `"schema_version": {"const": 1}`, so any other value fails the row guard. An
       added row cannot move it without changing the guard schema too, which this
       task does not do. Restate this in the commit message; do not re-investigate.
  4. Validate: both `test_038_*` files fully green; `scripts/wire-shape.py --check`
     still exits 0. Then **prove the two guards still bite** — and for the deletion
     half, leave an artefact behind:
     - **Rewording is already owned** by
       `test_038_decision_inventory_join.py::test_injection_e_reworded_marker_breaches_the_floor`.
       Confirm it still passes at the new number; nothing new is needed.
     - **Deletion is NOT owned.** `test_wire_schema_marks_exactly_23_editable_fields`
       asserts against `WIRE_SCHEMA_PATH` — the real file — and its docstring claims
       "a future marker removed from the wire schema … would otherwise pass every
       other test in this file" while **nothing executes that claim**. That is the
       shape of spec 037's nine unbiteable mutations
       `[ref: README/A standing warning carried forward from spec 037]`. Add a
       committed injection test: deepcopy the wire schema, delete one
       `Editable`-marked description, write it to `tmp_path`, and assert the count
       guard fails on it — never mutating the committed file. Mirror
       injection-e's structure, including a `match=` pin so it is the intended
       assertion that fires and not an incidental one.
     - Neither mutation may leave both guards green.
  5. Success:
     - [ ] D24 names its wire field, and its note no longer predicts `[ref: PRD/F4]`
     - [ ] `proposed_name` has a row `[ref: PRD/F4]`
     - [ ] The join passes in both directions again
     - [ ] Both count guards updated to `25`, neither removed, **both demonstrated
           still able to fail** by executed mutation
     - [ ] The deletion mutation is owned by a **committed** injection test, not a
           one-off run — the count guard's docstring claim is executed, not asserted
     - [ ] The commit message restates why the inventory's `schema_version` stays `1`

- [x] **T2.2 Project the conflict onto the wire** `[activity: backend-api]`

  1. Prime: read `build_wire_payload` (`suggestions-render.py:422`) and `_wire_note`
     (`:293`), and `detect_attachment_conflicts`'s output shape
     (`suggestions-reducer.py:582`, records written at `:2884`).
  2. Test: a conflict run's wire carries the array with the remedy defaulted as the
     markdown pre-ticks; a conflict-free run carries an empty array; an attachment
     embedded by several notes produces **one** entry `[ref: PRD/F1]`.
  3. Implement: project `d.get("attachment_conflicts") or []` into the payload —
     **the `or []` is load-bearing, not defensive style.** The reducer writes
     `doc["attachment_conflicts"]` **omit-when-empty**
     (`suggestions-reducer.py:2884`, `if attachment_conflicts:`), deliberately, so
     that a conflict-free run renders byte-identically to a pre-037 run. The
     suggestions-doc schema therefore does **not** require the key, while T2.1 made
     the wire field **required**. Measured: on a conflict-free run
     `d.get("attachment_conflicts")` is `None`, and projecting that bare emits
     `null` into a field the schema requires to be an array — the wire would fail
     its own validation on exactly the runs that are supposed to be unaffected.
     The asymmetry is intentional and worth stating in the code: the **doc** omits
     the key when empty, the **wire** always carries the array.
     The source is the same structured record the markdown block already renders
     from — computed once, rendered twice, **no second vault call**
     `[ref: SDD/Cross-Cutting Concepts; Cost]`.
  4. Validate: `emit_digest` covers the new field automatically — **already
     confirmed 2026-10-01, do not re-derive**: `compute_payload_digest`
     (`lib/render_md.py:383`) builds
     `{k: v for k, v in payload.items() if k != "emit_digest"}` over the whole
     payload, so any new top-level key is included by construction. Confirmed by
     reading the function rather than by observing a digest change, which would
     not distinguish "covered" from "coincidentally different".
     Then confirm the conflict-free path: a run with no conflicts must produce
     `attachment_conflicts: []` and still validate against the wire schema.
  5. Success:
     - [ ] The wire carries remedy, source, destination, `same_file`, `proposed_name` `[ref: PRD/F1]`
     - [ ] One entry per attachment however many notes embed it `[ref: PRD/F1]`
     - [ ] The owning notes are **not** carried `[ref: PRD/F1]`
     - [ ] No additional vault interaction `[ref: SDD/Cost]`
     - [ ] A conflict-free run emits `[]`, not `null`, and validates

- [x] **T2.3 Read the conflict back from the wire** `[activity: backend-api]`

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
     **One assertion inside the second test must be REHOMED, not deleted with it.**
     Its closing two assertions pin a behaviour that **survives** this fix: an
     *explicit* `remedy: "ignore"` leaves the `move_asset` destination at the
     occupied path and records nothing as skipped. Measured 2026-10-01 — nothing
     else in the suite pins that. `test_037_t3_3_embed_rewrite.py:168`
     (`test_non_rename_remedies_leave_the_body_unchanged`) covers `ignore` only for
     "the body is unchanged", and a grep for a move-destination assertion under
     `ignore` returns nothing. `ignore` stays reachable after the fix — the schema
     enum keeps it and `_resolve_attachment_remedy` (`suggestion-parser.py:2234`)
     returns it for specific tick combinations — so this is live behaviour, not
     defect residue. Write it as its own small test before deleting the host:
     explicit `ignore` ⇒ destination is the occupied path, `skipped == []`. The
     tdd-guardian reviewed this task and approved the deletion as safe; it read the
     test's first three assertions and not its last two.
  3. Implement: replace the `[]` with a projection producing the same
     `{source, remedy, proposed_name}` triple the markdown path yields.
  4. Validate: the two baseline tests in that file stay green; remove the xfail
     marker rather than leaving a passing xfail.
     **Then sweep the claim this task falsifies.** "The wire carries no
     Attachment-Conflicts data at all" is asserted in four places, and only two of
     them are files this task already opens — a diff-scoped review cannot see the
     other two, which is why they are listed here rather than left to be noticed:
     - `tomo/scripts/suggestion-parser.py:487-491` — the comment above the
       hardcoded `[]`. Rewritten by step 3 anyway; make sure the replacement does
       not keep the premise.
     - `tests/test_037_remedy_lost_on_the_wire_path.py:18` — the file's own
       docstring, in the file this task edits.
     - **`docs/tomo/scripts/suggestion-parser.md:1037-1041`** — the WHY-persistence
       layer for the file step 3 changes. It currently says the `[]` "is the honest
       and complete answer for a path where the question does not apply". After this
       task the question applies, so that passage becomes actively false. **No
       Phase 2 task mentioned `docs/tomo` before this amendment** (Phases 3 and 4
       do), so the WHY layer for both of Phase 2's production changes was unowned —
       T2.2's `suggestions-render.py` change included. Update this file for the
       parser change, and add the `build_wire_payload` projection to
       `docs/tomo/scripts/suggestions-render.md`, which documents that function and
       does not yet mention `attachment_conflicts`.
     - `docs/XDD/specs/037-…/solution.md:217` — a **shipped** spec's SDD. Do not
       rewrite its history; 038's ADR-1 already records that it supersedes 037's
       ADR-5. Add a one-line supersession pointer so a reader arriving at 037 is
       told the claim no longer holds. Measured: that file currently contains zero
       references to `superseded` or to 038.
  5. Success:
     - [ ] The wire path and the markdown path return identical triples for
           identical decisions `[ref: PRD/F1]`
     - [ ] The strict xfail is **removed**, not left passing `[ref: SDD/Implementation Gotchas]`
     - [ ] The two defect-recording tests are deleted with it
     - [ ] The explicit-`ignore` move-destination assertion is **rehomed** to its
           own test before its host is deleted, and that test fails if the
           behaviour changes — demonstrated, not assumed
     - [ ] All four sites asserting "the wire carries no Attachment-Conflicts
           data" are swept, including both `docs/tomo/` WHY files and a
           supersession pointer in 037's SDD

- [ ] **T2.4 A captured baseline, since the fixture sweep is already done** `[activity: testing]`

  **Premise replaced by measurement, owner ruling 2026-10-01.** This task was
  written as "add the key to every fixture that builds a full payload; update the
  expected `schema_version`". Measured after T2.2: there is nothing left to sweep,
  and the file the task named does not do what the task assumed.
  - `tests/test_suggestions_wire_golden.py` builds **no** wire payloads. It calls
    `build_wire_payload`, feeds the result to `build_from_wire`, and compares the
    **parse output** against the markdown parse. The lines the task cited
    (`:115-236`) are *suggestions-doc* fixtures, and the file imports `jsonschema`
    nowhere.
  - The only file that validates a built wire against the schema is
    `tests/test_suggestions_wire_emit.py`, closed by T2.2. The four hand-written
    fixtures were closed by T2.1. Every other `schema_version: "3"` in `tests/` is
    the **instructions** wire, at 3 since spec 036 — not this wire.
  So the sweep is complete. What is **not** complete is this task's own success
  criterion, which nothing in the repo owns: no test captures a baseline wire
  payload and diffs a later one against it (`grep` for a captured target finds only
  `capsys` stderr captures).

  1. Prime: read `tests/test_suggestions_wire_emit.py`'s `_doc()` fixture and
     `build_wire_payload` (`suggestions-render.py:422`). Note what T2.1 and T2.2
     changed about a conflict-free payload: the version stamp `2` → `3` and one new
     key holding `[]`. Nothing else should have moved.
  2. Test: capture a conflict-free wire payload as an explicit expected structure,
     then assert a freshly built one differs from the pre-038 shape in **exactly**
     the expected ways and no others. The point is the "no others" — this is the
     test that catches an unrelated top-level field being changed, dropped or
     renamed in passing.
     **The difference is THREE keys, not two — measured 2026-10-01, and the task
     said two.** Running today's `build_wire_payload` against the pre-038 one on the
     same `_doc()` fixture yields: `attachment_conflicts` (new), `schema_version`,
     and **`emit_digest`**. The digest is a hash over the payload minus itself, so
     it changes necessarily whenever any field changes; a criterion naming only two
     differences fails on the first run, for a reason that is correct behaviour.
     Handle it deliberately rather than by widening the allowance, and use the
     **strong** form of the digest assertion, not "the digest differs" — a digest
     that merely changed says nothing about *which* field moved it, and would pass
     just as happily if an unrelated field had been renamed. Instead: take the
     baseline, apply **only** the two intended changes (`schema_version` → `"3"`, add
     `attachment_conflicts: []`), recompute with `compute_payload_digest`
     (`lib/render_md.py:383`), and assert it reproduces today's digest **exactly**.
     **Verified end-to-end 2026-10-01 — it does**, and the negative control holds:
     omit the new key and the digest does not match. That one assertion subsumes the
     "no others" criterion, because any unrelated field having moved would break the
     reconstruction, and it is the only *executed* proof that the digest covers the
     new field — T2.2 established that by reading `compute_payload_digest`, which is
     sound but is not a test. Keep the key-set comparison alongside it: when the
     reconstruction fails, the digest tells you only *that* something moved, while
     the key-set diff names *what*.
     **And do not derive the baseline by loading the old module.** Measured: the
     historical `suggestions-render.py` imported standalone and run on today's
     fixture stamps `schema_version: "3"`, not `"2"`, because
     `wire_schema_version` reads the schema **from disk at call time**
     (`lib/wire_version.py`) rather than carrying a literal. Old code plus today's
     schema gives you old structure with the current version stamp — so the one
     difference this test most wants to see would silently vanish.
     **Capture the baseline as committed data instead**, under `tests/fixtures/`.
     The source is **`50d8f1b`** — the last commit before Phase 2 touched either
     file. It is *not* the branch point, which is `8d284fb`, 36 commits earlier;
     either would in fact serve, because Phase 1 changed only `description` strings
     in the wire schema and nothing affecting a payload's shape, but `50d8f1b` is
     the tighter choice. Verified at that commit: the schema reads `const: "2"`
     with no `attachment_conflicts` property, and `tomo/scripts/suggestions-render.py`
     is untouched by anything on this branch before T2.2.
     **The recipe is verified, not merely suggested** — run 2026-10-01:
     `git worktree add --detach <scratch> 50d8f1b`, then inside that worktree load
     both `tests/test_suggestions_wire_emit.py` and
     `tomo/scripts/suggestions-render.py` from the worktree and call
     `build_wire_payload(_doc())`. It works for a reason worth stating:
     `tests/test_suggestions_wire_emit.py` is **byte-identical** at `50d8f1b` and at
     HEAD (`git diff` over that range is empty), so the baseline and the current
     payload are built from the same input — had the fixture drifted, the diff would
     have included fixture changes and proved nothing. Remove the worktree afterwards
     with `rm -rf` plus `git worktree prune`.
     What that recipe produces, recorded so a differing result reads as a problem
     rather than as news: **10 top-level keys**, `schema_version: "2"`, no
     `attachment_conflicts`. Today's payload has **11**. The only added key is
     `attachment_conflicts`; nothing is removed; `emit_digest` and `schema_version`
     are the only changed values. Do **not** hand-type it — a hand-typed baseline
     proves only that two people agreed on what they expected.
  3. Implement: nothing in `tomo/scripts/` changes. This task is test-only.
     **Commit the generator next to the baseline, not just the baseline.** A
     committed expected-payload fixture is easy to silence: when it fails, the
     cheapest response is to regenerate it rather than ask why it moved, and that
     turns the test into a rubber stamp. The tdd-guardian raised this as a real and
     unguarded risk and it is right. Two guards, both cheap:
     - Put the baseline under `tests/fixtures/038-wire-baseline/` **together with the
       script that produced it**, with `50d8f1b` hard-coded in that script. The
       fixture then stops being an assertion and becomes **reproducible** — a
       reviewer can re-run the generator and confirm the committed bytes, which is
       not possible for a hand-maintained expected value.
     - State the regeneration rule where someone about to break it will read it: a
       comment directly above the baseline load in the test, saying that this file
       is a frozen pre-038 artefact, that a diff against it moving is a finding
       rather than a maintenance chore, and that it is regenerated only when the
       pre-038 state itself is re-chosen — not when the current payload changes.
  4. Validate: the new test passes. Then **prove it bites**: on a scratch copy,
     rename or drop one unrelated top-level payload key and confirm the test fails
     naming that key, not merely "payloads differ".
  5. Success:
     - [ ] A conflict-free payload differs from the pre-038 baseline in exactly the
           version stamp and the new empty array, with `emit_digest` compared
           separately rather than counted among them `[ref: SDD/Acceptance Criteria]`
     - [ ] The digest is shown by execution to cover the new field — by
           reconstruction from the baseline, with the key-omitted negative control
     - [ ] The baseline is **captured**, not hand-typed `[ref: SDD/Acceptance Criteria]`
     - [ ] An unrelated top-level key change turns the test red, **demonstrated**,
           and the failure names the key
     - [ ] No production file is touched
     - [ ] The baseline ships with its generator and a stated regeneration rule, so
           a future failure cannot be silenced by regenerating it unthinkingly

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
    carry this change — but confirm it rather than assume it. `--yolo` is just
    `--keep-voice --yes` (`:46`), useful only to skip the confirmation prompt.
  - **Clear the stale wire before the run, or the demonstration is void.** Measured
    2026-10-01: `tomo-instance/tomo-tmp/suggestions-wire.json` exists **right now**
    at `schema_version: 2`, and eight cached run artefacts under
    `tomo-tmp/inbox-cache/` are at `"2"` as well. The moment `update-tomo` moves the
    instance schema to `"3"`, every one of those becomes version-mismatched — and
    `load_changed_wire` answers a mismatch with a stderr warning and a silent
    fallback to the markdown. So a run that reuses or is influenced by that older
    state takes the markdown path, looks entirely correct, and proves the opposite
    of what this step claims. This is **CON-2 in its actual form**: not a
    half-finished code move, which spec 035's ADR-5 made impossible, but a stale
    artefact on disk. Remove or regenerate `tomo-tmp/suggestions-wire.json` and
    confirm the fresh one carries `"3"` **before** editing it. The same hygiene the
    repo already learned once as "reset `tomo-tmp` before a live run".
  - Success: suite green; `ruff` clean; the wire path demonstrably taken after the
    version move `[ref: PRD/F1]`.
