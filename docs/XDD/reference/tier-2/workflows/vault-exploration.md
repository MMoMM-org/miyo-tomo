# Tier 2: Vault Exploration Workflow

> Parent: [PKM Intelligence Architecture](../../tier-1/pkm-intelligence-architecture.md)
> Status: Draft
> Children: [Structure Scan](../../tier-3/vault-exploration/structure-scan.md) · [Topic Extraction](../../tier-3/vault-exploration/topic-extraction.md) · [Cache Generation](../../tier-3/vault-exploration/cache-generation.md)

---

## 1. Purpose

Define how vault-explorer learns the vault's structure and content to build the discovery cache and refine vault-config.yaml. Triggered by `/explore-vault`.

## 2. Components Used

| Component | Role in Workflow |
|-----------|-----------------|
| User Config | Concept folder paths (where to scan) |
| Discovery Cache | Output target |
| Framework Profile | Classification categories for keyword enrichment |

## 3. Agent

`vault-explorer` — dedicated agent for vault learning. Read-only: never modifies vault content. Only writes to config and cache files within Tomo's instance.

## 4. Workflow

```
Manual trigger: /explore-vault
       │
       ▼
  ┌─────────────────────┐
  │  1. Structure Scan   │  Map folder contents via kado-search (listDir)
  │                      │  Count notes per concept folder
  │                      │  Detect folders not mapped to concepts
  └──────────┬──────────┘
             │
             ▼
  ┌──────────────────────┐
  │  2. Map Note Discovery│  Find ALL map_notes via:
  │                      │  - Configured paths (concepts.map_note.paths)
  │                      │  - Configured tags (concepts.map_note.tags)
  │                      │  Deduplicate, record discovery source.
  └──────────┬──────────┘
             │
             ▼
  ┌──────────────────────┐
  │  2b. Map Note Read    │  Read each map_note via kado-read
  │      + Tree Build     │  Extract: title, sections (H2), topics,
  │                      │  linked notes, maturity state.
  │                      │  Build parent/child tree by following
  │                      │  outgoing wikilinks to other map_notes.
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐
  │  3. Frontmatter      │  Sample N notes (configurable, default: 50)
  │     Sampling         │  Read frontmatter via kado-read
  │                      │  Detect field patterns and frequencies
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐
  │  4. Tag Analysis     │  kado-search by known tag prefixes
  │                      │  Count usage per tag value
  │                      │  Detect new prefixes not in config
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐
  │  5. Orphan Detection │  Find Tomo-managed notes (lifecycle-tagged)
  │                      │  with no incoming wikilinks
  │                      │  Find broken wikilinks (missing targets)
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐
  │  6. Present Findings │  Show user what was discovered
  │     & Confirm        │  User confirms/corrects each section
  │                      │  (Only on first run or when --confirm flag used)
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐
  │  7. Update Config    │  Merge confirmed findings into vault-config
  │     & Build Cache    │  Write discovery-cache.yaml
  └─────────────────────┘
```

## 5. Topic Extraction

For each map_note, extract topics by:
1. **Title analysis** — MOC title itself is a primary topic
2. **H2 section headings** — each section heading indicates a sub-topic
3. **Linked note titles** — titles of notes linked from the MOC
4. **Content keywords** — significant terms from the MOC body (excluding boilerplate callouts)

Topics are stored as a flat keyword list per MOC in the discovery cache.

**Detail spec:** [Topic Extraction](../../tier-3/vault-exploration/topic-extraction.md)

## 6. Config Refinement

On first run, `/explore-vault` can detect and propose:
- **Frontmatter schema** — which fields are used, in what format
- **Tag taxonomy** — which prefixes exist, what values are common
- **Callout mapping** — which callout types appear, which contain DataviewJS (→ protected)
- **Relationship markers** — what `up::` / `related::` patterns are used
- **Template patterns** — detect note structures that suggest template origins

User confirms each finding. Confirmed findings merge into vault-config.yaml.

## 7. Re-Run Behavior

| Aspect | First Run | Subsequent Runs |
|--------|-----------|-----------------|
| Config refinement | Full scan + user confirmation | Skip config (unless `--confirm`) |
| Cache rebuild | Full rebuild | Full rebuild (always fresh) |
| User interaction | Interactive confirmation per section | Silent (unless `--confirm`) |
| Duration | Longer (includes confirmation) | Shorter (scan + write only) |

## 8. Performance Considerations

- **Large vaults:** Scanning 500+ map_notes or 5000+ notes could be slow via individual Kado reads
- **Mitigation:** Use `kado-search` for bulk enumeration, `kado-read` only for content that needs analysis
- **Future optimization:** If Kado adds batch read or chunked search, vault-explorer benefits automatically
- **Progress feedback:** Report progress during scan ("Scanning MOCs... 15/27")
