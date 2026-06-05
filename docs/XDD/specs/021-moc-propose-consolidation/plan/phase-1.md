---
title: "Phase 1: Cache Foundation (builder + lib + schema + config)"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Cache Foundation (builder + lib + schema + config)

## Phase Context

**GATE**: Read before starting.

**Specification References**:
- `[ref: SDD/Building Block View/Directory Map]` — lib module split
- `[ref: SDD/Application Data Models]` — MocStructureCache, CacheEntry, UpParseResult
- `[ref: SDD/ADR-1,5,8,9]` — schema Option A, tag-primary, TTL, lib extraction
- `[ref: PRD/Feature 1, Feature 2, Feature 4]`

**Key Decisions**:
- Tag-primary discovery (`#type/others/moc`); exclude wins over tag (OQ-5).
- Real in-scope vault set is the placeholder denominator (fixes the 224).
- `up_parse` is the SSoT for both `up` forms; inline wins (ADR-2).
- Reuse `cache-builder` TTL primitives (CACHE_VERSION, last_scan, ISO validation, atomic write).

**Dependencies**: none (foundation). Schema-first: this phase must complete before Phase 2 consumers read the cache.

---

## Tasks

This phase delivers the rebuilt MOC-structure cache builder and its supporting `lib/` modules, the cache schema/file, and the scope config — the producer side, fully tested offline.

- [ ] **T1.1 `lib/up_parse.py` — dual-`up` SSoT** `[parallel: true]` `[activity: domain-modeling]` `[ref: SDD/Application Data Models UpParseResult; SDD/Implementation Examples; ADR-2,6]`
  1. Prime: read the three current inline-only sites (`moc-tree-builder.py:49`, `moc-discovery.py:1271`, `atomic-note-indexer.py:162`).
  2. Test (RED): inline-only → target+source=inline; frontmatter-only (list/scalar/`[[X]]`) → target+source=frontmatter; BOTH present, differing targets → inline wins; empty (`up:`, `up: []`, null, `up::` w/o wikilink) → absent; alias `[[Stem|Alias]]` → stem; anchor `[[X#^id]]` → X.
  3. Implement: `parse_up(frontmatter: dict, body: str) -> UpParseResult` (inline regex + frontmatter list/scalar extraction + anchor strip).
  4. Validate: `pytest tests/test_up_parse.py`; lint.
  5. Success: frontmatter-`up:` no longer false-orphan `[ref: PRD/AC F2#1]`; inline wins `[ref: PRD/AC F2#2]`; empty→absent `[ref: PRD/AC F2#3]`.

- [ ] **T1.2 `lib/moc_scan.py` — tag-primary discovery + scope/exclude** `[parallel: true]` `[activity: backend-api]` `[ref: SDD/Runtime View; ADR-5; OQ-1,5]`
  1. Prime: `kado_client.search_by_tag`, `list_notes`/`list_dir`; current `discover_via_paths/tags` (`moc-tree-builder.py:157,185`).
  2. Test (RED): `#type/others/moc` in-scope → discovered as MOC (kind=moc); same tag in an excluded path (daily/template) → NOT a MOC (exclude wins); exclude matches precise prefixes incl. the trailing-space `Calendar/301 Daily/ ` gotcha; scope read from config (default `map_note + atomic_note`).
  3. Implement: tag-primary discovery, client-side scope/exclude prefix filter (byTag has no server filter), returns MOC + in-scope note paths.
  4. Validate: `pytest tests/test_moc_scan.py` (with a fake Kado client); lint.
  5. Success: tag-in-scope recognized `[ref: PRD/AC F1#3]`; exclude wins `[ref: PRD/AC F1#5]`; config-driven scope `[ref: PRD/AC F1#4]`.

- [ ] **T1.3 `lib/placeholder_detect.py` — real-vault denominator** `[parallel: true]` `[activity: backend-api]` `[ref: SDD/Complex Logic placeholder correction; ADR-5]`
  1. Prime: current `detect_placeholders` (`moc-tree-builder.py:464+`, v0.3.0 anchor logic) + `tests/test_moc_tree_placeholders.py` (10 green).
  2. Test (RED): move the 10 existing cases; ADD: anchored/plain link to an EXISTING in-scope note → NOT a placeholder; link to genuinely-missing note → placeholder; denominator is the real in-scope vault set, not the discovered-MOC set.
  3. Implement: extract anchor-strip + per-note dedup here; accept a real `in_scope_vault_paths` set as the denominator. Use O(1) set/dict lookups for the MOC-name resolution (precompute a `{stem.lower(): path}` index once) — addresses review finding L1 (the old `resolve_link_to_path` did two O(M) scans per link) so this is fixed fresh here rather than patched in the about-to-be-replaced `moc-tree-builder`.
  4. Validate: `pytest tests/test_moc_tree_placeholders.py` (extended); lint.
  5. Success: 397→~171 on real data `[ref: PRD/M2]`; block-ref/heading anchors to existing notes excluded `[ref: PRD/AC F4#3]`.

- [ ] **T1.4 MOC-structure cache builder + schema + scope config** `[activity: data-architecture]` `[ref: SDD/Application Data Models; ADR-1,3,8,9; SDD/Directory Map]`
  1. Prime: `cache-builder.py` TTL primitives; `vault-example.yaml` `concepts.*`.
  2. Test (RED): builder assembles `entries[]` (kind moc|note, path/stem/title/topics/up_state/up_target/up_source/tags via T1.1–T1.3); writes `moc-structure-cache.yaml` with `moc_cache_version`, `last_scan`, `ttl_days`, `scope_paths`, `exclude_paths`, `moc_tag`; atomic tmp-rename; empty scope → empty entries, no crash; `up_state` resolves valid/broken vs the MOC set.
  3. Implement: rebuild `moc-tree-builder.py` to orchestrate `lib/moc_scan` + read + `lib/up_parse` + `lib/placeholder_detect` → cache; add `tomo.moc_structure_cache.{scope_paths,exclude_paths,ttl_days,moc_tag}` to `vault-example.yaml` (+ instance config). Bump `# version:`.
  4. Validate: `pytest tests/` (builder unit tests with fake Kado); lint; confirm `discovery-cache.yaml` `map_notes` still populated via cache-builder.
  5. Success: cache built with last_scan `[ref: PRD/AC F1#1-2]`; metadata-only `[ref: PRD/AC Privacy#2]`; scope config present `[ref: PRD/AC F1#4]`.

- [ ] **T1.5 Phase 1 Validation** `[activity: validate]`
  - Run all Phase 1 unit tests; lint. Verify the cache file shape matches SDD Application Data Models exactly (schema-first gate before Phase 2). Confirm no consumer yet reads the new fields.
