# Phase 5 — Validation + Migration

## Goal

Validate the refactor on the user's real inbox, retire the old
`suggestion-builder` agent, update docs, and lock in the new contract.

## Prerequisites

- Phases 1-4 complete
- User has a real inbox with ≥ 10 items (mixed: coding insights, quotes,
  potential tracker entries, one or two edge cases like malformed YAML)

## Acceptance Gate

- [ ] Full `/inbox` run on real inbox completes without aborting
- [ ] Resulting Suggestions doc format matches what the user reviewed in
  prior runs (same shape, tri-state checkboxes, Proposed MOC sections,
  Needs Attention section)
- [ ] Peak subagent context verified < 80K tokens via log inspection
- [ ] A deliberately interrupted run (Ctrl-C during Phase B) resumes
  correctly on re-invocation
- [ ] Zero references to `suggestion-builder` remain in `tomo/.claude/`
- [ ] No references to the old Phase-1 flow in `tomo/.claude/commands/inbox.md`

## Tasks

### 5.1 Retire `suggestion-builder` agent

- Verify `inbox-orchestrator.md` contains all format rules from
  `suggestion-builder.md` (Classification Guard, anti-parrot, wikilink
  rules, per-item section format, per-action decision checkboxes)
- Delete `tomo/.claude/agents/suggestion-builder.md` (and the instance copy
  if it exists)
- Grep for references: `grep -rn "suggestion-builder" tomo/ scripts/ docs/`
  — update or remove each hit
- Update `tomo/.claude/rules/project-context.md` agent table: remove
  `suggestion-builder` row, add `inbox-orchestrator` row

### 5.2 Update install/update tooling

- `scripts/install-tomo.sh`: ensure `tomo-tmp/items/` is created (Phase 1
  change); verify the new agents are copied into the instance
- `scripts/update-tomo.sh`: when the user updates from a pre-004 instance,
  remove `tomo-instance/.claude/agents/suggestion-builder.md` if present and
  install `inbox-orchestrator.md`
- Add a migration note to `docs/evolution/2026-04/`

### 5.3 Documentation updates

Files to touch:
- `tomo/CLAUDE.md.template` — Key Commands section: `/inbox` description
  still correct but reference the orchestrator flow if mentioned
- `tomo/.claude/commands/tomo-help.md` — topic-map entry for "/inbox"
  reflects the new two-stage-with-fan-out model
- `docs/XDD/reference/tier-2/workflows/` — update the 2-pass workflow diagram if it
  exists to show fan-out in Pass 1
- README.md — keep the user-facing description; add a note that `/inbox`
  now scales to 100+ items

### 5.4 Real-Inbox Validation

Run `/inbox` against the user's actual inbox (37+ items at time of writing).
Record:
- Wall-clock duration
- Peak context per subagent (from logs)
- Any items that went `failed` — root-cause each
- User reviews the Suggestions doc and reports quality vs pre-refactor runs

Document findings in `docs/evolution/2026-04/<date>_fanout-refactor-validation.md`.

### 5.5 Rollback Plan

If real-inbox validation fails catastrophically:
- Revert the commits for Phases 3-5
- Restore `suggestion-builder.md` from git history
- Keep Phase 1-2 scaffolding — harmless leftovers, ignored by old flow

## Tests

- [ ] `bash scripts/test-phase2.sh && bash scripts/test-phase3.sh &&
  bash scripts/test-phase4.sh` all pass
- [ ] `grep -rn "suggestion-builder" tomo/ scripts/` returns no hits
- [ ] Manual smoke test: user runs `/inbox`, approves, runs Pass 2
  (`/inbox` again), everything flows to `/execute` and the instruction set
  is applied successfully
- [ ] Evolution note written and committed

## Close

This spec (004) moves to `Ready`. Update `docs/XDD/specs/004-.../README.md`
Status to `Completed`, log the close-out decision in the decisions table.
