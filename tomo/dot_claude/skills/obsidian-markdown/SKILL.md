---
name: obsidian-markdown
description: "Reference for Obsidian markdown syntax — callouts, wikilinks, embeds, dataview inline-fields. Lazy-loaded by moc-architect agent."
user-invocable: false
model: sonnet
effort: low
---
# Obsidian Markdown
# version: 0.1.0

Reference for Obsidian-flavoured markdown syntax. Lazy-loaded as a side-effect via agent frontmatter `skills:` references — not user-invocable.

## Callouts

Block-level admonitions. Syntax: a blockquote whose first line is `> [!type]` followed by an optional title; subsequent lines start with `> ` and form the callout body.

**Basic forms:**
```markdown
> [!note]
> Plain note callout, default title is "Note".

> [!warning] Custom Title
> Warning callout with an explicit title.

> [!info]
> Info callout. Lines stay inside the callout as long as they
> are prefixed with `> `.
```

**Foldable state** (Obsidian-only suffixes on the type):
- `[!note]+` — present and expanded
- `[!note]-` — present and collapsed
- `[!note]`  — not foldable

**Common types:** `note`, `info`, `tip`, `success`, `question`, `warning`, `failure`, `danger`, `bug`, `example`, `quote`, `abstract`, `summary`, `todo`. Custom types are allowed; unknown types render with the default `note` styling.

**Boundaries:** a callout starts at `> [!type]` and ends at the first non-`> `-prefixed line (or end of file).

**Nesting:** callouts can nest by stacking blockquote prefixes (`>> [!note]` inside an outer `> [!info]`).

## Wikilinks

Internal links between vault notes. Resolution is by note title (filename without `.md`), not by path.

**Forms:**
- `[[stem]]` — link by stem; rendered text is `stem`
- `[[stem|alias]]` — link by stem; rendered text is `alias`
- `[[#heading]]` — link to a heading inside the current note
- `[[stem#heading]]` — link to a heading inside another note
- `[[stem#^block-id]]` — link to a block reference inside another note
- `[[stem#heading|alias]]` — heading link with display alias

**Stem rules:** the stem is the filename without the `.md` extension. Spaces are allowed (`[[My Note]]`). Path-style links (`[[folder/stem]]`) are accepted; Obsidian resolves them when stems are ambiguous.

**Forbidden characters in stems:** `\ / : * ? " < > |` — links containing these will not resolve. Sanitise external-source filenames before deriving wikilinks.

## Embeds

Wikilink prefixed with `!` — inlines the target's rendered content rather than linking to it.

**Forms:**
- `![[stem]]` — embed an entire note
- `![[stem#heading]]` — embed a single section under that heading
- `![[stem#^block-id]]` — embed a single block
- `![[image.png]]` — embed an image attachment
- `![[file.pdf]]` — embed a PDF
- `![[stem|alias]]` — embed with an alias (rarely used; mostly affects fallback rendering)

**Resolution:** identical to wikilinks. The leading `!` is the only syntactic difference.

**Use sparingly:** embeds re-render the target in place; a vault with deep embed chains can become slow to open.

## Dataview Inline Fields

Plugin-managed key/value metadata that lives inside note bodies (not in frontmatter). Recognised by the Dataview community plugin and read by Tomo when configured as a frontmatter alternative.

**Forms:**
- `field:: value` — visible inline field; the literal `field::` and value both render in reading view
- `(field:: value)` — bracketed/hidden inline field; only the value renders, the key is suppressed in reading view

**Placement:** anywhere in the note body. Each non-empty value on its own conceptual unit (typically one per line for the visible form).

**Examples:**
```markdown
status:: active
due:: 2026-05-15
priority:: high

The project is (status:: active) and due (due:: 2026-05-15).
```

**Multi-value fields:** Dataview treats comma-separated values as a list (`tags:: alpha, beta, gamma`).

**Wikilink values:** inline-field values may themselves be wikilinks (`up:: [[Parent MOC]]`) — this is the canonical pattern for relationship markers stored as inline fields.

**Position discipline:** when writing inline fields programmatically, place them at a deterministic position (top of body, end of frontmatter section, or inside a designated callout) per `vault-config.yaml` `relationships.<type>.position`. Never sprinkle them at random locations — readers cannot find them reliably.
