# Tier 3: Relationship Config

> Parent: [User Config](../../tier-2/components/user-config.md)
> Status: Implemented

---

## 1. Purpose

Define how Tomo describes, detects, and writes relationships between notes. Relationships are **syntax patterns** — not plugin-specific features. Tomo supports any marker format via configuration.

## 2. Core Principle

**Tomo does not depend on Dataview.** `up::` and `related::` are just text patterns. Some users write `up:: [[X]]`, others write `top: [[X]]`, others use frontmatter `parent: X`. Tomo reads and writes whatever marker the user configures.

## 3. Schema Location

Lives under `relationships:` in `vault-config.yaml`:

```yaml
relationships:
  parent:
    marker: string            # The text pattern preceding the link
    format: string            # Template string for writing (uses {{link}})
    position: string          # Where to place it in the note
    location_type: string     # "inline" (body) or "frontmatter"
  peer:
    marker: string
    format: string
    position: string
    location_type: string
  # Optional: additional relationship types
  <custom_name>:
    ...
```

## 4. Relationship Properties

| Key | Type | Description |
|-----|------|-------------|
| `marker` | string | The prefix that identifies this relationship when reading. E.g., `"up::"`, `"top:"`, `"parent:"`. Used for both read (pattern match) and write (prefix). |
| `format` | string | Template for writing. Must contain `{{link}}`. E.g., `"up:: {{link}}"`. Multiple links joined with `", "` by default (configurable). |
| `position` | enum | Where in the note to place/find it: `connect_callout` (inside a designated callout), `frontmatter` (in YAML), `top_of_body` (first non-heading line), `end_of_frontmatter` (last line before closing `---`) |
| `location_type` | enum | `inline` (in note body — uses `marker` pattern match) or `frontmatter` (in YAML — uses `marker` as YAML key) |
| `multi` | boolean | Whether this relationship allows multiple links (default: true for peer, true for parent) |
| `separator` | string | How multiple links are joined. Default: `, ` |

## 5. Examples

### MiYo (Dataview-style inline fields in a callout)

```yaml
relationships:
  parent:
    marker: "up::"
    format: "up:: {{link}}"
    position: "connect_callout"
    location_type: "inline"
    multi: true
    separator: ", "
  peer:
    marker: "related::"
    format: "related:: {{link}}"
    position: "connect_callout"
    location_type: "inline"
    multi: true
    separator: ", "
```

### Simple user (plain frontmatter)

```yaml
relationships:
  parent:
    marker: "parent"
    format: "{{link}}"
    position: "frontmatter"
    location_type: "frontmatter"
    multi: false
  peer:
    marker: "related"
    format: "{{link}}"
    position: "frontmatter"
    location_type: "frontmatter"
    multi: true
```

### Zettelkasten (single-colon inline)

```yaml
relationships:
  parent:
    marker: "top:"
    format: "top: {{link}}"
    position: "top_of_body"
    location_type: "inline"
    multi: false
```

## 6. Writing Relationships

When Tomo generates note content (template rendering or modification), it places relationships based on `position`:

| Position | Placement |
|----------|-----------|
| `connect_callout` | Inside a callout matching `callouts.editable.connect` (e.g., `> [!connect]`). If the callout doesn't exist, Tomo creates it at the top of the body. |
| `frontmatter` | As a YAML key. Values formatted per YAML (string or list depending on `multi`). |
| `top_of_body` | First non-heading line after the frontmatter `---` fence. |
| `end_of_frontmatter` | Last line inside the YAML block, before the closing `---`. |

## 7. Reading Relationships

When Tomo reads a note to understand its links:

1. **If `location_type: frontmatter`** → parse YAML, look up the `marker` key
2. **If `location_type: inline`** → pattern match `^<marker>\s*(.+)$` in the note body
3. **Extract wikilinks** from the matched value (parse `[[...]]` syntax)
4. **Return** a list of `ParsedLink` objects with the target note name and any display alias

## 8. Detection (during /explore-vault)

vault-explorer samples M notes (default 20) that have linked content and detects:
- **Common markers** — look for patterns like `^(\w+)::`, `^(\w+):\s*\[\[`, frontmatter keys `parent`/`up`/`related`/etc.
- **Position patterns** — where are these markers typically found (in callouts, frontmatter, body top)
- **Callout usage** — if markers consistently appear in a specific callout, that's the `connect_callout`

Proposed relationship config is shown to the user. User confirms or adjusts.

## 9. Edge Cases

**Mixed syntaxes in the same vault:** Rare. If detected during `/explore-vault`, report as inconsistency and ask user to pick one (or configure multiple relationships with different markers).

**Relationship links that point to non-existent notes:** Treat as broken links. Include in orphan detection. Do not auto-remove.

**Self-links (`up:: [[Self]]`):** Treat as invalid, skip, warn.

**Multiple parents (`up:: [[A]], [[B]]`):** Allowed if `multi: true`. Most LYT vaults use this (a note can belong to multiple MOCs).

## 10. Interaction with Callouts

When `position: connect_callout`, Tomo needs to know the callout type and its [callout mapping](callout-mapping.md) status. The referenced callout must be in `callouts.editable` — Tomo will never write relationship content into a protected callout.
