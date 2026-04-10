# Tier 2: Inbox Processing Workflow

> Parent: [PKM Intelligence Architecture](../../tier-1/pkm-intelligence-architecture.md)
> Status: Draft
> Children: [Inbox Analysis](../../tier-3/inbox/inbox-analysis.md) · [Suggestions Document](../../tier-3/inbox/suggestions-document.md) · [Instruction Set Generation](../../tier-3/inbox/instruction-set-generation.md) · [Instruction Set Apply](../../tier-3/inbox/instruction-set-apply.md) · [Instruction Set Cleanup](../../tier-3/inbox/instruction-set-cleanup.md) · [State Tag Lifecycle](../../tier-3/inbox/state-tag-lifecycle.md)
> Related: [existing workflow doc](../../workflows/inbox-process.md)

---

## 1. Purpose

Define the end-to-end inbox processing workflow — Tomo's primary use case. Two-pass model:

```
Capture → Analyse → Suggestions (Pass 1) → User Confirms Direction
        → Instruction Set (Pass 2) → User Applies → Cleanup
```

## 2. Components Used

| Component | Role in Workflow |
|-----------|-----------------|
| User Config | Folder paths, frontmatter schema, templates, lifecycle tags |
| Discovery Cache | MOC matching, classification, tag suggestions |
| Framework Profile | Classification keywords, relationship conventions |
| Template System | Note creation from templates |

## 3. Two-Pass Proposal Model

Inbox processing uses a **two-pass model** where the user reviews Tomo's interpretation before Tomo commits to detailed instructions. This mirrors the Post-MVP Seigyo dual-vetting pattern.

| Pass | Tomo Output | User Input |
|------|------------|------------|
| **Pass 1: Direction** | Action Suggestions document — high-level findings, options, alternatives, confidence | Review, approve/deny/modify the *direction* |
| **Pass 2: Details** | Instruction Set — detailed per-note actions based on confirmed direction | Apply the actions manually |

**Why two-pass:**
- User catches Tomo's misclassifications early, before details are generated
- Tomo can offer alternatives ("link to MOC A or MOC B?") with confidence scores
- The instruction set is built from confirmed intent, reducing rejection cycles
- Architecturally consistent with Post-MVP Seigyo dual vetting

## 4. Agents and Executor

| Step | Actor | Responsibility |
|------|-------|----------------|
| Read & Analyse | `inbox-analyst` agent | Read inbox, classify items, find candidates with alternatives |
| Suggest (Pass 1) | `suggestion-builder` agent | Generate Action Suggestions document with options and confidence |
| Review (Pass 1) | **User** | Approve/deny/modify suggestions in Obsidian |
| Build (Pass 2) | `instruction-builder` agent | Read confirmed suggestions, generate detailed Instruction Set |
| Apply (outside inbox) | **User (MVP)** / Seigyo (Post-MVP) | Manually perform approved changes in Obsidian |
| Cleanup (inbox-side) | `vault-executor` agent | Tag instruction set, tag inbox items, archive within inbox folder |

**MVP execution boundary:** Tomo writes only to the inbox folder. All vault content changes outside the inbox are performed by the user. See [Tier 1 §7 Execution Model](../../tier-1/pkm-intelligence-architecture.md#7-execution-model).

## 5. Workflow (2-Pass)

```
Manual trigger: /inbox
       │
       ▼
  ┌─────────────────────┐
  │  1. Read Inbox       │  inbox-analyst reads all files in inbox folder
  │     via Kado         │  kado-search (listDir) + kado-read per file
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐
  │  2. Analyse          │  For each file, determine:
  │     Each Item        │  - Type (fleeting note, coding insight, etc.)
  │                      │  - Date relevance
  │                      │  - MOC candidates with alternatives + confidence
  │                      │  - Classification candidates (top N)
  │                      │  - Tracker matches
  │                      │  - Atomic note worth?
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────────────────────┐
  │  PASS 1                              │
  │                                      │
  │  3. Generate Action Suggestions      │  suggestion-builder writes ONE
  │                                      │  document to inbox folder.
  │                                      │  Per-item findings with:
  │                                      │  - Source link to inbox file
  │                                      │  - Suggested action(s)
  │                                      │  - Alternative options ranked
  │                                      │    by confidence (e.g., MOC A
  │                                      │    85%, MOC B 60%)
  │                                      │  - Reasoning
  │                                      │  - Optional context links
  │                                      │  Tag: #MiYo-Tomo/proposed
  └──────────┬──────────────────────────┘
             │
             ▼
  ┌─────────────────────────────────────┐
  │  4. User Reviews Suggestions         │  User opens suggestions document
  │     (Direction Approval)             │  in Obsidian. For each item:
  │                                      │  - Approve as-is
  │                                      │  - Pick alternative
  │                                      │  - Modify (write own MOC, tags,
  │                                      │    title, etc.)
  │                                      │  - Deny (skip this item)
  │                                      │
  │                                      │  User then signals "ready" by
  │                                      │  changing the suggestions doc tag
  │                                      │  from #proposed to #confirmed
  └──────────┬──────────────────────────┘
             │
             ▼  next /inbox run picks up #confirmed suggestions docs
  ┌─────────────────────────────────────┐
  │  PASS 2                              │
  │                                      │
  │  5. Build Instruction Set            │  instruction-builder reads the
  │                                      │  confirmed suggestions and
  │                                      │  generates a detailed instruction
  │                                      │  set in the inbox folder.
  │                                      │  Per approved suggestion:
  │                                      │  - Exact action (file path,
  │                                      │    section, link, content)
  │                                      │  - Rendered template content
  │                                      │    (for new notes)
  │                                      │  - Diffs (for modifications)
  │                                      │  Tag: #MiYo-Tomo/instructions
  └──────────┬──────────────────────────┘
             │
             ▼
  ┌──────────────────────────────────────┐
  │  6. APPLY (MVP: User)                 │  USER performs the actions
  │                                       │  in Obsidian:
  │                                       │  - Move new notes from inbox
  │                                       │    to target folder
  │                                       │  - Apply diffs to existing notes
  │                                       │  - Update tracker fields
  │                                       │  - Add MOC links via direct
  │                                       │    [[MOC#Section]] links
  │                                       │
  │                                       │  Post-MVP: Seigyo executes via
  │                                       │  locked scripts (no second
  │                                       │  approval needed — direction
  │                                       │  was approved in Pass 1).
  └──────────────┬───────────────────────┘
                 │
                 ▼  user signals done (tag instructions doc as #applied)
  ┌─────────────────────┐
  │  7. Inbox Cleanup    │  vault-executor (inbox-side only):
  │                      │  - Tag processed inbox items: #MiYo-Tomo/active
  │                      │  - Tag suggestions doc: #MiYo-Tomo/archived
  │                      │  - Tag instruction set: #MiYo-Tomo/archived
  │                      │  - Optionally move items to inbox archive folder
  │                      │
  │                      │  All writes via Kado, all within inbox folder
  └─────────────────────┘
```

### Why Two Passes (and not Three)

The user is NOT asked to approve the detailed instruction set separately. Approval happens at the **direction** level (Pass 1). The instruction set is the deterministic expansion of the approved direction. Reviewing details a second time would slow things down without adding meaningful control — the user already saw the alternatives and chose.

When the user applies actions manually in MVP, they read each instruction as they apply it, so they have full visibility regardless.

### State Tags on Inbox Documents

Tomo uses tags to track which document is at which stage:

| Tag | What it marks | Set by |
|-----|--------------|--------|
| `#MiYo-Tomo/captured` | New inbox item, unprocessed | User (manual or Claude Code auto-capture) |
| `#MiYo-Tomo/proposed` | Suggestions document waiting for user direction | Tomo (suggestion-builder) |
| `#MiYo-Tomo/confirmed` | Suggestions document with user direction set | User (manual tag change) |
| `#MiYo-Tomo/instructions` | Detailed instruction set ready to apply | Tomo (instruction-builder) |
| `#MiYo-Tomo/applied` | User has applied all actions in the instruction set | User (manual tag change) |
| `#MiYo-Tomo/active` | Processed inbox item (its content is now in the vault) | Tomo (vault-executor cleanup) |
| `#MiYo-Tomo/archived` | Suggestions doc / instruction set retired | Tomo (vault-executor cleanup) |

### MVP Execution Boundary

Steps 1-3, 5, and 7 are Tomo operations (read or inbox-folder writes only). Steps 4 and 6 are user operations. Tomo never writes vault content outside the inbox folder.

## 6. Document Formats

### Suggestions Document (Pass 1 output)

- Filename: `YYYY-MM-DD_HHMM_suggestions.md`
- Initial tag: `#MiYo-Tomo/proposed`
- Per-item structure:
  - Source link to inbox file
  - Suggested action with reasoning
  - Alternative options (ranked by confidence)
  - Editable fields (title, MOC choice, tags, classification)
  - Approve / Deny checkbox per item
- User confirms by changing the document tag to `#MiYo-Tomo/confirmed`

### Instruction Set (Pass 2 output)

- Filename: `YYYY-MM-DD_HHMM_instructions.md`
- Initial tag: `#MiYo-Tomo/instructions`
- Per approved suggestion: a detailed action ready to be applied
- Action types:
  - **New Note** — Full rendered note content (created in inbox folder by Tomo, user moves to target)
  - **MOC Link** — Direct `[[MOC#Section]]` link, exact text to add
  - **New MOC** — Full rendered MOC content (created in inbox by Tomo, user moves)
  - **Daily Note Update** — Tracker field syntax + value, or content snippet for a section
  - **Tag Update** — Existing note path + tags to add/remove
  - **Note Modification** — Diff (before/after) for an existing note
- User marks as applied by changing tag to `#MiYo-Tomo/applied`

## 7. Multi-Day Coverage

The inbox process covers ALL unprocessed items, not just today's:
- If inbox hasn't been processed for 3 days, all 3 days are covered
- Daily note actions are grouped by date
- Suggestions and instruction sets clearly indicate which date each action relates to

## 8. Run-to-Run State

`/inbox` is idempotent across runs. On each invocation, Tomo checks for state in this order:

1. **Are there `#MiYo-Tomo/applied` instruction sets?** → Run cleanup (Step 7) for those, then continue
2. **Are there `#MiYo-Tomo/confirmed` suggestions docs?** → Run Pass 2 (Step 5) for those
3. **Are there fresh `#MiYo-Tomo/captured` inbox items?** → Run Pass 1 (Steps 1-3)
4. **Nothing pending** → Report idle state, exit

A single user workflow can span multiple `/inbox` invocations:
- Day 1: User runs `/inbox` → gets suggestions, reviews later
- Day 2: User confirms suggestions, runs `/inbox` → gets detailed instructions
- Day 3: User applies instructions, runs `/inbox` → cleanup + new items processed

## 9. Error Handling

- **Kado unavailable:** abort with clear error
- **Partial analysis failure:** skip failed item, continue with rest, report skipped items
- **User confirmed suggestions but introduced contradictions:** report conflict, skip ambiguous items, continue with rest
- **User does not apply some actions in instruction set:** no impact on Tomo — instruction set remains until user tags as applied or deletes
- **Inbox cleanup failure:** log failed cleanup action, continue with remaining; failed cleanups can be retried on next run
- **Stale cache:** warn user, proceed with degraded matching
