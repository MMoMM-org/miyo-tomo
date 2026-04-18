# Tier 3: LYT Profile

> Parent: [Framework Profiles](../../tier-2/components/framework-profiles.md)
> Status: Draft
> Role: Validation target — standard LYT/Ideaverse conventions

---

## 1. Purpose

The LYT profile captures **standard LYT conventions** as defined by Nick Milo's Ideaverse Pro. Tomo validates against this profile after MVP works on MiYo — if Tomo can correctly work with both MiYo and LYT vaults, the framework-agnostic design is proven.

## 2. Source of Truth

This profile is derived from the Ideaverse Pro 2.5 demo vault (in `../temp/Ideaverse` during development). See:
- `tomo/references/lyt-obsidian-knowledge-model.md` §1 — LYT Framework Core Concepts
- Brainstorm research of Ideaverse Pro structure (904 markdown files, ACE framework)

## 3. Profile File

Location: `tomo/profiles/lyt.yaml`

```yaml
name: "LYT (Linking Your Thinking)"
version: "15"                 # LYT 15 curriculum
description: "Standard LYT conventions per Nick Milo's Ideaverse Pro"
base_structure: "ACE"         # Atlas, Calendar, Efforts

# Concept → folder mapping defaults (Ideaverse Pro 2.5)
concept_defaults:
  inbox: "+/"

  atomic_note:
    base_path: "Atlas/Dots/"
    has_subdirectories: true       # Ideaverse uses typed subfolders
    subdirectories:
      - path: "Atlas/Dots/Things/"
        purpose: "Concepts, topics"
      - path: "Atlas/Dots/Statements/"
        purpose: "Claims, ideas, assertions"
      - path: "Atlas/Dots/People/"
        purpose: "Person notes"
      - path: "Atlas/Dots/Quotes/"
        purpose: "Attributed statements"
      - path: "Atlas/Dots/Questions/"
        purpose: "Open inquiries"

  map_note:
    paths:
      - "Atlas/Maps/"
    tags:
      - "moc"                   # standard Ideaverse tag

  calendar:
    base_path: "Calendar/"
    granularities:
      daily:    { enabled: true,  path: "Calendar/Days/" }
      weekly:   { enabled: false, path: null }
      monthly:  { enabled: false, path: null }
      quarterly: { enabled: false, path: null }
      yearly:   { enabled: false, path: null }

  project: "Efforts/Projects/"
  area: "Efforts/Areas/"
  source: "Atlas/Sources/"
  template: "x/Templates/"
  asset: "Atlas/Assets/"

# Classification system (LYT Dewey-lite)
classification:
  enabled: true
  system: "dewey-lyt"
  categories:
    2000:
      name: "Knowledge Management"
      keywords: [PKM, notes, learning, knowledge]
    2100:
      name: "Personal Management"
      keywords: [habits, productivity, goals, routines, health]
    2200:
      name: "Philosophy & Psychology"
      keywords: [philosophy, psychology, spirituality, mind, religion]
    2300:
      name: "Social Sciences"
      keywords: [society, politics, economics, culture]
    2400:
      name: "Communications & Language"
      keywords: [language, rhetoric, writing, linguistics]
    2500:
      name: "Natural Sciences"
      keywords: [science, physics, biology, nature]
    2600:
      name: "Applied Sciences"
      keywords: [coding, software, engineering, tools, technology]
    2700:
      name: "Art & Recreation"
      keywords: [art, music, movies, games, recreation]
    2800:
      name: "Literature"
      keywords: [literature, fiction, poetry, novels]
    2900:
      name: "History & Biography & Geography"
      keywords: [history, geography, biography, places]

# Map note maturity states (Ideaverse convention)
map_note_states:
  gathering:
    icon: "🟥"
    meaning: "Gather — rough, unpolished collection"
  developing:
    icon: "🟨"
    meaning: "Develop — exploring connections"
  navigating:
    icon: "🟩"
    meaning: "Navigate — stable wayfinding"

# Relationship defaults
relationship_defaults:
  parent:
    marker: "up::"
    format: "up:: {{link}}"
  peer:
    marker: "related::"
    format: "related:: {{link}}"

# Tag conventions (Ideaverse uses simpler hierarchies)
tag_conventions:
  type: {}                      # LYT doesn't enforce type tags
  status: {}                    # LYT doesn't enforce status tags
  topic_prefix: null
  project_prefix: null

# Ideaverse uses standard callouts (no custom ones by default)
callout_defaults:
  editable:
    note: "Standard note callout"
    info: "Informational"
    abstract: "Summary"
    quote: "Quotation"
  protected: {}                 # None by default; vaults may add their own

# Protected code blocks (Dataview is common in Ideaverse)
protected_patterns:
  - "```dataviewjs"
  - "```dataview"
  - "```base"                   # Ideaverse uses .base files

# Frontmatter schema (Base 4 template from Ideaverse)
frontmatter_defaults:
  required:
    - { key: "title", token: "title" }
  optional:
    - { key: "up",       token: "up" }
    - { key: "related",  token: "related" }
    - { key: "created",  token: "datestamp", format: "YYYY-MM-DD" }
    - { key: "tags",     token: "tags" }
    - { key: "rank",     token: "rank" }
    - { key: "collections", token: "collections" }
    - { key: "mapState", token: "map_state" }
    - { key: "wayfinder", token: "wayfinder" }
```

## 4. Key Differences from MiYo Profile

| Aspect | LYT (Ideaverse) | MiYo |
|--------|----------------|------|
| Notes folder | `Atlas/Dots/` with subfolders (Things, People, Quotes, Statements, Questions) | `Atlas/202 Notes/` flat |
| Maps folder | `Atlas/Maps/` | `Atlas/200 Maps/` |
| Sources | `Atlas/Sources/` with typed subfolders | Same structure |
| Templates | `x/Templates/` (lowercase x) | `X/900 Support/Templates/` |
| Assets | `Atlas/Assets/` | `Atlas/290 Assets/295 Attachments/` |
| MOC state tracking | `mapState:` frontmatter field (🟥🟨🟩) | Not tracked |
| Frontmatter schema | Progressive (Base 1/2/3/4 templates) | Richer, always includes UUID |
| Classification maps | Pure navigation — no content per category | Full MOCs with content |
| Tag taxonomy | Minimal (mostly free-form) | Hierarchical with prefixes |

## 5. Dots Taxonomy (LYT-specific Note Types)

LYT's Dots taxonomy is a special case that MiYo doesn't use. For the LYT profile:

```yaml
# Optional extension to atomic_note concept
dots_taxonomy:
  enabled: true
  subfolders:
    things:
      path: "Atlas/Dots/Things/"
      keywords: [concept, topic, thing]
    people:
      path: "Atlas/Dots/People/"
      keywords: [person, individual]
    quotes:
      path: "Atlas/Dots/Quotes/"
      keywords: [quote, saying]
    statements:
      path: "Atlas/Dots/Statements/"
      keywords: [claim, assertion, idea]
    questions:
      path: "Atlas/Dots/Questions/"
      keywords: [question, inquiry]
```

When enabled, Tomo classifies atomic notes further into these sub-types during inbox processing. This is post-MVP behavior — MVP treats atomic_note as flat.

## 6. Validation Approach

Once Tomo works with MiYo, validate against LYT by:
1. Cloning a fresh Ideaverse Pro vault
2. Configuring Tomo with the LYT profile via install wizard
3. Running `/explore-vault` — check that all MOCs are detected
4. Running `/inbox` with test items — check that classifications and MOC matches are reasonable
5. Comparing suggestions to what a LYT expert would recommend

Issues found during validation are either:
- **Profile bugs** → fix the LYT profile
- **Framework bugs** → fix Tomo code (the design must stay framework-agnostic)
- **Vault divergence from standard** → expected; user config overrides are the escape hatch

## 7. Version Management

This profile tracks the **LYT curriculum version** it targets. LYT 15 is the current target. If LYT 16 introduces changes (new conventions, deprecated patterns), a new profile file is added (`lyt-16.yaml`) rather than overwriting — users on older curricula stay on their version.
