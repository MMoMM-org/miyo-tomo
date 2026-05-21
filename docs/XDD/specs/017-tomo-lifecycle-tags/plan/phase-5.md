---
title: "Phase 5: F-43 MOC-Consumption (F-47.P4)"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: F-43 MOC-Consumption (F-47.P4)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/Feature 5; AC-5.1..AC-5.4]` — F-43 MOC-consumption acceptance gap closure
- `[ref: PRD/§6.2; lines: 466-537]` — `/moc-propose` lifecycle flow diagram (discovery → accept → bundled instructions → cleanup)
- `[ref: SDD/Cross-Spec Coordination; lines: 956-960]` — 013 F-43 PAUSED coordination rules (T6.2/T6.4 unblock map)
- `[ref: docs/XDD/specs/013-moc-creation-skill/plan/phase-6.md T6.2 T6.4]` — paused tasks resumed by this phase
- `[ref: docs/XDD/reference/tier-3/lyt-moc/new-moc-proposal.md]` — MOC title patterns + duplicate thresholds (existing F-43 reference)
- `[ref: docs/XDD/reference/tier-3/lyt-moc/moc-matching.md]` — scoring algorithm for parent resolution (existing F-43 reference)
- `[ref: tomo/scripts/lib/squelch.py]` — F-43 squelch sidecar (existing — reused for un-ticked clusters)
- `[ref: feedback_classification_guard]` — Dewey MOCs are MOC-only — never link notes directly

**Key Decisions**:
- **Bundled actions** (PRD AC-5.1 + Design note): One accepted cluster → one bundled instructions doc containing 1× `create_moc` + N× child-relationship-update actions. NOT N instructions docs (one per child). Keeps Hashi apply transactional per cluster.
- **Cluster destination**: New MOCs land in `<inbox_path>/<YYYY-MM-DD>_<slugified-moc-title>.md` per AC-5.1. User-initiated move to a topic folder (e.g. `200 MOCs/`) is **outside F-47 scope** (AC-5.4).
- **Un-ticked clusters → squelch** (AC-5.2): Per-cluster rejection is handled via the **existing** F-43 squelch-persistence mechanism (`state/moc-squelch.json`). No file-level `rejected` state on the proposal-doc (locked OQ12).
- **Single bundled instructions doc** for multi-cluster acceptance (AC-5.2): 3 ticked clusters → 1 instructions doc with 3× `create_moc` + N× child-relationship-update actions, NOT 3 separate instructions docs.

**Dependencies**:
- **Hard**: Phase 3 must be merged. The state-promoter dispatches the MOC-branch of `instruction-builder` (this phase implements that branch).
- **Hard**: Phase 2 producers must emit `tomo:` block (T2.4 for proposal-doc; T2.3 for instructions).
- **Hashi consumer side**: bundled `create_moc` + child-update actions per cluster — verify Hashi 0.2.0 destination-collision guard (F-43 T1.1) is live and handles same-MOC dependent failures correctly.

---

## Tasks

This phase closes the F-43 acceptance gap. When the user ticks `[x] Accept` on a cluster in a `pending-accept` proposal-doc and re-runs `/inbox`, the state-promoter (already wired in Phase 3) dispatches the MOC-branch of `instruction-builder`. The MOC-branch produces ONE bundled instructions doc with `create_moc` + child-relationship-update actions. Un-ticked clusters persist to squelch.

- [ ] **T5.1 `suggestion-parser` MOC-branch dispatch** `[activity: parser-extension]`

  1. Prime: Read `tomo/scripts/lib/suggestion-parser.py` (or wherever the parser entry point lives) end-to-end. Identify the existing `_is_moc_proposal_doc` heuristic and `enumerate_all_moc_sections` function from F-43 work. Read F-43 plan T6.5 / T6.5.5 commits for parser-extension precedent. Read PRD §6.2 flow diagram — Step "instruction-builder MOC-branch via suggestion-parser MOC dispatch" `[ref: PRD/§6.2; lines: 503-517]`. Read PRD AC-5.1 for the input shape (ticked clusters with child wikilinks) and output shape (1× create_moc + N× updates per cluster).
  2. Test: `tests/test_suggestion_parser_moc_branch.py::test_dispatch_classified_as_moc_proposal_via_tomo_doc_type` (input doc has `tomo.doc_type=moc-proposal` → parser dispatches MOC-branch; filename heuristic NO LONGER needed but kept as fallback for old fixtures); `test_enumerate_returns_only_ticked_clusters` (3 clusters: MOC01 ticked, MOC02 unticked, MOC03 ticked → returns [MOC01, MOC03]); `test_child_wikilinks_extracted_per_cluster` (cluster with 5 children → 5 wikilink strings); `test_unticked_clusters_returned_separately_for_squelch` (MOC02 returned as squelch candidate); `test_override_checkbox_per_child` (existing F-43 `up::` override behaviour — preserved per PRD AC-4.x in F-43 spec).
  3. Implement: Extend parser to classify by `tomo.doc_type == "moc-proposal"` first (preferred), falling back to existing filename heuristic for historical compat. Add return signature: `(ticked_clusters, unticked_clusters)` where `ticked_clusters` is a list of `{title, children, supporting_items, parent_moc_hint}` dicts and `unticked_clusters` is a list of `{title, topic_signature}` dicts ready for squelch insertion. Bump `# version:`.
  4. Validate: `pytest tests/test_suggestion_parser_moc_branch.py -v`; `pytest tests/ -v` — no F-43 regressions; `ruff check`.
  5. Success: Parser correctly identifies F-47 v1.2 proposal-docs via `tomo.doc_type` AND returns ticked vs unticked clusters separately `[ref: PRD/AC-5.1, AC-5.2]`. Filename-based dispatch still works for any pre-F-47 fixtures in `tests/` (backwards-compat for test data only — not for production proposal-docs, per OQ4/5).

- [ ] **T5.2 `instruction-builder.md` MOC-branch — bundled actions emission** `[activity: agent-prompt-update]`

  1. Prime: Read `tomo/dot_claude/agents/instruction-builder.md` Pass-2 dispatch section. Confirm it currently produces ONE instructions doc per dispatch. Read PRD AC-5.1 (bundled actions per cluster), AC-5.2 (multi-cluster → single bundled doc), AC-5.3 (Hashi cleanup trashes instructions + proposal-doc), AC-5.4 (MOC lands in inbox folder). Read PRD §6.2 MOC-branch step for the action list. Read existing `tomo/schemas/instructions.schema.json` — confirm `create_moc` + `update_frontmatter` / `update_relationships` actions exist (they should — F-43 already needs `create_moc`).
  2. Test: N/A (agent prompt). Manual smoke after T5.5: ticked proposal-doc with 1 cluster (3 children) → produces 1 instructions doc with 1× `create_moc` (target path `<inbox_path>/<YYYY-MM-DD>_<slug>.md`) + 3× child-relationship-update actions; proposal-doc's `tomo.state` flips to `accepted`. Multi-cluster smoke: 3 ticked + 2 unticked → 1 instructions doc bundles 3× `create_moc` + N× child updates; unticked → squelch (T5.3).
  3. Implement: Extend `instruction-builder.md` Pass-2 prompt with explicit MOC-branch handling:
     - When input doc has `tomo.doc_type=moc-proposal`, invoke `suggestion-parser` MOC-branch (T5.1) to get `(ticked_clusters, unticked_clusters)`.
     - For each ticked cluster: emit `create_moc` action with `destination = <inbox_path>/<YYYY-MM-DD>_<slugified-title>.md` (slug rules per `obsidian-filename.sanitize_stem`); emit `update_frontmatter` or `update_relationships` action per child writing `up:: [[<moc-title>]]` (and optional `related::` per cluster spec).
     - Bundle ALL actions into ONE `tomo-tmp/instructions.json` payload.
     - Call `instruction-render.py` with upstream-type flag = `moc-proposal` so `tomo.source_moc_proposal=<proposal-path>` is emitted (T2.3 already wired).
     - Pass un-ticked clusters to T5.3 squelch helper.
     - STRICT: "Multi-cluster acceptance produces ONE instructions doc with ALL clusters' actions bundled. NOT N separate instructions docs."
     - Bump `# version:`.
  4. Validate: Run `./scripts/update-tomo.sh`; restart Claude. Smoke per step 2. Verify: produced instructions doc has exactly 1× `create_moc` per cluster ticked + the correct number of child updates; `tomo.source_moc_proposal` is set; proposal-doc state flips to `accepted`.
  5. Success: Multi-cluster acceptance produces single bundled instructions doc per PRD `[ref: PRD/AC-5.1, AC-5.2, AC-5.4]` `[ref: PRD/§6.2; lines: 503-517]`. Unticked clusters routed to T5.3 squelch.

- [ ] **T5.3 Squelch persistence integration for un-ticked clusters** `[activity: state-management]`

  1. Prime: Read `tomo/scripts/lib/squelch.py` (F-43 deliverable: load/save/decrement/add-or-replace/is_active). Read F-43 plan T5.1/T5.2 for squelch-write call shape. Read PRD AC-5.2 — un-ticked clusters persist to `state/moc-squelch.json` via existing mechanism, NO new state added on the proposal-doc. Read PRD §3 Locked decisions OQ12 (no file-level rejected state).
  2. Test: `tests/test_moc_consumption_squelch.py::test_unticked_clusters_added_to_squelch` (fixture: proposal-doc with 1 ticked + 2 unticked clusters; after MOC-branch run, `state/moc-squelch.json` contains entries for the 2 unticked topic-signatures with `runs_remaining` = configured default); `test_ticked_clusters_not_added_to_squelch`; `test_squelch_signature_collision_replaces_no_duplicate` (existing F-43 invariant — must not regress); `test_squelch_state_persistence_atomic` (existing F-43 invariant — tmp-then-rename).
  3. Implement: In `instruction-builder.md` (or a shared helper script invoked from MOC-branch — operator's choice), after bundling actions for ticked clusters, iterate `unticked_clusters` from T5.1 and call `squelch.add_or_replace(registry, entry)` per cluster; persist via `squelch.save_registry_atomic(...)`. No new code in `squelch.py` itself — reuse F-43 API.
  4. Validate: `pytest tests/test_moc_consumption_squelch.py -v`; verify `state/moc-squelch.json` after a multi-cluster smoke run contains expected entries; verify atomicity via process-kill mid-write (manual or via a fault-injection fixture); existing F-43 squelch tests still pass.
  5. Success: Un-ticked clusters persist exactly as F-43 designed; no file-level rejected state on the proposal-doc `[ref: PRD/AC-5.2]` `[ref: PRD/OQ12]`.

- [ ] **T5.4 F-43 T6.2 remaining 5 modes + T6.4 launch-gate regression** `[activity: integration-test]`

  1. Prime: Read `docs/XDD/specs/013-moc-creation-skill/plan/phase-6.md` T6.2 (remaining 5 modes: folder, class, title, free-text, scan) and T6.4 (final launch gate). Both are PAUSED on F-47.P2 + F-47.P4 per SDD §Cross-Spec Coordination `[ref: SDD/Cross-Spec Coordination; lines: 956-960]`. Read F-43 README + plan to recall the specific test scenarios for each mode.
  2. Test: T6.2 modes — manual smoke for each: `/moc-propose folder:<path>`, `/moc-propose class:<class>`, `/moc-propose title:<regex>`, `/moc-propose <free text>`, `/moc-propose --scan`. Each must produce a proposal-doc with `tomo.state=pending-accept`; orchestrator discovery (Phase 3 wiring) sees it; ticking accept + re-running `/inbox` produces bundled instructions; Hashi can apply them (use Hashi 0.2.0 destination-collision guard from F-43 T1.1). T6.4 launch gate — end-to-end accept-flow against Privat-Test for all 5 modes + the original tag-mode = 6 happy-path E2E runs.
  3. Implement: This is largely test runs, not code. Document each run's outcome in `evolution/2026-05/` (or wherever F-43 T6.2 tracking lives). Update `docs/XDD/specs/013-moc-creation-skill/README.md` to mark T6.2 + T6.4 as DONE for the modes that pass. If any mode reveals a bug, file as a F-47 deviation in this phase file (NOT a F-43 regression — F-43 was paused expecting F-47 changes).
  4. Validate: All 6 modes (5 paused + 1 tag-mode regression) pass end-to-end. Run `pytest tests/test_moc_*.py -v` — F-43 unit suite passes. Update 013 README + plan checkboxes.
  5. Success: F-43 T6.2 + T6.4 closed `[ref: SDD/Cross-Spec Coordination; lines: 956-960]` `[ref: PRD/Success Metrics row "F-43 unblock"]`. F-43 spec status moves toward COMPLETE (013 README updated).

- [ ] **T5.5 Phase 5 Validation** `[activity: validate]`

  Run `pytest tests/test_suggestion_parser_moc_branch.py tests/test_moc_consumption_squelch.py -v`. Run full `pytest tests/ -v` — no regressions. Run `ruff check`. Live E2E acceptance flow: prepare Privat-Test with 5+ notes tagged for a topic; run `/moc-propose tag:<topic>` → proposal-doc lands with `tomo.state=pending-accept`; tick `[x] Accept` on MOC01 (3 children) in Obsidian; run `/inbox` → orchestrator discovers proposal-doc, dispatches instruction-builder MOC-branch, produces ONE instructions doc with 1× `create_moc` + 3× `update_frontmatter`/`update_relationships`; proposal-doc state flips to `accepted`. Hand off to Hashi (or simulate by reading instructions JSON): Hashi applies actions, flips `tomo.state=applied`, trashes instructions + proposal-doc per `source_moc_proposal` ref (Phase 6 ships the formal Hashi handoff but Hashi 0.2.0 collision guard is live from F-43 T1.1 — the apply side should work). New MOC file in inbox folder survives cleanup as a real vault artefact. Verify against PRD AC-5.1..5.4 end-to-end. Verify F-43 T6.2 multi-mode smoke per T5.4. Update 013 README marking T6.2 + T6.4 as DONE.
