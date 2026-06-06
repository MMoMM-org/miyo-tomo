# Tier 3: New MOC Proposal (Mental Squeeze Point)

> Parent: [LYT/MOC Linking](../../tier-2/workflows/lyt-moc-linking.md)
> Status: Implemented
> Related: [MOC Matching](moc-matching.md) · [MOC Indexing](../discovery/moc-indexing.md)

---

## 1. Purpose

Define when and how Tomo proposes creating a new MOC. Based on LYT's "Mental Squeeze Point" concept: when enough notes on a topic accumulate without a dedicated MOC, the cognitive overhead of managing them separately exceeds the cost of creating a map.

## 2. Trigger Conditions

A new MOC proposal is generated when ANY of these conditions are met:

### Condition A: Cluster Detection (Batch)

During inbox processing, `inbox-analyst` detects that 3+ items in the **current batch** share topics not covered by any existing MOC.

```
cluster_topics = topics shared by 3+ items in the batch
For each cluster_topic set:
  If NO MOC in cache has overlap > threshold with these topics → propose
```

### Condition B: Accumulation Detection — RETIRED (spec 021 ADR-10)

> **Was implemented: XDD 015** (feat/f-34-msp-condition-b-accumulation).
> **Retired: spec 021 T3.1–T3.3** (branch feat/f-34-msp-condition-b-accumulation).

Condition B triggered when the note being analyzed matched topics shared by
existing unclassified notes in the vault ("accumulation cluster"). It consumed
`accumulation_index` from `shared-ctx.json`, which was built by
`atomic-note-indexer.py` and persisted via `cache-builder.py`.

**Why retired:** spec 021 moved vault-wide MOC discovery to `/moc-propose`, a
dedicated command that scans the vault live. Keeping Condition B in the inbox
pipeline would create a parallel, lower-quality discovery path that conflicts
with `/moc-propose`. Additionally, the accumulation index suffered from 224
false-positive placeholder entries (the `all_vault_paths=89-MOC` denominator
bug, fixed in `lib/placeholder_detect.py` for the remaining placeholder flow).
ADR-10 records the retirement decision.

**Current state:** `atomic-note-indexer.py` deleted; `accumulation_index` field
removed from shared-ctx schema; `unclassified_topic_clusters` removed from
discovery-cache schema; Condition B text removed from `inbox-analyst.md`.
Condition C (placeholder match) is the retained high-confidence path for
inbox-time MOC proposals. The accumulation use case is served by `/moc-propose`.

### Condition C: Placeholder Match

A note's topics match a **placeholder MOC** (dead link in an existing MOC):

```
For each placeholder in discovery-cache.placeholder_mocs:
  If item topics overlap with placeholder's implied topic → propose
  The proposal replaces the dead link with a real MOC
```

### Condition D: Manual Trigger (`/moc-propose`)

User runs the standalone MOC density scan via `/moc-propose` (see [LYT/MOC Linking §8](../../tier-2/workflows/lyt-moc-linking.md#8-standalone-moc-density-workflow)). This scans the vault live at call time for clustering opportunities, orphan notes, and placeholder replacements — not bound to the discovery-cache snapshot. (The originally-planned `/scan-mocs` was superseded by `/moc-propose`, F-43.)

## 3. Threshold

**Default:** 3 notes on a shared topic without a dedicated MOC.

This is Nick Milo's heuristic from LYT: the Mental Squeeze Point occurs when you have "about 5-10 notes on a topic" — Tomo uses a lower threshold (3) because it's proposing, not deciding. The user can always reject.

**Configurable:** future vault-config setting `moc_proposal.min_notes` (default: 3).

## 4. Proposal Content

When a new MOC is proposed, the suggestion includes:

```yaml
type: "new_moc"
confidence: float                    # How confident is the cluster detection
title: "Shell & Terminal (MOC)"      # Suggested title
suggested_path: "Atlas/200 Maps/Shell & Terminal (MOC).md"
template: "t_moc_tomo"              # From vault-config templates.mapping.map_note

# Where this fits in the tree
parent_moc:
  path: "Atlas/200 Maps/2600 - Applied Sciences.md"
  section: "## Sub-MOCs"             # Or null if no clear parent section
  classification: 2600

# Initial content
initial_links:
  - { path: "+/2026-04-08_oh-my-zsh.md", title: "oh-my-zsh — Installation" }
  - { path: "Atlas/202 Notes/zsh-aliases.md", title: "zsh Aliases" }
  - { path: "+/2026-04-07_iterm-config.md", title: "iTerm Configuration" }

# Context
trigger: "cluster"                   # or "placeholder", "manual" ("accumulation" retired, ADR-10)
trigger_detail: "3 items in batch share shell/terminal topics"

# Placeholder resolution (if applicable)
replaces_placeholder:
  link_text: "Shell & Terminal (MOC)"
  referenced_from: "Atlas/200 Maps/2600 - Applied Sciences.md"
```

## 5. Suggestions Document Entry

```markdown
## 🔍 New MOC Proposal: Shell & Terminal

**Trigger:** 3 items in this batch share the "shell/terminal" topic
**Confidence:** 75%

### Suggestion — [ ] Create MOC

- Title: "Shell & Terminal (MOC)"
- Location: Atlas/200 Maps/
- Template: t_moc_tomo
- Parent: [[2600 - Applied Sciences#Sub-MOCs]]
- Classification: 2600

**Initial links (notes to add to the new MOC):**
- [[oh-my-zsh — Installation & Configuration]]
- [[zsh Aliases]]
- [[iTerm Configuration]]

**Resolves placeholder:** Dead link `[[Shell & Terminal (MOC)]]` in
[[2600 - Applied Sciences]] would become live.

### Alternatives

- [ ] Skip — don't create MOC yet (notes will link to classification level instead)
- [ ] Create with different title: ____________________

### Why this proposal

These notes share terminal/shell topics (oh-my-zsh, zsh, iTerm) with no
dedicated MOC covering this area. The 2600 classification map has a dead link
`[[Shell & Terminal (MOC)]]` that this would resolve.
```

## 6. What Happens After Approval

If the user approves the new MOC proposal in Pass 1:

1. **Pass 2 generates:**
   - A rendered MOC file in the inbox folder (from `t_moc_tomo` template)
   - Pre-populated with initial links
   - `up::` set to the parent MOC
   - Tags set per tag taxonomy (`type/others/moc`, relevant `topic/` tags)

2. **Instruction set includes:**
   - `I04 — Create new MOC: Shell & Terminal (MOC)`
   - Move rendered file from inbox to `Atlas/200 Maps/`
   - After moving: add link in parent MOC's section
   - If placeholder: note that the dead link is now live

3. **Other notes in the batch** that were initially matched to classification-level are **re-linked** to the new MOC instead:
   - Their instruction set entries reference the new MOC, not `2600 - Applied Sciences`
   - This happens automatically during Pass 2 — the instruction-builder knows the MOC will exist

## 7. Title Generation

Suggested MOC titles follow patterns observed in the vault:

| Pattern | Example | When used |
|---------|---------|-----------|
| `<Topic> (MOC)` | "Shell & Terminal (MOC)" | MiYo profile (all MOCs have "(MOC)" suffix) |
| `<Topic>` | "Shell & Terminal" | LYT profile (plain titles) |
| `<Number> - <Topic>` | "2650 - Shell & Terminal" | If Dewey sub-numbering is used |

The suffix pattern is detected from existing MOCs during `/explore-vault` and stored in the profile or config.

**User always has the final word** — the title is editable in the suggestions document.

## 8. Preventing Duplicate Proposals

Tomo checks before proposing:

1. **Exact title match:** Does a MOC with this title already exist? → Don't propose
2. **High topic overlap:** Does an existing MOC cover 80%+ of the cluster topics? → Suggest linking there instead
3. **Recent proposal:** Was this MOC proposed in a recent suggestions document that wasn't confirmed? → Don't re-propose in the next run (avoid nagging)

"Recent" = within the last 3 `/inbox` runs. Tracked by checking archived suggestions documents for rejected MOC proposals.

## 9. `/moc-propose` Command (Condition D)

The standalone density scan works differently from batch detection. Implemented
as spec 021 (was originally `/scan-mocs`, superseded by `/moc-propose`, F-43):

```
1. moc-discovery.py: tag-primary MOC discovery (lib/moc_scan, #type/others/moc)
2. TTL-gated cache load via lib/moc_cache_loader (rebuilds inline if stale)
3. Phases 1–6: topic clustering, parent resolution, duplicate filtering
4. Case-(a) orphan pass (lib/orphan_link): notes and MOCs with up_state=="absent"
   → link_existing (≥1 MOC above LINK_THRESHOLD) or create_new + reason
5. suggestions-reducer.py --moc-proposal-mode: render proposal-doc (incl. Orphan section)
6. Proposal-doc written to inbox — user reviews + confirms
7. /inbox Pass 2 generates instruction set; applied by hand or via Hashi
```

This is a heavier operation (reads MOCs and notes via Kado) but only runs on
user request, and uses the MOC-structure cache (TTL: configurable, default 1 day)
to avoid a full live scan when the cache is fresh.

## 10. Edge Cases

**User rejects a MOC proposal multiple times:** After 3 rejections of the same topic cluster, Tomo stops proposing it. The topic cluster is marked as "user-declined" in the analysis context. Can be reset by running `/moc-propose --reset-declined` (post-MVP).

**New MOC would create a very deep tree (level 4+):** Warn in the proposal: "This MOC would be at depth 4 in the tree. Consider linking it higher to keep the tree shallow." Don't block — just inform.

**Cluster of binary files:** Binary files (PDFs, images) can trigger clusters too if their filenames share topics. The MOC proposal would be for the topic, not for the file type.
