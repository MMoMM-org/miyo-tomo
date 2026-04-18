# Tier 3: First-Session Discovery (Phase 2)

> Parent: [Setup Wizard](../../tier-2/components/setup-wizard.md)
> Status: Implemented
> Agent: `vault-explorer`

---

## 1. Purpose

Define what happens during the first `/explore-vault` run in a new Tomo session. This completes the setup started by the install script — deep-scanning the vault via Kado to detect frontmatter patterns, tag taxonomy, callout usage, relationship markers, and build the discovery cache.

## 2. Prerequisites

- Phase 1 (install script) has run: `vault-config.yaml` exists with basic concept paths
- Docker container is running
- Kado is reachable (connection details from vault-config or MCP config)

## 3. Process

```
/explore-vault (first run, or with --confirm flag)
       │
       ▼
  ┌────────────────────┐
  │  1. Connect Kado    │  Verify MCP connection
  │                     │  Test kado-search (listDir on vault root)
  │                     │  If fail → abort with connection error
  └──────────┬─────────┘
             │
             ▼
  ┌────────────────────────────┐
  │  2. Structure Scan          │  See: structure-scan.md
  │     (with user confirmation)│  Present folder mapping
  │                             │  Ask about unmapped folders
  │                             │  Detect subdirectory structures
  └──────────┬─────────────────┘
             │
             ▼
  ┌────────────────────────────┐
  │  3. Frontmatter Detection   │  Sample 50 notes
  │                             │  Detect field patterns
  │                             │  Present: "I found these frontmatter fields..."
  │                             │  User confirms required/optional/skip
  │                             │  Update vault-config.yaml frontmatter section
  └──────────┬─────────────────┘
             │
             ▼
  ┌────────────────────────────┐
  │  4. Tag Taxonomy Detection  │  kado-search listTags
  │                             │  Group by prefix
  │                             │  Present: "Your tags use these prefixes..."
  │                             │  User confirms taxonomy structure
  │                             │  Update vault-config.yaml tags section
  └──────────┬─────────────────┘
             │
             ▼
  ┌────────────────────────────┐
  │  5. Relationship Detection  │  Sample notes with up::/related:: patterns
  │                             │  Detect marker syntax and position
  │                             │  Present: "Your notes use up:: for parent..."
  │                             │  User confirms relationship config
  │                             │  Update vault-config.yaml relationships section
  └──────────┬─────────────────┘
             │
             ▼
  ┌────────────────────────────┐
  │  6. Callout Detection       │  Sample notes for callout patterns
  │     (if callouts enabled)   │  Classify: editable / protected / ignore
  │                             │  Present findings
  │                             │  User confirms classifications
  │                             │  Update vault-config.yaml callouts section
  └──────────┬─────────────────┘
             │
             ▼
  ┌────────────────────────────┐
  │  7. Tracker Detection       │  Read daily note template via Kado
  │     (if daily notes enabled)│  Find tracker fields + syntax
  │                             │  Present: "Found these trackers..."
  │                             │  User confirms tracker config
  │                             │  Update vault-config.yaml trackers section
  └──────────┬─────────────────┘
             │
             ▼
  ┌────────────────────────────┐
  │  8. Template Check          │  For each note type in templates.mapping:
  │                             │  Does the template file exist in vault?
  │                             │  If missing: offer to create from example
  │                             │  (writes example to inbox folder for review)
  └──────────┬─────────────────┘
             │
             ▼
  ┌────────────────────────────┐
  │  9. MOC Indexing +          │  See: moc-indexing.md, topic-extraction.md
  │     Cache Generation        │  Full MOC tree scan
  │                             │  Topic extraction per MOC
  │                             │  Classification coverage computation
  │                             │  Orphan detection
  │                             │  Write discovery-cache.yaml
  └──────────┬─────────────────┘
             │
             ▼
  ┌────────────────────────────┐
  │  10. Summary Report         │  "Setup complete! Here's what I found:"
  │                             │  - N notes across M concept folders
  │                             │  - N MOCs in a tree of depth D
  │                             │  - N frontmatter fields detected
  │                             │  - N unique tags across P prefixes
  │                             │  - N tracker fields configured
  │                             │  - Template status per note type
  │                             │  "Run /inbox to start processing."
  └────────────────────────────┘
```

## 4. Presentation Style

Each detection step follows the same pattern:

```
1. Tomo scans silently (progress indicator)
2. Tomo presents findings in a structured format
3. Tomo asks the user to confirm or correct
4. User responds (approve all, modify specific items, skip)
5. Tomo writes confirmed config
```

**Example (frontmatter detection):**

```
📋 Frontmatter fields detected (sampled 50 notes):

   Required (found in 90%+ of notes):
   ✓ UUID         (string, format: YYYYMMDDHHmmss)    — 95%
   ✓ DateStamp    (date, format: YYYY-MM-DD)           — 95%
   ✓ Updated      (string, format: YYYY-MM-DD HH:mm)  — 90%
   ✓ title        (string)                              — 98%
   ✓ tags         (list)                                — 99%

   Optional (found in 10-90%):
   ○ Summary      (string)                              — 60%
   ○ aliases      (list)                                — 30%
   ○ banner       (string)                              — 15%

   Rare (<10%, not adding):
   · ProjectCode  (string)                              — 5%

   Look correct? [Y/n/edit]
```

## 5. Config Update Strategy

**First run:** Write all detected sections to vault-config.yaml (user confirmed).

**Subsequent runs (`/explore-vault` without `--confirm`):**
- Skip user confirmation for config sections — only rebuild the discovery cache
- Config is NOT modified on subsequent runs unless `--confirm` flag is used
- This prevents overwriting user customizations

**Explicit re-detection (`/explore-vault --confirm`):**
- Re-runs all detection steps with user confirmation
- Useful after major vault restructuring
- Warns if current config will be overwritten

## 6. Handling Vault State Edge Cases

**Empty vault (new setup):**
- Structure scan finds empty concept folders → "Vault is mostly empty. That's OK — configuration will become richer as you add content."
- No frontmatter to detect → skip, use profile defaults
- No tags to detect → skip, use profile defaults
- No MOCs to index → empty cache, Tomo is still functional

**Very large vault (5000+ notes):**
- Frontmatter sampling stays at 50 (random sample is sufficient)
- Tag analysis via listTags is O(1) regardless of vault size
- MOC indexing scales with MOC count, not note count
- Structure scan lists directories, not files — fast
- Progress reporting is important ("Indexing MOCs... 45/120")

**Vault with no Obsidian configuration (.obsidian missing):**
- Kado should still serve content (Obsidian plugin needs to be running regardless)
- If Kado can't reach the vault → connection error in Step 1

## 7. Template Creation Offer

If a configured template doesn't exist:

```
⚠️ Template 't_note_tomo' not found at X/900 Support/Templates/t_note_tomo.md

Options:
  1. Create from MiYo example template (writes to inbox for review)
  2. Skip (Tomo will use a minimal fallback when rendering)
  3. Specify a different template file

Choose [1/2/3]:
```

If option 1: Tomo writes the example template to the inbox folder. User reviews, customizes, and moves it to the template folder. Tomo does NOT write directly to the template folder (inbox boundary in MVP).

## 8. Interaction with Phase 1

Phase 2 enriches what Phase 1 started:

| Section | Phase 1 (install script) | Phase 2 (first /explore-vault) |
|---------|------------------------|-------------------------------|
| `schema_version` | ✓ Set | Validated |
| `profile` | ✓ Set | Validated |
| `concepts` | ✓ Basic paths | Enriched (subdirs, tag discovery for map_note) |
| `naming` | Profile defaults | Enriched (calendar_patterns detected) |
| `lifecycle` | ✓ Prefix set | Validated |
| `templates` | Profile defaults | Enriched (check existence, offer creation) |
| `frontmatter` | Not set (profile defaults) | **Detected and written** |
| `relationships` | Not set (profile defaults) | **Detected and written** |
| `tags` | Not set (profile defaults) | **Detected and written** |
| `callouts` | Not set (profile defaults) | **Detected and written** |
| `trackers` | Not set | **Detected and written** |

## 9. Duration Estimates

| Step | Typical duration |
|------|-----------------|
| Connect + structure scan | 2-5 seconds |
| Frontmatter sampling (50 notes) | 3-5 seconds |
| Tag analysis | 1-2 seconds |
| Relationship detection | 2-3 seconds |
| Callout detection | 2-3 seconds |
| Tracker detection | 1-2 seconds |
| Template check | <1 second |
| MOC indexing + cache | 10-30 seconds (depends on MOC count) |
| **Total (excluding user confirmation)** | **~30-60 seconds** |

User confirmation time dominates on first run. Subsequent runs (no confirmation) complete in 30-60 seconds.
