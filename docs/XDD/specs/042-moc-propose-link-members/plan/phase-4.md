---
title: "Phase 4: around:<MOC> extension, doc to instructions"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: around:<MOC> extension, doc to instructions

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-5, ADR-6]`, `[ref: SDD/Runtime View; Secondary flows — around:<MOC>, Apply (extension)]`, `[ref: SDD/Implementation Gotchas]`
- `[ref: PRD/Detailed Feature Specifications; around:<MOC>]` (Rules 1-6, edge cases)
- `tomo/scripts/moc-proposal-parser.py:23, :41-66, :70-179`
- `tomo/scripts/instruction-render.py:493-500` (template-less skip), filter order, `:897-918` (drop_sources assert)
- `tomo/scripts/lib/render_actions.py` — `emit_up_preservation_actions`, `_build_link_to_moc_actions :1397-1524`, `_build_up_preservation_actions :2091-2133`, `build_actions :2552-2600`
- `tomo/scripts/lib/render_resolve.py:33, :551`; `tomo/scripts/instructions-diff.py:591, :1125-1150`

**Key Decisions**:
- The extension never changes doc_type, promoter, triage or the conductor (eval gate stays untouched).
- `extend_moc` never reaches the wire; it expands into `add_relationship` + `link_to_moc` built from `confirmed`, not from the manifest.
- Already-linked is decided at render time from `outgoing(moc)`; on failure, emit all and report.
- Extensions are never squelched.

**Dependencies**: Phases 1-3 (resolver routes a MOC target here).

---

## Tasks

Delivers F3 end to end: from `around:<MOC>` to instructions that add `up::` to each ticked member and a link line to the MOC where it is missing.

- [x] **T4.1 Discovery: missing members of a MOC** `[activity: backend-api]` `[component: around builder]`

  1. Prime: WHY section in `docs/tomo/scripts/moc-discovery.md` — Rule 1 (missing member), why cached `up_target`
  2. Test: extend `tests/test_moc_discovery_around.py` (RED): MOC target → `report.extension` with eligible neighbours whose cached `up_target` is not the MOC (frontmatter-`up` member counts as present), all unticked, `linked_with=[moc]` `[ref: PRD/F3-AC1]`; none missing → abort "no missing members" `[ref: PRD/F3-AC2]`; a parent MOC among the neighbours is never a member; one missing member suffices; replace `test_moc_seed_routes_to_extension_stub` (keep the `around.kind == moc` routing assertion) and delete `ABORT_MESSAGES['around-moc-pending']` and the `_run_around_extension` stub; add a rejection-path squelch test for an Extend section (its `**Trigger:** around:<MOC>` on its own line)
  3. Implement: extension branch of the builder; bump version
  4. Validate: tests green; ruff clean
  5. Success: `[ref: PRD/F3-AC1, F3-AC2]`

- [x] **T4.2 Reducer: the extension section** `[activity: frontend-ui]` `[component: Reducer]` `[parallel: true]`

  1. Prime: `[ref: SDD/UI Visualization Guide]` (extension block); WHY section in `docs/tomo/scripts/suggestions-reducer.md`
  2. Test: extend `tests/test_reducer_moc_proposal_mode.py` (RED): `### MOC01 — Extend [[X]]`, `- [ ] Accept`, `**Extends:** [[X]]`, `#### Missing members (n)`, Override text naming X, Why "N notes link with [[X]] but have no up:: to it"; no Title/Location/Template, no `#### Parent` `[ref: PRD/F3-AC5]`; filename keeps `_moc-proposal`; frontmatter `proposal_kind: moc-extension`, doc_type unchanged; `state-promoter` regex still matches the Accept line (existing helper, no promoter change)
  3. Implement: `_render_extension_section`; bump version
  4. Validate: reducer suite green; ruff clean
  5. Success: `[ref: PRD/F3-AC5]`

- [x] **T4.3 Parser: `extend_moc`** `[activity: backend-api]` `[component: moc-proposal-parser, suggestion-parser]` `[parallel: true]`

  1. Prime: WHY doc first — `docs/tomo/scripts/moc-proposal-parser.md` (new): why the `MOCxx` heading is kept, the `**Extends:**` branch
  2. Test: extend `tests/test_moc_proposal_parser.py` (RED): an accepted extension section → `{action: "extend_moc", target_moc, supporting_items: [ticked], override_preserve_existing_up}` with no template/destination; accepted with zero ticked members → skipped and reported; an extension followed by a new-MOC section parses as two blocks; `suggestion-parser` / `squelch_persist` skip extension sections entirely
  3. Implement: branch in `_parse_moc_block`; `#### Missing members` read as children; squelch skip; bump versions
  4. Validate: tests green; ruff clean
  5. Success: extension reaches `parsed-suggestions.json` correctly `[ref: SDD/ADR-5]`

- [x] **T4.4 Render: extension actions, target filter, diff gate** `[activity: backend-api]` `[component: instruction-render, render_actions, instructions-diff]`

  1. Prime: WHY sections first in `docs/tomo/scripts/lib/render_actions.md`, `docs/tomo/scripts/instruction-render.md`, `docs/tomo/scripts/instructions-diff.md` `[ref: SDD/ADR-6]`
  2. Test (RED):
     - `filter_missing_extension_targets`: target MOC gone → item withheld with a stated cause, nothing emitted for its members (mirror `tests/test_instruction_render_missing_source.py`);
     - `_build_moc_extension_actions` with a graph fake: per ticked member the same Rule 4.x outcomes as `emit_up_preservation_actions` (reuse its tests' fixtures) `[ref: PRD/F1-AC5, F3-AC3]`; `link_to_moc` (`line_to_add "- [[member]]"`, anchor from the existing resolver) only for members not in `outgoing(moc)` `[ref: PRD/F3-AC4]`; `outgoing` failure → link lines for all, reported in instructions.md; null anchor → action still emitted with the existing unresolved notice;
     - `extend_moc` never appears in `instructions.json`; wire validates against `instructions.schema.json` unchanged;
     - `instructions-diff`: an extension with 3 ticked, 1 already linked → OK; a missing `add_relationship` or an extra `link_to_moc` → hard fail;
     - `drop_sources == WITHDRAWAL_GUARDS` assert still holds.
  3. Implement: filter `filter_missing_extension_targets` in `lib/render_resolve.py`, called from `instruction-render.py` (pre-build, client passed in); builder in `render_actions.py` wired into `build_actions` after up-preservation, built from `confirmed`; `extend_moc` branch in `instructions-diff.py`; bump versions
  4. Validate: full suite; mutation check in a `git archive` copy — make the builder ignore `outgoing` and the F3-AC4 test must fail; ruff clean
  5. Success: `[ref: PRD/F3-AC3, F3-AC4, F1-AC5]`; `[ref: PRD/Detailed Feature Specifications; edge cases]`

- [x] **T4.5 Phase Validation** `[activity: validate]`

  - Full suite + ruff; drift check against ADR-5/ADR-6; confirm `synthesis-conductor.md`, `inbox.md`, `settings.json`, `instructions.schema.json`, `hashi-instructions.schema.json`, `state-promoter.py`, `inbox-triage.py` are untouched (`git diff --stat main...HEAD`).
