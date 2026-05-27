# 2026-05-21 — F-47 Privat-Test Inbox Reset Procedure

**Context**: F-47 Phase 3 (consumer cut-over) ships byFrontmatter-first discovery and the new state-promoter. Per ADR-6 and locked OQ4, the Privat-Test inbox must be wiped before any live `/inbox` run on the new code path — there is NO backward-compat for the legacy state-init body-read path.

**Status**: **DEFERRED — operator action required.** This procedure cannot run from inside the Tomo container or the Claude Code orchestrator session. The operator must perform steps 1-4 manually in Obsidian.

---

## Why this matters

After Phase 3 merges:

- `/inbox` Phase A relies on `tomo.state=*` frontmatter on every Tomo-managed doc.
- Legacy state-init.py is deleted.
- Pre-Phase-3 docs in the Privat-Test inbox carry no `tomo:` block — they're invisible to the new discovery.
- A clean wipe + fresh-run is the only way to validate the new pipeline end-to-end without untangling legacy state.

---

## Procedure (operator-side)

1. **Backup** the current Privat-Test inbox contents:
   ```bash
   mkdir -p ~/tmp/F-47-prereset-$(date +%Y%m%d-%H%M%S)
   cp -R "/Volumes/Moon/Coding/MiYo/temp/Privat-Test/100 Inbox/." "~/tmp/F-47-prereset-$(date +%Y%m%d-%H%M%S)/"
   ```
   *(adjust path if the actual Privat-Test inbox folder differs — see `reference_test_vault_path` in memory)*

2. **Trash via Obsidian (NOT `rm`, NOT `git rm`)**:
   - Open Obsidian → Privat-Test vault.
   - Navigate to `100 Inbox/`.
   - Multi-select all `.md` files → right-click → "Move to system trash" (or use Obsidian's trash setting).
   - **Reason**: Obsidian rebuilds its metadata cache when files are moved through its UI. Using `rm` or `git rm` leaves stale entries in `.obsidian/cache` and Kado may return ghost hits on the next byFrontmatter query.

3. **Drop 2-3 fresh source notes** into `100 Inbox/`:
   - Either drag-drop from Finder OR create new notes inside Obsidian.
   - Vary the content (one with frontmatter `tags:` array, one without, one with a body link to a non-existent target).
   - Do NOT add `tomo.state=*` manually — these must look like untagged fresh sources.

4. **Run smoke**:
   - Launch Tomo: `./begin-tomo.sh`.
   - In the container: `/inbox`.
   - Capture stderr to a file: `/inbox 2> /tmp/F47-P3-smoke-stderr.log`.

## Expected smoke output

- `lifecycle.discovery` event in stderr with: `pendingApproval=0, pendingAccept=0, pendingApply=0, captured=0, newSources=2-3, drift=false`.
- Phase A2.5e loop runs zero iterations (no pending docs).
- Phase B (Pass-1) fans out for the new sources.
- Final inbox state:
  - 2-3 `<ts>_<stem>_suggestions.md` files with `tomo.doc_type=suggestions, tomo.state=pending-approval`.
  - Original 2-3 fresh source files now carry `tomo.doc_type=source, tomo.state=captured`.
- No errors, no exit code != 0.

## What this validates

- T3.1 inbox-discovery.py: 4 byFrontmatter calls (zero pending hits expected) + 1 listDir.
- T3.2 state-promoter.py: not exercised (no pending docs to flip).
- T3.3 inbox-orchestrator Phase A2.5b/c/d/e: discovery → parse → drift-quiet → empty loop.
- T2.1 mark-captured.py: triggered on each fresh source via the existing Phase B Pass-1 flow.
- T2.2 suggestions-render.py: triggered for each fresh source's resulting suggestions doc.

## Follow-up (separate session)

After the smoke clean-runs, the operator can validate the **mixed-state scenario** by:

1. Manually place 1 pending-approval suggestions doc (handcrafted YAML or from a prior run's backup) in the inbox.
2. Tick `- [x] Approved` in its body.
3. Re-run `/inbox`.
4. Expected: A2.5e picks up the pending doc, dispatches instruction-builder, flips state to `approved`, then proceeds with any new sources.

This second pass exercises T3.2 flip_state + the sequential loop in T3.3.

---

## Trace location

After smoke runs, the stderr trace lives in `/tmp/F47-P3-smoke-stderr.log` (operator's choice — adjust path). Forward findings (especially any `lifecycle.transition_rejected` events or non-zero exit codes) to a follow-up task in `_outbox/for-claude/` for Claude to triage on the next session.

---

## References

- `docs/XDD/specs/017-tomo-lifecycle-tags/solution.md` ADR-6 (clean cut-over rationale).
- `docs/XDD/specs/017-tomo-lifecycle-tags/requirements.md` §8 Assumptions ("Privat-Test vault reset is acceptable").
- `docs/XDD/specs/017-tomo-lifecycle-tags/plan/phase-3.md` T3.5 (this procedure).
- Memory: `reference_test_vault_path` (Privat-Test location).
