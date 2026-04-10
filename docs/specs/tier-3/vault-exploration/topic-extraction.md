# Tier 3: Topic Extraction

> Parent: [Vault Exploration](../../tier-2/workflows/vault-exploration.md)
> Status: Draft
> Related: [MOC Indexing](../discovery/moc-indexing.md) · [MOC Matching](../lyt-moc/moc-matching.md)

---

## 1. Purpose

Define how vault-explorer and inbox-analyst extract topic keywords from note content. Topics are the primary signal for MOC matching, classification, and cluster detection.

## 2. Two Contexts

Topic extraction runs in two contexts with different constraints:

| Context | Agent | Input | Budget |
|---------|-------|-------|--------|
| **Vault exploration** | vault-explorer | Full MOC content (via kado-read) | Slow is OK — runs once per /explore-vault |
| **Inbox analysis** | inbox-analyst | Inbox item content (short) | Must be fast — runs per item per /inbox |

The extraction logic is the same; only the input size and performance expectations differ.

## 3. Extraction Methods

Topics are extracted using multiple methods, combined:

### Method 1: Title Analysis

The note title itself is a strong topic signal:

```
"Systems Thinking (MOC)" → topics: [systems, thinking, systems thinking]
"oh-my-zsh — Installation & Configuration" → topics: [oh-my-zsh, installation, configuration]
```

Rules:
- Strip common suffixes: `(MOC)`, `(Thought)`, `(Definition)`
- Split on ` — `, ` - `, `: ` delimiters
- Each segment becomes a topic
- Multi-word segments also yield individual words as topics

### Method 2: H2 Section Headings

Each H2 heading in a note indicates a sub-topic:

```
"## Key Concepts" → topic: [concepts]
"## Tools" → topic: [tools]
"## Shell & Terminal" → topic: [shell, terminal]
```

Rules:
- H2 headings only (H3+ are too granular)
- Strip markdown formatting (`**`, `*`, `[[`, etc.)
- Skip boilerplate headings: "Overview", "Related", "Action Items", "Recent Updates"
- Skip empty headings

### Method 3: Linked Note Titles

Notes linked FROM the MOC provide context about what the MOC covers:

```
MOC contains: [[Feedback Loops]], [[Emergence]], [[Leverage Points]]
→ topics: [feedback loops, emergence, leverage points]
```

Rules:
- Extract all `[[wikilink]]` targets
- Use the display text if aliased: `[[Long Title|Short]]` → "Short"
- Limit to first 20 unique links (diminishing returns beyond that)
- Skip links to non-existent notes (dead links)

### Method 4: Content Keywords (LLM-Assisted)

For richer extraction, use a short LLM prompt:

```
Given this note content (first 500 words), extract 5-10 topic keywords
that describe what this note is about. Return only the keywords, comma-separated.
```

Rules:
- Only used for MOCs during vault exploration (not for inbox items — too slow per-item)
- Fallback if LLM unavailable: skip this method, use methods 1-3 only
- Keywords are lowercased and deduplicated against existing topics

### Method 5: Tag-Based Topics

Tags in the note's frontmatter contain topic signals:

```
tags: [topic/knowledge/lyt, topic/applied/ai]
→ topics: [lyt, ai, knowledge, applied]
```

Rules:
- Extract the leaf segment of hierarchical tags (last `/` segment)
- Also extract the second-to-last segment as broader context
- Skip structural tags (type/, status/) — they don't indicate topics

## 4. Topic Normalization

All extracted topics go through normalization:

1. **Lowercase**: "Systems Thinking" → "systems thinking"
2. **Deduplicate**: exact string match
3. **Merge near-duplicates**: "system" and "systems" → keep both (both are valid search targets)
4. **Remove stop words**: "the", "a", "and", "of", "in", "to", "for" (unless part of a proper name)
5. **Max topics per note**: 30 (after dedup). Beyond that, diminishing returns.

## 5. Output

Per note, the extracted topics are a flat keyword list:

```yaml
topics: [systems, thinking, systems thinking, feedback loops, emergence,
         complexity, mental models, leverage points, causal loops]
```

Stored in:
- `discovery-cache.yaml → map_notes[].topics` (for MOCs)
- `InboxItemAnalysis.topics.extracted` (for inbox items, in-memory)

## 6. Topic Quality

Not all topics are equally useful. Quality signals:

| Signal | Weight | Rationale |
|--------|--------|-----------|
| From title | High | Title is the most intentional summary |
| From H2 headings | High | Structural choices reflect core sub-topics |
| From linked note titles | Medium | Content coverage indicator |
| From tags | Medium | Explicit user categorization |
| From LLM extraction | Medium | AI-derived, may include noise |
| From content keywords | Low | High volume, lower precision |

MOC matching should weight title and heading topics higher than content keywords. MVP implementation can treat all topics equally — weighting is a post-MVP refinement.

## 7. Inbox Item Specifics

For inbox items (short, often unstructured):

- **Methods used:** 1 (title), 5 (tags if present), and a simplified version of 4 (short LLM prompt)
- **Methods NOT used:** 2 (rarely have H2 sections), 3 (rarely link to other notes)
- **Binary files:** Topics from filename only (split on `-`, `_`, spaces)
- **Very short items (<50 chars):** LLM extraction skipped, title-only

## 8. Performance

| Context | Target | Constraint |
|---------|--------|------------|
| MOC extraction (vault-explorer) | <2s per MOC | LLM call allowed (one per MOC) |
| Inbox item extraction (inbox-analyst) | <0.5s per item | LLM call allowed (short prompt) |
| Binary file extraction | <0.1s per file | Filename only, no LLM |

## 9. Edge Cases

**MOC with no meaningful content** (only boilerplate template): Extract topics from title + tags only. Log as "thin MOC — consider adding content."

**Non-English content:** MiYo vault has `locale: de`. Topics should be extracted in the content's language. LLM prompts should specify "extract topics in the content's language."

**Code snippets in notes:** Code blocks are noise for topic extraction. Strip ``` fenced blocks before extracting content keywords.

**Notes with only embeds (`![[other note]]`):** Embedded content is NOT expanded by Kado — Tomo sees the embed syntax, not the content. Extract the linked note name as a topic.
