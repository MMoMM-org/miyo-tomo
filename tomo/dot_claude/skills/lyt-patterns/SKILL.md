---
name: lyt-patterns
description: MOC matching algorithm, section placement rules, mental squeeze point detection, and new MOC proposal heuristics for LYT-style vaults. Use when analyzing inbox items for MOC linkage, placing links inside MOC structures, or deciding whether to propose a new Map of Content.
user-invocable: false
---
# LYT Patterns
# version: 0.2.1

Knowledge patterns for MOC matching, section placement, and new MOC proposals.

## MOC Matching Algorithm

Given an inbox item's extracted topics and the MOC index from discovery-cache.yaml, score each MOC:

**Step 1 — Topic Overlap:**
- `overlap_count = count(item_topics ∩ moc_topics)`
- `overlap_ratio = overlap_count / max(len(item_topics), 1)`
- If `overlap_count == 0` → skip this MOC entirely

**Step 2 — Depth Bonus** (prefer specific over generic):
- Level 0 (root MOC): +0.0
- Level 1 (classification): +0.1
- Level 2 (topic MOC): +0.2
- Level 3 (sub-topic): +0.3

**Step 3 — Size Penalty** (large MOCs are less specific):
- `linked_notes > 50`: -0.05
- `linked_notes > 100`: -0.10
- Otherwise: 0

**Step 4 — Final Score:**
- `confidence = clamp(overlap_ratio + depth_bonus + size_penalty, 0.0, 1.0)`

**Step 5 — Rank and Return:**
- Sort descending by confidence
- Return top 3 with confidence > threshold (default: 0.15)

**Special case — Exact title match:**
If the inbox item's title exactly matches a MOC's title or alias, boost confidence to 0.95 regardless of topic scoring.

## Confidence Thresholds

| Setting | Default | Notes |
|---------|---------|-------|
| `confidence_threshold` | 0.15 | Minimum score to include a MOC match |
| `max_results` | 3 | Maximum MOC matches to return per item |
| `depth_bonus_weight` | 0.1 per level | Hardcoded MVP; post-MVP: configurable |
| `size_penalty_threshold` | 50 notes | When to start penalizing large MOCs |
| Exact title match override | 0.95 | Overrides topic scoring |
| Batch context boost | +boost for all matching items | When 3+ batch items match the same MOC |

## MOC-Only Layers (Classification Guard)

Classification-level MOCs (Dewey layer — e.g. `2600 - Applied Sciences`, `2000 - Knowledge
Management`) are **MOC-only containers**. They link to thematic MOCs, never to individual notes.

**Detection:** A MOC is classification-level when:
- Its level in the MOC tree is 0 or 1 (root or first tier below root)
- Its name matches the Dewey pattern `\d{4} - .+`
- It has `up:: [[200 Maps]]` or equivalent root-level parent

**STRICT RULE:** When the best MOC match for a note is a classification-level MOC and no
deeper thematic MOC matches above threshold:
1. Do NOT link the note directly to the classification MOC
2. Instead, trigger a **New MOC Proposal** (see Mental Squeeze Point Detection below)
3. The proposed MOC gets `up::` pointing to the classification MOC
4. The note links to the proposed MOC, not the classification layer

**Batch grouping:** When multiple items in the same batch would fall back to the same
classification MOC, group them and propose a single thematic MOC covering the shared topic.
This is Condition A (Cluster) of Mental Squeeze Point Detection.

**Single item, no cluster:** Even a single note that only matches a classification MOC should
trigger a MOC proposal suggestion (not a hard requirement). The suggestion notes: "No thematic
MOC found under [[2600 - Applied Sciences]]. Consider creating one if more notes accumulate."
Meanwhile, the note gets the classification MOC as **context** (shown in the suggestion) but
the primary action is `up:: TBD` — the user decides during review.

## Fallback When No MOC Matches At All

When MOC matching returns no results above threshold (not even classification level):
1. Flag in suggestions: "No MOC match found. User should assign manually or propose a new MOC."
2. Do NOT silently assign a classification MOC as parent.

When both a thematic MOC and its parent classification MOC match: show the thematic MOC as
primary link. The classification MOC is implicit via the tree — do not add it as a second link.

## Placeholder MOC Awareness

From the cache's `placeholder_mocs` list: if item topics match a placeholder MOC's implied topics, include in suggestions as: "This note matches placeholder [[Name (MOC)]] (dead link in [[Parent MOC]]). Creating this MOC would resolve the placeholder."

## Section Placement Rules

When placing a link inside a matched MOC, follow this algorithm:

**Step 1 — Parse MOC Structure:**
- H2 headings → candidate sections
- `> [!name]` callouts → classify as editable/protected/ignore per vault-config
- ` ```dataview `, ` ```dataviewjs `, ` ```folder-overview ` blocks → protected

**Step 2 — Identify Candidate Sections:**
Exclude from candidates:
- Inside a protected callout (`[!boxes]`, `[!shell]`, `[!keaton]` in MiYo)
- Footer area (after the last `[!video]` or `[!calendar]` callout)
- Overview/Anchor section (introductory, not a link list)

Safe insertion zones in MiYo MOC template: `[!blocks]` (Key Concepts) and content H2 sections above the `[!video]` footer boundary.

**Step 3 — Score Sections:**
- Note topic exactly matches section name → 1.0
- Note topic is substring of section name → 0.7
- Section contains existing links with similar topics → 0.5
- `[!blocks]` callout content area → 0.3 (generic "Key Concepts" fallback)

**Step 4 — Select and Insert:**
- score >= 0.5 → use that section
- score < 0.5 AND clear topic → propose creating a new section
- No sections found → append before footer

**Link insertion format:**
- Append as bullet: `- [[New Note Title]]`
- If section uses summaries, match the pattern: `- [[New Note Title]] — One-line description`
- Detect format by reading the last 3 links in the section

**In instruction set:** always use direct section wikilinks: `[[MOC Name#Section Name]]` so the user lands at the exact spot.

## Protected Zones — Never Write Here

| Zone | Identification |
|------|---------------|
| Protected callouts | `callouts.protected` from config (e.g., `[!boxes]`, `[!shell]`, `[!keaton]`) |
| DataviewJS blocks | ` ```dataviewjs ``` ` |
| Dataview blocks | ` ```dataview ``` ` |
| Folder-overview blocks | ` ```folder-overview ``` ` |

## New Section Proposals

When no existing section fits: propose creating a new H2 before the footer area. Section naming: primary topic or matched classification sub-category, 2-4 words. Example instruction:

```
- **Target:** [[2600 - Applied Sciences]]
- **Create section:** `## Shell & Terminal` (insert before ## Related)
- **Add this line:** `- [[oh-my-zsh — Installation & Configuration]]`
```

## Mental Squeeze Point Detection

A new MOC proposal is triggered when ANY of these conditions are met:

**Condition A — Cluster (Batch):**
3+ items in the current batch share topics not covered by any existing MOC.

**Condition B — Accumulation (Historical):**
The note being analysed matches topics shared by 2+ existing unclassified notes (no `up::` to a MOC). Combined with the current item = 3+ notes → threshold met.

**Condition C — Placeholder Match:**
Note topics match a placeholder MOC (dead link in an existing MOC). Propose creating the MOC to resolve the dead link.

**Condition D — Manual Trigger (`/scan-mocs`):**
User-initiated vault-wide density scan.

**Default threshold:** 3 notes on a shared topic without a dedicated MOC. Future: configurable via `moc_proposal.min_notes`.

## New MOC Proposal Content

A proposal includes:
- Suggested title (pattern detected from vault: `<Topic> (MOC)` for MiYo, plain `<Topic>` for LYT, `<Number> - <Topic>` for Dewey)
- Suggested path in `Atlas/200 Maps/` (or equivalent from vault-config)
- Template reference (`t_moc_tomo` or profile default)
- Parent MOC and target section
- Initial links — the notes that triggered the proposal
- Trigger type: `cluster`, `accumulation`, `placeholder`, or `manual`
- Placeholder resolution note if applicable

**Duplicate prevention:** Before proposing, check:
1. Exact title already exists → skip
2. Existing MOC covers 80%+ of cluster topics → suggest linking there instead
3. Same MOC proposed in last 3 `/inbox` runs and rejected → don't re-propose

**After approval (Pass 2):** Generate a rendered MOC file in the inbox folder from the profile template, pre-populated with initial links, `up::` set to parent MOC, tags per taxonomy. Other batch items initially linked to classification level are re-linked to the new MOC.

## MiYo MOC Template Structure (reference)

```
1. Frontmatter
2. [!connect]  — up:: / related::        EDITABLE
3. Title + summary DataviewJS
4. [!anchor]   — Overview                EDITABLE
5. [!blocks]   — Key Concepts            EDITABLE (primary link insertion zone)
6. Content H2 sections                   EDITABLE (secondary link insertion zone)
7. [!video]    — Action Items            FOOTER BOUNDARY
8. [!calendar] — Recent Updates          EDITABLE
9. [!connect]  — Categories (tags)       EDITABLE
10. [!puzzle]  — Related Topics          EDITABLE
11. [!compass] — Look at this            EDITABLE
12. [!boxes]   — Unrequited Notes        PROTECTED (DataviewJS)
13. [!shell]   — Same-tag unmentioned    PROTECTED (DataviewJS)
14. [!keaton]  — Title-match notes       PROTECTED (DataviewJS)
```
