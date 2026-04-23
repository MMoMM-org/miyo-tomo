# Tier 2: Universal PKM Concepts

> Parent: [PKM Intelligence Architecture](../../tier-1/pkm-intelligence-architecture.md) — Knowledge Layer 1
> Status: Implemented
> Children: — (concepts are atomic, no Tier 3 decomposition)

---

## 1. Purpose

Define the framework-agnostic vocabulary Tomo uses internally. Every PKM framework (LYT, PARA, Zettelkasten, custom) maps onto these concepts. This is Layer 1 of the knowledge stack — concept identity only, no folder paths, no framework-specific behavior.

## 2. Concepts

| Concept | Description | Notes |
|---------|-------------|-------|
| `inbox` | Capture point for unprocessed items | Single folder, flat file list |
| `atomic_note` | Single-idea note | The basic unit of knowledge |
| `map_note` | Index/overview that connects other notes | LYT: MOC, PARA: Index, Zettelkasten: Structure note. **Forms a tree** — top-level (e.g., classification), mid-level, leaf-level. Discovered by path AND/OR tag. |
| `calendar` | Container for time-based notes | Not a note type itself — a grouping |
| `calendar.daily` | Daily periodic note | Most common periodic type |
| `calendar.weekly` | Weekly periodic note | Optional |
| `calendar.monthly` | Monthly periodic note | Optional |
| `calendar.quarterly` | Quarterly periodic note | Rare |
| `calendar.yearly` | Yearly periodic note | Optional |
| `project` | Time-bound effort with deliverable | Has an end state |
| `area` | Ongoing responsibility without end date | Never "done" |
| `source` | External reference (book, article, etc.) | Not original thought — captured from outside |
| `template` | Note skeleton for creation | Defines structure, not content |
| `asset` | Non-markdown file (image, PDF) | Binary content |

### Concept Properties

Each concept is defined by its identity. Concepts do NOT carry:
- Folder paths (that's Layer 2/3)
- Templates (that's Layer 3)
- Tags (that's Layer 3)
- Behavior (that's Skills)

## 3. Relationships

| Type | Description | Directionality | Example |
|------|-------------|----------------|---------|
| `parent` | Hierarchical: child → parent | Unidirectional | Note → MOC, MOC → Classification Map |
| `peer` | Sibling/related | Bidirectional (conceptually) | Note ↔ Note, MOC ↔ MOC |
| `mention` | Inline wikilink reference | Unidirectional | `[[Other Note]]` in body text |
| `embed` | Transclusion | Unidirectional | `![[Other Note]]` or `![[Note#Section]]` |

### Relationship Properties

Relationships are abstract at this layer. They do NOT carry:
- Syntax markers (that's Layer 2/3: `up::`, `related::`, `top:`)
- Position rules (that's Layer 3: in callout, after frontmatter, etc.)
- Plugin dependencies (Dataview, etc.)

## 4. Lifecycle States

States describe where an item is in **Tomo's processing pipeline**, not its PKM maturity.

```
captured → processing → proposed → active → archived
```

| State | Meaning | Trigger |
|-------|---------|---------|
| `captured` | In inbox, unprocessed | Item arrives in inbox |
| `processing` | Being analyzed by Tomo | `/inbox` command starts |
| `proposed` | In instruction set, awaiting user approval | Instruction set generated |
| `active` | In vault, linked, evolving | User approved + applied (MVP: user; Post-MVP: Tomo Hashi via Obsidian Plugin API) |
| `archived` | Completed/inactive | User or Tomo archives |

### Lifecycle Properties

- State names are **fixed** — not configurable. They are Tomo workflow states, framework-agnostic by nature.
- The **tag prefix** is configurable (default: `MiYo-Tomo`). Tags: `#MiYo-Tomo/captured`, `#MiYo-Tomo/active`, etc.
- A note can only be in one lifecycle state at a time.
- State transitions are tracked by replacing the lifecycle tag, not by adding new ones.

## 5. Concept Extensibility

The concept list is designed to be **sufficient for MVP**, not exhaustive. Future concepts may include:
- `person` — Person note (LYT: People dot)
- `quote` — Attributed statement
- `question` — Open inquiry
- `meeting` — Meeting note (calendar-adjacent)

These are deferred until a workflow requires them. YAGNI.
