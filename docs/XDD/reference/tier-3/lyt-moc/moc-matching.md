# Tier 3: MOC Matching

> Parent: [LYT/MOC Linking](../../tier-2/workflows/lyt-moc-linking.md)
> Status: Implemented
> Related: [MOC Indexing](../discovery/moc-indexing.md) · [Classification Matching](../discovery/classification-matching.md)

---

## 1. Purpose

Define how Tomo matches an inbox item's topics against the MOC index to find the best MOC(s) to link to. This is the core intelligence for the "which MOC does this note belong to?" question.

## 2. Inputs

| Input | Source |
|-------|--------|
| Item topics | `InboxItemAnalysis.topics.extracted[]` — keywords from the inbox item |
| MOC index | `discovery-cache.yaml → map_notes[]` — each MOC's topics, level, sections |
| Classification matches | `InboxItemAnalysis.classification_matches[]` — fallback categories |

## 3. Algorithm

### Step 1: Topic Overlap Scoring

For each MOC in the cache:

```
overlap_count = count(item_topics ∩ moc_topics)
overlap_ratio = overlap_count / max(len(item_topics), 1)

If overlap_count == 0 → skip this MOC (no match)
```

### Step 2: Depth Bonus

Prefer deeper (more specific) MOCs over shallow (generic) ones:

```
depth_bonus = moc.level * 0.1

# Level 0 (root):           +0.0
# Level 1 (classification): +0.1
# Level 2 (topic MOC):      +0.2
# Level 3 (sub-topic):      +0.3
```

### Step 3: Size Penalty (Optional)

Very large MOCs (many linked notes) are less specific — slight penalty:

```
if moc.linked_notes > 50:
  size_penalty = -0.05
elif moc.linked_notes > 100:
  size_penalty = -0.10
else:
  size_penalty = 0
```

### Step 4: Final Score

```
confidence = overlap_ratio + depth_bonus + size_penalty
confidence = clamp(confidence, 0.0, 1.0)
```

### Step 5: Rank and Return

```
Sort MOCs by confidence descending
Return top 3 with confidence > threshold (default: 0.15)
```

## 4. Example

Item topics: `[oh-my-zsh, zsh, shell, terminal, installation]`

| MOC | Topics | Overlap | Ratio | Level | Depth Bonus | Score |
|-----|--------|---------|-------|-------|-------------|-------|
| Shell & Terminal (MOC) | [shell, terminal, cli, zsh, bash] | 3 | 0.60 | 2 | 0.20 | **0.80** |
| 2600 - Applied Sciences | [coding, software, tools, AI] | 0 | 0.00 | 1 | 0.10 | 0.00 (skip) |
| Dotfiles (MOC) | [dotfiles, config, shell, brew] | 1 | 0.20 | 2 | 0.20 | **0.40** |
| My PKM (MOC) | [PKM, obsidian, notes, knowledge] | 0 | 0.00 | 2 | 0.20 | 0.00 (skip) |

Result: Shell & Terminal (MOC) at 80%, Dotfiles (MOC) at 40%.

## 5. Fallback to Classification

When MOC matching returns NO results above threshold:

1. Use classification matching results (see [Classification Matching](../discovery/classification-matching.md))
2. Propose the classification-level map as the parent link
3. Note in suggestions: "No specific MOC found. Linked to classification level — consider creating a dedicated MOC if more notes in this area accumulate."

When MOC matching returns results AND classification also matches:
- Show both in suggestions — MOC match as primary, classification as context
- This helps the user see the full hierarchy

## 6. Placeholder MOC Awareness

From the cache's `placeholder_mocs` list:

```
If item topics match a placeholder MOC's implied topics:
  Include in suggestions as a special option:
  "This note matches placeholder [[Shell & Terminal (MOC)]] 
   (dead link in [[2600 - Applied Sciences]]). 
   Creating this MOC would resolve the placeholder."
```

This connects new MOC proposals to existing placeholder expectations.

## 7. Cross-Item Matching (Batch Context)

When processing a batch of inbox items, MOC matching can use cross-item context:

- If 3+ items in the same batch match the same MOC → boost confidence for all
- If 3+ items share topics but NO MOC matches → trigger Mental Squeeze Point (see [New MOC Proposal](new-moc-proposal.md))
- Batch context is informational — it doesn't override per-item scoring

## 8. Configuration

| Setting | Location | Default | Description |
|---------|----------|---------|-------------|
| `confidence_threshold` | future vault-config | 0.15 | Minimum score to include a MOC match |
| `max_results` | future vault-config | 3 | Maximum MOC matches to return per item |
| `depth_bonus_weight` | hardcoded | 0.1 per level | How much to prefer deeper MOCs |
| `size_penalty_threshold` | hardcoded | 50 notes | When to start penalizing large MOCs |

MVP: thresholds are hardcoded. Post-MVP: user-configurable in vault-config.

## 9. Degraded Mode (No Cache)

Without a discovery cache:
- Read MOCs on-demand via Kado (see [Staleness Policy](../discovery/staleness-policy.md) §5)
- Topic extraction happens inline (slower)
- Scoring algorithm is the same, just with live data instead of cached

## 10. Edge Cases

**MOC has no topics in cache:** Treat as zero overlap. Log a warning — this MOC may need richer content for vault-explorer to extract topics from.

**Item has no extractable topics:** Return empty match list. Note as "no topics detected — content may be too short or too ambiguous."

**All MOCs match weakly (below threshold):** Return empty list + classification fallback. Don't force a weak match.

**Exact title match:** If an item's title exactly matches a MOC's title (or an alias), boost confidence to 0.95 regardless of topic scoring. This handles cases like an inbox item titled "Systems Thinking" matching the "Systems Thinking (MOC)".
