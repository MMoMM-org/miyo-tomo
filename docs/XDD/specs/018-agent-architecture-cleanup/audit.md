# Agent Architecture Audit — 2026-05-21

Snapshot of the current `tomo/dot_claude/{agents,commands}` and `tomo/skills/`
inventory ahead of the proposed cleanup refactor (XDD 018, not yet scaffolded).

The cleanup has two distinct goals:

1. **Collapse impersonation-only agents into their callers.** Agents that are
   never dispatched via the `Agent` tool are fiction — their `model: opus`
   declarations are dead, their existence forces the reader to follow a
   pointer indirection (command → agent.md → workflow). Where the consumer
   is 1:1, the workflow belongs inline in the command.
2. **Strip non-execution clutter from all surviving files.** Spec references
   (`F-47`, `XDD 012`, `ADR-6`), historical comments ("legacy", "deleted",
   "replaces", "shipped"), and version-history paragraphs are tech-debt
   inside execution files. Versions live in `# version:` comments;
   spec history lives in `docs/XDD/specs/`, `backlog.md`, and git log.

This document is the **working board** for the refactor — not a final spec.
Marcus marks files with HTML comments to indicate what should change; I
execute based on the comments, delete them, and verify with `git diff`.

---

## Dispatch classification

| Agent | Dispatched? | Real consumers (impersonation) | Recommended treatment |
|---|---|---|---|
| `inbox-orchestrator` | ❌ never | `/inbox` (1:1) | **MERGE into `/inbox` command + delete agent file** |
| `moc-architect` | ❌ never | `/moc-propose` (1:1) | KEEP — clean clutter only, defer merge (see note below) |
| `vault-executor` | ❌ never | `/execute` + `/inbox` (1:2) | KEEP — clean clutter only |
| `vault-explorer` | ❌ never | `/explore-vault` + `/tomo-setup` (1:2) | KEEP — clean clutter only |
| `inbox-analyst` | ✅ dispatched | `inbox-orchestrator` + `instruction-builder` | KEEP — clean clutter only |
| `instruction-builder` | ✅ dispatched | `inbox-orchestrator` + `/inbox` | KEEP — clean clutter only |
| `voice-transcriber` | ✅ dispatched | `inbox-orchestrator` | KEEP — already minimal |

> **Note on `moc-architect` deferral**: backlog F-44 (garden-audit), F-45
> (weekly-review), F-46 (tag-audit), F-48 (incremental cache) do not invoke
> moc-architect directly. The agent is 1:1 with `/moc-propose` today, so the
> merge would be safe — but the truly reusable artefacts (`moc-discovery.py`,
> `suggestions-reducer.py`) are already standalone scripts, so the agent
> file's only value-add is light orchestration glue. If a future feature
> (e.g. `inbox-analyst`'s `needs_new_moc=true` flow becoming active) ever
> wants to compose the same flow, having `moc-architect.md` as a discrete
> module is a small but real flexibility win. Deferring keeps that door open.

> "Real consumers" excludes `tomo-help.md` because it only documents agents
> (points at file paths), it does not impersonate them.

> `model: opus` on `inbox-orchestrator` is **inactive** — impersonated
> agents run in the parent session's model (Tomo = `sonnet`). The
> declaration will be removed when the workflow moves into `/inbox`.

## Clutter density

Lines of file, F-XX/ADR references, and historical comments. Sorted by
priority (highest clutter first).

| File | Lines | F-XX/ADR refs | History terms | Action |
|---|---|---|---|---|
| `agents/inbox-orchestrator.md` | 735 | 9 | 3 | **MERGE + delete** |
| `agents/instruction-builder.md` | 375 | 6 | 1 | Strip refs |
| `agents/inbox-analyst.md` | 550 | 4 | 1 | Strip refs |
| `commands/inbox.md` | 201 | 3 | 1 | Strip refs + absorb orchestrator merge |
| `agents/moc-architect.md` | 350 | 2 | 1 | **MERGE + delete** |
| `agents/voice-transcriber.md` | 299 | 1 | 0 | Strip 1 ref |
| `agents/vault-executor.md` | 129 | 0 | 2 | Strip history |
| `agents/vault-explorer.md` | 508 | 0 | 1 | Strip history |
| `commands/moc-propose.md` | 85 | 0 | 0 | Absorb moc-architect merge |
| `commands/explore-vault.md` | 24 | 0 | 0 | (clean) |
| `commands/execute.md` | 58 | 0 | 0 | (clean) |
| `commands/tomo-setup.md` | 271 | 0 | 0 | (clean) |
| `commands/tomo-help.md` | 225 | 0 | 0 | (clean — but update agent-list when files removed) |
| `skills/*` (all 7) | 96–272 | 0 | 0 | (clean) |

## Sample clutter lines (jump-points for review)

These are the lines you can mark up directly with HTML comments to request
removal or rewording.

### `agents/inbox-orchestrator.md`

```
 15  # version: 0.10.3 (F-52: voice-precheck.py guards voice-transcriber dispatch — ...)
 16  # state-init.py deleted (ADR-6). Steps A2.5b–A2.5e replace legacy A4.
100  ### Phase 0a — Voice transcription (conditional, XDD 009)
242  Step A2.5a — Media transcription stop-gate (T4.3 — F-47 Feature 5b):
281  # F-50 fix (branch i): when `transcribed == 0` ...
313  KNOWN LIMITATION — F-50 branch (iii) deferred: ...
316  strict reading). Proper fix tracked in backlog F-50 branch (iii) — ...
402  # "⚠ N captured notes have no associated workflow doc ..."
```

### `agents/instruction-builder.md`

```
 72  doc — XDD 012). If one exists AND its `[ ] Approved` checkbox is ticked
 87  ### Step 2.5 — FAN Resolve Subflow (XDD 012)
188  - `moc-proposal` — F-43 MOC-creation chain (upstream is a `...`)
189  - `suggestions-fan` — XDD 012 force-atomic chain (upstream is a `...`)
205  - NEVER add legacy lifecycle tags like `#<prefix>/instructions/pending-apply` —
206    F-47 v1.2 lock: state lives only in frontmatter `tomo.state`.
346  `state/moc-squelch.json` via F-43 squelch API. Script exits 0 even when
```

### `agents/inbox-analyst.md`

```
 37  FAN resolve subflow (XDD 012) when the user ticked Force Atomic Note
133  Condition C — Placeholder MOC trigger (Mental Squeeze Point §2.C, F-35).
190  `force_atomic=true` override (XDD 012). When the orchestrator passed
205  `shared_ctx.daily_notes.daily_log.date_sources`; if missing (legacy configs),
```

### `commands/inbox.md`

```
  2  # version: 0.8.0 (F-47 T4.1: --recover flag for drift recovery)
 51  `pending_fan_resolutions` (XDD 012 — force-atomic items ...)
 71  suggestions or instructions file was manually deleted mid-flow ...
118  `*_suggestions-fan.md` — XDD 012
```

## Refactor protocol (the workflow)

1. **Marcus marks up files** he wants me to clean. Use HTML comments:

   ```markdown
   <!-- TODO: remove this paragraph -->
   <!-- TODO: rewrite without XDD 012 reference -->
   <!-- TODO: keep but rephrase as "force-atomic override" -->
   ```

2. **I execute the marked changes** in one pass per file. I:
   - Apply the change the comment requests.
   - Delete the comment.
   - Bump the `# version:` if the file has one.

3. **Marcus deletes references he wants gone himself** — direct edits.

4. **I run `git diff`** after a batch to verify the result matches intent.
   Surface any drift to Marcus before committing.

5. **No commits without Marcus's explicit OK.** This is a multi-file
   surgical refactor; commits should be grouped sensibly (e.g., one per
   merged-and-deleted agent + its absorbing command).

## Suggested execution order

1. **Clutter strip across all 8 files with refs** (`voice-transcriber`,
   `vault-executor`, `vault-explorer`, `moc-architect`, `inbox.md`,
   `inbox-analyst`, `instruction-builder`, `inbox-orchestrator`). Smallest
   first to validate the pattern, biggest last. Independent of any merge.
2. **`inbox-orchestrator` → `/inbox`** (the big one, 735+201 lines). Only
   1:1 merge candidate without future-consumer ambiguity.
3. **Re-run audit** to confirm `F/ADR=0` and `history=0` across the board.
4. **Update `commands/tomo-help.md`** if the merged orchestrator file is
   deleted (the help-doc points at the file).

`moc-architect` merge deferred — see note above.

## Live test (deferred until file-by-file review is complete)

Commits already staged but NOT YET LIVE-TESTED:

- `2d92ff8` — `inbox-orchestrator.md` frontmatter `model: opus` → `sonnet`,
  `effort: xhigh` → `medium`. Aligns the agent's declared model with the
  actual workload (pure orchestration + dispatch, no deep reasoning).
- `d927b41` — `/inbox.md` Pass-1 flipped from impersonation to dispatch
  via `Agent` tool. Empirical test of the long-held "subagents can't
  spawn further subagents" assumption — `instruction-builder` already
  does this nesting successfully in production (Step 2.5).

**Test plan**: once Marcus has reviewed all remaining agent/command/skill
files and the per-file TODO sweep is complete, run a fresh `/inbox` on
Privat-Test. Observe:

- Does Pass-1 launch as a proper dispatched subagent? (visible in
  `tomo-home/.claude/projects/<project>/<sid>/subagents/` transcripts)
- Does Phase B fan-out (orchestrator → `inbox-analyst` × N) work, or
  does it fail with "Agent tool not available" / similar?
- Token-cost split: orchestrator subagent cost vs parent `/inbox`
  context, via `python3 scripts/measure-f47-token-cost.py --session-latest`.

**On success**: F-54 marked shipped, XDD 018 Phase 2 (inbox-orchestrator
→ /inbox merge) becomes obsolete — the agent file IS now the dispatched
subagent's spec, no merge needed. The architecture is cleaner without
the merge than with it.

**On failure**: `git revert d927b41` restores impersonation. The B commit
(`2d92ff8`) stays — sonnet is still the right model claim even when
impersonated. F-54 updated with the concrete failure mode so we know
what specifically about orchestrator-as-subagent breaks vs
instruction-builder-as-subagent working.

**Why deferred**: doing the test mid-sweep risks conflating "live-test
result" with "stale file state" if the orchestrator/analyst files still
have unprocessed review TODOs. Clean baseline first, then test.

## Open questions for Marcus

- Should the workflow live entirely inside the command file, or should
  `inbox.md` continue to reference shared instruction modules (e.g. the
  skill files like `pkm-workflows`, `lyt-patterns`)? Current proposal:
  inline the inbox-orchestrator workflow, keep skill references as-is.
- Do you want a formal XDD 018 spec scaffold (PRD → SDD → PLAN), or just
  iterate on this audit doc + per-file markup until done?
