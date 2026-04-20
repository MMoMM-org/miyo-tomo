---
name: obsidian-fields
description: Frontmatter field handling, relationship marker parsing, callout classification, and tag taxonomy resolution for Obsidian vaults. Use when reading or writing note metadata, detecting field patterns during vault exploration, or resolving parent/peer relationships.
user-invocable: false
---
# Obsidian Fields
# version: 0.1.0

Knowledge patterns for handling Obsidian frontmatter, relationships, callouts, and tags.

## Frontmatter Handling

Frontmatter is described in `vault-config.yaml` under `frontmatter:` with `required` and `optional` field lists and a `strict` flag.

**Field definition properties:**
- `key` — the YAML key name in the note (e.g., `UUID`, `title`, `tags`)
- `token` — template token that resolves the value (e.g., `uuid`, `title`, `datestamp`)
- `format` — expected format for generated values (e.g., `YYYY-MM-DD`, `YYYYMMDDHHmmss`)
- `type` — expected YAML type: `string`, `number`, `boolean`, `list`, `date`
- `default` — fallback for optional fields when the token cannot resolve

**Required fields:**
- If a required token cannot resolve → rendering fails, error in instruction set
- Tomo never writes a note that would break the required schema
- Empty value (`title: ""`) counts as missing when `strict: true`

**Optional fields:**
- Token resolves → use it
- Token fails + default set → use default
- Token fails + no default → omit the field entirely

**Detection during `/explore-vault`:**
- Sample 50 notes (configurable)
- Fields in >90% of notes → propose as `required`
- Fields in 10-90% → propose as `optional`
- Fields in <10% → mention but don't add
- Format and type inferred from observed values

**Format grammar (Moment.js subset):**
- `YYYY` — 4-digit year, `MM` — 2-digit month, `DD` — 2-digit day
- `HH` — 24-hour hour, `mm` — minute, `ss` — second
- Example: `YYYY-MM-DD HH:mm` → `2026-04-07 14:30`
- UUID: `YYYYMMDDHHmmss` → `20260407143045`

**Validation at render time:**
1. All required keys are present
2. Types match declared types (lenient — string is ok where text is expected)
3. Formats match for generated fields
4. The YAML parses without error

**Unknown fields:** Never remove or modify fields not in the schema. Schema constrains what Tomo writes, not what it tolerates. Pass through all unknown fields unchanged.

**Frontmatter position:** Obsidian requires frontmatter at position 0. If content appears before the `---` fence, treat the note as having no frontmatter and warn.

**YAML resilience:** Pre-process potentially malformed YAML before parsing: normalize tabs to spaces, fix common indentation errors, quote bare strings containing `:`, auto-close unclosed sequences. If the fixer fails, pass broken YAML + error to a short LLM prompt: "Fix this YAML so it parses correctly. Only fix syntax, don't change values."

## Relationship Markers

Relationships between notes are described in `vault-config.yaml` under `relationships:` with `parent` and `peer` relationship types (and optionally custom types).

**Relationship properties:**
- `marker` — prefix identifying this relationship when reading (e.g., `up::`, `top:`, `parent`)
- `format` — template for writing, must contain `{{link}}` (e.g., `up:: {{link}}`)
- `position` — where to place it: `connect_callout`, `frontmatter`, `top_of_body`, `end_of_frontmatter`
- `location_type` — `inline` (body pattern match) or `frontmatter` (YAML key)
- `multi` — whether multiple links are allowed (default: true for both parent and peer)
- `separator` — how multiple links are joined (default: `, `)

**Reading relationships:**
- `location_type: frontmatter` → parse YAML, look up the `marker` key
- `location_type: inline` → pattern match `^<marker>\s*(.+)$` in note body
- Extract all `[[...]]` wikilinks from the matched value

**Writing relationships by position:**
- `connect_callout` — inside a callout matching the `editable.connect` callout type; create the callout if it doesn't exist
- `frontmatter` — as a YAML key (string or list based on `multi`)
- `top_of_body` — first non-heading line after the frontmatter `---` fence
- `end_of_frontmatter` — last line inside the YAML block before closing `---`

**Multiple parents:** Allowed when `multi: true`. Most LYT vaults allow a note to belong to multiple MOCs.

**Self-links:** Invalid — skip and warn.

**Broken relationship links:** Treat as orphan candidates. Do not auto-remove.

**`connect_callout` requirement:** The referenced callout must be listed as `editable` in vault-config. Never write relationship content into a protected callout.

## Callout Classification

Callout tracking is optional. `callouts.enabled: false` → Tomo ignores all callouts and treats note content as flat markdown.

When `callouts.enabled: true`, every callout (`> [!name]`) is classified as one of three categories:

**Editable:** Tomo may read, insert, or update content.
**Protected:** Read-only. Never write inside (typically wraps DataviewJS/Dataview/plugin code — content is rendered at read time and would be overwritten or broken).
**Ignore:** Skip entirely — decorative or visual, no semantic value.

**Default for any unlisted callout:** `protected` (safe default — don't touch what you don't understand).

**Detection during `/explore-vault`:**
- Regex match `^> \[!(\w+)\]`
- Sample 10 occurrences per callout name
- Callout contains a code block → propose `protected`
- Callout contains only prose and wikilinks → propose `editable`
- Callout is empty → propose `editable`
- User confirms classifications

**Writing inside an editable callout:**
1. Locate the callout: scan for `> [!<name>]`
2. Find boundaries: all consecutive lines starting with `> `
3. Append or replace within the callout, preserving `> ` line prefixes
4. Preserve foldable state: keep `[!name]-` (collapsed) or `[!name]+` (expanded) suffix

**Creating an editable callout (when it doesn't exist):**
1. Insert at the target position (based on relationship config or template)
2. Write callout header: `> [!<name>] <optional title>`
3. Add content lines with `> ` prefix
4. Ensure blank line separation above and below

**Callouts with mixed content (prose + code block):** Treat as protected — cannot safely edit prose when code lives in the same callout.

**Nested callouts:** Write at the outermost callout depth unless the action specifies a nested target.

## Tag Taxonomy

The taxonomy lives in `vault-config.yaml` under `tags.prefixes`. Each prefix entry has:
- `description` — what this prefix category is for
- `known_values` — observed values under this prefix
- `wildcard` — whether new values beyond known_values are allowed
- `required_for` — concept types that must have this prefix set

**Tag structure:** hierarchical slash-separated paths. Example: `type/note/normal`
- Prefix: `type`
- First segment: `note`
- Second segment: `normal`

**Wildcard: false** — Tomo only proposes tags from `known_values`. New values require explicit user approval before being added.

**Wildcard: true** — Tomo may propose new values under this prefix based on content analysis. New values added opportunistically to `known_values`.

**Tag assignment logic for proposals:**
1. Required prefixes first — for each prefix with `required_for` matching the note's concept type, find a value
2. Topic detection — classify note content against `topic` prefix known values; propose best match(es) with confidence scores
3. Status — default to `inwork` (or skip if not required and not explicitly set)
4. Project detection — if clearly project-related, propose `projects/<code>` tag

**Emoji in tags:** Valid Unicode characters, passed through unchanged. Comparisons are literal string matches.

**Tag normalization before writing:**
1. Remove leading `#` (frontmatter tags don't use `#`)
2. Trim whitespace
3. Preserve case (tags are case-sensitive in Obsidian)
4. Validate no spaces inside a tag
5. Validate no special chars except `/`, `-`, `_`, and emoji

**Unknown tags (outside taxonomy):**
- `wildcard: true` prefix → add to `known_values` automatically
- `wildcard: false` prefix → flag as taxonomy violation, ask user to add to taxonomy or fix the note

**No fitting prefix:** Don't invent new prefixes silently. Surface the question in the suggestions document. User approves before a new prefix is added.

**Duplicate tags at different depths** (e.g., `topic/ai` and `topic/applied/ai`): Flag during `/explore-vault`, user decides canonical form.

**Detection during `/explore-vault`:**
- List all unique tags via Kado `listTags`
- Group by prefix (first `/` segment)
- Count usage per value
- `required_for` detection: prefixes present on >95% of notes of certain types
- `wildcard` detection: many unique values under a prefix → `wildcard: true`; few values repeated heavily → `wildcard: false`
