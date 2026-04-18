# Tier 2: LYT/MOC Linking Workflow

> Parent: [PKM Intelligence Architecture](../../tier-1/pkm-intelligence-architecture.md)
> Status: Implemented
> Children: [MOC Matching](../../tier-3/lyt-moc/moc-matching.md) · [Section Placement](../../tier-3/lyt-moc/section-placement.md) · [New MOC Proposal](../../tier-3/lyt-moc/new-moc-proposal.md)
> Related: [existing workflow doc](../../workflows/lyt-moc.md)

---

## 1. Purpose

Define how Tomo connects notes to Maps of Content (MOCs) and proposes new MOCs when patterns emerge. This is where the framework profile's classification system and the discovery cache's semantic index converge.

## 2. Components Used

| Component | Role in Workflow |
|-----------|-----------------|
| Framework Profile | Classification categories + keywords |
| Discovery Cache | MOC topics, sections, linked note counts |
| User Config | map_note folder, relationship markers, callout mapping |

## 3. Core Principle

**MOCs stay empty because manual linking is too much friction.** Tomo handles the **decision work** as proposals — what links to which MOC, which section, why. The user still applies the changes manually in MVP, but the cognitive load is removed: every proposal includes the exact MOC, section, link, and reasoning.

This workflow is framework-aware but not framework-locked:
- LYT: MOC linking with Dewey classification + sub-MOC tree
- PARA: Index note maintenance
- Custom: whatever the user's map_note convention is

### MOC Tree (Not Just Classification-Level)

LYT and MiYo start from the **HomeNote** and branch into the **Dewey classification level** (2000-2900). From there, multiple layers of sub-MOCs exist. Tomo must work with **the entire tree**, not just the top level:

```
HomeNote
  ├── 2000 - Knowledge Management (classification MOC)
  │   ├── Linking Your Thinking (MOC)      ← mid-level
  │   │   ├── LYT Standards of Classification  ← leaf
  │   │   └── 4 PKM Personalities             ← leaf
  │   └── My PKM (MOC)                      ← mid-level
  ├── 2600 - Applied Sciences
  │   └── MiYo Research (MOC)               ← mid-level
  │       └── Claude Docker Research        ← leaf
  └── ...
```

**Implications for linking:**
- Tomo should prefer linking to the **deepest matching MOC** (most specific context) rather than the classification root
- Classification MOCs can contain placeholders for non-existent sub-MOCs. Tomo can propose replacing those placeholders with links to existing viable sub-MOCs when they're discovered
- Classification-level MOCs are themselves manageable content — Tomo can propose updates to them

**MVP execution:** MOCs live outside the inbox folder, so all approved MOC changes are applied **by the user manually**. The instruction set provides everything needed: direct `[[MOC#Section]]` wikilink, exact text to add, fallback if section is missing. See [Tier 1 §7 Execution Model](../../tier-1/pkm-intelligence-architecture.md#7-execution-model).

## 4. Workflow (during Inbox Processing)

For each inbox item identified as an atomic_note candidate:

```
1. Extract topics from content
       │
       ▼
2. Match against discovery cache (MOC topics)
       │
   ┌───┴────────────────┐
   Match found           No match
   │                     │
   ▼                     ▼
3a. Propose MOC link    3b. Match against profile
    - Which MOC?             classification keywords
    - Which section?         │
    - What link format?  ┌───┴──────────┐
                         Match           No match
                         │               │
                         ▼               ▼
                    3c. Propose      3d. Log as
                        classification   unclassified
                        parent link      (no MOC action)
                         │
                         ▼
4. Mental Squeeze Point check:
   Are there 3+ unlinked notes on a similar topic?
       │
   ┌───┴───┐
   Yes     No
   │       │
   ▼       ▼
5a. Propose  5b. Done
    new MOC
```

## 5. MOC Matching (Detail)

**Primary:** Discovery cache MOC topics, prefer deepest match
- Compare inbox item topics against ALL cached MOC topic lists (all tree levels)
- Confidence scoring: topic overlap / total topics + depth bonus (deeper = more specific)
- Threshold: configurable (default: at least 1 strong topic match)
- If multiple matches: present alternatives in Pass 1 suggestions, ranked by confidence
- Prefer leaf or mid-level MOCs over classification-root MOCs (specificity wins)

**Fallback:** Profile classification keywords
- If no specific MOC match, fall back to classification category keywords
- Propose `parent` link to classification MOC (e.g., `up:: [[2600 - Applied Sciences]]`)
- Note in the suggestion that this is a fallback — user may prefer to wait for a sub-MOC to emerge

**No match:** Note is created without MOC link. Tagged as unclassified for future `/explore-vault` to detect patterns.

**Detail spec:** [MOC Matching](../../tier-3/lyt-moc/moc-matching.md)

## 6. Section Placement (Detail)

When linking a note to an MOC, Tomo must decide WHERE in the MOC to place the link.

**Strategy:**
1. Read MOC's H2 sections (from cache or on-demand)
2. Match note's topic against section headings
3. If match: propose placement in that section
4. If no match: propose new section or placement in a general section

**Respects callout mapping:** editable callouts (e.g., `[!blocks]`) can receive content; protected callouts (e.g., `[!boxes]`) must never be modified.

**Detail spec:** [Section Placement](../../tier-3/lyt-moc/section-placement.md)

## 7. New MOC Proposal (Mental Squeeze Point)

**Trigger:** 3+ notes on a similar topic exist without a dedicated MOC.

**Detection:**
- During inbox analysis: check discovery cache for topic clusters
- Count notes that would match a hypothetical MOC
- If threshold met (default: 3): propose new MOC

**Proposal includes:**
- Suggested MOC title and file path
- Initial links (the notes that triggered the proposal)
- Suggested parent MOC (where this fits in the tree)
- Suggested classification category (if applicable)
- Template: configured `map_note` template (e.g., `t_moc_tomo`)
- Replaces placeholder? — if a non-existent placeholder MOC exists in a parent, propose replacing it

**Detail spec:** [New MOC Proposal](../../tier-3/lyt-moc/new-moc-proposal.md)

## 8. Standalone MOC Density Workflow

Beyond inbox processing, Tomo can run a **standalone MOC density scan** to densify the existing network:

- **Trigger:** dedicated command (e.g., `/scan-mocs`) — independent of `/inbox`
- **Goal:** find clustering opportunities, placeholder replacements, and orphan notes that could join an existing MOC
- **Output:** Pass 1 Suggestions document (same format as inbox processing) with MOC-density actions only
- **Same 2-pass approval:** user confirms direction, then Tomo generates instruction set, then user applies

This lets the user maintain MOC coverage continuously, not only when new inbox items arrive.

## 9. Instruction Set Action Examples

Instruction set entries use **direct section links** so the user can click and land at the right spot before applying the change.

```markdown
### [A05] MOC Link: oh-my-zsh → Shell & Terminal MOC
- [ ] **Apply**
- Target: [[MOC - Shell & Terminal#Tools]]   ← click to land at the section
- Add this line to the section:
  `- [[oh-my-zsh — Installation & Configuration]]`
- Section will be created at end of file if missing

### [A06] New MOC: Dotfiles & System Config
- [ ] **Apply**
- New file path: Atlas/200 Maps/Dotfiles & System Config (MOC).md
- Pre-rendered content: see attachment below (Tomo created this in inbox folder)
- Source path in inbox: [[+/2026-04-07_1430_dotfiles-moc.md]]
- After moving the file, add to parent MOC: [[2600 - Applied Sciences#Sub-MOCs]]
- Initial links to populate: [[oh-my-zsh]], [[git-config]], [[brew-setup]]
- Replaces placeholder: [[Dotfiles & System Config]] (currently a dead link in [[2600 - Applied Sciences]])
```
