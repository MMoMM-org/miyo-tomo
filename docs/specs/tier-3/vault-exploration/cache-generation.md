# Tier 3: Cache Generation

> Parent: [Vault Exploration](../../tier-2/workflows/vault-exploration.md)
> Status: Draft
> Related: [Structure Scan](structure-scan.md) · [MOC Indexing](../discovery/moc-indexing.md) · [Topic Extraction](topic-extraction.md)

---

## Implementation Status

> Steps 1-2 (structure scan, MOC indexing) are **implemented** (`vault-scan.py`, `moc-tree-builder.py`).
> Steps 3-7 (classification coverage, frontmatter sampling, tag analysis, orphan detection, metadata) are **specified but not yet implemented** — they are Phase 4 items.

## 1. Purpose

Define how vault-explorer assembles all scan results into the final `discovery-cache.yaml` file. This is the last step of `/explore-vault` — after structure scan, MOC indexing, frontmatter sampling, tag analysis, and orphan detection.

## 2. Assembly Order

The cache is built sequentially — each step depends on prior results:

```
1. Structure scan results    → vault_structure section
2. MOC indexing results      → map_notes section + placeholder_mocs
3. Classification coverage   → classifications section (computed from map_notes)
4. Frontmatter sampling      → frontmatter_usage section
5. Tag analysis              → tag_patterns section
6. Orphan detection          → orphans section
7. Metadata                  → cache_version, last_scan, scan_stats
```

## 3. Sections

### 3.1 Metadata

```yaml
cache_version: 1
last_scan: "2026-04-09T14:30:00Z"    # ISO 8601, UTC

scan_stats:
  total_notes: 614
  total_map_notes: 27
  total_classification_maps: 10
  total_tags_unique: 89
  scan_duration_seconds: 45
```

### 3.2 Vault Structure

From [Structure Scan](structure-scan.md):

```yaml
vault_structure:
  concepts_mapped: { ... }   # note counts per concept
  unmapped_folders: [ ... ]  # folders not claimed by concepts
  total_notes: 614
  total_files: 673
```

### 3.3 Map Notes

From [MOC Indexing](../discovery/moc-indexing.md):

```yaml
map_notes:
  - path: string
    title: string
    discovered_via: "path" | "tag" | "both"
    level: integer
    parent_moc: string | null
    child_mocs: string[]
    state: string | null
    topics: string[]
    sections: string[]
    linked_notes: integer
    classification: integer | null

placeholder_mocs:
  - target: string
    referenced_by: string
    section: string | null      # specified, not yet implemented
```

### 3.4 Classification Coverage

Computed by aggregating `map_notes` data:

```yaml
classifications:
  2000:
    map_count: 3              # MOCs classified under 2000
    note_count: 35            # non-MOC notes linked from those MOCs
    top_keywords: [...]       # union of all MOC topics in this category
  2600:
    map_count: 1
    note_count: 28
    top_keywords: [...]
```

**Computation:**
```
For each classification category in the profile:
  map_count = count(map_notes where classification == category)
  note_count = sum(map_notes.linked_notes where classification == category)
  top_keywords = deduplicate(flatten(map_notes.topics where classification == category))
```

### 3.5 Frontmatter Usage

From sampling N notes (default: 50, configurable):

```yaml
frontmatter_usage:
  UUID: 0.95           # fraction of sampled notes with this field
  DateStamp: 0.95
  Updated: 0.90
  title: 0.98
  tags: 0.99
  Summary: 0.60
  aliases: 0.30
  banner: 0.15
```

**Sampling strategy:** Pick N notes randomly from `atomic_note` paths. Read frontmatter via `kado-read` (operation: `frontmatter`). Count field presence.

### 3.6 Tag Patterns

From `kado-search listTags` + per-prefix counting:

```yaml
tag_patterns:
  type:
    "note/normal": 180
    "others/moc": 27
  status:
    "inwork/💭": 23
    "done/✅": 45
  topic:
    "knowledge/lyt": 25
    "applied/ai": 18
    "applied/tools": 12
```

**Process:**
```
1. kado-search listTags → all unique tags
2. Group by first segment (prefix)
3. For each tag: kado-search byTag → count results
4. Store counts per tag value under each prefix
```

**Optimization:** If listTags returns counts, skip per-tag counting.

### 3.7 Orphan Detection (Specified, not yet implemented)

```yaml
orphans:
  unlinked_notes: 12          # Tomo-managed notes with no incoming links
  missing_targets: 3          # wikilinks pointing to non-existent notes
  unlinked_paths:             # optional detail
    - "Atlas/202 Notes/some-orphan.md"
    - "Atlas/202 Notes/another-orphan.md"
```

**Scope:** Only notes tagged with the lifecycle prefix (`#MiYo-Tomo/*`) are checked for orphans. Unmanaged notes are the user's business.

**Detection method:**
```
For each Tomo-managed note (byTag #MiYo-Tomo/*):
  Check if any other note links to it (heuristic: search by name)
  If no incoming links found → orphan
```

**Missing targets:** Detected during MOC indexing — wikilinks that don't resolve to any file.

## 4. File Writing

The cache is written as a single YAML file:

- **Path:** `discovery-cache.yaml` in the Tomo instance directory (NOT in the vault)
- **Written via:** local filesystem (Tomo has write access to its own instance dir)
- **NOT written via Kado** — the cache is Tomo-internal, not vault content
- **Atomicity:** write to temp file first, then rename (prevent partial writes)

## 5. Cache File Size

Expected sizes for typical vaults:

| Vault size | Notes | MOCs | Cache file size |
|------------|-------|------|----------------|
| Small | <100 | <10 | ~5 KB |
| Medium | 100-500 | 10-30 | ~15 KB |
| Large | 500-2000 | 30-100 | ~50 KB |
| Very large | 2000+ | 100+ | ~100+ KB |

No compression needed for MVP. If cache files grow >1MB, consider trimming low-value data (frontmatter_usage percentages, rarely-used tag counts).

## 6. Validation (Specified, not yet implemented)

After writing, vault-explorer validates the cache:

1. **Parseable:** YAML loads without error
2. **cache_version** present and matches expected version
3. **last_scan** is a valid ISO 8601 timestamp
4. **map_notes** is a list with at least one entry (warn if empty)
5. **No NaN or Infinity values** in numeric fields
6. **All paths are vault-relative** (no absolute paths leaked)

If validation fails: log error, keep previous cache, warn user.

## 7. Overwrite Behavior

`/explore-vault` always generates a **fresh cache** — it does not merge with the previous one. Reasons:
- MOCs may have been deleted or renamed
- Notes may have been moved or removed
- A merge would preserve stale data from deleted content

The previous cache is simply overwritten. No backup is kept (it's a derived artifact, fully rebuildable).

## 8. Progress Reporting

During generation, vault-explorer reports progress:

```
🔍 Vault exploration started
   Scanning structure... 614 notes in 8 concept folders
   Indexing MOCs... 27/27 (3 placeholders found)
   Sampling frontmatter... 50/50
   Analyzing tags... 89 unique tags across 4 prefixes
   Detecting orphans... 12 unlinked managed notes
   Writing cache... done (23 KB)
📦 Discovery cache updated (2026-04-09T14:30:00Z)
```

## 9. Error Handling

| Error | Impact | Recovery |
|-------|--------|----------|
| Kado unavailable | Fatal | Abort /explore-vault, report error |
| Single MOC read fails | Non-fatal | Skip that MOC, log warning, continue |
| Tag count query fails | Non-fatal | Use count=0, log warning |
| Frontmatter sample read fails | Non-fatal | Reduce sample size, log warning |
| Cache write fails | Fatal | Keep previous cache, report error |
| YAML serialization error | Fatal | Debug issue, report with details |
