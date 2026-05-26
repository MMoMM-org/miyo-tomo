---
name: suggestions-doc-format
description: Use PROACTIVELY when producing or parsing suggestions, suggestions-fan, or MOC-proposal docs. Provides approval checkbox patterns, item structure, and tomo frontmatter format.
user-invocable: false
---
# Suggestions Doc Format
# version: 0.1.0

## Approval Checkboxes

Suggestions and suggestions-fan docs use:
```
- [x] Approved
```

MOC-proposal docs use:
```
- [x] Accept
```

Both are case-sensitive, line-start anchored.

## Force Atomic Note

Per-item checkbox within a suggestions doc:
```
- [x] Force Atomic Note
```

When ticked, the item gets a fan companion analysis before synthesis.

## Suggestion Item Structure

```
### S<NN> — <title>
**Source:** [[<stem>]]
**Topics:** <topic1>, <topic2>

<analysis content>

- [ ] Approved
- [ ] Force Atomic Note
```

## Suggestions-Fan Companion

Mirrors the parent suggestions doc but contains only force-atomic items with expanded analysis. Filename pattern: `<date>_suggestions-fan.md`.

## Tomo Frontmatter

All suggestions docs carry a `tomo:` frontmatter block:

```yaml
tomo:
  doc_type: suggestions  # or suggestions-fan, moc-proposal
  state: pending-approval  # or approved, pending-accept, accepted
  run_id: "<run-id>"
  updated_at: "<ISO-8601>"
```

| doc_type | valid states |
|----------|-------------|
| `suggestions` | `pending-approval`, `approved` |
| `suggestions-fan` | `pending-approval`, `approved` |
| `moc-proposal` | `pending-accept`, `accepted` |
