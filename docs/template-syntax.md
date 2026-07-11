# Tomo Template Syntax

How to write Obsidian note templates that work with Tomo's rendering pipeline.

## Overview

Tomo templates are standard Obsidian markdown files that contain `{{token}}` placeholders.
When Tomo creates a new note (Pass 2), it replaces the tokens with actual values — title,
tags, body content, etc. Everything else in the template is preserved exactly as-is,
including Templater expressions, Dataview code, and callouts.

## Available Tokens

### Generated (computed at render time)

| Token | Format | Example |
|-------|--------|---------|
| `{{uuid}}` | `YYYYMMDDHHmmss` | `20260417143045` |
| `{{datestamp}}` | `YYYY-MM-DD` | `2026-04-17` |
| `{{updated}}` | `YYYY-MM-DD HH:mm` | `2026-04-17 14:30` |
| `{{date_iso}}` | ISO 8601 | `2026-04-17T14:30:45Z` |

These always resolve. No configuration needed.

### Content (from the inbox item and user decisions)

| Token | Source | Required |
|-------|--------|----------|
| `{{title}}` | Suggested name from suggestions doc | **Yes** |
| `{{tags}}` | Confirmed tags, comma-separated | No |
| `{{body}}` | Source note content (without frontmatter) | No |
| `{{up}}` | Parent MOC as wikilink, e.g. `[[Japan (MOC)]]` | No |
| `{{summary}}` | Extracted summary | No |
| `{{aliases}}` | Aliases, comma-separated | No |
| `{{related}}` | Related notes as wikilinks | No |
| `{{children}}` | Child note bullets for MOC content callout, callout-prefixed (e.g. `> - [[Note]]`). Currently only populated for MOC proposal flow; empty for suggest flow. | No |

### Config-sourced (from vault-config.yaml)

Tokens derived from `frontmatter.optional` entries that have a `default` value.
Common examples:

| Token | Typical Value |
|-------|---------------|
| `{{locale}}` | `de` |
| `{{vault}}` | `Privat` |
| `{{vault_version}}` | `2` |
| `{{profile}}` | `miyo` |

### Metadata (from processing context)

| Token | Source |
|-------|--------|
| `{{source_path}}` | Original inbox item path |
| `{{source_link}}` | Original item as wikilink |
| `{{classification}}` | Best-fit classification name |
| `{{classification_number}}` | Dewey number (e.g., 2600) |

## Tags: Inline Array Syntax

Tags are passed as a **comma-separated string**, not a YAML list. This lets you
embed `{{tags}}` inside an inline YAML array alongside static base tags:

```yaml
tags: [type/note/normal, status/fleeting/🎗️, {{tags}}]
```

Renders to:

```yaml
tags: [type/note/normal, status/fleeting/🎗️, topic/travel/japan, topic/hokkaido]
```

If no tags are confirmed, the token resolves to empty string:

```yaml
tags: [type/note/normal, status/fleeting/🎗️, ]
```

The trailing comma is harmless in YAML.

## Templater Coexistence

Templates can contain both `{{tomo_tokens}}` and Obsidian Templater syntax.
Tomo resolves `{{tokens}}` first. Templater syntax passes through unchanged:

```markdown
---
UUID: <% tp.date.now("YYYYMMDDHHmmss") %>
DateStamp: <% tp.date.now("YYYY-MM-DD") %>
title: "{{title}}"
tags: [type/note/normal, {{tags}}]
aliases: [<% await tp.file.include("[[i_alias]]")-%>]
---

# [[{{title}}]]

{{body}}
```

After Tomo rendering, the file contains resolved `{{tokens}}` and untouched
Templater expressions. The user runs `Templater: Replace Templates in Active File`
(Cmd+P) after moving the note to its target folder.

### What is preserved

| Syntax | Preserved | Example |
|--------|-----------|---------|
| `<% expression %>` | Yes | `<% tp.date.now("YYYY") %>` |
| `<%* statement %>` | Yes | `<%* let title = tp.file.title %>` |
| `<% await tp.file.include(...) %>` | Yes | `<% await tp.file.include("[[x_frontmatter]]") %>` |
| ` ``` dataviewjs ... ``` ` | Yes | Dataview code blocks |
| `> [!callout]` | Yes | Obsidian callouts |
| `\{\{` (escaped) | → literal `{{` | For documenting token syntax |

> **Careful with `<% ... include("[[x_frontmatter]]") ... %>`:** an include is
> preserved fine, but it must not be the thing that supplies your template's
> *opening* `---` fence. See [Frontmatter: a complete `---` block is required](#frontmatter-a-complete----block-is-required).

## Frontmatter: a complete `---` block is required

Tomo stamps a `tomo:` provenance block into every rendered note, and it does so by
inserting that block into the note's **leading `---` frontmatter**. Two rules follow
— both are load-bearing.

### Rule 1 — the template must open with a literal `---` fence

The first line of the template must be a literal `---`, and the frontmatter must be a
complete, self-contained block (opening `---` … closing `---`) with your keys inside:

```markdown
---
UUID: <% tp.date.now("YYYYMMDDHHmmss") %>
title: "{{title}}"
tags: [type/others/moc, {{tags}}]
aliases: [<% await tp.file.include("[[i_alias]]")-%>]
---
```

**Do not delegate the opening fence to a Templater include.** Tomo does not run
Templater at render time (see Rule 2), so a template that *starts* with an include
meant to supply the fence has, from Tomo's point of view, no opening `---` at all:

```markdown
<%await tp.file.include("[[x_frontmatter]]")-%>   ← ✗ x_frontmatter emits the opening ---
title: "{{title}}"                                 ←   only at Templater-time; Tomo never runs it
tags: [type/others/moc, {{tags}}]
---
```

Seeing no leading `---`, Tomo prepends its own `---\ntomo: …\n---` block, and
**everything below becomes note body** — `title`, `tags`, `aliases`, `banner`, … end
up as plain text after the frontmatter instead of as frontmatter keys. Fix: inline
the shared frontmatter with a literal `---` (the `x_yaml_*` sub-includes can still
live *inside* the block, exactly as the atomic-note template does).

### Rule 2 — Templater runs *after* Tomo

Order of operations for a rendered note:

1. Tomo resolves `{{tokens}}`.
2. Tomo inserts the `tomo:` block into the leading `---` frontmatter.
3. The note is written to the inbox; you move it to its destination.
4. **Then** you run `Templater: Replace Templates in Active File`, which resolves the
   `<% tp.* %>` expressions.

So Tomo always sees the raw `<% … %>` (never their results), and your frontmatter must
already be *structurally valid before Templater runs* — i.e. the `---` fences must be
literal. Put Templater expressions **inside** the block as values
(`UUID: <% tp.date.now() %>`), never as the construct that produces the fence itself.

### What Tomo adds to the frontmatter

Immediately after the opening `---`, Tomo inserts a `tomo:` block:

```yaml
tomo:
  doc_type: rendered-note
  state: pending-move
  run_id: 2026-07-10T13-24-36Z-6af113
  updated_at: '2026-07-10T13:25:08Z'
```

- Inserted **once**, right after the opening fence. Every existing frontmatter line is
  preserved **byte-for-byte** — no YAML round-trip, so inline arrays, key order,
  quoting, and your `<% … %>` expressions are untouched.
- Fail-safe: if the leading fence is unclosed, or a top-level `tomo:` key is already
  present, Tomo writes the note **unstamped** rather than risk a corrupt frontmatter
  (worst case: triage re-ingests the note later — never a corrupted note).

`state: pending-move` marks the note as staged in the inbox awaiting apply; Tomo/Hashi
flip it as the note moves to its destination. You never author the `tomo:` block
yourself — leave it out of your template.

## Dataview Code Blocks

Tokens inside fenced code blocks are NOT resolved. This prevents breaking
Dataview queries or code examples:

````markdown
``` dataviewjs
let page = dv.current();
if (page.summary && page.summary.length > 0) {
    dv.paragraph("\n**Summary:** _" + page.summary + "_");
}
```
````

This entire block passes through unchanged.

## Example: Tomo Note Template

A complete example (`t_note_tomo.md`):

```markdown
---
UUID: <% tp.date.now("YYYYMMDDHHmmss") %>
DateStamp: <% tp.date.now("YYYY-MM-DD") %>
Updated: 
<% await tp.file.include("[[x_yaml_language]]") %>
<% await tp.file.include("[[x_yaml_vault]]") %>
<% await tp.file.include("[[x_yaml_vaultVersion]]") %>
Summary:
title: "{{title}}"
tags: [type/note/normal, status/fleeting/🎗️, {{tags}}]
aliases: [<% await tp.file.include("[[i_alias]]")-%>]
---

> [!connect] Your way around
> up:: {{up}}
> related::

# [[{{title}}]]

` `` dataviewjs
let page = dv.current();
if (page.summary && page.summary.length > 0) {
    dv.paragraph("\n**Summary:** _" + page.summary + "_");
}
` ``

{{body}}
```

After Tomo rendering with title="Sapporo", tags=topic/travel/japan, up=[[Japan (MOC)]]:
- `{{title}}` → `Sapporo`
- `{{tags}}` → `topic/travel/japan`
- `{{up}}` → `[[Japan (MOC)]]`
- `{{body}}` → source note content
- All `<% %>` expressions → unchanged (Templater resolves later)
- Dataview code block → unchanged

## Required vs Optional Tokens

- **Required** (`uuid`, `datestamp`, `title`): rendering fails if unresolvable
- **Optional** (everything else): resolves to empty string if missing

If a required token cannot be resolved, the rendering script reports an error
and skips that item. No broken file is written.

## Template Mapping

Which template is used for which note type is configured in `vault-config.yaml`:

```yaml
templates:
  mapping:
    atomic_note: "X/900 Support/930 Templater/t_note_tomo.md"
    map_note:    "X/900 Support/930 Templater/t_moc.md"
    source:      "X/900 Support/930 Templater/t_resource.md"
```

Users can override the template per item in the suggestions document before approving.
