---
name: obsidian-dataview
description: "Use PROACTIVELY when authoring an Obsidian Dataview DQL query block — TABLE/LIST/TASK/CALENDAR queries, FROM/WHERE/SORT, inline fields. Triggers when the task asks for a ```dataview block or a Dataview query. (Filtered note views -> prefer obsidian-bases; Markdown -> obsidian-markdown; field semantics -> obsidian-fields.)"
user-invocable: true
model: sonnet
effort: low
---
# Obsidian Dataview
# version: 0.1.0

Dataview Query Language (DQL) blocks query vault notes by frontmatter, inline fields, tasks, and file metadata. Author DQL only when the user explicitly asks for a Dataview block.

## When to Use

- **Prefer a `.base` view** for a simple filtered list or table of notes — it is the native, no-plugin, mobile-friendly default. See obsidian-bases. Emit DQL only on an explicit request for a Dataview query.
- **DataviewJS (`dataviewjs` / `dv.*` JS API) is out of scope.** That surface is large and best served by TypeScript type definitions / IntelliSense in a coding IDE, not by this skill. Do not author `dataviewjs` blocks here.

## Fenced Block

A DQL query is a fenced code block with the `dataview` language tag:

````markdown
```dataview
TABLE status, due
FROM "Projects"
WHERE status != "done"
SORT due ASC
```
````

`dataview` = DQL (this skill). `dataviewjs` = JavaScript (out of scope).

## Query Structure

Every query starts with one query type, then optional clauses in order.

| Query type | Output |
|------------|--------|
| `TABLE col1, col2 AS "Label"` | Table; one row per page |
| `LIST [expression]` | Bulleted list of links |
| `TASK` | Interactive task list (queries `- [ ]` items, not pages) |
| `CALENDAR dateField` | Calendar keyed on a date field |

| Clause | Purpose |
|--------|---------|
| `FROM source` | Restrict the page set (folder / tag / link) |
| `WHERE expr` | Keep rows where `expr` is truthy |
| `SORT field [ASC\|DESC]` | Order rows |
| `GROUP BY field` | Collapse rows into groups (adds `rows`) |
| `FLATTEN field` | Expand a list field into one row per element |
| `LIMIT n` | Cap row count |

## Inline Fields

Body-level metadata Dataview can query, written with a **double colon**:

```markdown
status:: active
due:: 2026-06-29
```

- **Double colon `key:: value`** is queryable in the note body. A single colon `key: value` in the body does nothing — single colon only defines fields inside YAML frontmatter.
- **Inline keys are normalized:** lowercased and spaces replaced with hyphens. `Due Date:: ...` is queried as `due-date`. This normalization applies to **inline fields only** — frontmatter keys are queried verbatim.

## Sources (FROM)

| Form | Meaning |
|------|---------|
| `FROM "Folder/Sub"` | Quoted string = folder path |
| `FROM #tag` | Tag (and its subtags) |
| `FROM [[Note]]` | Pages linking to / from a note |
| `FROM "A" AND #b` | Combine with `AND` / `OR` |

Bare `FROM Projects` (unquoted, no `#`) is parsed as a tag-like source and matches nothing.

## Troubleshooting

### Query returns nothing

- **Single colon in body** — `status: active` is invisible to DQL. Use `status:: active`.
- **Wrong field name** — an inline field `Due Date::` is queried as `due-date`, not `Due Date`. Frontmatter keys are not normalized.
- **Unquoted folder** — `FROM Projects` fails; use `FROM "Projects"`.
- **Case mismatch** — comparisons are case-sensitive: `status != "active"` does not match `Active`, and `#Work` ≠ `#work`. Match the stored case.

### Wrong rows leak in

- **Missing field is `null`, not skipped** — a page without the field evaluates to `null`, and `null <= date(today)` is true, so undated pages appear in "overdue" lists. Guard with an existence check:

```dataview
TABLE due
WHERE due AND due <= date(today)
```

### Date comparison fails

- **Wrap dates in `date()` with ISO format** — compare `date(due)` against `date(today)` or `date(2026-06-29)`. A raw string compared to a date does not match.
