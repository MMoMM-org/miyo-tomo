# Specification: 041-plugin-eval-gate-for-runtime-prose

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-25 |
| **Current Phase** | Ready |
| **Decomposition tier** | Incremental |
| **Last Updated** | 2026-10-25 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | v1.1; 7 Must, 1 Should, 1 Could; 35 acceptance criteria |
| solution.md | completed | v1.1 (plan-review fixes); 8 components, ADR-1…ADR-10 confirmed 2026-10-25; 35 EARS criteria, 1:1 with the PRD |
| plan/ | completed | 5 phases, 19 tasks (4 parallel); plan-review findings folded in |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-24 | Manifest generated at eval time (e.g. `scripts/run-evals.sh` assembles a plugin dir from `tomo/dot_claude/` + `evals/`); no permanent `.claude-plugin/plugin.json` | Owner decision on #174. Runtime tree stays single-purpose, `install-tomo.sh` / `update-tomo.sh` untouched; no cross-component interface, so no Kokoro ADR. |
| 2026-10-25 | Start with PRD; research mode Standard (3 parallel agents: eval tool, runtime targets, repo integration) | Owner choice. |
| 2026-10-25 | Spike artifacts archived to `spike/` | They existed only in an ephemeral session scratchpad; they seed the first cases. |
| 2026-10-25 | Suite lives in top-level `evals/` | Not synced by install/update (both copy only named `tomo/dot_claude/` subdirs); keeps `tomo/` runtime-only. Never under `tomo/dot_claude/skills/<name>/`, which both scripts sync recursively. |
| 2026-10-25 | Gate = manual run + documented rule: a change to an evaluated runtime file runs its cases before merge, result recorded in the PR | Owner choice. No CI exists; a pre-push hook would spend money and network on every push. |
| 2026-10-25 | First cases: conductor ordering, STRICT stop on audit mismatch, withheld-notice relay, plus a `not_contains` leak guard (run_id, action ids, guard names) on `last_message` in every case | Owner choice; the leak guard covers the `836602c` defect class at no extra run cost. |
| 2026-10-25 | Verdict: green only if every grader passes in all 3 runs (threshold 1.0); partial / API error / rate limit = "not graded", never green | Owner choice. A STRICT rule that holds 2 of 3 runs is a real defect. |
| 2026-10-25 | Main session model pinned; subagents keep their frontmatter model | Owner choice: test the production model mix. Whether `--model` overrides an agent's `model:` is undocumented — verify in SDD. |
| 2026-10-25 | Coverage list in `evals/` + always run the full suite | Owner choice; selection by diff is YAGNI at ~4 cases (~$1.20/run). |
| 2026-10-25 | Every gate grader proven red against a named mutation (pre-fix commit or deliberate mutation), recorded in close-out; control graders exempt | Owner choice; a grader never seen failing proves nothing. |
| 2026-10-25 | Cost cap $5 per invocation by default, overridable per invocation | Owner choice; ~4× the estimate, stops runaway loops. |
| 2026-10-25 | Cases run against stubbed scripts; no stub↔script contract check | Owner choice over a contract check; drift recorded as a known risk / Won't Have. |
| 2026-10-25 | A `main` that is not 3/3 green is fixed within 041 (prose fix, version bump, instance sync, deviation recorded) | Owner choice over record-and-follow-up; brings covered runtime prose into scope conditionally. |
| 2026-10-25 | Feature 5 covers both relay files (`withheld-deletes.md` and `withheld-attachments.md`) in one case | Owner choice; same STRICT rule, same run. |
| 2026-10-25 | Cite `docs/XDD/backlog.md:1007-1022` for the untestable-layer finding, not the spec 036 close-out | Research: the close-out does not contain the passage #174 quotes. |
| 2026-10-25 | PRD v1.0 approved; continue to SDD | Owner approval. |
| 2026-10-25 | SDD verification spike (~$0.73): `--model` sets the main session only; scaffold `$0` is its real path; `match: contains` valid; `main` 6/6 green on ordering + STRICT stop, **not** green on the relay (trailing `Files used:` block 1/3, run id in the report) | Owner-approved spend; archived in `spike/3-sdd-verification/`. Triggers the "fix within 041" decision. |
| 2026-10-25 | Leak guard also bans absolute paths and internal working-file names; PRD → v1.1 (F6-AC1) | Owner choice; ADR-11 (no executor internals in user-facing text). |
| 2026-10-25 | Main-session model = `tomo/dot_claude/settings.json` `model` (sonnet) | Production value; verified agents keep their frontmatter model. |
| 2026-10-25 | SDD v1.0: ADR-1…ADR-10 confirmed (TMPDIR assembly + --rev; bash runner + Python verdict; shared stub kit; real output formats; canonical leak guard + bait; model from settings.json; mutation patches; exit 0/1/2/3; outside the Bash sandbox; conductor Step 4 STRICT fix, 0.23.0 → 0.24.0) | Owner confirmation. |
| 2026-10-25 | Decomposition tier: Incremental | Classifier recommended Incremental (rule 1: 7 Must features, 7 new components; no parallel markers). Accepted. Hard ordering: gate → red baseline → C7 fix → regenerate mutations → RED proofs → 3× green close-out. |
| 2026-10-25 | Plan v1.0: 5 phases, 19 tasks; independent plan review (2 blocking, 11 should-fix) folded into plan + SDD v1.1 + PRD F7-AC6 wording; real eval results archived in `spike/results/` as fixtures | Review found fixtures without a source and tests writing into the real repo; both resolved by design, not by deferral. |
| 2026-10-25 | Specification finalized; readiness HIGH | PRD, SDD, plan complete; all ADRs confirmed; 35/35 criteria traced to tasks. |
| 2026-10-25 | Phase 1 complete | Runner, verdict reader, stub kit, sync guard; drift fixes (fixture sanitising, `--cost-cap`, rev SHA); $0.06 spent. |
| 2026-10-25 | ADR-10 widened to one report-level STRICT | Baseline (`baseline.md`, RED, $0.64) showed three failure modes the first scope missed: RESULT line paraphrased, render stderr with action ids/guard names quoted, headings between relay lines. Owner chose one STRICT over two, and over iterating on the narrow rule. |
| 2026-10-25 | Failed-step line names the note | Code review: with several docs, `<step> exited <code>.` could not say which doc failed. Owner chose to fix in 041: `<step> exited <code> for "<note>".`, note name only, never a path. |
| 2026-10-25 | Phase 3 complete | Conductor 0.24.0: full suite GREEN 9/9 on attempts 2 and 3; synced to tomo-instance only; phase spend $1.78. |
| 2026-10-25 | Phase 2 complete | Three cases (incl. a second F4-AC4 grader for copies), conductor-case tests split out; baseline recorded; phase spend $0.90. |

## Context

Issue #174: `claude plugin eval` as a gate for Tomo's LLM-read runtime prose (`tomo/dot_claude/{agents,skills,commands}`, `tomo/skills/`), which pytest cannot test. Two spikes (Claude Code 2.1.310) established: (1) an eval run reaches a plugin subagent and `tool_used` / `tool_order` see calls made inside it (`parent_tool_use_id`); (2) stubbed-script cases against `synthesis-conductor` go RED on `4350ddd^` and GREEN on `main`, and the conductor's STRICT stop under an audit mismatch was observed for the first time. Scope per owner: the `evals/` layout, the runner, and the first cases (conductor ordering, the STRICT stop, the withheld-notice relay) at `runs: 3`.

---
*This file is managed by the xdd-meta skill.*
