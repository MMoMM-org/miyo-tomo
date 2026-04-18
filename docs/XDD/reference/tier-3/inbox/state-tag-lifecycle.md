# Tier 3: State Tag Lifecycle

> Parent: [Inbox Processing](../../tier-2/workflows/inbox-processing.md)
> Status: Implemented

---

## 1. Purpose

Define the state machine that governs inbox documents as they move through the 2-pass inbox processing workflow. State is tracked via tags with a configurable prefix (default `MiYo-Tomo`) so the user can see progress in Obsidian and Tomo can pick up where it left off across sessions.

## 2. State Machine

```
                    ┌──────────────┐
                    │   captured    │  Fresh inbox item, untouched
                    └──────┬───────┘
                           │ /inbox (Pass 1)
                           ▼
                    ┌──────────────┐
                    │   proposed    │  Suggestions doc written by Tomo,
                    │               │  waiting for user direction
                    └──────┬───────┘
                           │ user reviews, tags manually
                           ▼
                    ┌──────────────┐
                    │   confirmed   │  User has approved direction
                    └──────┬───────┘
                           │ /inbox (Pass 2)
                           ▼
                    ┌──────────────┐
                    │  instructions │  Detailed instruction set ready
                    └──────┬───────┘
                           │ user applies actions, tags manually
                           ▼
                    ┌──────────────┐
                    │    applied    │  All actions from instruction set
                    │               │  have been applied by user
                    └──────┬───────┘
                           │ /inbox (cleanup)
                           ▼
              ┌────────────┴────────────┐
              ▼                         ▼
       ┌──────────────┐          ┌──────────────┐
       │    active     │          │   archived    │
       │ (inbox items) │          │ (sugg+instr)  │
       └──────────────┘          └──────────────┘
```

## 3. States

| State | Applied to | Set by | Meaning |
|-------|-----------|--------|---------|
| `captured` | Inbox items | User or auto-capture | Fresh, untouched, waiting for processing |
| `proposed` | Suggestions document | Tomo (suggestion-builder) | Pass 1 output, user review needed |
| `confirmed` | Suggestions document | **User** (manual tag change) | Direction approved, ready for Pass 2 |
| `instructions` | Instruction set document | Tomo (instruction-builder) | Pass 2 output, user application needed |
| `applied` | Instruction set document | **User** (manual tag change) | All actions applied in vault |
| `active` | Inbox items | Tomo (vault-executor cleanup) | Item has been integrated into vault content |
| `archived` | Suggestions doc + Instruction set | Tomo (vault-executor cleanup) | Document retired, keep for history |

## 4. Who Sets What

**Tomo sets:**
- `proposed` — when generating a suggestions document
- `instructions` — when generating an instruction set
- `active` — during cleanup, applied to the original inbox items
- `archived` — during cleanup, applied to completed suggestions/instructions docs

**User sets (manually in Obsidian):**
- `captured` — implicitly, when creating the inbox file (may be auto-set by auto-capture)
- `confirmed` — to signal "I've reviewed the suggestions, proceed to Pass 2"
- `applied` — to signal "I've done the work, you can clean up"

This split keeps the state machine deterministic from Tomo's side while giving the user explicit control over the handoff points.

## 5. Tag Format

Tags follow the pattern: `#<prefix>/<state>`

Default prefix: `MiYo-Tomo`

Examples:
- `#MiYo-Tomo/captured`
- `#MiYo-Tomo/proposed`
- `#MiYo-Tomo/confirmed`
- `#MiYo-Tomo/instructions`
- `#MiYo-Tomo/applied`
- `#MiYo-Tomo/active`
- `#MiYo-Tomo/archived`

**Prefix is configurable** via `lifecycle.tag_prefix` in vault-config.yaml. State names are fixed.

## 6. Tag Transitions

Tags are **replaced**, not accumulated. When a state transitions:
1. Remove the old state tag
2. Add the new state tag
3. A document has **exactly one** lifecycle state tag at any time

If multiple lifecycle tags are observed on the same document, Tomo reports it as an inconsistency and asks the user to resolve.

## 7. Run-to-Run State Discovery

On each `/inbox` invocation, Tomo queries Kado by tag to determine what work exists:

```
1. kado-search byTag #MiYo-Tomo/applied
   → If any found: run cleanup for those docs + their linked inbox items
   
2. kado-search byTag #MiYo-Tomo/confirmed
   → If any found: run Pass 2 (generate instruction sets) for those
   
3. kado-search byTag #MiYo-Tomo/captured
   → If any found AND no blocking state earlier: run Pass 1 (analyse + suggest)
   
4. If nothing pending → report idle state, exit
```

This makes `/inbox` idempotent and resumable. The user can walk away mid-flow and come back days later.

## 8. Invariants

1. **Exactly one lifecycle tag per document** — any violation is an error state
2. **Tomo never sets user-owned states** — Tomo cannot write `confirmed` or `applied` tags
3. **User never sets Tomo-owned states** — discouraged; if detected during scan, warn (not blocking)
4. **Terminal states are `active` and `archived`** — no further transitions
5. **Transitions are monotonic** — a document cannot go backwards in the state machine. To redo, the user creates a new inbox item.

## 9. Edge Cases

**User marks a suggestions doc `confirmed` before reviewing:**
- Tomo proceeds to Pass 2 (takes user at their word)
- If the generated instructions look wrong, user can delete and re-tag the source inbox items as `captured`

**User modifies a suggestions doc content but forgets to change the tag:**
- On next `/inbox`, Tomo still sees it as `proposed` — no action
- User eventually tags it `confirmed` → Tomo reads the modified content for Pass 2

**User marks an instruction set `applied` but didn't do all actions:**
- Tomo trusts the user
- Unapplied actions are "lost" from Tomo's perspective
- User can recreate missing actions from the source inbox items in a new `/inbox` run

**Partial failures in cleanup:**
- If Tomo fails to tag some inbox items as `active`, it logs the failures and leaves them in their previous state
- Next `/inbox` run retries

**User deletes a suggestions doc:**
- The source inbox items are orphaned (still tagged `captured` but referenced nowhere)
- Next `/inbox` run treats them as fresh and re-runs Pass 1

## 10. Tag Queries Cheat Sheet

Common Tomo operations and their Kado queries:

| Operation | Query |
|-----------|-------|
| Find new inbox items | `kado-search byTag #MiYo-Tomo/captured` |
| Find suggestions awaiting review | `kado-search byTag #MiYo-Tomo/proposed` |
| Find confirmed suggestions to process | `kado-search byTag #MiYo-Tomo/confirmed` |
| Find instruction sets awaiting user application | `kado-search byTag #MiYo-Tomo/instructions` |
| Find applied instruction sets to clean up | `kado-search byTag #MiYo-Tomo/applied` |
| Count processed items | `kado-search byTag #MiYo-Tomo/active` + `count` |
