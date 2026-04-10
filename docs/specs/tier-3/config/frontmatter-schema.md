# Tier 3: Frontmatter Schema

> Parent: [User Config](../../tier-2/components/user-config.md)
> Status: Draft

---

## 1. Purpose

Define how Tomo describes, validates, and generates frontmatter (YAML properties at the top of notes). The schema tells Tomo which fields must exist, which are optional, and how to populate them when creating new notes.

### Cross-Cutting Concern: YAML Resilience

YAML is error-prone for users — tab/space mixing, wrong indentation, missing quotes around special characters. This affects both:
- **Note frontmatter** (user-edited YAML in vault notes)
- **vault-config.yaml** (Tomo's own configuration)

Tomo must handle malformed YAML gracefully. Two strategies:

| Strategy | When to use | How |
|----------|------------|-----|
| **YAML fixer** | Reading vault-config.yaml and note frontmatter | Pre-process: normalize tabs→spaces, fix common indentation errors, quote bare strings containing `:`, auto-close unclosed sequences. Then parse. |
| **LLM fallback** | When the fixer can't resolve the issue | Pass the broken YAML + error message to a short LLM prompt: "Fix this YAML so it parses correctly. Only fix syntax, don't change values." |

**Reference:** Marcus built a similar YAML comment-preserving configuration parser in Java (MakeMeMod `CommentConfiguration.java`). The pattern applies here — tolerant parsing that preserves user intent.

**Where this lives in implementation:** A shared `yaml-resilient-parser` utility used by both vault-config loading and frontmatter reading. Not a per-spec concern — it's infrastructure. Documented here because frontmatter is the primary surface where users hit YAML issues.

## 2. Schema Location

Lives under `frontmatter:` in `vault-config.yaml`:

```yaml
frontmatter:
  required:
    - { key: string, token: string, format: string | null, type: string | null }
    - ...
  optional:
    - { key: string, token: string, format: string | null, default: any | null }
    - ...
  strict: boolean             # If true: Tomo refuses to write notes missing required fields
                              # If false: Tomo warns but proceeds
```

## 3. Field Definition

Each field entry has:

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `key` | string | yes | The YAML key name as it appears in the note (e.g., `UUID`, `title`, `tags`) |
| `token` | string | yes | The template token that resolves this field (e.g., `uuid`, `title`). See [Token Vocabulary](../templates/token-vocabulary.md) |
| `format` | string | no | Expected format for generated values (e.g., `YYYY-MM-DD` for dates). Only relevant for generated tokens. |
| `type` | string | no | Expected YAML type: `string`, `number`, `boolean`, `list`, `date`. Used for validation. |
| `default` | any | no | Default value for optional fields. Used if the token cannot resolve. |

## 4. Required vs Optional

**Required fields** are non-negotiable. When Tomo renders a template:
- If a required field has no value → rendering fails, error in instruction set
- Tomo never writes a note that would break the required schema
- These must map to tokens that are guaranteed resolvable (e.g., `uuid`, `title`)

**Optional fields** are best-effort. When Tomo renders a template:
- If the token resolves → use the resolved value
- If the token doesn't resolve AND a `default` is set → use the default
- If neither → the field is simply omitted from the rendered note

## 5. Example: MiYo Schema

```yaml
frontmatter:
  strict: true
  required:
    - key: "UUID"
      token: "uuid"
      format: "YYYYMMDDHHmmss"
      type: "string"
    - key: "DateStamp"
      token: "datestamp"
      format: "YYYY-MM-DD"
      type: "date"
    - key: "Updated"
      token: "updated"
      format: "YYYY-MM-DD HH:mm"
      type: "string"
    - key: "title"
      token: "title"
      type: "string"
    - key: "tags"
      token: "tags"
      type: "list"

  optional:
    - key: "locale"
      token: "locale"
      type: "string"
      default: "de"
    - key: "Vault"
      token: "vault"
      type: "string"
      default: "Privat"
    - key: "VaultVersion"
      token: "vault_version"
      type: "string"
      default: "2"
    - key: "Summary"
      token: "summary"
      type: "string"
    - key: "aliases"
      token: "aliases"
      type: "list"
    - key: "banner"
      token: "banner"
      type: "string"
```

## 6. Validation

At session start, Tomo validates the schema itself:
1. Every `required` entry has a valid `token`
2. No duplicate `key` values across required and optional
3. `format` strings are parseable for their token types
4. No optional field uses a token reserved for required-only generation

At render time, Tomo validates the rendered frontmatter:
1. All required keys are present in the output YAML
2. Types match declared types (lenient — e.g., string is ok where text is expected)
3. Formats match for generated fields
4. The YAML parses without error

## 7. Detection (during /explore-vault)

vault-explorer samples N notes (configurable, default 50) and detects frontmatter patterns:
- **Field frequency** — what fraction of notes use each field
- **Format detection** — regex match common formats (dates, UUIDs, numeric)
- **Type detection** — YAML type of values

Suggested schema is presented to the user:
- Fields present in >90% of notes → propose as `required`
- Fields present in 10-90% → propose as `optional`
- Fields present in <10% → mention but don't add
- Format and type are inferred from observed values

User confirms each field before it's added to `vault-config.yaml`.

## 8. Format Grammar

Supported format strings for date/time fields (subset of Moment.js):

| Format | Meaning | Example |
|--------|---------|---------|
| `YYYY` | 4-digit year | `2026` |
| `MM` | 2-digit month | `04` |
| `DD` | 2-digit day | `07` |
| `HH` | 24-hour hour | `14` |
| `mm` | 2-digit minute | `30` |
| `ss` | 2-digit second | `45` |

Example: `YYYY-MM-DD HH:mm` → `2026-04-07 14:30`
UUID format: `YYYYMMDDHHmmss` → `20260407143045`

## 9. Unknown Fields

When Tomo reads a note with frontmatter fields not in the schema:
- **Do not remove them** — preserve all existing fields
- **Do not modify them** — pass-through for any field not touched by the action
- **Log them** (debug level) as "unknown fields observed in `<path>`: `[keys]`"

Schema is additive at read time. The schema constrains what Tomo WRITES, not what it TOLERATES.

## 10. Edge Cases

**Empty vs missing required field:** An empty value (`title: ""`) counts as missing if `strict: true`.

**Field that must be a list with at least one entry:** Not enforceable in the schema directly. Use required + type `list` and let the token generation ensure the list is non-empty.

**Frontmatter that's not at position 0:** Obsidian requires frontmatter at the very top. If a note has content before the `---` fence, Tomo treats it as having no frontmatter. Warn in logs.

**Multiline YAML values:** Supported. Tomo preserves pipe-literal and folded-scalar syntax as-is when reading, emits single-line when writing new values.
