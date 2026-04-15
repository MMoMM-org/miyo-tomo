# Specification: 004-Inbox Fan-Out Refactor

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-04-15 |
| **Current Phase** | Completed (all 5 plan phases) |
| **Last Updated** | 2026-04-15 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | WHAT + WHY for the refactor |
| solution.md | completed | Architecture and interfaces (8 ADRs confirmed) |
| plan/ | completed | 5 phases: scaffolding → Phase A → core fan-out → daily-updates → validation (incl. retirement) |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-15 | Fan-out architecture over monolithic processing | Context budget blows past 200K at ~50 items; 1M requirement would force Claude Max |
| 2026-04-15 | JSONL for state-file | Append-safe, resume-friendly |
| 2026-04-15 | 3-5 parallel subagents | Kado is bottleneck; higher parallelism buys nothing |
| 2026-04-15 | Shared-ctx destilled, not full cache | 75KB cache → ~10KB ctx per subagent |
| 2026-04-15 | MOC-creation stays in inbox flow | Two-layer: per-item flag + cross-item cluster at orchestrator |
| 2026-04-15 | Other notes NOT in shared-ctx | 4K notes = 80K tokens; on-demand via Kado if ever needed |
| 2026-04-15 | User-configurable proposable tag prefixes (default `["topic"]`) | `status/*`, `projects/*`, `type/*` etc. are structural; not user-proposable |
| 2026-04-15 | Polymorphic per-item `actions[]` | One item can produce atomic-note + daily-update simultaneously |
| 2026-04-15 | Merge `suggestion-builder` into `inbox-orchestrator` | After refactor, suggestion-builder has no independent logic |
| 2026-04-15 | Daily-note tracker handling as Plan Phase 4 | Layer on top of core fan-out; validate core first with atomic notes only |
| 2026-04-15 | All 5 phases implemented + tested (21/21 tests pass); suggestion-builder retired; evolution note written | See `docs/evolution/2026-04/2026-04-15_inbox-fanout-refactor.md` |

## Context

Rearchitect `/inbox` processing from a single monolithic agent holding all items +
discovery cache + intermediate results, into a fan-out pipeline:

- **Phase A (orchestrator):** build state-file + distilled shared-context
- **Phase B (subagents):** process one item each, in parallel, with minimal context
- **Phase C (orchestrator):** reduce per-item results into Suggestions document

Target: handle 100+ inbox items on standard 200K-context Claude without 1M requirement.

---
*This file is managed by the xdd-meta skill.*
