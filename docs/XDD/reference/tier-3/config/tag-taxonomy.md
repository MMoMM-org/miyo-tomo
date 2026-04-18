# Tier 3: Tag Taxonomy

> Parent: [User Config](../../tier-2/components/user-config.md)
> Status: Implemented

---

## 1. Purpose

Define how Tomo understands and assigns tags. The taxonomy describes the user's tag hierarchy (which prefixes exist, which values are common under each) so Tomo can propose tags that match the user's conventions.

## 2. Schema Location

Lives under `tags:` in `vault-config.yaml`:

```yaml
tags:
  prefixes:
    <prefix_name>:
      description: string      # What this prefix is for
      known_values: string[]   # Values commonly observed under this prefix
      wildcard: boolean        # Whether sub-paths beyond known values are allowed
      required_for:
        - concept_name         # Concepts that must have this prefix set
```

## 3. Prefix Model

Tomo uses **hierarchical slash-separated tags**. A prefix is the top-level namespace; known values are the next segment.

Example: `type/note/normal`
- Prefix: `type`
- First segment: `note`
- Second segment: `normal`

The taxonomy describes **prefix-level categories** and tracks **observed values** at any depth.

## 4. Example: MiYo Taxonomy

```yaml
tags:
  prefixes:
    type:
      description: "Note type (structural)"
      known_values:
        - "note/normal"
        - "others/moc"
      wildcard: false
      required_for: [atomic_note, map_note]

    status:
      description: "Note status in the thinking process"
      known_values:
        - "inwork/💭"
        - "done/✅"
      wildcard: true            # Other statuses may exist
      required_for: []          # Not required

    topic:
      description: "Topic area (free-form, hierarchical)"
      known_values:
        - "knowledge/lyt"
        - "knowledge/miyo"
        - "knowledge/personal"
        - "applied/ai"
        - "applied/docker"
        - "applied/tools"
      wildcard: true            # User adds new topics freely
      required_for: []

    projects:
      description: "Project association"
      known_values:
        - "60-00"               # Project codes
        - "60-00/60-06"
      wildcard: true
      required_for: [project]
```

## 5. Tag Assignment Logic

When Tomo proposes tags for a new or modified note, it walks the taxonomy:

1. **Required prefixes first** — for each prefix with `required_for` matching the note's concept, find a value
2. **Topic detection** — classify the note content against `topic` prefix known values; propose the best match(es)
3. **Status** — default to `inwork` (or skip if `required_for: []` and not explicitly set)
4. **Project detection** — if the note is clearly project-related, propose a `projects/<code>` tag

Proposed tags always land in the suggestions document (Pass 1) with alternatives:

```markdown
### Tags for "oh-my-zsh — Installation & Configuration"
- Required:
  - type/note/normal ✓ (only option, type=atomic_note)
- Suggested topic: topic/applied/tools (confidence 85%)
- Alternatives: topic/applied/shell (60%), topic/knowledge/miyo (20%)
- Status: status/inwork/💭 (default)
```

## 6. Detection (during /explore-vault)

vault-explorer scans all tags in the vault:
1. `kado-search` with `listTags` operation → get all unique tags
2. Group by prefix (first `/` segment)
3. For each prefix, collect known_values (second-level segments or full paths)
4. Count usage per value
5. Heuristically detect:
   - **Required prefixes** — prefixes present on >95% of notes of certain types
   - **Wildcard usage** — if many unique values under a prefix, mark `wildcard: true`
   - **Static taxonomies** — if few values repeated heavily, mark `wildcard: false`

Proposed taxonomy is shown to the user for confirmation.

## 7. Wildcard Behavior

**`wildcard: false`:**
- Tomo only proposes tags from the `known_values` list for this prefix
- If a new value is needed, Tomo flags it and asks the user to approve adding it to `known_values`
- Example: `type` — Tomo won't invent new note types

**`wildcard: true`:**
- Tomo may propose new values under this prefix based on content
- New values get added to `known_values` opportunistically (via `/explore-vault` or explicit user action)
- Example: `topic` — Tomo can suggest `topic/applied/new-thing` if the content warrants it

## 8. Emoji in Tags

MiYo uses emojis in tag paths (`status/inwork/💭`). Support rules:
- **Reading:** emojis are valid Unicode characters in tags; Kado preserves them
- **Writing:** Tomo passes emoji tags through unchanged
- **Matching:** tag comparisons are literal string matches (emoji-aware)
- **Display in proposals:** rendered as-is in markdown

## 9. Tag Normalization

Before writing tags:
1. Remove leading `#` if present (frontmatter tags don't use `#`; inline tags do)
2. Trim whitespace
3. Preserve case (tags are case-sensitive in Obsidian)
4. Validate no spaces inside a tag (Obsidian disallows)
5. Validate no special chars except `/`, `-`, `_`, and emoji

## 10. Edge Cases

**User manually tags a note with something outside the taxonomy:**
- `/explore-vault` discovers it on next run
- If `wildcard: true` for that prefix → add to `known_values` automatically
- If `wildcard: false` → flag as "taxonomy violation", ask user to either add to taxonomy or fix the note

**Tomo wants to add a tag but no prefix fits:**
- Don't invent new prefixes silently
- Put the question in the suggestions document: "Should this have a new tag category? Proposed: `<name>`"
- User approves → new prefix added to taxonomy via config update

**Duplicate tags at different depths (`topic/ai` and `topic/applied/ai`):**
- Warn as potential duplication during `/explore-vault`
- User decides which is canonical
