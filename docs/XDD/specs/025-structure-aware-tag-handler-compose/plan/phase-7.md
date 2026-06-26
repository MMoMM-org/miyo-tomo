---
title: "Phase 7: Integration, Docs & Live Validation"
status: done
version: "1.0"
phase: 7
---

# Phase 7: Integration, Docs & Live Validation

## Phase Context

**GATE**: Read before starting.
- `[ref: SDD/Deployment View]`, `[ref: SDD/Risks and Technical Debt]`
- `tomo/config/tag-handlers/tsukai.json` (the motivating handler — user-owned, seeded create-only)
- Memory: sync instance before any live walk; run cheap paths from host against live Kado; tsukai config is
  create-only seeded (don't silently overwrite a populated map).

**Key Decisions**: migrate `tsukai.json` to `output_format` (table_row, newest_first, per_item); ship WHY
docs; validate end-to-end against the table-shaped Tomo Dev Log fixture through Hashi.

**Dependencies**: **Phases 1–6 complete & green.**

---

## Tasks

Proves the feature end-to-end on the real vault and lands the docs + the motivating config.

- [x] **T7.1 WHY docs mirrors** `[activity: documentation]` `[parallel: true]` — target_structure / tag-handler-group / tag-handler-compose mirrors written (549b0c5); spec-compliance PASS.
  1. Prime: the docs/tomo mirroring rule `[ref: CLAUDE.md runtime-file rule]`
  2. Implement: add/refresh `docs/tomo/scripts/lib/target_structure.md`, `…/instruction-render.md`,
     `…/suggestions-reducer.md`, `…/tag-handler-resolve.md`, `…/tag-handler-group.md`, and the interpreter
     skill doc — WHY (ADR refs, the 3-way-drift + byte-exact-anchor rationale), not WHAT.
  3. Validate: docs reference the SDD ADRs; no rationale left only in runtime files.
  - Success: `[ref: SDD/Cross-Cutting]` WHY persisted outside runtime files.

- [x] **T7.2 Migrate tsukai handler to output_format** `[activity: config]` — output_format (table_row/newest_first/per_item) + `created` read-field added; map `{}` preserved; 15 schema tests (6e711b6); spec-compliance PASS.
  1. Prime: tsukai config + the create-only seed behaviour `[ref: SDD/Implementation Boundaries]`
  2. Test: the migrated config validates against the Phase-1 schema; existing populated `target.map` is
     preserved (do not overwrite).
  3. Implement: add `output_format` (table_row, newest_first, per_item, cells
     `[{field:created},{field:category},{synthesize:"one-line summary of what changed"}]`) to `tsukai.json`;
     document the migration (seeded create-only — update the repo source; note the instance copy is user-owned).
  4. Validate: schema-valid; map intact.
  - Success: `[ref: PRD/User Journey]` tsukai emits table rows.

- [x] **T7.3 End-to-end live validation (gated)** `[activity: integration-test]` — HOST-SIDE validation done (user choice): real `Efforts/Tomo Dev Log.md` `| Date | Type | Description |` header+separator read from live Kado, fed through tag-handler-compose.py → status=ok, resolved_anchor.value BYTE-EXACT to the note, 2 rows assembled, ADR-9 prose-skip proven; forced 2-vs-3 mismatch → fallback(cell_count_mismatch). NO vault mutation. **Full `/inbox` live apply DEFERRED to the user** with two preconditions: (1) add a `## Captures` heading above the table (the note currently has the table under H1 with no marker → marker_missing guard would fire); (2) verify Tsukai capture-insight emits a `created` frontmatter field (no live captures exist to confirm; `{field:created}` else renders empty).
  1. Prime: the live-walk memory rules (sync instance first; cheap-path-from-host) `[ref: SDD/Deployment View]`
  2. Test: with the Tomo Dev Log shaped as a table (header+separator+seed row), run `/inbox` over real
     tsukai captures; verify rows land newest-first directly under the header via Hashi; table intact;
     verify a forced mismatch surfaces the ⚠️ fallback in the suggestions doc.
  3. Implement: `./scripts/update-tomo.sh --yolo` to sync; run the walk; capture results in the inbox cost log.
  4. Validate: rows correct in the vault; suggestions-doc preview matched the applied output.
  - Success: `[ref: PRD/Success Metrics — Operational impact]` newest-first rows land end-to-end at least once.

- [x] **T7.4 Full-suite + parity regression** `[activity: validate]` — 1704 passed / 1 skipped; parity green; ruff clean; backward-compat (240 tag-handler tests) green.
  - `./venv/bin/python -m pytest tests/ -q` all green (incl. parity); `ruff check` clean. Confirm
    backward-compat: a handler without `output_format` is byte-identical to pre-025 behaviour `[ref: PRD/FR-15]`.
