---
name: obsidian-bases
description: "Use PROACTIVELY when authoring an Obsidian .base (Bases) view — filters, formulas, properties, views, summaries. Triggers when the task mentions a .base file or a Bases view. (Markdown → obsidian-markdown; .canvas → obsidian-canvas.)"
user-invocable: true
---
# Obsidian Bases
# version: 0.1.0

Format reference for Obsidian `.base` files. A `.base` file is a JSON document that defines a database view over vault notes. Compose the JSON directly — do not use a token renderer.

## File Structure

```json
{
  "filters": [],
  "views": [
    {
      "type": "table",
      "name": "View Name",
      "properties": [],
      "sort": [],
      "group": null
    }
  ],
  "formulas": [],
  "summaries": []
}
```

Top-level keys:
- `filters` — global filter applied to every view (array of filter objects)
- `views` — one or more view definitions (array); at least one required
- `formulas` — computed property definitions (array; may be empty)
- `summaries` — aggregate calculations shown at the bottom of views (array; may be empty)

## Filters

Filters control which vault notes appear in the view. Global `filters` apply to all views; a `view.filters` array can add view-local conditions.

**Single condition:**
```json
{
  "property": "status",
  "operator": "is",
  "value": "active"
}
```

**Compound filter (AND/OR):**
```json
{
  "type": "and",
  "filters": [
    { "property": "status", "operator": "is", "value": "active" },
    { "property": "due", "operator": "is-not-empty" }
  ]
}
```

**Filter by tag:**
```json
{ "tag": "project" }
```

**Filter by folder/path prefix:**
```json
{ "path": "Projects/" }
```

**Operators:**
- Equality: `is` / `is-not`
- Text: `contains` / `does-not-contain` / `starts-with` / `ends-with`
- Existence: `is-empty` / `is-not-empty`
- Numeric/date comparison: `is-greater-than` / `is-less-than` / `is-greater-than-or-equal` / `is-less-than-or-equal`

## Properties

Properties define which frontmatter fields appear as columns.

```json
{
  "property": "status",
  "label": "Status",
  "hidden": false,
  "width": 120
}
```

- `property` — frontmatter key name (required)
- `label` — column header override (optional; defaults to property name)
- `hidden` — exclude from current view without removing from schema (optional; default `false`)
- `width` — column width in pixels (optional)

**Built-in file properties** (no frontmatter required):

| Property | Type | Value |
|---|---|---|
| `file.name` | text | Filename without extension |
| `file.path` | text | Full vault-relative path |
| `file.ctime` | datetime | Creation timestamp |
| `file.mtime` | datetime | Last-modified timestamp |
| `file.size` | number | Size in bytes |
| `file.tags` | multitext | All tags on the note |
| `file.inlinks` | multitext | Notes that link to this note |
| `file.outlinks` | multitext | Notes this note links to |

## Views

### Table

```json
{
  "type": "table",
  "name": "All Notes",
  "filters": [],
  "properties": [
    { "property": "status" },
    { "property": "due" }
  ],
  "sort": [
    { "property": "due", "direction": "asc" }
  ],
  "group": null
}
```

- `sort` — array of `{ "property": "<key>", "direction": "asc" | "desc" }` objects
- `group` — optional `{ "property": "<key>" }` to group rows by a property value; omit or `null` for ungrouped

### Gallery

```json
{
  "type": "gallery",
  "name": "Cards",
  "cover": { "property": "image" },
  "properties": [
    { "property": "status" }
  ],
  "sort": []
}
```

- `cover.property` — frontmatter key whose value is an image path for the card thumbnail (optional)

### Calendar

```json
{
  "type": "calendar",
  "name": "Schedule",
  "date": { "property": "due" },
  "properties": [
    { "property": "status" }
  ]
}
```

- `date.property` — frontmatter key that provides the calendar date (required for calendar; must be a date/datetime property)

### Board (Kanban)

```json
{
  "type": "board",
  "name": "Kanban",
  "group": { "property": "status" },
  "properties": [
    { "property": "due" }
  ],
  "sort": []
}
```

- `group.property` — property whose distinct values become the board columns (required for board)

### List

```json
{
  "type": "list",
  "name": "Quick List",
  "sort": [
    { "property": "file.mtime", "direction": "desc" }
  ]
}
```

Minimal view — shows note titles only, no column config needed.

## Formulas

Formulas define computed columns derived from other properties. See `reference/FUNCTIONS_REFERENCE.md` for the full function catalog.

```json
{
  "name": "Days Until Due",
  "type": "number",
  "expression": "dateDiff(prop('due'), now(), 'days')"
}
```

- `name` — column header for the formula result
- `type` — result type: `text` | `number` | `boolean` | `date` | `datetime`
- `expression` — function expression (see FUNCTIONS_REFERENCE for available functions)

Reference a formula result in `properties` by using its `name` as the `property` value.

## Summaries

Summaries aggregate formula or property values and appear in a row at the bottom of table views.

```json
{
  "property": "due",
  "formula": "countNotEmpty"
}
```

Available formula values: `count`, `countEmpty`, `countNotEmpty`, `sum`, `average`, `min`, `max`, `range`

- `count` — total number of rows
- `countEmpty` / `countNotEmpty` — rows where the property is absent/present
- `sum` / `average` / `min` / `max` — numeric aggregates
- `range` — max − min for numeric properties

## Troubleshooting

**View shows no notes:** Check global `filters` — an overly strict filter eliminates all rows. Remove all filters temporarily to verify notes load, then re-add conditions.

**Property column missing:** The frontmatter key is absent or misspelled. Verify the exact key name with `kado-read` → `frontmatter`. Key names are case-sensitive.

**Calendar shows blank:** The `date.property` must point to a `date` or `datetime` frontmatter property. A `text` property with a date string will not render.

**Board columns empty:** `group.property` must have at least one non-empty value across the matched notes. Notes with an empty group property appear in an "ungrouped" column.

**Formula returns null:** Property reference in the expression does not match any frontmatter key. Use `prop('exact-key-name')` with the verbatim frontmatter key.

**JSON parse error on write:** Run `python3 scripts/validate-json.py <path>` before writing. Common causes: trailing commas, single-quoted strings, missing closing braces.
