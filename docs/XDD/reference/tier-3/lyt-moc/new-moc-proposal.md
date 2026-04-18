# Tier 3: New MOC Proposal (Mental Squeeze Point)

> Parent: [LYT/MOC Linking](../../tier-2/workflows/lyt-moc-linking.md)
> Status: Draft
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

### Condition B: Accumulation Detection (Historical)

During inbox analysis, Tomo finds that the **note being analyzed** matches topics shared by 2+ **existing unclassified notes** in the vault.

```
For current item's topics:
  kado-search by content or tag for similar existing notes
  If found 2+ notes with no MOC link (no up:: to a MOC) → propose
  Combined with current item = 3+ notes → threshold met
```

### Condition C: Placeholder Match

A note's topics match a **placeholder MOC** (dead link in an existing MOC):

```
For each placeholder in discovery-cache.placeholder_mocs:
  If item topics overlap with placeholder's implied topic → propose
  The proposal replaces the dead link with a real MOC
```

### Condition D: Manual Trigger (`/scan-mocs`)

User runs the standalone MOC density scan (see [LYT/MOC Linking §8](../../tier-2/workflows/lyt-moc-linking.md#8-standalone-moc-density-workflow)). This scans the entire vault for clustering opportunities, not just the current inbox batch.

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
trigger: "cluster"                   # or "accumulation", "placeholder", "manual"
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

## 9. `/scan-mocs` Command

The standalone density scan (Condition D) works differently from batch detection:

```
1. Read ALL notes in atomic_note paths (not just inbox)
2. For each note without a MOC parent (no up:: to a MOC):
   → Extract topics
   → Group by shared topics
3. For each group with 3+ notes:
   → Check if existing MOC covers these topics
   → If not → propose new MOC
4. Generate a suggestions document (same format as inbox processing Pass 1)
5. User reviews and confirms
6. Run /inbox to execute Pass 2 + cleanup
```

This is a heavier operation (reads many notes) but only runs on user request.

## 10. Edge Cases

**User rejects a MOC proposal multiple times:** After 3 rejections of the same topic cluster, Tomo stops proposing it. The topic cluster is marked as "user-declined" in the analysis context. Can be reset by running `/scan-mocs --reset-declined`.

**New MOC would create a very deep tree (level 4+):** Warn in the proposal: "This MOC would be at depth 4 in the tree. Consider linking it higher to keep the tree shallow." Don't block — just inform.

**Cluster of binary files:** Binary files (PDFs, images) can trigger clusters too if their filenames share topics. The MOC proposal would be for the topic, not for the file type.
