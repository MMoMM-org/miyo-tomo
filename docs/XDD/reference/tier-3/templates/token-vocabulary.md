# Tier 3: Token Vocabulary

> Parent: [Template System](../../tier-2/components/template-system.md)
> Status: Draft
> Related: [Frontmatter Schema](../config/frontmatter-schema.md) · [Instruction Set Generation](../inbox/instruction-set-generation.md)

---

## 1. Purpose

Define the full set of built-in `{{token}}` placeholders Tomo can resolve, plus the mechanism for user-defined custom tokens. Tokens are how templates get their content — the template defines the structure, tokens fill in the values.

### Universal vs Profile-Specific Tokens

Not all built-in tokens apply to every vault. Tokens like `{{vault}}` and `{{vault_version}}` are MiYo-specific — most LYT or PARA users won't have these frontmatter fields.

**Design rule:** Config-sourced tokens are **derived from the user's frontmatter schema**, not hardcoded per profile. If the user has a `Vault` field in their `frontmatter.optional` config, the `{{vault}}` token exists. If they don't, it doesn't. No token is forced onto users who don't need it.

This means:
- **Generated tokens** (uuid, datestamp, updated) → universal, always available
- **Content tokens** (title, tags, body, up, related) → universal, always available
- **Config-sourced tokens** → derived from each user's frontmatter schema (only what they configured)
- **Metadata tokens** (source_path, classification, profile) → universal, always available

## 2. Token Syntax

- **Format:** `{{token_name}}`
- **Case:** lowercase, underscores for multi-word (`vault_version`, not `vaultVersion`)
- **Resolution:** simple string replacement — no expressions, no conditionals, no loops
- **Nesting:** NOT supported — `{{tokens}}` inside resolved values are not re-processed
- **Escaping:** literal `{{` in templates that should NOT be resolved → `\{\{` (or wrap in a code block)

## 3. Built-in Tokens

### Generated (computed at render time)

| Token | Output | Example |
|-------|--------|---------|
| `{{uuid}}` | Timestamp-based unique ID | `20260409143045` |
| `{{datestamp}}` | Creation date | `2026-04-09` |
| `{{updated}}` | Last modified timestamp | `2026-04-09 14:30` |
| `{{date_iso}}` | ISO 8601 full timestamp | `2026-04-09T14:30:45Z` |

Format is taken from the frontmatter schema's `format` field for the corresponding key. If no format specified, defaults above apply.

### Config-Sourced (derived from user's frontmatter schema)

These tokens are **auto-generated from the user's frontmatter config** — one token per optional field that has a `default` value. They are NOT hardcoded per profile.

**MiYo example** (these exist because MiYo's frontmatter schema defines them):

| Token | Source | Example |
|-------|--------|---------|
| `{{locale}}` | `frontmatter.optional[locale].default` | `de` |
| `{{vault}}` | `frontmatter.optional[Vault].default` | `Privat` |
| `{{vault_version}}` | `frontmatter.optional[VaultVersion].default` | `2` |

**LYT example** (different fields, different tokens):

| Token | Source | Example |
|-------|--------|---------|
| `{{rank}}` | `frontmatter.optional[rank].default` | `0` |

A user without `Vault` in their frontmatter schema simply has no `{{vault}}` token. Templates that reference `{{vault}}` resolve to empty string (optional token behavior).

### Content Tokens (from the action context)

| Token | Source | Example |
|-------|--------|---------|
| `{{title}}` | Suggested note title from inbox analysis | `oh-my-zsh — Installation & Configuration` |
| `{{tags}}` | Assigned tags, YAML list format | `\n  - type/note/normal\n  - topic/applied/tools` |
| `{{aliases}}` | Detected aliases, YAML list format | `\n  - oh-my-zsh` |
| `{{summary}}` | Generated one-line summary | `Shell configuration tool installation guide` |
| `{{body}}` | Main note content | Multi-line markdown |
| `{{up}}` | Parent link(s) as wikilink(s) | `[[Shell & Terminal (MOC)]]` |
| `{{related}}` | Peer link(s) as wikilink(s) | `[[zsh Aliases]], [[iTerm Config]]` |

### Metadata Tokens

| Token | Source | Example |
|-------|--------|---------|
| `{{source_path}}` | Path to the original inbox item | `+/2026-04-09_1430_oh-my-zsh.md` |
| `{{source_link}}` | Wikilink to the original inbox item | `[[+/2026-04-09_1430_oh-my-zsh]]` |
| `{{classification}}` | Classification category name | `Applied Sciences` |
| `{{classification_number}}` | Classification category number | `2600` |
| `{{profile}}` | Active profile name | `miyo` |

## 4. Required vs Optional Tokens

| Category | Behavior if unresolvable |
|----------|------------------------|
| **Required:** `{{uuid}}`, `{{datestamp}}`, `{{title}}` | Render fails — error reported in instruction set. These must always resolve. |
| **Optional:** all others | Resolve to empty string. No error. |

Required tokens are guaranteed resolvable because they're either generated (uuid, datestamp) or come from user-confirmed suggestions (title).

## 5. User-Defined Custom Tokens

Users can declare custom tokens in vault-config.yaml:

```yaml
templates:
  custom_tokens:
    - name: "project_code"
      description: "The project code from the parent project note"
      source: "frontmatter"
      field: "ProjectCode"
      from: "parent"           # resolve from the parent note's frontmatter
      required: false

    - name: "weekday"
      description: "Weekday name in the vault's locale"
      source: "computed"
      logic: "weekday of {{datestamp}} in locale {{locale}}"
      required: false

    - name: "banner_image"
      description: "Default banner image for this note type"
      source: "static"
      value: "X/900 Support/970 Media/Banner/openBooks.jpg"
      required: false

    - name: "moc_link"
      description: "Primary MOC wikilink for this note"
      source: "context"
      logic: "the resolved primary MOC match from suggestions"
      required: false
```

### Custom Token Sources

| Source | How it resolves | LLM needed? |
|--------|----------------|-------------|
| `static` | Fixed value from config | No |
| `frontmatter` | Read a field from another note's frontmatter (specified by `from` + `field`) | No |
| `computed` | Derive from other token values using a `logic` description | Maybe (if logic is complex) |
| `context` | Pull from the current action's analysis context | No |

For `computed` tokens with simple logic (date formatting, string concatenation), Tomo resolves mechanically. For complex `logic` descriptions, Tomo uses a short LLM call.

## 6. Token Resolution Order

When rendering a template:

```
1. Resolve generated tokens (uuid, datestamp, updated, date_iso)
2. Resolve config-sourced tokens (locale, vault, vault_version)
3. Resolve metadata tokens (source_path, classification, profile)
4. Resolve content tokens (title, tags, aliases, summary, up, related, body)
5. Resolve custom tokens (in order declared in config)
6. Validate: all required tokens resolved? If not → error
7. Final pass: replace remaining {{unresolved}} with empty string (optional tokens)
```

**Step 5 can reference other tokens** — but only tokens resolved in steps 1-4. No circular references. If a custom token's `logic` references another custom token, resolution order in config determines which is available.

## 7. YAML List Formatting

Tokens that produce lists (`{{tags}}`, `{{aliases}}`) must output valid YAML when placed in frontmatter. The format is:

```yaml
tags:
  - type/note/normal
  - topic/applied/tools
```

The token resolves to the indented list portion (without the key):
```
{{tags}} → "\n  - type/note/normal\n  - topic/applied/tools"
```

This means the template should look like:
```yaml
tags:{{tags}}
```

NOT:
```yaml
tags:
{{tags}}
```

The leading newline in the token value handles the line break.

## 8. Edge Cases

**Token name collision (built-in vs custom):** Custom tokens cannot use built-in token names. Validation at config load rejects duplicates.

**Template contains `{{token}}` in a code block:** Code blocks (fenced with ``` ) are NOT processed — tokens inside them are left as-is. This prevents breaking code examples in templates.

**Empty body token:** If `{{body}}` resolves to empty string (inbox item had no meaningful content), the rendered note has an empty body section. That's OK — user can fill it in.

**Token produces invalid YAML:** If a resolved token value contains YAML-special characters (`:`, `#`, `[`, etc.) and ends up in frontmatter, the YAML fixer (see [Frontmatter Schema §1](../config/frontmatter-schema.md)) handles quoting. Token resolution itself does NOT add quotes — that's the YAML layer's job.

## 9. Token Documentation for Users

When the setup wizard runs and templates are discussed, Tomo should generate a **token reference** for the user showing:
- All available tokens (built-in + custom)
- What each resolves to
- Which are required vs optional
- Example output

This reference helps the user design their `t_*_tomo` templates.
