---
title: "Phase 4: Register the new action kind"
status: pending
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

- [ ] **T4.1 Schemas — producer and mirror** `[activity: data-architecture]`

  1. **Prime**: `edit_frontmatter` is shipped in Hashi 0.22.0/0.23.0. Copy the `$def` **verbatim** from `Hashi/src/schema/instructions.schema.json` and diff it, exactly as spec 031 did for `move_asset` — the mirror's value is that it is byte-equal.
  2. **Test** (RED):
     - a well-formed `edit_frontmatter` validates against **both** `instructions.schema.json` and `hashi-instructions.schema.json` `[ref: PRD/AC-F5 family]`
     - dropping any required field is rejected by both
     - `expected` and `expected_absent` together is a **validation error**, not a precedence rule `[ref: CON-1]`
     - `additionalProperties:false` rejects an added field
     - the parity test passes with the kind in **both** schemas, i.e. it is **not** added to `MIRROR_ONLY_ACTIONS` — Tomo emits it
     - `schema_version` is unchanged `[ref: CON-2]`
  3. **Implement**: add the `$def` and `oneOf` ref to both schemas; verify byte-equality against Hashi's copy programmatically, not by eye.
  4. **Validate**: schema and parity tests pass. Bytewise sync, no version bump `[ref: CON-8]`.
  5. **Success**: the mirror stays a faithful copy of Hashi's wire surface

- [ ] **T4.2 Coverage audit registration** `[activity: backend-logic]`

  1. **Prime**: Read `run_diff` at `:645-659`. Write the blind-spot test **first**, so it fails once the kind is registered — a test that is green before and after proves nothing.
  2. **Test** (RED):
     - pre-registration: a set containing `edit_frontmatter` yields a `TOTAL` that **excludes** them, while `action_count` includes them — the documented symptom
     - post-registration: expected N, actual N → pass `[ref: PRD/AC-F5.1]`
     - expected N, actual N−1 → **hard fail** `[ref: PRD/AC-F5.2]`
     - the kind appears in the printed table and contributes to `TOTAL` `[ref: PRD/AC-F5.3]`
     - `action_count` equals `TOTAL` for a set containing the kind
  3. **Implement**: add `"edit_frontmatter": 0` to the counts initialiser and the kind to `ACTION_ORDER`.
  4. **Validate**: unit tests pass; `# version:` bumped.
  5. **Success**: an unaudited property action is impossible `[ref: PRD/Risks; row 1]`

- [ ] **T4.3 Expectation derivation** `[activity: backend-logic]`

  1. **Prime**: `derive_expected` predicts per-kind counts from the parsed decisions. The prediction must model the **routing**, not the finding count — a `broken_up` finding produces either kind, never both.
  2. **Test** (RED):
     - N approved frontmatter-routed findings → expects N `edit_frontmatter` and **zero** additional `remove_up_link`/`add_relationship` for them `[ref: PRD/AC-F5.1]`
     - a mixed batch → each kind expected in its own count, totals reconciling `[ref: memory: count parity ≠ correctness]`
     - unroutable findings expect **nothing** — they produce no action of any kind `[ref: PRD/AC-F6.3]`
     - skipped findings contribute nothing
  3. **Implement**: extend `derive_expected` to branch on the same `up_source` the parser used, so expectation and emission cannot disagree.
  4. **Validate**: unit tests pass.
  5. **Success**: expectation and emission share one routing rule `[ref: SDD/Complex Logic]`

- [ ] **T4.4 Dry run and readable output** `[activity: backend-logic]` `[parallel: true]`

  1. **Prime**: `instructions-dryrun.py:25-33` `REQUIRED` is a whitelist — an unlisted kind exits 1. `render_md.py:239` falls through to an "unknown action" placeholder.
  2. **Test** (RED):
     - a dry run over a set containing `edit_frontmatter` exits 0 and describes each action
     - an action missing `expected` is reported invalid
     - the readable document names the note, the property and the change `[ref: PRD/Feature 4 adjacent]`
     - the string `unknown action` never appears for this kind
  3. **Implement**: `REQUIRED` entry plus `describe` branch; `_md_section_for` and `_render_action_md` branches.
  4. **Validate**: unit tests pass; `# version:` bumped on both files.
  5. **Success**: neither tool rejects nor mislabels a valid set

- [ ] **T4.5 Path validation** `[activity: backend-logic]` `[parallel: true]`

  1. **Prime**: `_REQUIRED_PATH_FIELDS` at `render_actions.py:204-219`; an unlisted kind is silently skipped by `_validate_action_paths`.
  2. **Test** (RED): an `edit_frontmatter` with an empty `path` is rejected, proving the kind is no longer skipped.
  3. **Implement**: add the entry.
  4. **Validate**: unit tests pass.
  5. **Success**: property actions are shape-validated like every other kind

- [ ] **T4.6 Phase Validation** `[activity: validate]`

  - Full suite green. Walk all five sites and confirm each has a passing test: producer schema, mirror schema, `instructions-diff`, `instructions-dryrun`, `render_md`, `_REQUIRED_PATH_FIELDS`. Confirm the pre-registration blind-spot test now fails for the right reason. `ruff` clean.
