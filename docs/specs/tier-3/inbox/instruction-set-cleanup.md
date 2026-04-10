# Tier 3: Instruction Set Cleanup

> Parent: [Inbox Processing](../../tier-2/workflows/inbox-processing.md)
> Status: Draft
> Agent: `vault-executor` (cleanup scope only in MVP)
> Related: [Instruction Set Apply](instruction-set-apply.md) · [State Tag Lifecycle](state-tag-lifecycle.md)

---

## 1. Purpose

Define what `vault-executor` does during the cleanup phase of inbox processing. This is the **only write operation Tomo performs outside the inbox folder in MVP** — and even then, only lifecycle tag updates on processed inbox items. All content changes are user-applied.

## 2. Scope Clarification (MVP vs Original Design)

**Original architecture** (before execution model decision): `vault-executor` was planned to perform ALL vault writes — create notes, modify MOCs, update daily notes.

**MVP scope** ([per §7 Execution Model](../../tier-1/pkm-intelligence-architecture.md#7-execution-model)): `vault-executor` only handles **inbox-side state**:
- Tagging processed inbox items as `#MiYo-Tomo/active`
- Tagging completed suggestions/instructions docs as `#MiYo-Tomo/archived`
- Optionally moving processed inbox items to an archive subdirectory within the inbox folder
- Optionally deleting auxiliary files (rendered notes and diffs) that the user has already moved

It does **not** write content to atomic notes, MOCs, daily notes, or anywhere outside the inbox folder.

**Post-MVP:** Seigyo takes over the content write operations. `vault-executor` remains responsible for inbox-side state in both MVP and post-MVP.

## 3. Trigger

Runs when `/inbox` detects one or more `#MiYo-Tomo/applied` instruction set documents. The run-to-run state machine checks for applied instructions first, before confirmed suggestions or captured items — cleanup finishes the previous cycle before starting a new one.

## 4. Inputs

| Input | Source |
|-------|--------|
| `#MiYo-Tomo/applied` instruction set(s) | `kado-search byTag` in the inbox folder |
| Source inbox items | Referenced by each instruction set (via wikilinks in actions) |
| Auxiliary files | Rendered notes and diffs linked from the instruction set |
| vault-config | Inbox folder path, lifecycle prefix, archive preferences |

## 5. Automated Applied Detection (Optional)

Before requiring the user to manually tag instruction sets as `#MiYo-Tomo/applied`, Tomo can **auto-detect** whether actions have been applied:

| Action type | How to detect |
|-------------|---------------|
| New note (file was in inbox) | File no longer exists in inbox → user moved it. Or: file exists at target location (check via `kado-search byName`). |
| MOC link addition | Read the target MOC, check if the link text exists in the expected section. |
| Tracker update | Read the daily note, check if the tracker field has the proposed value. |
| Note modification (diff) | Read the target note, check if the expected "after" content is present. |

**Behavior:**
- If ALL actions in an instruction set are confirmed applied by auto-detection → auto-transition to `#MiYo-Tomo/applied`
- If some are applied but not all → report status, ask user: "3 of 5 actions detected as applied. Mark as complete?"
- If divergence found (file exists but content differs from expectation) → flag for user review, don't auto-apply

**Config:** `lifecycle.auto_detect_applied: true | false` (default: `true`). If disabled, Tomo waits for the user's manual tag change as before.

This auto-detection runs at the **start of every `/inbox` invocation**, before checking for fresh items. It reduces user friction — the user just does the work in Obsidian and runs `/inbox`; Tomo figures out what changed.

## 6. Process

For each applied instruction set (manually tagged or auto-detected):

```
1. Read the applied instruction set
   → Parse action entries
   → Collect referenced inbox items (source files)
   → Collect referenced auxiliary files (rendered notes, diffs)

2. Determine cleanup actions
   → Which checkboxes are checked (applied)
   → Which source items had at least one applied action → mark as active
   → Which source items had NO applied actions → leave as captured
   → Which auxiliary files still exist in inbox → candidates for removal

3. Apply cleanup (all writes via Kado, all inside inbox folder):

   a. Tag each "fully applied" source inbox item:
      - Remove #MiYo-Tomo/captured
      - Add #MiYo-Tomo/active

   b. Tag the instruction set itself:
      - Remove #MiYo-Tomo/applied
      - Add #MiYo-Tomo/archived

   c. Tag the linked suggestions document:
      - Remove #MiYo-Tomo/confirmed
      - Add #MiYo-Tomo/archived

   d. If configured: move tagged items to inbox archive subdir
      - Default: disabled (items stay in inbox folder with archived tag)
      - If enabled: move to +/archive/YYYY-MM/

   e. If configured: delete stale auxiliary files
      - Default: disabled (safer to leave them)
      - If enabled: kado-write delete (if Kado supports it) or flag for user

4. Report what was done
   → Items archived
   → Files moved (if any)
   → Files deleted (if any)
   → Any failures
```

## 7. State Tag Transitions Performed

| Document | Before | After |
|----------|--------|-------|
| Source inbox items (applied) | `#MiYo-Tomo/captured` | `#MiYo-Tomo/active` |
| Source inbox items (unapplied) | `#MiYo-Tomo/captured` | unchanged |
| Suggestions document | `#MiYo-Tomo/confirmed` | `#MiYo-Tomo/archived` |
| Instruction set document | `#MiYo-Tomo/applied` | `#MiYo-Tomo/archived` |
| Rendered new notes (auxiliary) | no tag (not typically tagged) | either left alone or deleted per config |
| Diff documents (auxiliary) | no tag | either left alone or deleted per config |

## 8. "Fully Applied" vs "Partially Applied"

A source inbox item can have multiple actions in the instruction set (e.g., "create note I01" + "update daily note I03"). The source is **fully applied** only if ALL its actions are checked.

**Rules:**
- Fully applied source → transition to `active`
- Partially applied source → **leave as `captured`**, warn user
- User can manually mark partially-applied as `active` if they want

**Rationale:** the inbox item represents the original thought. If only part of what Tomo proposed actually happened, the thought isn't fully integrated into the vault. Better to leave it as captured and let the user decide in the next `/inbox` run.

## 9. Archive Subdirectory (Optional)

If `lifecycle.archive_on_active: true` in vault-config:

```yaml
lifecycle:
  archive_on_active: true
  archive_path: "+/archive/YYYY-MM/"  # configurable — user chooses location
```

- Target subdirectory: user-configured `archive_path` with `YYYY-MM` date substitution
- Default if path not specified: `<inbox>/archive/YYYY-MM/` (e.g., `+/archive/2026-04/`)
- Items are moved via `kado-write` (file operation, not note content)
- Subdirectory is created if missing
- **The user is responsible for ensuring Tomo has write access** (via Kado's scope config) to the archive path. If archive path is outside the inbox folder, the user must add it to Kado's whitelist.

**Why optional:** some users prefer tags only, no file movement. Default is off. Tagging alone is always done.

## 10. Handling Auxiliary Files

Rendered new notes and diffs live in the inbox folder. After the user applies the actions (moves them or applies the diffs), the files might still be in the inbox:

- **Rendered note not moved:** user probably forgot or decided to skip. Leave it alone; tag it as `#MiYo-Tomo/archived` to stop it from appearing in fresh scans.
- **Diff file still there:** diffs are consumable once — user read them and applied the change. Safe to tag as archived.
- **Files the user moved to the correct location:** they're no longer in the inbox at all; nothing to clean up.

**Config option:** `lifecycle.delete_auxiliary: false` (default). If `true`, Tomo deletes auxiliary files that are still in the inbox after cleanup (cautiously — only files Tomo generated itself, identified by being referenced from the archived instruction set).

## 11. Error Handling

- **Source inbox item missing (deleted by user):** log, skip, continue
- **Instruction set parse error:** log, skip that instruction set, continue with others
- **Kado write failure:** log the specific failure, continue with remaining operations (don't abort the whole cleanup)
- **Orphaned auxiliary file not referenced anywhere:** log as warning, leave alone
- **Multiple instruction sets for the same source items:** process in order, first wins the `active` transition; later ones find the source already tagged and skip

## 12. Idempotency

Cleanup is idempotent — running it twice on the same applied instruction set is safe:
- Second run finds the instruction set already tagged `archived` → no action
- Second run finds source items already tagged `active` → no action
- Second run finds suggestions already tagged `archived` → no action

The only way to "re-clean" is for the user to manually reset tags. That's by design.

## 13. Interaction with Fresh `/inbox` Runs

After cleanup completes, the same `/inbox` invocation continues to the next state-machine check:
1. ✅ Applied instructions → cleaned up (just done)
2. Are there confirmed suggestions? → Run Pass 2 if any
3. Are there fresh captured items? → Run Pass 1 if any

So a single `/inbox` invocation can clean up yesterday's cycle AND start a new one, if all the states are present.

## 14. Logging and Reporting

Cleanup reports to the user via the CLI output:

```
📦 Cleanup completed
   Processed instruction set: 2026-04-08_1435_instructions.md
   Archived suggestions doc:  2026-04-08_1430_suggestions.md
   Source items marked active: 4
   Source items left captured (partial): 1
   Auxiliary files left alone: 5
```

Plus any warnings or errors inline.
