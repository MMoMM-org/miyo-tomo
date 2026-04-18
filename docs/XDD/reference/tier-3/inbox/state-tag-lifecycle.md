# Tier 3: State Tag Lifecycle

> Parent: [Inbox Processing](../../tier-2/workflows/inbox-processing.md)
> Status: Implemented (with deviations)

> **⚠️ Deviation**
> **Original**: 7-state tag-based lifecycle for all documents (captured → proposed → confirmed → instructions → applied → active/archived).
> **Actual**: Simplified to 2 tags for source items only + checkbox-based state for workflow documents. Tags on workflow documents were dropped because frontmatter tags are not easily accessible to users in Obsidian.

---

## 1. Purpose

Define the state model that governs inbox documents as they move through the 2-pass inbox processing workflow. Source items use tags; workflow documents use checkboxes.

## 2. State Model

Two separate tracking mechanisms:

```
SOURCE ITEMS (tags — Tomo-managed)
──────────────────────────────────
  (no tag)  →  captured  →  active
                  ↑            ↑
           tag-captured.py   vault-executor

WORKFLOW DOCUMENTS (checkboxes — user-facing)
─────────────────────────────────────────────
  Suggestions:   [ ] Approved  →  [x] Approved   (user checks)
  Instructions:  [ ] Applied   →  [x] Applied    (user checks per action)
```

## 3. Source Item Tags

Source items (inbox notes the user creates) use frontmatter tags managed by Tomo:

| Tag | Set by | Meaning |
|-----|--------|---------|
| `#<prefix>/captured` | `tag-captured.py` (orchestrator Phase C) | Item has been processed by Pass 1 |
| `#<prefix>/active` | `vault-executor` (cleanup) | Item's content is integrated into the vault |

Default prefix: `MiYo-Tomo`. Configurable via `lifecycle.tag_prefix` in vault-config.yaml.

**Items without a tag** are considered fresh — eligible for Pass 1 processing.

## 4. Workflow Document State

Workflow documents (suggestions, instructions) use **visible checkboxes** instead of tags:

| Document | State signal | Meaning |
|----------|-------------|---------|
| Suggestions | `- [ ] Approved` | Waiting for user review |
| Suggestions | `- [x] Approved` | User has approved direction → ready for Pass 2 |
| Instructions | `- [ ] Applied` (per action) | Action not yet applied |
| Instructions | `- [x] Applied` (per action) | Action applied by user |

Discovery is by filename pattern: `*_suggestions.md`, `*_instructions.md`.

**Why checkboxes over tags:**
- Visible in Obsidian reading view — user sees progress at a glance
- No frontmatter manipulation needed — just check a box
- Suggestions have one global `[x] Approved`; instructions have per-action `[x] Applied`
- Tomo discovers state by parsing checkboxes, not querying tags

## 5. Run-to-Run State Discovery

On each `/inbox` invocation, Tomo discovers state in priority order:

```
1. Scan inbox for *_instructions.md files
   → Read each, count [x] Applied vs total actions
   → If any actions applied: run cleanup (vault-executor)

2. Scan inbox for *_suggestions.md files
   → Read each, check for [x] Approved
   → If approved: run Pass 2 (instruction-builder)

3. Scan inbox for source items without #<prefix>/captured tag
   → If any found: run Pass 1 (orchestrator)

4. Nothing pending → report idle state, exit
```

This makes `/inbox` idempotent and resumable.

## 6. Who Sets What

**Tomo sets:**
- `#<prefix>/captured` tag on source items (after Pass 1)
- `#<prefix>/active` tag on source items (during cleanup)

**User sets:**
- `[x] Approved` checkbox in suggestions document
- `[x] Applied` checkboxes in instruction set (per action)

**Nobody sets tags on workflow documents.** State is derived from checkboxes and filename patterns.

## 7. Tag Format

Tags follow the pattern: `#<prefix>/<state>`

Only two states exist:
- `#MiYo-Tomo/captured`
- `#MiYo-Tomo/active`

Prefix is configurable via `lifecycle.tag_prefix` in vault-config.yaml. State names are fixed.

Tags are **replaced**, not accumulated. When `captured` → `active`, the old tag is removed and the new one added. A source item has exactly one lifecycle tag at any time.

## 8. Edge Cases

**User checks `[x] Approved` on suggestions before reviewing:**
- Tomo proceeds to Pass 2 (takes user at their word)
- If instructions look wrong, user deletes them and unchecks Approved

**User checks some but not all `[x] Applied` on instructions:**
- vault-executor asks user about partially-applied items
- Fully-applied source items → `active`
- Partially-applied source items → stay `captured`, user decides

**User deletes a suggestions doc:**
- Source items are orphaned (tagged `captured` but referenced nowhere)
- They won't be re-processed because they have the `captured` tag
- User can manually remove the tag to re-process

**Partial failures in cleanup:**
- If Tomo fails to tag some items as `active`, it logs failures and leaves them as `captured`
- Next `/inbox` run retries cleanup (idempotent)

## 9. Discovery Queries

| Operation | Method |
|-----------|--------|
| Find fresh inbox items | `listDir` inbox → filter files without `#<prefix>/captured` frontmatter tag |
| Find approved suggestions | `listDir` inbox → filter `*_suggestions.md` → read → check `[x] Approved` |
| Find instruction sets with applied actions | `listDir` inbox → filter `*_instructions.md` → read → count `[x] Applied` |
| Count processed items | `kado-search byTag #<prefix>/active` |
