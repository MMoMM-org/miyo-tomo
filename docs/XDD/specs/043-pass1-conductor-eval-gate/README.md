# Specification: 043-pass1-conductor-eval-gate

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-30 |
| **Current Phase** | SDD |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Last Updated** | 2026-10-30 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | v1.0, 31 criteria (F1–F7) |
| solution.md | in_progress | draft v1.0; ADR-3, ADR-5, ADR-6 pending |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-30 | Next eval-gate target: the Pass 1 conductor (`agents/suggestion-conductor.md` plus the skills `suggest-handling` and `force-atomic-handling`) | Owner decision on #207. Regression history since 2026-09-01: 6 + 5 + 1 fix commits, the most of any file outside the gate. |
| 2026-10-30 | Stubbed scripts as in spec 041 (`evals/_lib/stubs.sh`); no Kado mocks | Owner decision on #207. All three files drive Tomo only through scripts. `inbox-analyst` (direct Kado MCP access) gets its own later spec. |
| 2026-10-30 | Same spec adds a "reply is only the report" grader for `synthesis-conductor`; it reads the conductor's Agent tool_result in the trace | Owner decision on #207. Input from #205: in 1 of 6 runs, conductor 0.24.1 wrote a status sentence around its report. |
| 2026-10-30 | Cost budget: about 3–4 new cases, roughly +$0.60–0.80 per full gate run | Owner decision on #207. Measured rate: $0.20 per case at 3 runs. |
| 2026-10-30 | Research (Standard mode, 3 agents). Findings: the Pass 1 conductor is IMPERSONATED, so the main session is the conductor, a case enters via `/tomo:inbox`, and `last_message` is its own report. 7 new script stubs extend `evals/_lib/stubs.sh`. `inbox-analyst` (direct Kado MCP) cannot be script-stubbed. Cost re-estimated at $0.45–0.90 per Pass 1 case (sonnet main session, ~15–18 turns), unmeasured. The report-only grader is feasible as a free `regex` on `target: trace` (`tool_use_result`), validated offline on the 12 #205 traces (3 red, 9 green) | Research synthesis. Open: subagent resolution in plugin eval, skill loading under impersonation, `trace` grader field coverage. |
| 2026-10-30 | Replace `inbox-analyst` with a stub AGENT (haiku, replies `done`) in Pass 1 cases | Owner decision. Keeps the dispatch regressions (`subagent_type`, `path = item_key`, `force_atomic`, count) gradeable. Extends the "stubbed scripts only" decision: still no Kado mocks. |
| 2026-10-30 | Measure before fixing the case count: the spike measures real Pass 1 case cost; then choose 2–4 cases and possibly raise the $5 cap | Owner decision; the estimate exceeds the original budget. |
| 2026-10-30 | Spike before the PRD (~$0.20–0.30, run by the owner outside the sandbox): stub-agent resolution, skill loading under impersonation, `trace` grader on `tool_use_result`, cost per Pass 1 case | Owner decision. |
| 2026-10-30 | Spike result ($0.296, `spike/write-up.md`): impersonation, stub-agent resolution (`tomo:inbox-analyst`, background dispatch) and skill loading all work. One Pass 1 run costs $0.21, about $0.75 per case at `runs: 3`. Script stubs must write plausible artifacts, or the conductor aborts before the end of the pipeline. Pattern A is red on 2.1.314, so the report-only grader uses pattern B plus the canary | Measured, not estimated. Owner picks the case count next. |
| 2026-10-30 | 2 Pass 1 cases: `pass1-suggest-pipeline` and `pass1-warn-and-duplicates-relayed`; about +$1.50 per gate run, within the $5 cap. `pass1-fan-resolve-real-path` is out of scope | Owner decision after the spike. This replaces the earlier +$0.60–0.80 budget. |
| 2026-10-30 | PRD v1.0 approved. `force-atomic-handling` is not gated in this phase because it has no case. If WARN-before-dispatch is RED, that is a finding, and the fix goes into the prose | Owner approved `requirements.md`. The phase moves to SDD. |

## Context

Issue #207 (extend the eval gate beyond `synthesis-conductor`), follow-up to spec 041 (`docs/XDD/specs/041-plugin-eval-gate-for-runtime-prose/`), PR #204 and #205.
The gate today: `evals/README.md`, `scripts/run-evals.sh`, the mutation and RED-proof discipline in `evals/_mutations/README.md`.

---
*This file is managed by the xdd-meta skill.*
