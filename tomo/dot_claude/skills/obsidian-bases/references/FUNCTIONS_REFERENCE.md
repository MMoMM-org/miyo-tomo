# Obsidian Bases — Functions Reference

Formula expressions used in `.base` `formulas[].expression` fields.

---

## Property Access

| Expression | Returns |
|---|---|
| `prop('key')` | Value of frontmatter property `key`; `null` if absent |
| `prop('file.name')` | Note filename without extension |
| `prop('file.path')` | Full vault-relative path |
| `prop('file.ctime')` | Creation datetime |
| `prop('file.mtime')` | Last-modified datetime |
| `prop('file.size')` | File size in bytes (number) |

---

## Arithmetic

| Expression | Description |
|---|---|
| `add(a, b)` | a + b |
| `subtract(a, b)` | a − b |
| `multiply(a, b)` | a × b |
| `divide(a, b)` | a / b (returns null when b = 0) |
| `mod(a, b)` | a modulo b |
| `abs(n)` | Absolute value |
| `floor(n)` | Round down to nearest integer |
| `ceil(n)` | Round up to nearest integer |
| `round(n)` | Round to nearest integer |
| `max(a, b)` | Larger of two numbers |
| `min(a, b)` | Smaller of two numbers |

---

## Date & Time

All date functions accept `date` / `datetime` property values or `now()`.

| Expression | Description |
|---|---|
| `now()` | Current datetime |
| `today()` | Current date (midnight) |
| `dateDiff(a, b, unit)` | Difference between two dates in `unit`: `'days'` / `'hours'` / `'minutes'` / `'months'` / `'years'` |
| `dateAdd(d, n, unit)` | Add n units to date d |
| `formatDate(d, format)` | Format a date using Moment.js tokens (e.g. `'YYYY-MM-DD'`) |
| `year(d)` | Extract year (number) |
| `month(d)` | Extract month 1–12 (number) |
| `day(d)` | Extract day of month (number) |
| `weekday(d)` | Day of week 0 (Sun) – 6 (Sat) (number) |

---

## Text

| Expression | Description |
|---|---|
| `concat(a, b, ...)` | Concatenate strings |
| `contains(text, sub)` | True if `text` contains `sub` |
| `startsWith(text, prefix)` | True if `text` starts with `prefix` |
| `endsWith(text, suffix)` | True if `text` ends with `suffix` |
| `lower(text)` | Lowercase |
| `upper(text)` | Uppercase |
| `trim(text)` | Strip leading/trailing whitespace |
| `replace(text, from, to)` | Replace first occurrence of `from` with `to` |
| `slice(text, start, end)` | Substring (0-indexed, `end` exclusive) |
| `length(text)` | Character count |

---

## Logic & Conditionals

| Expression | Description |
|---|---|
| `if(cond, then, else)` | Return `then` when `cond` is truthy, otherwise `else` |
| `and(a, b)` | Logical AND |
| `or(a, b)` | Logical OR |
| `not(a)` | Logical NOT |
| `equal(a, b)` | True if a equals b |
| `gt(a, b)` | a > b |
| `lt(a, b)` | a < b |
| `gte(a, b)` | a >= b |
| `lte(a, b)` | a <= b |
| `empty(v)` | True if v is null, empty string, or empty array |

---

## Common Formula Patterns

**Days overdue (negative = overdue):**
```
dateDiff(now(), prop('due'), 'days')
```

**Status label with fallback:**
```
if(empty(prop('status')), 'Unknown', prop('status'))
```

**Full display title:**
```
concat(prop('file.name'), ' — ', prop('status'))
```

**Is this week (boolean):**
```
and(gte(prop('due'), today()), lte(prop('due'), dateAdd(today(), 7, 'days')))
```
