---
name: template-render
description: Token resolution pipeline, category precedence (generated → config → content → metadata → custom), and rendering rules for note templates. Use when rendering templates during Pass 2, debugging unresolved tokens, or explaining template/Templater coexistence.
user-invocable: false
---
# Template Render
# version: 0.1.0

Knowledge patterns for the token resolution system used when rendering note templates.

## Token Categories

Tokens are resolved in this order. Earlier categories take precedence.

### 1. Generated Tokens (computed at render time)

| Token | Format | Example |
|-------|--------|---------|
| `{{uuid}}` | `YYYYMMDDHHmmss` | `20260410143045` |
| `{{datestamp}}` | `YYYY-MM-DD` | `2026-04-10` |
| `{{updated}}` | `YYYY-MM-DD HH:mm` | `2026-04-10 14:30` |
| `{{date_iso}}` | ISO 8601 | `2026-04-10T14:30:45Z` |

These always resolve. No configuration needed.

### 2. Config-Sourced Tokens (from vault-config.yaml)

Derived from `frontmatter.optional` fields that have a `default` value:

| Token | Source | MiYo Default |
|-------|--------|-------------|
| `{{locale}}` | frontmatter.optional[locale].default | `de` |
| `{{vault}}` | frontmatter.optional[Vault].default | `Privat` |
| `{{vault_version}}` | frontmatter.optional[VaultVersion].default | `2` |

Config-sourced tokens exist only if the user has defined them. They resolve to the default value.

### 3. Content Tokens (from action context)

| Token | Source | Required |
|-------|--------|----------|
| `{{title}}` | Suggestion-confirmed title | **Yes** |
| `{{tags}}` | Confirmed tags (list → YAML format) | No |
| `{{aliases}}` | Aliases (list → YAML format) | No |
| `{{summary}}` | Extracted or generated summary | No |
| `{{body}}` | Main content from source item | No |
| `{{up}}` | Parent MOC as wikilink | No |
| `{{related}}` | Related notes as wikilinks | No |

### 4. Metadata Tokens (from processing context)

| Token | Source |
|-------|--------|
| `{{source_path}}` | Original inbox item path |
| `{{source_link}}` | Original item as wikilink |
| `{{classification}}` | Best-fit classification name |
| `{{classification_number}}` | Dewey number (e.g., 2600) |
| `{{profile}}` | Active profile name |

### 5. Custom Tokens (user-defined in vault-config.yaml)

```yaml
templates:
  custom_tokens:
    - name: "project_code"
      source: "frontmatter"
      field: "ProjectCode"
      required: false
    - name: "weekday"
      source: "computed"
      logic: "weekday name in locale"
      required: false
```

Sources:
- `static` — literal value from config
- `frontmatter` — field lookup from source note or context note
- `computed` — mechanical computation (date formatting, string ops)
- `context` — pulled from current action context

## Resolution Rules

### Required vs Optional

- **Required tokens** (`uuid`, `datestamp`, `title`): rendering fails if unresolvable
- **Optional tokens**: resolve to empty string if missing

### Tags and List Formatting

Tags are passed to the renderer as a **comma-separated string** (not a list).
This allows templates to embed `{{tags}}` inside inline YAML arrays:

```yaml
tags: [type/note/normal, status/fleeting/🎗️, {{tags}}]
```

Renders to:

```yaml
tags: [type/note/normal, status/fleeting/🎗️, topic/travel/japan, topic/hokkaido]
```

**Why comma-separated?** Tomo templates use inline YAML arrays `[...]` because
the template also contains Templater syntax and static base tags. If `{{tags}}`
produced YAML block format (`\n  - tag`), it would break the inline array.

For standalone list tokens (aliases), the same rule applies — pass as
comma-separated string if the template uses inline array syntax.

### Code Block Protection

Tokens inside fenced code blocks (``` ``` ```) are NOT resolved. This prevents
breaking code examples that happen to contain `{{` patterns.

### Templater Coexistence

Templates may contain both `{{tomo_tokens}}` and Templater syntax:
- `<% expression %>` — single line output
- `<%* statement %>` — multi-line JavaScript (opaque block)
- `<% tp.* %>` — Templater API calls
- `-%>` — whitespace-trimming close

**Tomo resolves `{{tokens}}` first. Templater syntax passes through unchanged.**

The instruction set should note when a rendered file contains Templater syntax:
"This file contains Templater syntax. After moving to target, run `Templater: Replace Templates in Active File`."

### Escaping

`\{\{` in template → literal `{{` in output (not treated as a token).

### Empty Token Behavior

| Token Status | Behavior |
|-------------|----------|
| Required, unresolvable | Error — rendering fails |
| Optional, unresolvable | Replace with empty string |
| Optional, value is empty string | Keep empty string (intentional) |
| Optional, value is null | Replace with empty string |

## Rendering Pipeline

1. Read template content
2. Identify code blocks (mark regions to skip)
3. Identify Templater blocks (mark regions to skip)
4. Resolve `\{\{` escapes
5. Resolve generated tokens
6. Resolve config-sourced tokens
7. Resolve content tokens
8. Resolve metadata tokens
9. Resolve custom tokens
10. Check all required tokens resolved (error if not)
11. Replace remaining `{{unresolved_optional}}` with empty string
12. Validate rendered frontmatter (YAML parses, required fields present)
13. Output rendered content

## Fallback Template

If a configured template file doesn't exist (not found via Kado):

```markdown
---
title: {{title}}
tags:{{tags}}
---
# [[{{title}}]]

{{body}}
```

Warn: "Template `<name>` not found. Using minimal fallback."

## Script Usage

```bash
python3 scripts/token-render.py \
  --template template.md \
  --tokens-json '{"title":"My Note","tags":["type/note"],"body":"Content"}' \
  --config config/vault-config.yaml
```

Or via stdin:
```bash
cat template.md | python3 scripts/token-render.py --tokens-json '{...}'
```
