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
