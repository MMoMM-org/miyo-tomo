---
title: "Phase 4: Integration and the live path"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Integration and the live path

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-5]` — no wire field, no Hashi change
- `[ref: SDD/Cross-Component Boundaries]`
- `[ref: PRD/Success Metrics]`, `[ref: PRD/C2]`

**Key Decisions**:
- ADR-5 is asserted **by absence**: the wire schema and Hashi's vendored copy
  must be unchanged. That is a test, not a promise.
- The live path is the only place the whole chain is exercised. The fixture that
  produced the 2026-09-15 failure still exists in the test vault — two 69-byte
  PNGs named `karte.png`, one in `100 Inbox/Scans/`, one in
  `Atlas/290 Assets/295 Attachments/`. Do not "clean it up"; it is the fixture.
- Cost is measured, not estimated. `base_kado_calls` must still read 2.

**Dependencies**: Phases 1, 2 and 3.

---

## Tasks

Establishes that the chain works end to end and that nothing outside Tomo moved.

- [ ] **T4.1 Nothing outside Tomo changed** `[activity: testing]` `[parallel: true]`

  1. Prime: Read `[ref: SDD/External Interfaces]`, `[ref: SDD/Cross-Component Boundaries]` and ADR-5. Read `tomo/schemas/hashi-instructions.schema.json:35` — `properties.tomo` deliberately carries **no** `additionalProperties: false`, and `tests/test_wire_snapshot_parity.py`'s `SANCTIONED_ASYMMETRIES` excludes `/properties/tomo` by name for that reason. Hashi's vendored copy is `/Volumes/Moon/Coding/MiYo/Hashi/src/schema/instructions.schema.json`; its validator is `src/schema/validator.ts` (Ajv2020). **Read-only across that boundary — never edit anything under `Hashi/`**
  2. Test (hermetic, pytest): **no emitted action carries a field absent from the strict action schema** — **mutation: append `"remedy": remedy` (or any stray key) to the `move_asset` dict at `[ref: render_actions.py:838-843]`**, which `additionalProperties: false` at `[ref: hashi-instructions.schema.json:105-116]` rejects. This is the ONE assertion in this task with a reachable mutation; validate a rendered three-remedy instruction set against our own copy of the schema with Python `jsonschema`, the way the repo's existing schema tests do
  3. Implement: nothing. A change needed in `tomo/schemas/hashi-instructions.schema.json` is a deviation against ADR-5 — stop, record it, revisit ADR-5 before proceeding `[ref: plan/README.md; Deviation Protocol]`
  4. Validate (environment-dependent, recorded in the close-out rather than pinned as a test, since a sibling repo may not be checked out elsewhere): (a) `git diff main...HEAD -- tomo/schemas/` touches only `suggestions-doc.schema.json` — label it *"confirms no edit was made"*, NOT proof of ADR-5; (b) `diff` our copy against Hashi's checked-out copy and record the result — the existing parity tests do offline producer↔mirror parity and a network fetch of upstream, but **never a direct filesystem comparison against the sibling working tree**, so this is the one genuinely new check here; (c) run **Hashi's own Ajv2020** over a real rendered three-remedy instruction set, from `cd /Volumes/Moon/Coding/MiYo/Hashi` against their installed `node_modules`, writing nothing under `Hashi/`. Its value is proof-by-execution against the consumer's real compiled validator rather than our Python `jsonschema` — not new coverage: it can only fail on the same stray-key mutation as bullet 2
  5. Success: Hashi receives no new field and needs no change `[ref: SDD/ADR-5]`; the contrast with spec 036's consumerless `depends_on` is preserved


- [ ] **T4.2 Pass 2's summary names what it did not resolve** `[activity: backend-api]` `[parallel: true]`

  1. Prime: Read `render_instructions_md`'s "Skipped — un-appliable actions" section `[ref: lib/render_md.py:886-935]` and the metadata dict that feeds it `[ref: instruction-render.py:1103-1123]`. This is a **script**, not a runtime skill — ordinary Python + pytest, no `docs/tomo` imperatives-only constraint. Read `_withdrawn_links_note`'s docstring `[ref: render_md.py:666-678]` for ADR-11 and the `⚠️ **<label>:**` convention it shares with Pass 1
  2. Test: **the `vault_collision_held` fallback is gone** — on HEAD a `keep_in_inbox` conflict renders `(no remedy defined for skip kind 'vault_collision_held' — check render_md.py)`, a live user-facing defect T3.1 shipped, since every Phase 3 test asserted on `skipped_assets` as data and none rendered it. **Mutation: delete the new `kind` branch** and that catch-all returns, which `test_031_t2_3_move_asset_md_rendering.py::test_unrecognized_skip_kind_never_inherits_a_remedy` pins for a genuinely unknown kind; one fixture carrying a `keep_in_inbox`, an `ignore` and a **successful** `rename` together names the two non-rename sources **verbatim** and the rename source **nowhere** in that reporting — **mutation: filter `attachment_conflict_remedies` on `remedy != "rename"`**, which silently drops a DEGRADED rename (`proposed_name: null`, which SDD:292 degrades to `keep_in_inbox`) — the two source lists are `skipped_assets` filtered to `kind == "vault_collision_held"` (which already unifies keep-in-inbox and degraded rename) PLUS `attachment_conflict_remedies` filtered to `remedy == "ignore"`; naming is asserted as **the exact expected strings**, and separately that no rendered sentence matches a bare `\d+ conflicts?` count — **mutation: render `"2 conflicts remain: a.png, b.png"`**, which a vague "names both" assertion would accept `[ref: PRD/C2 — "conflicts not resolved by rename"]`; a run with no conflicts renders the section byte-identically to a captured pre-change literal — **NOT** asserted alone, since it is already true on HEAD `[ref: plan/phase-1.md:45]`
  3. Implement: add the `vault_collision_held` branch; thread `attachment_conflict_remedies` into the metadata dict (it reaches `instruction-render.py:374` today but is used only for the embed rewrite at `:439-441` and never passed to `render_instructions_md` — the same missing-transport shape as T3.0); **and drop the wire action name from the section** — owner ruling 2026-09-27, ADR-11: it states the effect, never `move_asset`, for all three entries, using the `⚠️ **<label>:**` convention
  4. Validate: full suite; `ruff`; prove RED by deleting the new `kind` branch and showing the catch-all string reaches the rendered markdown
  5. Success: an owner who unticked a default is reminded before applying `[ref: PRD/S2]`; no rendered line names a wire action `[ref: ADR-11, render_md.py:668]`


- [ ] **T4.3 The live run reproduces the 2026-09-15 case and resolves it** `[activity: testing]`

  1. Prime: Read the run log `100 Inbox/tomo-hashi-run-log_2026-09-15T2057.md` for the failing row; confirm both `karte.png` files are still in place and still differ
  2. Test — as a live `/inbox` run, not a fixture: Pass 1 raises exactly one conflict for `karte.png`; the document shows it with rename ticked and states that a **different** file holds the name; Pass 2 with the default emits a move to a free name; the coverage audit passes; Hashi applies the run with **zero** `move_asset` failures — the row that was red on 2026-09-15 is green
  3. Implement: nothing new; this task is the proof
  4. Validate: compare `base_kado_calls` against the spec 034 T6.4 baseline of **2** — it must be unchanged, since the reducer is a separate process `[ref: SDD/Cost]`; record `folder_listing_calls` and confirm it rose by at most one
  5. Success: every PRD KPI has a measured value from this run `[ref: PRD/Success Metrics]`; owner agency goes from 0-of-1 to 1-of-1; the failed action goes from 1 to 0

- [ ] **T4.4 The unresolved remedies behave as designed on the live vault** `[activity: testing]`

  1. Prime: T4.3's run must be complete and its vault state known
  2. Test — two further live runs against the same fixture: with `keep_in_inbox`, no `move_asset` is emitted and Hashi reports no failure; with `ignore`, the move is emitted and **Hashi refuses it with the same message as 2026-09-15** — which is the remedy working, not a regression
  3. Implement: nothing; this task is the proof that ADR-5's dependency on Hashi's existing behaviour is real and not assumed
  4. Validate: read both run logs; assert the `ignore` run's failure count is exactly 1 and names `move_asset`
  5. Success: all three remedies are demonstrated against a live vault `[ref: PRD/F3]`; the fixture is restored afterwards so the next run starts from the same state `[ref: scratchpad/restore-trigger-notes.sh]`

---

> **Deviation recorded 2026-09-27 — T4.1 rewritten before dispatch. ADR-5 holds, measured, and for a better reason than the plan gave.**
> The guardian blocked it. The headline is a clean result rather than a defect:
> **there is no ADR-5 violation, and it was consequence-free by design.**
> `skipped_assets` — the field carrying spec 037's new `kind: vault_collision_held`
> — is not a named property in `hashi-instructions.schema.json` at all. It lives
> under `properties.tomo`, which deliberately carries no `additionalProperties:
> false` (`:35`, *"kept permissive so Tomo can evolve the block without a
> coordinated round-trip"*), and `tests/test_wire_snapshot_parity.py`'s
> `SANCTIONED_ASYMMETRIES` excludes `/properties/tomo` by name. Hashi's checked-out
> copy is byte-identical to ours. Someone paid this cost in advance so a spec like
> this one would need no cross-repo handshake — the same shape as ADR-3 reusing
> `skipped_assets` rather than adding a records list.
>
> That result also hollowed out most of the task. Three findings:
> (1) **Bullet 1 was vacuous** — `git diff main...HEAD -- tomo/schemas/` touches only
> `suggestions-doc.schema.json`, so "byte-identical to its pre-change version" was
> true before any test ran, and named no comparison target. Third instance of the
> defect `plan/phase-1.md:45` names, after T3.0 and T3.2. Demoted to a Validate
> check labelled as what it is.
> (2) **The `keep_in_inbox` half of the validator bullet cannot fail.** Because
> `properties.tomo` is permissive, a `vault_collision_held` entry cannot make
> Hashi's validator reject anything, whatever shape it takes — unfalsifiable by
> design, not by oversight. And a successful `rename` and an `ignore` are
> *wire-identical* (`render_actions.py:838`, SDD:234), so the fixture exercises two
> shapes, not three. The task had implied three independent checks.
> (3) **One real mutation exists** and the plan never named it: append a stray key
> to the `move_asset` dict at `render_actions.py:838-843`, which the action schema's
> `additionalProperties: false` (`:105-116`) rejects. That is now bullet 2, the only
> hermetic test in the task.
>
> The split matters: the pytest assertion is hermetic and uses our own schema copy,
> while the two environment-dependent proofs — a direct filesystem `diff` against
> Hashi's working tree, and running Hashi's real Ajv2020 — move to Validate and the
> close-out, because a sibling repo may not be checked out elsewhere. The direct
> filesystem diff is the one genuinely new check: existing parity tests compare
> producer to mirror offline and fetch upstream over the network, but never the
> sibling working tree. Running Hashi's own compiled validator adds no coverage —
> it can only fail on the same stray-key mutation — but it is proof by execution
> against the consumer's real validator instead of our Python `jsonschema`, which
> is worth recording once. Verified runnable read-only: their Ajv2020 compiles their
> schema from their own `node_modules`, writing nothing under `Hashi/`.

> **Deviation recorded 2026-09-27 — T4.2 rewritten before dispatch, and it uncovered a shipped defect.**
> The guardian blocked it. Five findings, one owner ruling, and one live bug.
>
> **Phase 3 shipped a `kind` no renderer knows.** T3.1 added
> `skipped_assets` `kind: vault_collision_held`; `render_md.py`'s kind dispatch
> (`:924-933`) branches only on `no_basename` and `collision`. On HEAD a
> *keep in inbox* conflict therefore renders to the owner as
> `(no remedy defined for skip kind 'vault_collision_held' — check render_md.py)`
> — a user-facing string naming a source file. Eight Phase 3 reviews missed it
> because every Phase 3 test asserted on `skipped_assets` as a data structure
> and not one rendered it to markdown. The repo already had the rule this
> violates: *an internal field on a wire action owes a triad*. A new `kind`
> owes a renderer branch, and nothing checked.
>
> **`ignore` has no transport to the summary.** It records nothing in
> `skipped_assets` by design (SDD:234), and `attachment_conflict_remedies`
> reaches `instruction-render.py:374` but is consumed only by the embed rewrite
> — it never enters the metadata dict `render_instructions_md` reads. Exactly
> T3.0's missing-caller shape, one level further downstream. The plan's
> "extend the summary from the conflict records" concealed a transport step.
>
> **The naive filter drops a degraded rename.** Filtering
> `attachment_conflict_remedies` on `remedy != "rename"` misses
> `{remedy: "rename", proposed_name: null}`, which SDD:292 degrades to
> keep-in-inbox behaviour. The correct combination is two source lists, not one
> filter: `skipped_assets` on `kind == "vault_collision_held"` (which already
> unifies both) plus `attachment_conflict_remedies` on `remedy == "ignore"`.
>
> **Owner ruling — ADR-11 applies to this section.** `render_md.py:668` states
> it in the same file: *"no executor internals in the rendered text — no action
> id, no wire action name."* The `skipped_assets` loop prints `move_asset` on
> every line. Because the prefix is shared, a compliant new line is impossible
> without changing the existing two, so the owner ruled the section is fixed as
> a whole: state the effect, drop the wire name, use the `⚠️ **<label>:**`
> convention the withheld-delete bullet and Pass 1 already share.
>
> **Two bullets were vacuous.** "a run with none adds no line" and "a `rename`
> conflict is not reported as unresolved" are both already true on HEAD —
> nothing is reported as unresolved today, for anything. Neither can fail before
> implementation. Merged into one joint fixture carrying all three remedies.
> "names both rather than counting them" was not assertable either: a mutant
> rendering `"2 conflicts remain: a.png, b.png"` arguably does both, so the
> test now names exact strings and separately forbids a bare count.
>
> No owner decision was needed on what "unresolved" means — `requirements.md:240`
> settles it in C2's own words, *"conflicts not resolved by rename"*, which is
> keep-in-inbox and ignore together.
