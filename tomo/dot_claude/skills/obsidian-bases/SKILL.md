---
name: obsidian-bases
description: "Use PROACTIVELY when authoring an Obsidian .base (Bases) view — filters, formulas, properties, views, summaries. Triggers when the task mentions a .base file or a Bases view. (Markdown -> obsidian-markdown; .canvas -> obsidian-canvas.)"
user-invocable: true
model: sonnet
effort: low
---
# Obsidian Bases
# version: 0.1.1

Base files (`.base` extension) contain valid **YAML**. They define filters, formulas, and views over vault notes.

## Schema

```yaml
# Global filters — applied to ALL views
filters:
  and:
    - 'status == "active"'
    - not:
        - 'file.hasTag("archived")'

# Computed properties usable in views
formulas:
  formula_name: 'expression'

# Display names for properties and formulas
properties:
  property_name:
    displayName: "Display Name"
  formula.formula_name:
    displayName: "Formula Label"

# Custom aggregate formulas (used in view summaries:)
summaries:
  custom_agg: 'values.mean().round(3)'

# One or more views
views:
  - type: table | cards | list | map
    name: "View Name"
    limit: 10
    groupBy:
      property: property_name
      direction: ASC | DESC
    filters:              # view-local filters; same structure as global
      and:
        - 'status == "active"'
    order:                # properties to display, in column order
      - file.name
      - property_name
      - formula.formula_name
    summaries:            # map property name to summary formula
      property_name: Average
```

## Filter Syntax

A filter is a **quoted expression string** or a recursive object with exactly one key: `and`, `or`, or `not`.

```yaml
# Single filter
filters: 'status == "done"'

# AND — all must be true
filters:
  and:
    - 'status == "done"'
    - 'priority > 3'

# OR — any must be true
filters:
  or:
    - 'file.hasTag("book")'
    - 'file.hasTag("article")'

# NOT
filters:
  not:
    - 'file.hasTag("archived")'

# Nested
filters:
  or:
    - file.hasTag("tag")
    - and:
        - file.hasTag("book")
        - file.hasLink("Textbook")
    - not:
        - file.inFolder("Archive")
```

### Filter Operators

| Operator | Meaning |
|----------|---------|
| `==` | equals |
| `!=` | not equal |
| `>` `<` `>=` `<=` | numeric / date comparison |
| `&&` | logical and (inside expression string) |
| `\|\|` | logical or (inside expression string) |
| `!` | logical not (inside expression string) |

## Properties

Three types:

1. **Note properties** — frontmatter: `author` or `note.author`
2. **File metadata** — `file.name`, `file.mtime`, etc.
3. **Formula results** — `formula.my_formula`

### File Properties

| Property | Type | Description |
|----------|------|-------------|
| `file.name` | String | File name with extension |
| `file.basename` | String | File name without extension |
| `file.path` | String | Full vault path |
| `file.folder` | String | Parent folder path |
| `file.ext` | String | Extension |
| `file.size` | Number | Size in bytes |
| `file.ctime` | Date | Created time |
| `file.mtime` | Date | Modified time |
| `file.tags` | List | All tags |
| `file.links` | List | Outbound links |
| `file.backlinks` | List | Files linking here |
| `file.embeds` | List | Embeds in the note |
| `file.properties` | Object | All frontmatter properties |

### The `this` Keyword

In main content area: refers to the base file itself. When embedded: refers to the embedding file. In sidebar: refers to the active file in main content.

## Formulas

Defined under `formulas:`. Reference as `formula.name` in `order`, `properties`, and `summaries`.

```yaml
formulas:
  total: "price * quantity"
  status_icon: 'if(done, "done", "pending")'
  formatted_price: 'if(price, price.toFixed(2) + " dollars")'
  created: 'file.ctime.format("YYYY-MM-DD")'
  days_old: '(now() - file.ctime).days'
  days_until_due: 'if(due_date, (date(due_date) - today()).days, "")'
```

### Key Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `date()` | `date(string): date` | Parse string (`YYYY-MM-DD HH:mm:ss`) |
| `now()` | `now(): date` | Current date and time |
| `today()` | `today(): date` | Current date (00:00:00) |
| `if()` | `if(condition, trueVal, falseVal?)` | Conditional |
| `duration()` | `duration(string): duration` | Parse duration string |
| `file()` | `file(path): file` | Get file object |
| `link()` | `link(path, display?): Link` | Create a link |

For the complete function reference (Date, String, Number, List, File, Link, Object, RegExp types), see [FUNCTIONS_REFERENCE.md](references/FUNCTIONS_REFERENCE.md).

### Duration Type

Date subtraction returns a **Duration**, not a number. Access `.days`, `.hours`, etc. before calling `.round()`.

```yaml
# CORRECT
"(date(due_date) - today()).days"            # number of days
"(now() - file.ctime).days.round(0)"        # rounded

# WRONG — Duration has no .round() directly
# "(now() - file.ctime).round(0)"
```

### Date Arithmetic Units

`y/year/years`, `M/month/months`, `d/day/days`, `w/week/weeks`, `h/hour/hours`, `m/minute/minutes`, `s/second/seconds`

```yaml
"now() + \"1 day\""      # tomorrow
"today() + \"7d\""       # a week from today
```

## View Types

### Table

```yaml
views:
  - type: table
    name: "My Table"
    order:
      - file.name
      - status
      - due_date
    summaries:
      price: Sum
```

### Cards

```yaml
views:
  - type: cards
    name: "Gallery"
    order:
      - file.name
      - cover_image
      - description
```

### List

```yaml
views:
  - type: list
    name: "Simple List"
    order:
      - file.name
      - status
```

### Map

Requires latitude/longitude properties and the Maps community plugin.

```yaml
views:
  - type: map
    name: "Locations"
```

## Default Summary Formulas

| Name | Input | Description |
|------|-------|-------------|
| `Average` | Number | Mean |
| `Min` / `Max` | Number | Smallest / largest |
| `Sum` | Number | Total |
| `Range` | Number | Max - Min |
| `Median` | Number | Median |
| `Stddev` | Number | Standard deviation |
| `Earliest` / `Latest` | Date | Earliest / latest date |
| `Checked` / `Unchecked` | Boolean | Count of true / false |
| `Empty` / `Filled` | Any | Count of empty / non-empty |
| `Unique` | Any | Count of unique values |

## Embedding

```markdown
![[MyBase.base]]

![[MyBase.base#View Name]]
```

## YAML Quoting Rules

- Use **single quotes** for formulas containing double quotes: `'if(done, "Yes", "No")'`
- Use **double quotes** for plain strings: `"My View Name"`
- Strings containing `:`, `{`, `}`, `[`, `]`, `#`, `|`, `>`, `!`, etc. must be quoted.

## Troubleshooting

### YAML Syntax Errors

```yaml
# WRONG — unquoted colon
displayName: Status: Active

# CORRECT
displayName: "Status: Active"

# WRONG — double quotes inside double quotes
formulas:
  label: "if(done, "Yes", "No")"

# CORRECT — single quotes wrapping double quotes
formulas:
  label: 'if(done, "Yes", "No")'
```

### Formula Errors

**Duration without field access** — `(now() - file.ctime)` returns Duration, not a number:
```yaml
# WRONG
"(now() - file.ctime).round(0)"
# CORRECT
"(now() - file.ctime).days.round(0)"
```

**Missing null guard** — properties may be absent on some notes:
```yaml
# WRONG — crashes if due_date is empty
"(date(due_date) - today()).days"
# CORRECT
'if(due_date, (date(due_date) - today()).days, "")'
```

**Undefined formula reference** — every `formula.X` in `order` or `properties` needs a matching entry in `formulas`.
