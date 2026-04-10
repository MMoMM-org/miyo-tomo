# Tier 3: Template Files

> Parent: [Template System](../../tier-2/components/template-system.md)
> Status: Draft
> Related: [Token Vocabulary](token-vocabulary.md) · [MiYo Profile](../profiles/miyo-profile.md)

---

## 1. Purpose

Define what Tomo template files look like, how they're structured, and provide reference examples for each MVP note type. These templates live in the user's vault (not in the Tomo instance) and are read via Kado.

## 2. Template Location

Templates are stored in the vault at the path configured in `vault-config.yaml`:

```yaml
templates:
  base_path: "X/900 Support/Templates/"
  mapping:
    atomic_note: "t_note_tomo"      # → X/900 Support/Templates/t_note_tomo.md
    map_note:    "t_moc_tomo"
    daily:       "t_daily_tomo"
    project:     "t_project_tomo"
    source:      "t_source_tomo"
```

**Naming is user-defined** — no `t_*_tomo` convention enforced. The user picks whatever filenames they want.

## 3. Template Structure

A template file is a normal Obsidian markdown file with `{{token}}` placeholders where dynamic content goes. Everything else is static and copied as-is into the rendered note.

```
┌─────────────────────────────┐
│  --- (frontmatter start)    │  Static YAML keys + {{token}} values
│  key: {{token}}             │
│  --- (frontmatter end)      │
│                             │
│  > [!callout]               │  Static structure (callouts, headings)
│  > field:: {{token}}        │  Inline fields with token values
│                             │
│  # [[{{title}}]]            │  Dynamic title as wikilink
│                             │
│  {{body}}                   │  Dynamic content area
│                             │
│  ## Static Section          │  Static section headings
│  - {{token}}                │  Dynamic content in static structure
└─────────────────────────────┘
```

## 4. Reference Templates (MiYo Profile)

### 4.1 Atomic Note Template

```markdown
---
UUID: {{uuid}}
DateStamp: {{datestamp}}
Updated: {{updated}}
locale: {{locale}}
Vault: {{vault}}
VaultVersion: {{vault_version}}
title: {{title}}
tags:{{tags}}
aliases:{{aliases}}
Summary: {{summary}}
---

> [!connect] Your way around
> up:: {{up}}
> related:: {{related}}

# [[{{title}}]]

{{body}}

> [!video] Action Items

> [!calendar]- Recent Updates

## Related
> [!connect] Categories

> [!puzzle] Related Topics
```

### 4.2 Map Note (MOC) Template

```markdown
---
UUID: {{uuid}}
DateStamp: {{datestamp}}
Updated: {{updated}}
locale: {{locale}}
Vault: {{vault}}
VaultVersion: {{vault_version}}
title: {{title}}
tags:{{tags}}
aliases:{{aliases}}
Summary: {{summary}}
---

> [!connect] Your way around
> up:: {{up}}
> related:: {{related}}

# [[{{title}}]]

---
> [!anchor] Overview

{{body}}

> [!blocks] Key Concepts

> [!video] Action Items

> [!calendar]- Recent Updates

## Related
> [!connect] Categories

> [!puzzle] Related Topics

> [!compass] Something you should look at perhaps..
```

### 4.3 Daily Note Template (Simplified)

```markdown
---
UUID: {{uuid}}
DateStamp: {{datestamp}}
Updated: {{updated}}
locale: {{locale}}
Vault: {{vault}}
title: {{title}}
tags:
  - type/calendar/daily
---

# [[{{title}}]]

## Morning

## Notes

{{body}}

## Tracker
```

**Note:** This is a simplified Tomo-compatible daily template. The user's actual daily template is likely more complex (Templater chain-loading, custom JS, etc.). Tomo's daily template is used ONLY when creating a missing daily note — the user normally creates daily notes via their own Templater flow.

### 4.4 Project Template

```markdown
---
UUID: {{uuid}}
DateStamp: {{datestamp}}
Updated: {{updated}}
title: {{title}}
tags:{{tags}}
Summary: {{summary}}
---

> [!connect] Your way around
> up:: {{up}}

# [[{{title}}]]

## Goal

{{body}}

## Tasks

## Log
```

### 4.5 Source Template

```markdown
---
UUID: {{uuid}}
DateStamp: {{datestamp}}
Updated: {{updated}}
title: {{title}}
tags:{{tags}}
Summary: {{summary}}
source_url: {{source_url}}
source_author: {{source_author}}
---

> [!connect] Your way around
> up:: {{up}}

# [[{{title}}]]

## Summary

{{body}}

## Key Takeaways

## Quotes
```

## 5. Templater Syntax Coexistence

Templates may contain both `{{tomo_tokens}}` and `<% tp.* %>` Templater syntax:

```markdown
---
UUID: {{uuid}}
DateStamp: {{datestamp}}
title: {{title}}
created: <% tp.date.now("YYYY-MM-DD") %>
---
```

**Resolution order:**
1. Tomo resolves `{{tokens}}` → produces a rendered file
2. User opens the file in Obsidian
3. User runs "Templater: Replace Templates in Active File" → resolves `<% tp.* %>`

Tomo does NOT touch any Templater syntax — it passes through unchanged. The instruction set notes when Templater syntax is present so the user knows to run the command.

### Templater Syntax Variants to Preserve

| Syntax | Purpose | Can span multiple lines? |
|--------|---------|------------------------|
| `<% expression %>` | Output expression result | Typically single line |
| `<%* statement %>` | Execute JS without output | **Yes — can span many lines** |
| `<% tp.* %>` | Templater API calls | Typically single line |
| `-%>` | Whitespace-trimming close tag | Used with any opener |

**Important:** `<%* ... %>` blocks can contain entire JavaScript functions spanning 10+ lines. Tomo must NOT parse inside them, not treat their content as markdown, and not attempt token resolution within them. The entire block from `<%*` to the matching `%>` (or `-%>`) is opaque.

## 6. Template Validation

When Tomo reads a template during rendering:

1. **Check file exists** via Kado — if not, use hardcoded fallback
2. **Check for unknown required tokens** — if template uses `{{xyz}}` and `xyz` is not a known token, warn (it will resolve to empty string)
3. **Check for invalid YAML** — frontmatter must parse after token resolution
4. **Check for unclosed `{{`** — likely a typo
5. **Check for Templater syntax** — note in instruction set if present

## 7. Fallback (No Template)

If a template file doesn't exist (referenced in config but not found via Kado):

```
Tomo generates a minimal note:
---
title: {{title}}
tags:{{tags}}
---
# [[{{title}}]]

{{body}}
```

This ensures the workflow doesn't break on missing templates. Tomo warns: "Template `<name>` not found. Using minimal fallback. Create the template for better results."

## 8. Tomo Example Templates

Tomo ships with example templates in `tomo/config/templates/` (in the Tomo source repo, not the vault). During first-session discovery, Tomo offers to create vault templates based on these examples:

```
"I notice you don't have a Tomo-compatible note template yet.
 Would you like me to create one based on the MiYo example template?
 It will be written to your inbox folder — you can review and move it
 to your templates folder."
```

The examples serve as a starting point — users are expected to customize them.
