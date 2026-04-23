# Tier 2: Daily Note Workflow

> Parent: [PKM Intelligence Architecture](../../tier-1/pkm-intelligence-architecture.md)
> Status: Implemented (with deviations)
> Children: [Daily Note Detection](../../tier-3/daily-note/daily-note-detection.md) · [Tracker Field Handling](../../tier-3/daily-note/tracker-field-handling.md)
> Related: [existing workflow doc](../../workflows/daily-note.md)

---

## 1. Purpose

Define how Tomo integrates with daily (and other periodic) notes. Tomo does NOT replace the user's existing daily note setup (Templater, etc.) — it adds content **after** initialization, **only after approval**.

## 2. Components Used

| Component | Role in Workflow |
|-----------|-----------------|
| User Config | Calendar paths, patterns, template mapping |
| Template System | Create periodic notes if they don't exist |
| Framework Profile | Relationship conventions |

## 3. Core Principle

**Tomo augments, never replaces.** The daily note is the user's space. Tomo's role:
- Propose tracker field updates (e.g., `coding-session:: true`)
- Propose content additions (links to new notes, brief mentions of processed items)
- All via instruction set — user approves each change

**MVP execution:** Daily notes live outside the inbox folder, so all approved daily note changes are applied **by the user manually**. Tomo proposes; the user updates the daily note in Obsidian. See [Tier 1 §7 Execution Model](../../tier-1/pkm-intelligence-architecture.md#7-execution-model).

## 4. Workflow

### Propose Phase (Tomo)

During inbox processing, the inbox-analyst identifies daily-note-relevant items:
1. **Date extraction** — determine which date each inbox item relates to
2. **Tracker matching** — match content against known tracker fields
3. **Content proposals** — what to add to the daily note

> **⚠️ Deviation (XDD-005)**
> **Original**: Two-step detection (date extraction + tracker matching).
> **Actual**: Three classification dimensions per inbox item, evaluated in a single subagent pass:
> 1. **Tracker match** — does the item trigger any configured tracker?
> 2. **Log-entry candidate** — should this item appear as a log entry in the daily note? (Only if item does NOT produce an atomic note)
> 3. **Log-link candidate** — should the daily note link to this item's new atomic note? (Only if item DOES produce an atomic note)
>
> The `log_entry` vs `log_link` distinction is driven by `atomic_note_worthiness`. Updates use polymorphic `updates[]` with a `kind` field (`tracker` | `log_entry` | `log_link`), carried inside the existing `update_daily` action.
>
> Additional extensions:
> - Tracker descriptions in vault-config.yaml (semantic context for better matching)
> - Daily-log config section in vault-config.yaml (log section heading, format preferences)
> - `/tomo-setup trackers` and `/tomo-setup daily-log` sub-wizards
> - 30-day cutoff default (keeps daily-note actions bounded to realistic recency)
> - Tomo never creates daily notes — surfaces `- [ ] Create daily note first` checkbox when missing
> **See**: [specs/005-daily-note-workflow/solution.md](../../specs/005-daily-note-workflow/solution.md)

These become instruction set actions (type: Daily Note Update). Each action contains everything the user needs to apply it:

- Target daily note path (e.g., `Calendar/Days/2026-04-07.md`)
- Whether the daily note exists (Tomo checks via `kado-read`)
- For tracker updates: the exact field, current value, proposed value, syntax (inline or frontmatter)
- For content additions: the target section heading and the markdown to insert

### Apply Phase (MVP: User)

The user opens the instruction set, reviews each approved action, and applies it manually in Obsidian:

```
For each approved Daily Note Update action:
   │
   ▼
Daily note exists?
   │
   ┌─Yes─┐         ┌─No──┐
   │     │         │
   │     │         ▼
   │     │     User decides:
   │     │     - Create daily note manually (Templater),
   │     │       then apply changes
   │     │     - Skip this action
   │     │
   │     └─────────┘
   ▼
For each change in action:
   ├── Tracker field → user edits the inline field or frontmatter
   └── Content addition → user pastes the markdown into the section
```

### Apply Phase (Post-MVP: Tomo Hashi)

Post-MVP, **Tomo Hashi** (友橋, the Obsidian plugin — see Kokoro
ADR-009) applies daily note updates deterministically via the Obsidian
Plugin API, reading action payloads from `instructions.json`:

- Tracker field updates via `update_tracker` actions (surgical inline-field, callout-body, or checkbox writes per the action's `syntax`).
- Content additions via `update_log_entry` / `update_log_link` actions (section-targeted, with `after_last_line` / `before_first_line` / `at_time` positioning).
- Daily note creation (if missing) uses the vault's normal Templater flow, triggered by Hashi before the first write into the note.

Until Tomo Hashi is installed, user-applied is the contract.

## 5. Tracker Detection

Trackers are **structured fields the user wants Tomo to set** based on inbox content. Their syntax is **not framework-locked** — Tomo supports multiple tracker formats and the vault-config declares which syntax each tracker uses.

### Supported Tracker Syntaxes (MVP)

| Syntax | Example | When to use |
|--------|---------|-------------|
| `inline_field` | `Coding:: true` | Dataview inline fields (MiYo's choice) |
| `task_checkbox` | `- [ ] Coding` → `- [x] Coding` | Plain markdown task lists |
| `frontmatter` | `coding: true` in YAML | Frontmatter properties |

For MVP, the first two are required. Frontmatter is supported because the underlying mechanism (Kado `frontmatter` operations) already exists. Other syntaxes (callout-based trackers, custom plugins) are out of scope.

### Tracker Types

Trackers are not always boolean. Supported value types:

| Type | Example values | Update method |
|------|---------------|---------------|
| `boolean` | `true`, `false` (or `[x]`/`[ ]` for checkbox syntax) | Set/toggle |
| `scale` | `1-10`, `0-5` | Set numeric value |
| `count` | integer ≥ 0 | Set or increment |
| `text` | free string | Set or append |
| `choice` | one of N labels | Set |

### Detection (during /explore-vault)

1. Read daily note template via Kado
2. Scan for tracker patterns (all supported syntaxes)
3. Identify fields with empty/default values
4. Propose tracker definitions for vault-config.yaml — user confirms

```yaml
# In vault-config.yaml (auto-detected, user can edit)
trackers:
  - name: "coding-session"
    syntax: "inline_field"
    field: "Coding"
    type: "boolean"
    trigger_keywords: ["coded", "programming", "installed", "configured"]
  - name: "sport"
    syntax: "task_checkbox"
    label: "Sport"
    type: "boolean"
    trigger_keywords: ["sport", "gym", "run", "workout"]
  - name: "energie"
    syntax: "inline_field"
    field: "Energie"
    type: "scale"
    range: [1, 10]
    trigger_keywords: []   # only set if explicitly mentioned
```

Triggers are heuristics — the instruction set shows what Tomo wants to set and why. User confirms in Pass 1, applies manually in Step 6.

## 6. Multi-Day Coverage

If inbox contains items from multiple days:
- Actions are grouped by target date
- Each date's daily note is handled independently
- Missing daily notes: creation proposed (or skipped per config)

## 7. Periodic Note Types Beyond Daily (Post-MVP)

**MVP scope:** Daily notes only.

**Post-MVP:** Weekly, Monthly, Quarterly, and Yearly notes follow the same workflow pattern but with different content expectations:
- Weekly: aggregate trackers across the week, summarize what shipped
- Monthly: rollups, themes, project progress
- Yearly: annual reviews, retrospectives

### Why Post-MVP

Periodic notes beyond daily rely heavily on LLM judgment to **generate the right content**. Daily notes are mostly tracker updates and content additions — relatively mechanical. Weekly+ notes ask "what mattered this week?" which requires synthesis.

For these to work well, the user must be able to **specify what they want in a periodic note and how it should be structured**. That's a configuration surface we don't want to design twice — better to learn from MVP usage first, then design the periodic-note configuration based on real needs.

### What Stays MVP (Even for Daily Notes)

- Tracker updates
- Content additions to existing sections
- Daily note creation if missing (configurable)
- Multi-day catchup (process all days since last run)

## 8. Open Items

- Should Tomo create missing daily notes, or only update existing ones? → Configurable per vault-config
- How to identify which section to append content to? → Section matching via heading text or configurable target section name
