# 2026-04-15 — Inbox Fan-Out Refactor (spec 004)

## Summary

Replaced the monolithic Pass-1 `/inbox` flow (`inbox-analyst → suggestion-builder`)
with a map-reduce fan-out pipeline coordinated by a new `inbox-orchestrator`
agent. Each item is now processed by a dedicated `inbox-analyst` subagent
with minimal context; up to 5 run concurrently. A reducer
(`suggestions-reducer.py`) assembles per-item results into the final
Suggestions document which the orchestrator writes via `kado-write`.

## Why

- Context budget blew past 200K on ~50-item inboxes, forcing 1M-context
  (Claude Max) as a hidden requirement.
- Symptoms: Bash heredoc parser-aborts on final writes, hallucinated tool
  availability (claiming `kado-write` missing), example-bleed-through on
  small batches.
- Refactor target: runs reliably on standard Claude context, resumable on
  interrupt, failures localised to individual items.

## Changes

### New files

- `tomo/.claude/agents/inbox-orchestrator.md` — Pass-1 coordinator
- `scripts/shared-ctx-builder.py` — Phase A: distil discovery cache + profile + vault-config
- `scripts/state-init.py` — Phase A: enumerate inbox, seed state-file
- `scripts/state-update.py` — Append-only state-file writer
- `scripts/suggestions-reducer.py` — Phase C: aggregate + cluster + render
- `tomo/schemas/*.json` — JSON schemas for shared-ctx, state-entry, item-result, suggestions-doc
- `scripts/test-004-phase{2,3,4}.sh` — Acceptance tests per plan phase
- `docs/XDD/specs/004-inbox-fanout-refactor/` — Spec (PRD + SDD + 5-phase plan)

### Modified files

- `tomo/.claude/agents/inbox-analyst.md` → v0.5.0: per-item subagent with
  strict IO contract (reads 1 item, writes 1 `result.json`, updates state).
  Tools list narrowed — `kado-write` removed (subagents never write to vault).
- `tomo/.claude/commands/inbox.md` → v0.4.0: Pass-1 dispatches to orchestrator.
- `tomo/.claude/rules/project-context.md`: agent table updated, new rules
  against Bash heredoc and `; echo "EXIT:$?"` tails.
- `tomo/.claude/skills/pkm-workflows.md`: Pass-1 action refers to orchestrator.
- `tomo/config/vault-example.yaml`: new `tomo.suggestions.{proposable_tag_prefixes, excluded_tag_prefixes, parallel}` section.
- `scripts/install-tomo.sh`: copies `profiles/` + `schemas/` into instance,
  creates `tomo-tmp/items/`.
- `scripts/update-tomo.sh`: retires `suggestion-builder.md`, copies profiles +
  schemas, ensures `tomo-tmp/items/` exists.
- `README.md`, tomo-instance mirror files.

### Retired files

- `tomo/.claude/agents/suggestion-builder.md` — format rules migrated into
  `inbox-orchestrator.md` (Classification Guard, anti-parrot, wikilink rules,
  per-item section format).

## Decisions (locked)

All 8 ADRs confirmed:

1. New `inbox-orchestrator` agent
2. Reuse `inbox-analyst` as per-item subagent (tool-scope tightened)
3. Filesystem-based coordination via `tomo-tmp/`
4. Orchestrator-driven batching (3-5 concurrent)
5. Inline errors in state + result JSON
6. `schema_version: "1"` on all scratch artefacts
7. Merge `suggestion-builder` into `inbox-orchestrator`
8. Polymorphic per-item `actions[]` (atomic + daily-update simultaneously)

See `docs/XDD/specs/004-inbox-fanout-refactor/` for full rationale.

## Migration

For existing instances: run `bash scripts/update-tomo.sh`. It retires the old
`suggestion-builder.md`, copies the new `profiles/`, `schemas/`, new scripts
and agents, and ensures `tomo-tmp/items/` exists.

## Validation

- `scripts/test-004-phase2.sh`: 6/6 pass (shared-ctx, state-init)
- `scripts/test-004-phase3.sh`: 9/9 pass (state-update, reducer, format rules)
- `scripts/test-004-phase4.sh`: 6/6 pass (tracker_fields, multi-action, daily-disabled guard)
- Real-vault dry run: 82 MOCs + 22 tracker fields distilled into 15.35 KB
  (under the 15 KB target after topic shortening).

Remaining validation requires a full live `/inbox` run against the user's
real inbox — pending the first post-migration session.
