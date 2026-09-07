---
name: suggestions-doc-format
description: Use PROACTIVELY when producing or parsing suggestions, suggestions-fan, or MOC-proposal docs. Provides approval checkbox patterns, item structure, and tomo frontmatter format.
user-invocable: false
---
# Suggestions Doc Format
# version: 0.5.0

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

When two items in the run share a filename, every `**Source:**` and
`- Source:` link for those items carries the path plus an alias instead:

```
**Source:** [[<vault-relative path without .md>|<stem>]]
```

Read the alias as the item's display name. Read the target as the note to
open. Never write the target into `**Suggested name:**` or any title.

## Name Clash Notice

An item whose proposed destination was already claimed — by another item in the
run, or by a note already in the target folder — carries one extra line
directly under its name:

```
**Suggested name:** <name>
**Name clash:** <reason>. The suggested name above was adjusted — edit it if you prefer another.
```

The line is informational. Treat `**Suggested name:**` as an ordinary editable
field: the user's value wins, whether they keep the adjusted name or replace
it. Never re-derive a name from the notice, never carry the notice into a
title, and never treat an adjusted name as different from any other.

## Suggestions-Fan Companion

Mirrors the parent suggestions doc but contains only force-atomic items with expanded analysis. Filename pattern: `<date>_suggestions-fan.md`.

## Steering Placements by Hand

Where an atomic note lands inside a MOC is controlled by an optional `**Placement:**`
line placed on the line **directly under** a checked `- [x] [[…MOC]]` link (column 0).
The reducer renders it only for a pre-resolved candidate; a user may add or edit one
under any checked MOC. A hand-edited Placement line overrides the doc-JSON.

Valid forms — `suggestion-parser.py` reverse-parses these exactly:

| Intent | Line |
|--------|------|
| Existing heading | `` **Placement:** under `## <Heading>` `` |
| New section before the MOC footer | `` **Placement:** new section `## <Name>` (before the footer) `` |
| New section at the end (no footer) | `` **Placement:** new section `## <Name>` (at the end of the MOC) `` |
| Inside an editable callout | `` **Placement:** inside the `[!<type>] <title>` callout `` |

Merge rule: notes that target the **same MOC** with the **same** new-section name collapse
into one `## <Name>` section (one heading, multiple bullets) at Pass-2. To group notes, give
them an identical `(MOC, new section)` pair.

A checked `[x]` MOC with **no** Placement line still produces a link — Pass-2 resolves its
section heuristically (editable callout, then heading). The Placement line only overrides that
default; it is not required for the link to exist. `parent_mocs` (every checked MOC) drives
link emission; `candidate_mocs` carries the anchor override only.

## Consolidating Proposed MOCs

The `## Proposed MOCs` section lists new-MOC proposals as `### Proposed MOC: <topic>` blocks,
each with a `- **Name:** <name>` line and a `- [ ] Approve` checkbox.

To collapse two proposed MOCs into one: set their `**Name:**` lines to the **same** value and
check `- [x] Approve` on both. Two approved blocks with an identical final Name merge into one
`create_moc` whose supporting notes are the **union** of both blocks. A note's membership is
recovered from its block's `### Proposed MOC: <topic>` header, so renaming the `**Name:**` line
alone re-homes every member of that block — the `## Suggestions` section needs no edit.

The `**Name:**` value is read up to its `←` edit-hint; keep or drop the hint suffix freely.

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
