---
title: "Phase 2: /moc-propose consumes cache + dual-up + case-a"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: /moc-propose consumes cache + dual-up + case-a

## Phase Context

**GATE**: Read before starting.

**Specification References**:
- `[ref: SDD/Runtime View Primary Flow]` — cache-backed /moc-propose
- `[ref: SDD/Implementation Examples case-(a) seam]`
- `[ref: SDD/ADR-1,2,3,6,7,8]`
- `[ref: PRD/Feature 1, Feature 3]`

**Key Decisions**:
- Loader shim projects `entries[kind==moc]` → `map_notes` so Phases 1–6 stay unchanged (ADR-1).
- `/moc-propose` rebuilds-if-stale inline; `/explore-vault` force-rebuilds (ADR-3).
- Case (a) seats at the Phase 6 match point; orphan MOCs become eligible (relax `restrict_to_atomic_note_paths`).
- Top-3 link candidates (OQ-4); reason in proposal-doc + `/execute` instruction (OQ-6), no note write.

**Dependencies**: Phase 1 (cache file + `lib/up_parse` + schema) must be complete.

---

## Tasks

This phase makes `/moc-propose` read the cache (no live full pull), detect both `up` forms, and emit orphan link-or-create suggestions.

- [ ] **T2.1 `lib/moc_cache_loader.py` — TTL + rebuild-if-stale + shim** `[activity: backend-api]` `[ref: SDD/Application Data Models loader shim; ADR-1,3,8]`
  1. Prime: `moc-discovery.py` `validate_cache_loaded:583`; `cache-builder` ISO parse.
  2. Test (RED): fresh (`now − last_scan ≤ ttl_days`) → load, no rebuild; stale/missing/corrupt → invoke builder inline then load; future `last_scan` → treated fresh; shim exposes `cache["map_notes"] = entries[kind==moc]`.
  3. Implement: loader with staleness check, inline rebuild trigger (rebuild-if-stale), shim projection.
  4. Validate: `pytest tests/test_moc_cache_loader.py`; lint.
  5. Success: no full tree-build when fresh `[ref: PRD/AC F1#1, M1]`; inline rebuild when stale `[ref: PRD/AC F1#2]`.

- [ ] **T2.2 moc-discovery Phase 6.5 uses `up_parse` (frontmatter + inline)** `[activity: backend-api]` `[ref: SDD/ADR-6; PRD/Feature 2]`
  1. Prime: Phase 6.5 `_UP_MARKER_RE:1271`, `_extract_first_up_marker`, the per-candidate `read_note:1404`.
  2. Test (RED): candidate with frontmatter `up:` only → valid (not orphan); inline only → valid; both differing → inline target; broken target (not in MOC set) → broken; empty → absent.
  3. Implement: replace inline-only regex with `lib/up_parse.parse_up`, reading frontmatter from the same fetched content (no extra Kado round-trip); resolve valid/broken vs the cache MOC set.
  4. Validate: `pytest` Phase 6.5 tests; lint. Retrofit `atomic-note-indexer.py:162` to `up_parse` (or note its removal in Phase 3).
  5. Success: frontmatter-`up` notes not orphaned `[ref: PRD/AC F2#1]`; inline-wins `[ref: PRD/AC F2#2]`.

- [ ] **T2.3 `lib/orphan_link.py` — case (a) link-or-create (notes AND MOCs)** `[activity: backend-api]` `[ref: SDD/Implementation Examples case-(a); ADR-7; OQ-4; PRD/Feature 3]`
  1. Prime: Phase 5 parent-resolution keyword overlap; Phase 6 dedup `duplicates_skipped`; `restrict_to_atomic_note_paths:502`.
  2. Test (RED): orphan matching ≥1 existing MOC ≥ threshold → `link_existing` with top-3 candidates; orphan matching none → `create_new` + reason; orphan MOC eligible (not filtered out); single-note cluster routed to link-or-create instead of silent skip.
  3. Implement: `resolve_orphan()` emitting `OrphanLinkSuggestion`; relax `restrict_to_atomic_note_paths` so orphan MOCs are candidates; wire into the Phase 6 match point.
  4. Validate: `pytest tests/test_orphan_link.py`; lint.
  5. Success: top-3 link offered `[ref: PRD/AC F3#1]`; create-new+reason `[ref: PRD/AC F3#2]`; MOCs handled `[ref: PRD/AC F3#3]`.

- [ ] **T2.4 moc-architect renders link-or-create in the proposal-doc** `[activity: backend-api]` `[ref: SDD/Runtime View; OQ-6; PRD/Feature 3]`
  1. Prime: `moc-architect.md` workflow + `suggestions-reducer` rendering.
  2. Test (RED): proposal-doc shows, per orphan, either top-3 link options OR a create-new entry with a reason line + an `/execute` instruction to stamp the reason into the note(s); `/moc-propose` writes no vault note.
  3. Implement: render path for `OrphanLinkSuggestion`; bump `# version:` on the agent. Rationale to `docs/tomo/...`, imperatives only in the agent (CON-4).
  4. Validate: render unit/snapshot test against a real artefact (`feedback_fixture_from_live_render`); lint.
  5. Success: link-or-create rendered, no note write `[ref: PRD/AC F3#2; CON-3]`.

- [ ] **T2.5 Phase 2 Validation** `[activity: validate]`
  - Run Phase 2 tests; lint. Verify Phases 1–6 behaviour unchanged via the shim (regression on existing moc-discovery tests). Confirm `/moc-propose` does no full live pull when the cache is fresh.
