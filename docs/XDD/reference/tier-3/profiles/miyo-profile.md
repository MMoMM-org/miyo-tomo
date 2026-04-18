# Tier 3: MiYo Profile

> Parent: [Framework Profiles](../../tier-2/components/framework-profiles.md)
> Status: Implemented
> Role: Primary development target — Marcus's actual vault conventions

---

## 1. Purpose

The MiYo profile is the **reference profile for development**. It captures Marcus's actual vault conventions: folder layout, classification system, relationship markers, MOC maturity states. Tomo is built against this profile first, then validated against the LYT profile, then best-effort for PARA.

## 2. Source of Truth

This profile is derived from Marcus's private vault as observed via Kado MCP (2026-04). See:
- `tomo/references/lyt-obsidian-knowledge-model.md` §2 — Marcus's Vault, Personal LYT Implementation
- Actual vault structure scanned: `Atlas/200 Maps/` (17 topic MOCs + 10 classification maps), `Atlas/202 Notes/`, `Efforts/`, `Calendar/`, `X/`

## 3. Profile File

Location: `tomo/profiles/miyo.yaml`

```yaml
name: "MiYo"
version: "1.0"
description: "Marcus Breiden's personal LYT-derived vault conventions"
base_structure: "ACE-modified"  # Atlas, Calendar, Efforts + X support folder

# Concept → folder mapping defaults
concept_defaults:
  inbox: "+/"

  atomic_note:
    base_path: "Atlas/202 Notes/"
    has_subdirectories: true       # NOT flat — has Dewey-numbered subdirs
    subdirectories:                # vault-explorer must scan recursively
      - path: "Atlas/202 Notes/2021 Thoughts/"
        purpose: "Long-form reflections and thought pieces"
        dewey_parent: 2000
      - path: "Atlas/202 Notes/2071 Links/"
        purpose: "Link/reference collection notes"
        dewey_parent: 2000
      - path: "Atlas/202 Notes/2101 Life Goals and Values/"
        purpose: "Personal goals, values, life planning"
        dewey_parent: 2100
      - path: "Atlas/202 Notes/2611 Code Snippets/"
        purpose: "Technical code snippets and how-tos"
        dewey_parent: 2600
      - path: "Atlas/202 Notes/2821 Quotes/"
        purpose: "Collected quotes"
        dewey_parent: 2800
      - path: "Atlas/202 Notes/2921 People/"
        purpose: "Person notes"
        dewey_parent: 2900

  map_note:
    paths:
      - "Atlas/200 Maps/"
    tags:
      - "type/others/moc"

  calendar:
    base_path: "Calendar/"
    granularities:
      daily:    { enabled: true,  path: "Calendar/301 Daily/" }
      weekly:   { enabled: false, path: null }
      monthly:  { enabled: false, path: null }
      quarterly: { enabled: false, path: null }
      yearly:   { enabled: false, path: null }

  project: "Efforts/Projects/"
  area: "Efforts/Areas/"
  source: "Atlas/Sources/"
  template: "X/900 Support/Templates/"
  asset: "Atlas/290 Assets/295 Attachments/"

# Classification system (LYT Dewey variant, personalized)
classification:
  enabled: true
  system: "dewey-lyt"
  categories:
    2000:
      name: "Knowledge Management"
      keywords: [PKM, LYT, notes, learning, knowledge, obsidian, MiYo]
    2100:
      name: "Personal Management"
      keywords: [habits, productivity, goals, routines, health, time, money]
    2200:
      name: "Mind-Body Connection"
      keywords: [philosophy, psychology, spirituality, mind, meditation, flow]
    2300:
      name: "Social Sciences"
      keywords: [society, politics, economics, culture, history-of-ideas]
    2400:
      name: "Communication"
      keywords: [language, rhetoric, writing, linguistics, communication]
    2500:
      name: "Natural Sciences"
      keywords: [science, physics, biology, nature, systems, complexity]
    2600:
      name: "Applied Sciences"
      keywords: [coding, software, AI, docker, tools, engineering, devops, shell]
    2700:
      name: "Art & Recreation"
      keywords: [art, music, movies, games, recreation, travel, japan]
    2800:
      name: "Literature"
      keywords: [literature, fiction, poetry, novels, books]
    2900:
      name: "History & Geography"
      keywords: [history, geography, biography, places]

# Map note maturity states (LYT convention)
map_note_states:
  gathering:
    icon: "🟥"
    meaning: "Collecting related notes — rough, unpolished"
  developing:
    icon: "🟨"
    meaning: "Exploring connections, finding tensions"
  navigating:
    icon: "🟩"
    meaning: "Stable reference and wayfinding"

# Relationship defaults (Dataview inline fields used in practice)
relationship_defaults:
  parent:
    marker: "up::"
    format: "up:: {{link}}"
  peer:
    marker: "related::"
    format: "related:: {{link}}"

# Tag prefix conventions observed in vault
tag_conventions:
  type:
    note: "type/note/normal"
    moc: "type/others/moc"
  status:
    in_work: "status/inwork/💭"
    done: "status/done/✅"
  topic_prefix: "topic"       # topic/knowledge/*, topic/applied/*
  project_prefix: "projects"  # projects/60-00/60-06

# Custom callouts observed in vault
callout_defaults:
  editable:
    connect: "Navigation breadcrumbs (up/related links)"
    anchor: "Overview section"
    blocks: "Key Concepts"
    video: "Action Items / Tasks"
    calendar: "Recent Updates"
    puzzle: "Related Topics"
    compass: "Suggestions to explore"
  protected:
    boxes: "Unrequited Notes (DataviewJS)"
    shell: "Same-tag unmentioned (DataviewJS)"
    keaton: "Title-match notes (DataviewJS)"

# Protected code blocks
protected_patterns:
  - "```dataviewjs"
  - "```dataview"
  - "```folder-overview"

# Frontmatter schema defaults
frontmatter_defaults:
  required:
    - { key: "UUID",       token: "uuid",       format: "YYYYMMDDHHmmss" }
    - { key: "DateStamp",  token: "datestamp",  format: "YYYY-MM-DD" }
    - { key: "Updated",    token: "updated",    format: "YYYY-MM-DD HH:mm" }
    - { key: "title",      token: "title" }
    - { key: "tags",       token: "tags" }
  optional:
    - { key: "locale",       token: "locale",       default: "de" }
    - { key: "Vault",        token: "vault",        default: "Privat" }
    - { key: "VaultVersion", token: "vault_version", default: "2" }
    - { key: "Summary",      token: "summary" }
    - { key: "aliases",      token: "aliases" }
    - { key: "banner",       token: "banner" }
```

## 4. Noteworthy Characteristics

Things that are specific to MiYo and differ from vanilla LYT:

| Trait | Detail |
|-------|--------|
| **Notes folder naming** | `Atlas/202 Notes/` (not `Atlas/Dots/` like Ideaverse) |
| **Notes have Dewey subdirectories** | `202 Notes/` is NOT flat — contains 6 subdirs following Dewey numbering: `2021 Thoughts/`, `2071 Links/`, `2101 Life Goals and Values/`, `2611 Code Snippets/`, `2821 Quotes/`, `2921 People/`. Plus 72 files at root level. vault-explorer must scan recursively. |
| **Assets nesting** | `Atlas/290 Assets/295 Attachments/` (double-numbered) |
| **Templates location** | `X/900 Support/Templates/` (not `x/Templates/`) |
| **Classification maps as notes** | Maps 2000-2900 exist as standalone files in `Atlas/200 Maps/` — they are MOCs themselves (unlike Ideaverse which treats them as pure nav) |
| **Custom callouts with symbolic names** | `[!boxes]`, `[!shell]`, `[!keaton]` have semantic meanings (DataviewJS blocks — must not be touched) |
| **Emoji in status tags** | `status/inwork/💭`, `status/done/✅` — emojis are part of the tag path |
| **Locale in frontmatter** | `locale: de` — bilingual vault |
| **Inbox files vary in format** | Not just `YYYY-MM-DD_HHMM_description.md` — can be timestamps only, names only, or even binary files (PDF, JPG). Analysis must handle all formats. |

## 5. Intentional Divergences from LYT Profile

The MiYo profile diverges from the LYT profile in these ways (captured so the LYT profile can stay faithful to Ideaverse):

| Aspect | LYT (Ideaverse) | MiYo |
|--------|----------------|------|
| Notes folder | `Atlas/Dots/Things/`, `Atlas/Dots/People/`, etc. | `Atlas/202 Notes/` (flat) |
| Note type system | Dots taxonomy (Things/Statements/People/Quotes/Questions) | Simple `type/note/normal` |
| MOC state tracking | `mapState:` frontmatter field | Not tracked in frontmatter (state is inferred or unused) |
| Classification maps | Pure navigation overlay | Full MOCs with content |
| Templates | `x/Templates/` | `X/900 Support/Templates/` |

## 6. Test Fixtures

For development, the MiYo profile doubles as the fixture set. Any new Tomo skill or agent should be testable against:
- The 17 observed topic MOCs in `Atlas/200 Maps/`
- The 10 classification maps (2000-2900)
- The hierarchical tag taxonomy
- The custom callout structure in MOCs

## 7. Version Management

This profile file is versioned with Tomo. If MiYo vault conventions change (e.g., folder restructure, new tag prefixes), this profile is updated and the version bumped. Users on older Tomo versions continue with their cached profile.
