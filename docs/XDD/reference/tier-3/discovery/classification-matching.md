# Tier 3: Classification Matching

> Parent: [Discovery Cache](../../tier-2/components/discovery-cache.md)
> Status: Draft
> Related: [MOC Matching](../lyt-moc/moc-matching.md) · [Framework Profiles](../../tier-2/components/framework-profiles.md)

---

## 1. Purpose

Define how Tomo assigns a classification category (e.g., Dewey 2000-2900) to a note based on its content. This is a **fallback mechanism** when no specific MOC match is found — the note gets linked to the classification-level map.

## 2. When Classification Runs

Classification happens during inbox analysis (Step 8 in `inbox-analysis.md`) as a parallel track to MOC matching:

```
MOC matching finds a specific MOC → use that (preferred, more specific)
MOC matching finds nothing → fall back to classification matching
Classification matching finds a category → propose classification-level link
Neither matches → note is unclassified
```

Classification results are always included in the suggestions document as context, even when a specific MOC match exists — so the user can see which broad category the note falls under.

## 3. Algorithm

### Input

- Note topics (extracted by inbox-analyst): list of keywords
- Profile classification categories: `classification.categories[N].keywords[]`
- Discovery cache classification data: `classifications[N].top_keywords[]` (enriched from vault)

### Matching

```
For each classification category:
  score = 0
  
  For each note topic:
    If topic IN category.keywords (profile seed) → score += 2
    If topic IN category.top_keywords (cache enriched) → score += 1
    If topic is substring of any keyword → score += 0.5
  
  Normalize: confidence = score / (max_possible_score)
  
Sort categories by confidence descending
Return top 3 with confidence > threshold (default: 0.2)
```

### Scoring Weights

| Match type | Points | Rationale |
|------------|--------|-----------|
| Exact match against profile keyword | 2 | Profile keywords are curated, high signal |
| Exact match against cache keyword | 1 | Cache keywords are discovered, medium signal |
| Substring match | 0.5 | Partial match, low confidence |

### Threshold

- **Default:** 0.2 (at least one strong keyword match)
- **Configurable** in vault-config (future): `classification.confidence_threshold`
- Below threshold → "unclassified" (no classification proposed)

## 4. Example

Note topics: `[oh-my-zsh, zsh, shell, terminal, installation, mac]`

| Category | Profile keywords | Matches | Score | Confidence |
|----------|-----------------|---------|-------|------------|
| 2600 Applied Sciences | `[coding, software, AI, docker, tools, engineering]` | `shell` substring of... no. But cache has `[shell, terminal, cli]` | shell(1) + terminal(1) = 2 | 0.33 |
| 2100 Personal Management | `[habits, productivity, goals, routines]` | none | 0 | 0.0 |
| 2000 Knowledge Management | `[PKM, notes, learning]` | none | 0 | 0.0 |

Result: `2600 Applied Sciences` at 33% confidence → proposed as fallback classification.

## 5. Keyword Enrichment

Profile keywords are the **seed set**. The discovery cache enriches them:

1. During `/explore-vault`, vault-explorer reads notes in each classification map
2. Extracts common topics from linked notes
3. Stores as `classifications[N].top_keywords` in cache
4. These enriched keywords participate in matching (at lower weight than profile keywords)

This means classification accuracy improves over time as the vault grows and `/explore-vault` discovers more content.

## 6. Multi-Category Notes

A note may match multiple categories. This is expected and handled:

- All matching categories (above threshold) are returned, ranked by confidence
- The **top category** is the primary suggestion
- Others are listed as alternatives in the suggestions document
- The user picks the right one (or accepts the primary)

## 7. Unclassified Notes

When no category matches above threshold:

- The note is tagged as unclassified in the analysis output
- In the suggestions document: "No classification match found. Suggested: leave unclassified, or manually pick a category."
- Unclassified notes accumulate and may trigger Mental Squeeze Point detection if they share topics

## 8. Profiles Without Classification

If the profile has `classification.enabled: false` (e.g., PARA):
- Classification matching is skipped entirely
- MOC matching is the only linking mechanism
- No classification-level maps exist in the vault
- This is normal and expected — not an error
