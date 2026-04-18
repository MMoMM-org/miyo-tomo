# Tier 2: Discovery Cache

> Parent: [PKM Intelligence Architecture](../../tier-1/pkm-intelligence-architecture.md) — Knowledge Layer 4
> Status: Implemented
> Children: [MOC Indexing](../../tier-3/discovery/moc-indexing.md) · [Classification Matching](../../tier-3/discovery/classification-matching.md) · [Staleness Policy](../../tier-3/discovery/staleness-policy.md)

---

## 1. Purpose

Define the auto-generated semantic index that gives Tomo runtime knowledge about the vault's content. Built by vault-explorer via `/explore-vault`. Advisory — never authoritative.

## 2. Role in Knowledge Stack

Layer 4 enriches decisions but is never required:
- **With cache:** inbox-analyst matches notes to MOCs using topics, sections, and classification data
- **Without cache:** inbox-analyst reads MOCs on-demand via Kado (slower, still functional)
- **Cache never overrides config:** if vault-config says "notes go to Atlas/202 Notes/", the cache can't redirect them

## 3. Schema

```yaml
cache_version: integer
last_scan: ISO 8601 timestamp
scan_duration_seconds: integer

scan_stats:
  total_notes: integer
  total_map_notes: integer
  total_classification_maps: integer
  total_tags_unique: integer

# MOC index — one entry per map_note (full tree, all levels)
map_notes:
  - path: string
    title: string
    discovered_via: "path" | "tag" | "both"  # How vault-explorer found it
    level: integer             # 0 = top (classification), 1 = mid, 2+ = leaf
    parent_moc: string | null  # Path to parent MOC (forms the tree)
    child_mocs: string[]       # Paths to direct child MOCs
    state: string | null       # Map note maturity (from profile states)
    topics: string[]           # Extracted from content + linked notes
    sections: string[]         # H2 headings found in the MOC
    linked_notes: integer      # Count of outgoing wikilinks to non-MOC notes
    classification: integer | null  # Best-fit category number

# Classification coverage
classifications:
  <number>:
    map_count: integer
    note_count: integer
    top_keywords: string[]

# Tag usage patterns
tag_patterns:
  <prefix>:
    <tag_value>: integer       # Usage count

# Frontmatter field frequency
frontmatter_usage:
  <field_name>: float          # 0.0-1.0, fraction of notes using this field

# Orphan detection (Tomo-managed notes only: tagged with lifecycle prefix)
orphans:
  unlinked_notes: integer
  missing_targets: integer     # Wikilinks pointing to non-existent notes
```

## 4. Generation Process

Built by vault-explorer agent via `/explore-vault`:

1. **Enumerate map_notes** — find via configured paths AND tags:
   - `kado-search` (listDir) for each path in `concepts.map_note.paths`
   - `kado-search` (byTag) for each tag in `concepts.map_note.tags`
   - Deduplicate by path; record `discovered_via` for each
2. **Read each map_note** — `kado-read` note content
3. **Build MOC tree** — parse outgoing wikilinks; if a linked note is also a map_note, record parent/child relationship
4. **Compute level** — distance from a root MOC (no parent) determines `level`
5. **Extract topics** — parse content for key themes, linked note titles, section headings
6. **Sample frontmatter** — read N random notes, detect field patterns and frequencies
7. **Count tags** — `kado-search` by tag for each known prefix
8. **Detect orphans** — find Tomo-managed notes (lifecycle-tagged) with no incoming links
9. **Write cache** — save as `discovery-cache.yaml`

## 5. Staleness Policy

- Cache includes `last_scan` timestamp
- Skills check cache age before using it
- **Warning threshold:** >7 days old → warn user, suggest `/explore-vault`
- **No expiry:** stale cache is better than no cache
- **Refresh trigger:** manual via `/explore-vault` only (no automatic background refresh)

## 6. Degraded Operation

Without a cache (first run before `/explore-vault`, or deleted cache):
- inbox-analyst reads MOCs on-demand via Kado for each inbox item
- Classification falls back to profile keywords only (no vault-specific enrichment)
- No orphan detection
- Performance impact: slower inbox processing, but functionally complete

## 7. Cache Integrity

- `cache_version` must match Tomo's expected version
- If mismatch: warn user, suggest `/explore-vault` to rebuild
- Cache file is auto-generated — manual edits are overwritten on next scan
- Cache is **not** committed to git (gitignored in Tomo instance)
