# Tier 2: Framework Profiles

> Parent: [PKM Intelligence Architecture](../../tier-1/pkm-intelligence-architecture.md) — Knowledge Layer 2
> Status: Draft
> Children: [MiYo Profile](../../tier-3/profiles/miyo-profile.md) · [LYT Profile](../../tier-3/profiles/lyt-profile.md)

---

## 1. Purpose

Define the schema and role of framework profiles. Profiles contain framework-specific **data** — not logic. They ship with Tomo and can be extended by the community.

## 2. Role in Knowledge Stack

Profiles sit between universal concepts (Layer 1) and user config (Layer 3):
- They map abstract concepts to framework-specific defaults
- They provide classification systems, maturity models, and relationship conventions
- They are **always overridden** by user config (Layer 3 > Layer 2)

## 3. Planned Profiles

| Profile | Role | Priority |
|---------|------|----------|
| `miyo` | Development target — Marcus's vault conventions | Primary |
| `lyt` | Validation — standard LYT/Ideaverse conventions | Secondary |
| `para` | Best-effort — basic PARA support | Tertiary |

## 4. Profile Schema

```yaml
# Required fields
name: string                    # Human-readable name
version: string                 # Framework version this profile targets
base_structure: string          # Folder philosophy (ACE, PARA, custom)

# Concept → folder mapping defaults
concept_defaults:
  inbox: string                 # Folder path
  atomic_note: string
  map_note: string
  calendar:
    base_path: string
    daily: string | null
    weekly: string | null
    monthly: string | null
    quarterly: string | null
    yearly: string | null
  project: string
  area: string
  source: string
  template: string
  asset: string

# Optional: Classification system
classification:
  enabled: boolean
  system: string               # Identifier (e.g., "dewey-lyt")
  categories:
    <number>:
      name: string
      keywords: string[]

# Optional: Map note maturity states
map_note_states:
  <state_name>:
    icon: string               # Emoji or symbol
    meaning: string            # Human-readable description

# Relationship defaults
relationship_defaults:
  parent:
    marker: string             # e.g., "up::"
    format: string             # e.g., "up:: {{link}}"
  peer:
    marker: string
    format: string
```

## 5. Design Rules

1. **Profiles are pure data.** No decision logic, no heuristics, no conditionals. Skills contain all logic.
2. **Profiles define defaults.** Every field can be overridden by vault-config.yaml.
3. **Profiles are portable.** A profile YAML can be shared, forked, or contributed back.
4. **Absent fields in profile = feature not supported.** E.g., PARA profile has `classification.enabled: false`.
5. **Community profiles** follow the same schema. No special treatment for built-in vs community profiles.

## 6. Profile Selection

- Selected during install wizard (Phase 1): user picks from available profiles
- Stored in vault-config.yaml: `profile: miyo`
- Profile switching post-install is a migration (out of scope for MVP)

## 7. Keywords and Classification

Keywords in profiles are **seed data** for the discovery cache. The vault-explorer may discover additional keywords from actual vault content. Profile keywords are the starting point; discovery enriches them.

Classification categories (e.g., LYT's 2000-2900 Dewey system) are profile-specific. PARA does not use classification. Custom profiles may define their own systems.
