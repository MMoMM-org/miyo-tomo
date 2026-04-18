---
title: "Phase 2: MOC Discovery + Cache Assembly"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: MOC Discovery + Cache Assembly

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `docs/XDD/reference/tier-3/discovery/moc-indexing.md` — MOC tree building, path + tag discovery, level computation
- `docs/XDD/reference/tier-3/vault-exploration/cache-generation.md` — cache YAML assembly, validation, atomic write
- `docs/XDD/reference/tier-2/components/discovery-cache.md` — cache schema, staleness policy, degraded operation

**Key Decisions**:
- MOC discovery uses both path-based AND tag-based detection, deduplicating
- Tree building: root MOCs (no up:: parent) → level 0; cycle detection required
- Cache overwrites on each scan (no merge)
- Cache written atomically (temp file → rename)

**Dependencies**:
- Phase 1 (Kado client, vault-scan.py, topic-extract.py)

---

## Tasks

Builds the MOC indexing pipeline and assembles the discovery cache from all scan results.

- [ ] **T2.1 MOC Tree Builder** `[activity: build-feature]`

  1. Prime: Read `[ref: docs/XDD/reference/tier-3/discovery/moc-indexing.md]` and `[ref: docs/XDD/reference/tier-3/lyt-moc/moc-matching.md]`
  2. Test: Discovers MOCs via path (list_dir on map_note paths) AND tag (search_by_tag on map_note tags); deduplicates; reads each MOC to extract title, H2 sections, wikilinks, frontmatter (up::, related::, mapState); builds parent/child/sibling tree; computes levels (root=0); detects cycles; identifies placeholder MOCs; calls topic-extract for each MOC
  3. Implement: Create `scripts/moc-tree-builder.py` — uses kado_client to discover and read MOCs, builds tree structure, outputs JSON array of MOC entries matching cache schema (path, title, discovered_via, level, parent_moc, child_mocs, sibling_mocs, topics, sections, linked_notes, classification)
  4. Validate: Outputs valid JSON; tree has no cycles; levels are consistent (child.level > parent.level)
  5. Success: MOC tree JSON matches discovery-cache map_notes[] schema; placeholder MOCs detected

- [ ] **T2.2 Cache Builder** `[activity: build-feature]`

  1. Prime: Read `[ref: docs/XDD/reference/tier-3/vault-exploration/cache-generation.md]` and `[ref: docs/XDD/reference/tier-2/components/discovery-cache.md]`
  2. Test: Assembles all scan results into single discovery-cache.yaml; includes cache_version, last_scan (ISO 8601 UTC), scan_stats, vault_structure (from vault-scan), map_notes (from moc-tree-builder), classifications (aggregated from map_notes), frontmatter_usage, tag_patterns, orphans; writes atomically; validates output YAML
  3. Implement: Create `scripts/cache-builder.py` — takes JSON inputs from vault-scan and moc-tree-builder (via file or stdin), optional frontmatter/tag/orphan data, assembles into YAML, validates, writes to specified output path
  4. Validate: Output parses as valid YAML; has all required top-level sections; cache_version present; last_scan is valid ISO 8601
  5. Success: discovery-cache.yaml matches spec schema; atomic write works (no partial files on error)

- [ ] **T2.3 Phase Validation** `[activity: validate]`

  - moc-tree-builder produces valid MOC tree JSON. cache-builder assembles valid discovery-cache.yaml. Both scripts handle empty inputs gracefully (new vaults with no MOCs). Pipeline: vault-scan → moc-tree-builder → cache-builder works end-to-end.
