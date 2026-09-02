---
title: "Phase 4: Register the new action kind"
status: in_progress
version: "1.0"
phase: 4
---

# Phase 4: Register the new action kind

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Known Technical Issues; "instructions-diff blind spot"]`
- `[ref: SDD/Implementation Gotchas]`
- `[ref: PRD/Feature 5]`, `[ref: PRD/Risks; row 1 — Likelihood High]`
- `[ref: docs/XDD/specs/031-inbox-attachment-filing/plan/phase-4.md]` — the same checklist, already worked through for `move_asset`. Read it; do not rediscover it.
- Source to read: `instructions-diff.py:168-177`, `:429-433`, `:645-659`; `instructions-dryrun.py:25-33`; `render_md.py:31-46`, `:239`; `render_actions.py:204-219`; `tests/test_tomo_schema_parity.py` (`MIRROR_ONLY_ACTIONS`)

**Key Decisions**:
- **This phase exists because the work it contains is the work that gets forgotten.** Spec 031 hit the identical trap one spec ago. Folding registration into the emission task is how a kind ends up emitted but unaudited.
- An unregistered kind does not fail loudly. `summarize_actual` counts it generically, but `run_diff` iterates `ACTION_ORDER` — so the audit passes **green** while the actions go unreconciled. The only symptom is `action_count` exceeding the printed `TOTAL`.

**Dependencies**: none. May run concurrently with Phases 1–3; the two meet in Phase 6.

---

## Tasks

The new-kind checklist. Five sites, none of which the emitter needs in order to work — which is precisely the danger.

- [x] **T4.1 Schemas — producer and mirror** `[activity: data-architecture]`

  1. **Prime**: `edit_frontmatter` is shipped in Hashi 0.22.0/0.23.0. Copy the `$def` **verbatim** from `Hashi/src/schema/instructions.schema.json` and diff it, exactly as spec 031 did for `move_asset` — the mirror's value is that it is byte-equal.
  2. **Test** (RED):
     - a well-formed `edit_frontmatter` validates against **both** `instructions.schema.json` and `hashi-instructions.schema.json` `[ref: PRD/AC-F5 family]`
     - dropping any required field is rejected by both
     - `expected` and `expected_absent` together is a **validation error**, not a precedence rule `[ref: CON-1]`
     - `operation: "set"` **without** `value` is a validation error — the second `allOf` clause
     - `additionalProperties:false` rejects an added field
     - **STRUCTURAL PARITY**: Hashi's `$def` carries an `allOf` with two clauses — the `oneOf`
       mutual exclusion above, and an `if operation==set then value required`. The existing
       parity test compares **property sets, not schema structure**, so a mirror that copies the
       properties and drops `allOf` passes parity **green** and fails only at Hashi's gate in
       production. Assert both clauses are present and enforced in **each** schema, by
       validating a violating document and requiring rejection — not by comparing property lists
     - the parity test passes with the kind in **both** schemas, i.e. it is **not** added to `MIRROR_ONLY_ACTIONS` — Tomo emits it
     - `schema_version` is unchanged `[ref: CON-2]`
  3. **Implement**: add the `$def` and `oneOf` ref to both schemas; verify byte-equality against Hashi's copy programmatically, not by eye.
  4. **Validate**: schema and parity tests pass. Bytewise sync, no version bump `[ref: CON-8]`.
  5. **Success**: the mirror stays a faithful copy of Hashi's wire surface

- [x] **T4.2 Coverage audit registration** `[activity: backend-logic]`

  > **SCOPE CORRECTION (2026-09-02).** `run_diff` **dispatches on document shape** at
  > `instructions-diff.py:~610`: `if _is_garden_parsed(parsed): return run_diff_garden(...)`.
  > `broken_up` findings are `garden_action` items, so spec 032's documents take the **garden**
  > branch. `derive_expected` is called at exactly one site — line 614, **after** that return —
  > so it, the counts initialiser and `ACTION_ORDER` are all **unreachable for this spec's data**.
  > Furthermore `run_diff_garden:~529-531` already appends unknown kinds dynamically
  > (`all_kinds = GARDEN_ACTION_ORDER + [k for k in sorted(actual_counts) if k not in ...]`),
  > so there is **no silent under-count on the garden path** — the premise this task was
  > written on does not hold here.
  > **Resolution:** the `ACTION_ORDER` + counts-initialiser registration is KEPT as
  > forward-compatible hygiene (harmless, correct if a non-garden flow ever emits the kind).
  > The real coverage-audit gap — `_GARDEN_EXPECTED_KINDS` not knowing that a
  > frontmatter-routed finding owes `edit_frontmatter` — **moves to T4.3**, which was already
  > held pending Phase 3's routing rule. That gap fails **loudly** (`[DIFF]` on two rows →
  > `hard_fail`), not silently.

  1. **Prime**: Read `run_diff` at `:645-659`. Test file is `tests/test-instructions-diff.py`
     (hyphenated). Write the tests as **invariants**, not as assertions about the current bug.
     A test that asserts the pre-fix symptom passes before the fix and fails after, so it has to
     be deleted or inverted — that documents temporary state rather than a requirement. Spec 031
     phase-4 hit this same question and did not resolve it; do not inherit the pattern.
  2. **Test** (RED — each must FAIL before registration and PASS after, and remain true forever):
     - **primary invariant**: for any instruction set, `action_count == TOTAL`. Unregistered kinds
       break this because `summarize_actual` counts generically while `run_diff` iterates
       `ACTION_ORDER`. RED before registration, GREEN after, never needs inverting
     - a set containing N `edit_frontmatter` actions contributes N to `TOTAL`
     - post-registration: expected N, actual N → pass `[ref: PRD/AC-F5.1]`
     - expected N, actual N−1 → **hard fail** `[ref: PRD/AC-F5.2]`
     - the kind appears in the printed table and contributes to `TOTAL` `[ref: PRD/AC-F5.3]`
     - `action_count` equals `TOTAL` for a set containing the kind
  3. **Implement**: add `"edit_frontmatter": 0` to the counts initialiser and the kind to `ACTION_ORDER`.
  4. **Validate**: unit tests pass; `# version:` bumped.
  5. **Success**: an unaudited property action is impossible `[ref: PRD/Risks; row 1]`

- [ ] **T4.3 Expectation derivation** `[activity: backend-logic]`

  > **SCOPE EXPANDED (2026-09-02)** — absorbs T4.2's real deliverable. The coverage audit for
  > spec 032 runs through `run_diff_garden`, whose expected side is built from
  > `_GARDEN_EXPECTED_KINDS` (`instructions-diff.py:~447-452`), **not** from `derive_expected`.
  > That map currently says `"remove_up_link": ("remove_up_link",)`. After this spec, a
  > **frontmatter-sourced** finding with the same `garden_action` owes `edit_frontmatter`
  > instead. So the mapping must become **routing-aware**, branching on the same `up_source`
  > the parser used — which is exactly why this task waits for Phase 3.
  > Expectation and emission must share ONE routing rule; two independently-authored rules that
  > must agree is the divergence this task exists to prevent.
  > **The genuine SILENT bug lives here** (verified empirically 2026-09-02). `_garden_item_covered`
  > (`instructions-diff.py:~462-493`) iterates `_GARDEN_EXPECTED_KINDS.get(ga, ())`. With no
  > `"edit_frontmatter"` key the loop body **never executes and the function returns `True`
  > vacuously** — per-item coverage prints `[OK]` for every such item having checked nothing.
  > The count-level TOTAL does hard-fail loudly, so this is silent only at per-item granularity —
  > but that is precisely the granularity the per-item coverage section exists to provide.
  > A test for this MUST assert that an `edit_frontmatter` item with a MISSING or MISMATCHED
  > action is reported NOT covered. A test that only checks a correct item shows `[OK]` passes
  > vacuously today and proves nothing.
  > Correction to an earlier assumption: per `solution.md:353` the routing branch sets
  > `garden_action = "edit_frontmatter"` **directly on the confirmed_item** — it does not keep
  > `remove_up_link` and vary only the emitted kind. So `_GARDEN_EXPECTED_KINDS` needs a NEW KEY,
  > and `GARDEN_ACTION_ORDER` likely needs the value too.
  >
  > **SCOPE SETTLED 2026-09-02 — two parts, and NOT in `derive_expected`.**
  > The Prime step below says "extend `derive_expected`". That function is **unreachable on the
  > garden path** — `run_diff` returns from `run_diff_garden` at `:612`, before `derive_expected`
  > is called at `:614`. Same F-J finding that invalidated T4.2's premise, left standing in the
  > neighbouring task text. Ignore the `derive_expected` mention.
  >
  > **(a)** Add `"edit_frontmatter": ("edit_frontmatter",)` to `_GARDEN_EXPECTED_KINDS`
  > (`instructions-diff.py:~448-453`).
  >
  > **(b) MOOT — do not implement.** I assumed withheld findings had to be excluded from the
  > expectation, or the audit would hard-fail exactly when the system behaves correctly. They are
  > never there to exclude: `_confirmed_item_from_wire_finding` returns `None` when the router
  > withholds (`garden-audit-parser.py:449`), and `build_from_report` appends only non-`None`
  > results (`:525-527`). Withheld findings live solely in the `unroutable` envelope key, which
  > `run_diff_garden` never reads. The coverage audit is already correct here — an exclusion would
  > be code handling a state that cannot occur.
  >
  > **(c)** Add the matching `elif` branch to `_garden_item_covered` (`:~462-493`). **This is the
  > genuine silent bug.** The function iterates `_GARDEN_EXPECTED_KINDS.get(ga, ())`, so a kind
  > with no entry yields an empty tuple, the loop body never runs, and it returns `True` **having
  > checked nothing** — per-item coverage prints `[OK]` for an item it never verified. Part (a)
  > alone does not fix this; the `elif` must exist here too.

  1. **Prime**: `derive_expected` predicts per-kind counts from the parsed decisions. The prediction must model the **routing**, not the finding count — a `broken_up` finding produces either kind, never both.
  2. **Test** (RED):
     - N approved frontmatter-routed findings → expects N `edit_frontmatter` and **zero** additional `remove_up_link`/`add_relationship` for them `[ref: PRD/AC-F5.1]`
     - a mixed batch → each kind expected in its own count, totals reconciling `[ref: memory: count parity ≠ correctness]`
     - unroutable findings expect **nothing** — they produce no action of any kind `[ref: PRD/AC-F6.3]`
     - skipped findings contribute nothing
  3. **Implement**: extend `derive_expected` to branch on the same `up_source` the parser used, so expectation and emission cannot disagree.
  4. **Validate**: unit tests pass.
  5. **Success**: expectation and emission share one routing rule `[ref: SDD/Complex Logic]`

- [x] **T4.4 Dry run and readable output** `[activity: backend-logic]` `[parallel: true]`

  1. **Prime**: `instructions-dryrun.py:25-33` `REQUIRED` is a whitelist — an unlisted kind exits 1. `render_md.py:239` falls through to an "unknown action" placeholder.
  2. **Test** (RED):
     - a dry run over a set containing `edit_frontmatter` exits 0 and describes each action
     - an action missing `expected` is reported invalid
     - the readable document names the note, the property and the change `[ref: PRD/Feature 4 adjacent]`
     - the string `unknown action` never appears for this kind
  3. **Implement**: `REQUIRED` entry plus `describe` branch; `_md_section_for` and `_render_action_md` branches.
  4. **Validate**: unit tests pass; `# version:` bumped on both files.
  5. **Success**: neither tool rejects nor mislabels a valid set

- [x] **T4.5 Path validation** `[activity: backend-logic]` `[parallel: true]`

  1. **Prime**: `_REQUIRED_PATH_FIELDS` at `render_actions.py:204-219`; an unlisted kind is silently skipped by `_validate_action_paths`.
  2. **Test** (RED): an `edit_frontmatter` with an empty `path` is rejected, proving the kind is no longer skipped.
  3. **Implement**: add the entry.
  4. **Validate**: unit tests pass.
  5. **Success**: property actions are shape-validated like every other kind

- [ ] **T4.6 Phase Validation** `[activity: validate]`

  - Full suite green. Walk every site and confirm each has a passing test that could actually
    fail: producer schema, mirror schema, `instructions-dryrun`, `render_md`,
    `_REQUIRED_PATH_FIELDS`, and — for `instructions-diff` — **the garden path specifically**
    (`run_diff_garden` + `_GARDEN_EXPECTED_KINDS`), which is the branch this spec's documents
    actually take. Do **not** accept an `ACTION_ORDER`/`derive_expected` test as evidence that
    the coverage audit is covered: that path is unreachable for garden-audit documents (see the
    T4.2 scope correction above). `ruff` clean.
