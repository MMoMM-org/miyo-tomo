---
from: tomo
to: kokoro
date: 2026-04-15
topic: Inbox Pass-1 refactored to fan-out — Kokoro architecture docs need updating
status: done
status_note: 5 tier specs updated with fan-out refactor (2026-04-15 banners + surgical section updates): tier-1 Workflow Map + header; tier-2 inbox-processing Agents table rewritten + workflow diagram + header; tier-3 inbox-analysis per-item + item-result schema; tier-3 suggestions-document reducer+orchestrator producer model; tier-3 state-tag-lifecycle new §11 on ephemeral run-level state file. No Kokoro-side ADR mirrored — deferring unless architectural precedent is needed beyond Tomo's 8 ADRs.
priority: normal
requires_action: true
---

# Inbox Pass-1 refactored to fan-out — tier-1/2/3 docs need updating

## What Changed

Tomo shipped spec 004 (commit `be7a4b8` on `feat/inbox-handling-and-specs`).
Pass 1 of `/inbox` is no longer a monolithic `inbox-analyst → suggestion-builder`
pair. It is now a map-reduce fan-out:

- `inbox-orchestrator` (new agent, opus) coordinates three phases.
- **Phase A** — build `tomo-tmp/shared-ctx.json` (distilled discovery cache +
  profile + user config, ≤ 15 KB) + seed append-only `tomo-tmp/inbox-state.jsonl`.
- **Phase B** — dispatch 3-5 parallel `inbox-analyst` subagents (sonnet). Each
  reads ONE item via `kado-read`, writes one `tomo-tmp/items/<stem>.result.json`,
  updates the state-file.
- **Phase C** — `suggestions-reducer.py` aggregates per-item results, clusters
  cross-item `proposed_moc_topic` values into Proposed-MOC sections, then the
  orchestrator renders markdown and writes the final Suggestions doc via
  `mcp__kado__kado-write`.

`suggestion-builder` agent is **retired**. Its format rules (Classification
Guard, wikilink rules, anti-parrot rules, per-item section format) live in
`inbox-orchestrator.md`.

Per-item results now carry a polymorphic `actions[]` array. A single inbox
item can produce both `create_atomic_note` and `update_daily` simultaneously
(e.g. "morning run" → daily tracker + atomic note).

## Why

Pre-refactor, Pass 1 blew past 200K context on real-world inbox sizes (37+ items),
causing Bash heredoc parser aborts, tool-availability hallucinations, and
example bleed-through. Fan-out runs on standard Claude context (peak ~20K per
subagent, ~90K parallel), resumable via state-file, failures localised per item.

Cost comparison for a 37-item inbox: pre-refactor 1M-Opus run ~$15-75;
post-refactor ~$3-5 with Sonnet subagents + Opus orchestrator.

## Impact on Kokoro

Kokoro tier specs describe the old agent topology. Please update:

- `docs/specs/tier-1/pkm-intelligence-architecture.md` — `suggestion-builder`
  removed from Key Agents; add `inbox-orchestrator`; document the fan-out
  model as the canonical Pass-1 execution pattern.
- `docs/specs/tier-2/workflows/inbox-processing.md` — rewrite Pass 1 section:
  monolithic → fan-out. Reference `tomo-tmp/` state file and result JSONs as
  the persistence substrate.
- `docs/specs/tier-3/inbox/inbox-analysis.md` — analyst is now per-item; output
  shape is `item-result.schema.json` (Tomo-side), not narrative.
- `docs/specs/tier-3/inbox/suggestions-document.md` — document producer changes
  (reducer + orchestrator instead of suggestion-builder). Per-item sections now
  render per-action decision checkboxes (multi-action possible per item).
- `docs/specs/tier-3/inbox/state-tag-lifecycle.md` — lifecycle tags on source
  items are unchanged, but the run-level state-file is new. Consider a short
  section on the append-only `tomo-tmp/inbox-state.jsonl` as an ephemeral
  complement to the persistent lifecycle tags.

## Action Required

1. Update the five tier specs above to reflect the fan-out architecture.
2. Consider whether a Kokoro-side ADR is warranted (Tomo has 8 ADRs in
   `docs/XDD/specs/004-inbox-fanout-refactor/solution.md`; Kokoro may want to
   mirror the map-reduce-pattern decision at the architecture-tier level).
3. No API or data-format changes that affect other repos — this is a Tomo-
   internal execution-model change.

## References

- Tomo spec: `docs/XDD/specs/004-inbox-fanout-refactor/` (requirements.md,
  solution.md with 8 ADRs, plan/ with 5 phases)
- Evolution note: `docs/evolution/2026-04/2026-04-15_inbox-fanout-refactor.md`
- Commit: `be7a4b8` on `feat/inbox-handling-and-specs`
- JSON schemas: `tomo/schemas/{shared-ctx,state-entry,item-result,suggestions-doc}.schema.json`
