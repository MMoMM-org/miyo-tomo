# Tier 3: MOC Indexing

> Parent: [Discovery Cache](../../tier-2/components/discovery-cache.md)
> Status: Draft
> Related: [Topic Extraction](../vault-exploration/topic-extraction.md) · [MOC Matching](../lyt-moc/moc-matching.md)

---

## 1. Purpose

Define how vault-explorer discovers, reads, and indexes all MOCs (map_notes) into the discovery cache — including building the parent/child tree across all levels.

## 2. Discovery Strategy

MOCs are found via **two parallel strategies** (configured in `vault-config.yaml`):

| Strategy | Config source | What it finds |
|----------|--------------|---------------|
| **Path-based** | `concepts.map_note.paths[]` | All `.md` files in configured map_note folders |
| **Tag-based** | `concepts.map_note.tags[]` | All notes tagged with configured MOC tags, regardless of folder |

Results are **deduplicated by path** — if a note is found by both path and tag, it appears once with `discovered_via: "both"`.

### Path-Based Discovery

```
For each path in concepts.map_note.paths:
  kado-search listDir (recursive)
  → collect all .md files
  → exclude folder notes that match known non-MOC patterns
```

### Tag-Based Discovery

```
For each tag in concepts.map_note.tags:
  kado-search byTag "#<tag>"
  → collect all results
  → verify each is a MOC not a note containing it (template etc.)
```

## 3. MOC Reading

For each discovered MOC, read via `kado-read` and extract:

| Field | Extraction method |
|-------|-------------------|
| `path` | File path (from discovery) |
| `title` | Frontmatter `title:` field, or first H1 heading, or filename without `.md` |
| `discovered_via` | `"path"`, `"tag"`, or `"both"` |
| `state` | Frontmatter `mapState:` if profile uses map_note_states |
| `topics` | See [Topic Extraction](../vault-exploration/topic-extraction.md) |
| `sections` | All H2 headings (`## ...`) in the note body |
| `linked_notes` | Count of outgoing `[[wikilinks]]` to non-MOC notes |
| `linked_mocs` | List of outgoing `[[wikilinks]]` that resolve to other MOCs |
| `classification` | Best-fit category number (from profile, if classification enabled) |

## 4. Tree Building

The MOC tree is built by analyzing outgoing wikilinks between MOCs. Note that MOCs can have **siblings** (peer relationships via `related::`) in addition to parent/child relationships.

```
For each MOC:
  Parse all [[wikilinks]] in content
  For each link:
    Does it resolve to another MOC? (check against the discovered MOC list)
    If yes → record as linked_moc

For each MOC:
  parent_moc = the MOC that this note's `up::` relationship points to
              (if that target is itself a MOC)
  child_mocs = all MOCs whose `up::` points to this MOC
  sibling_mocs = the MOC(s) that this note's `related::` points to
                (if those targets are MOCs) — peer relationships

Level assignment:
  Root MOCs (no parent_moc) → level 0
  Children of level 0 → level 1
  Children of level 1 → level 2
  ...
```

### Tree Invariants

- A MOC can have **multiple parents** (if `up::` has multiple links to MOCs) — level = min(parent levels) + 1
- A MOC can have **zero parents** (root/orphan) — level 0
- Cycles are detected and broken: if A→B→C→A, log a warning and assign the lowest level found before the cycle
- The tree is a DAG (directed acyclic graph), not strictly a tree — some MOCs may be reachable from multiple paths

### Example (MiYo vault)

```
Level 0 (roots):
  200 Maps.md (folder index)

Level 1 (classification):
  2000 - Knowledge Management.md
  2100 - Personal Management.md
  2600 - Applied Sciences.md
  ...

Level 2 (topic MOCs):
  Linking Your Thinking (MOC).md     [parent: 2000]
  My PKM (MOC).md                    [parent: 2000]
  Habits (MOC).md                    [parent: 2100]
  Systems Thinking (MOC).md          [parent: 2500]
  60-06 MiYo Research (MOC).md       [parent: 2600]
  ...

Level 3+ (sub-topic MOCs, if any):
  ...
```

## 5. Output Schema

Per MOC entry in `discovery-cache.yaml`:

```yaml
map_notes:
  - path: "Atlas/200 Maps/Systems Thinking (MOC).md"
    title: "Systems Thinking"
    discovered_via: "both"
    level: 2
    parent_moc: "Atlas/200 Maps/2500 - Natural Sciences.md"
    child_mocs: []
    sibling_mocs: ["Atlas/200 Maps/Frameworks (MOC).md"]
    state: null
    topics: [systems, feedback loops, emergence, complexity, mental models]
    sections: [Overview, Key Concepts, Workflows, Definitions]
    linked_notes: 12
    classification: 2500
```

## 6. Handling Non-Existent MOCs (Placeholder Links)

Classification-level MOCs may contain wikilinks to MOCs that **don't exist yet** (dead links / placeholder MOCs). These are detected during tree building:

**Scope:** Only `[[wikilinks]]` are detected as placeholders. Plain-text mentions (e.g., "Chemistry" as prose without `[[]]`) are NOT treated as placeholder MOCs. Rationale: a wikilink is a clear signal the user wants a connection; plain text is just description. If the user wants a placeholder, they should write `[[Chemistry]]`. This keeps detection deterministic and avoids false positives from prose.

- Outgoing wikilink target not found in discovered MOC list AND not found as any note → **placeholder**
- Recorded separately in the cache:

```yaml
placeholder_mocs:
  - target: "Shell & Terminal (MOC)"
    referenced_by: "Atlas/200 Maps/2600 - Applied Sciences.md"
    # note: section field is specified but not yet implemented
```

This feeds into [New MOC Proposal](../lyt-moc/new-moc-proposal.md) — when a new note matches a placeholder topic, Tomo can propose creating the placeholder as a real MOC.

## 7. Performance

- **MOC count is typically small** (20-100 even in large vaults) — reading all is feasible
- **Kado round-trips:** one `kado-read` per MOC + initial discovery queries
- **Target:** index 50 MOCs in <30 seconds including Kado latency
- **Caching:** the index is the cache — no in-memory caching beyond the yaml file

## 8. Incremental Refresh (Future)

Currently vault-explorer rebuilds the full index on every `/explore-vault` run. Future optimization:
- Compare `modified` timestamps from Kado against cached timestamps
- Only re-read MOCs that changed since last scan
- Re-build tree only if MOC set changed (add/remove/rename)

Not in MVP — full rebuild is acceptable given the small MOC count.
