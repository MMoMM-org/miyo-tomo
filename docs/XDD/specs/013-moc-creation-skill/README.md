# Specification: 013-moc-creation-skill

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-05-07 |
| **Current Phase** | Implemented (T6.2 paused — blocked-by F-47) |
| **Last Updated** | 2026-05-20 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 8 features (6 Must / 2 Should), 35 Gherkin AC, 4 deferred-to-SDD questions |
| solution.md | completed | 9 ADRs (7 PRD-locked + 2 SDD-new), all confirmed; 1234 lines |
| plan/ | completed | 6 phases · 29 tasks · 9 parallel-eligible · TDD structure throughout |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-07 | Spec scaffolded from `docs/XDD/ideas/2026-05-06-moc-creation-skill.md` | F-43 brainstorm spec ready to enter PRD phase; #1 on Obsidian-power roadmap |
| 2026-05-07 | Workflow mode = Standard | Brainstorm spec already detailed; parallel fire-and-forget research is sufficient |
| 2026-05-07 | Action-payload split = Option A (query Kado at render time) | Keep `supporting_items` as flat string; `instruction-render.py` reads each child's note to extract existing `up::`. No schema change; cost = N extra Kado reads per MOC accepted |
| 2026-05-07 | Multi-MOC filename slug = top-confidence cluster | Single deterministic identity per proposal-doc; users review all clusters in body |
| 2026-05-07 | Hashi `create_moc` filename-collision = NEW Hashi-side change request | Spec records dependency; cannot find existing destination-exists guard in Hashi docs. PRD adds explicit Hashi requirement |
| 2026-05-07 | §7 proposal-doc shape = match existing live render | `### MOC01 — <Title>` + `- [ ] Accept` list-item form. Consistent with `RE_SECTION_HEADER` regex and inbox-suggestions UX. Drop `## 🔍` heading |
| 2026-05-07 | `tomo_skip_inbox_analysis` filter placement = Step 2b post-Kado-read | Step 0 placement impossible (frontmatter not yet read); Step 2b after Kado read is the natural seam |
| 2026-05-07 | `kado-read listDir` `.md` filter = client-side in `moc-discovery.py` | Kado has no `type=md` MCP filter; client-side `.md` suffix filter on `items[]` is sufficient. No new MCP tool needed |
| 2026-05-07 | `kado-search byTag` prefix-match = glob suffix `*` | `tag:topic/applied/zsh` → query `#topic/applied/zsh*`. Documented; no Kado change |
| 2026-05-07 | PRD complete — 35 testable AC, 0 clarification markers | All 7 locked decisions reflected; 4 questions explicitly deferred to SDD |
| 2026-05-07 | Squelch state = sidecar registry file `state/moc-squelch.json` | Bounded, fast lookup, no archive scanning. Topic-signature keyed |
| 2026-05-07 | Why-narrative = template-rendered structured fields | Deterministic, no LLM cost per cluster, easy to test |
| 2026-05-07 | SDD complete — 9 ADRs confirmed, MiYo Constitution L1/L2 satisfied | Architecture: additive 2-pass extension; new components: moc-architect agent, moc-discovery.py; extensions to suggestions-reducer/parser/render and inbox-analyst Step 2b |
| 2026-05-07 | PLAN complete — 6 phases, 29 tasks, 9 parallel-eligible | Phase 1 foundation+handoff (parallel-heavy); Phase 2 moc-discovery.py (sequential); Phase 3 producer surface (mostly parallel); Phase 4 consumer extensions (3 parallel); Phase 5 squelch wiring; Phase 6 integration+live+docs+launch gate |
| 2026-05-07 | Validation passed: 3 minor findings patched | (1) Perf timing assertions added to T6.1 (45s/25s/8s with 1.5× CI tolerance); (2) Hashi receipt protocol made explicit in T1.1 + T6.4 launch gate; (3) Kokoro reflection sub-step added to T6.3. Constitution L1 fully passes |
| 2026-05-20 | T6.5 fix: agent-side topic extraction (2-pass discovery) | Live-validation 2026-05-20: `phase2_extract_topics` crashed on real cache misses (T2.8 left `llm_client=None` TODO). Fixed via `--emit-phase1`/`--phase1-input` + topic-extract in moc-architect Step 4b. Range: `17d5a00` + `6e66d65`. See `feedback_mock_at_orchestrator_not_helper` memory |
| 2026-05-20 | T6.5.5 fix: agent kado-write transports proposal-doc to vault | Live-validation 2026-05-20: reducer wrote proposal-doc to container local fs, user couldn't find it in vault. Fixed via moc-architect.md v0.3.0 + `mcp__kado__kado-write` tool. Mirrors inbox-orchestrator Step C4. Commit: `42e4d99` |
| 2026-05-20 | T6.2 PAUSED — blocks on F-47 Tomo lifecycle tags | Live-validation surfaced architectural debt: `/inbox` Auto-Discovery uses listDir + 3 body-reads to detect file state; `tomo-moc-proposal-*` not in SKIP_SUFFIXES; suggestions/instructions use markdown-checkbox state not frontmatter tags. F-43 acceptance-flow can't be live-validated without first unifying file-discovery via byTag. New spec **017-tomo-lifecycle-tags** (F-47) takes the discovery + state refactor; F-43 T6.2 + T6.4 resume after F-47 ships |
| 2026-05-21 | Resume mapping refined against F-47 v1.2 phase structure | T6.2 (remaining 5 modes + Override + collision-guard) resumes after **F-47.P2** ships (unified byFrontmatter discovery — proposal-doc with `tomo.state=pending-accept` becomes discoverable); T6.4 (launch gate, accept-flow end-to-end) resumes after **F-47.P4** ships (bundled MOC-consumption — `create_moc` + N× child-relationship updates in one instructions doc). Earlier note said "after F-47 ships" without phase granularity. See `docs/XDD/specs/017-tomo-lifecycle-tags/solution.md` §Cross-Spec Coordination for the full coordination map across 012 / 013 / 015 / 016. |

## Context

F-43 — proactive MOC creation/proposal skill. Adds `/moc-propose` command with prefix-routed args (tag/folder/class/title/free-text/no-args). Reuses existing 2-pass pipeline + `create_moc`/`add_relationship` action schema; NEW `moc-architect` agent + `moc-discovery.py` script. Foundation for F-44 Garden-Audit, F-45 Weekly Review, F-46 Tag-Audit.

Source idea: `docs/XDD/ideas/2026-05-06-moc-creation-skill.md` (15 sections, 14 open questions deferred to PRD).

---
*This file is managed by the xdd-meta skill.*
