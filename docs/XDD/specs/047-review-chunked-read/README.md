# Specification: 047-review-chunked-read

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-11-22 |
| **Current Phase** | Ready |
| **Decomposition tier** | Incremental |
| **Model tier** | hard |
| **Last Updated** | 2026-11-23 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | v1.1 (2026-11-22): 8 features (F1–F7 Must, F8 Should), 56 criteria; validation fixes worked in |
| solution.md | completed | v1.1 (2026-11-23): 12 ADRs, all confirmed; validation fixes worked in; 56/56 criteria owned |
| plan/ | completed | v1.1 (2026-11-23): 9 phases, 44 tasks (11 parallel), all 56 criteria mapped; validation fixes worked in |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

**Model tier**: `routine` | `hard` | `frontier`. The classifier recommends it at the decomposition step and the user confirms it; leave the placeholder until then. `spec.py --read` treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-22 | Spec 047 scaffolded for #270 on branch `feature/270-redesign-the-quarterly-read-chunked-data`, from the brainstorm `docs/XDD/ideas/2026-11-22-review-chunked-read-and-previous-reviews.md` (commit `cb90d4e1`) | Owner picked #270 from the board; brainstorm approved by the spec reviewer |
| 2026-11-22 | Scope widened: reviews read the previous review notes (week → previous week + previous month; month → previous month + previous quarter; quarter → previous quarter); one pipeline for week, month and quarter | Owner, 2026-11-22 brainstorm |
| 2026-11-22 | Approach A: per-day files plus one digester per week (haiku), a carryover agent for previous notes (sonnet), one proposer (opus) | Owner chose A (quality before cost); B and C rejected, see brainstorm §3 |
| 2026-11-22 | The new read layout replaces `read.json` everywhere; a behaviour-baseline e2e for week/month/quarter is written first | Owner ("Neues Layout ersetzt alles") |
| 2026-11-22 | Hard condition: no read day missing from the proposals (`not_read` = 0), no grep fallback; cost/duration KPIs are guidance | Owner ("Qualität vor Kosten") |
| 2026-11-22 | Previous notes found via the setup folder + period format; an empty previous note is reported as `empty`; carried items appear once, with a from-previous mark | Owner brainstorm answers |
| 2026-11-22 | Research done (Standard mode, 4 perspectives on sonnet: technical, performance, integration+privacy, requirements+UX); findings in `research.md` | Key facts: one merged read dict feeds review-doc; ~1.85 chars/token; no Hashi/Kado handoff (marks are text in `content`, wire v4 unchanged); read files are deleted at write (ADR-9), not at deliver |
| 2026-11-22 | Week keeps the full pipeline (haiku digester, sonnet carryover, opus proposer); week Pass 1 KPI ≤ $0.80 (046) is guidance, est. $0.9–1.1 | Owner (recommended): one pipeline, quality before cost |
| 2026-11-22 | All stage files (days/, weeks.json, context.json, previous/, digests/, carryover.json, proposals.json) are deleted at `review-doc.py write` and on abort/drop, as today (ADR-9); stage resume only within Pass 1 before write | Owner (recommended): privacy contract unchanged; corrects brainstorm §4.4 |
| 2026-11-22 | Fourth previous-note state `not set up` (no folder/format for that kind): one line at the top, review continues | Owner (recommended) |
| 2026-11-22 | Mark labels short and generic: EN "done (previous review)" / "still open (previous review)" / "not mentioned again (previous review)"; DE "erledigt (letzter Rückblick)" / "noch offen (letzter Rückblick)" / "nicht mehr erwähnt (letzter Rückblick)"; the source link names the previous note | Owner (recommended) |
| 2026-11-22 | A week's previous month is the month before the month the week starts in (W14 from 2026-03-30 → February) | Owner (recommended), confirms brainstorm |
| 2026-11-22 | Digesters read only the period's days; the day after the period stays limited to yesterday fields | Owner (recommended) |
| 2026-11-22 | PRD v1.0 written (opus), validated (sonnet): NEEDS FIXES, 15 fixes (046 F6-AC5 uncovered, resume ambiguity, cap overflow, partial carry failure, leakage, open questions settled from existing decisions) | Validation pass |
| 2026-11-22 | Rerun of an interrupted Pass 1 continues on the stored read (no new Kado read), says so in one line with the read's time, condenses only what is missing; "start over" or a changed section mapping reads anew | Owner (recommended) |
| 2026-11-22 | PRD v1.1 approved; section-full rule: a carried item moves to the group of its mark, never dropped (F4-AC10) | Owner |
| 2026-11-23 | SDD v1.0 drafted (opus, 12 ADRs), validated (sonnet): NEEDS FIXES, 13 non-structural fixes (carried failures must not land in `rejected`, carried+child mark rule, ids vs sources subset, one cutter in review_day, shared source resolver, nested-write smoke test, opus rates $15/$75 in tomo-token-usage.py) | Validation pass |
| 2026-11-23 | ADR-1..ADR-12 confirmed with the fixes worked in; a full section: the script moves a carried item into the group of its mark; stage files written line-broken (indent=1, texts as line arrays), the 40 KB ceiling on that form; ADR-12 top-line wording accepted | Owner |
| 2026-11-23 | Decomposition tier: Incremental | Classifier recommended Incremental (change_type=feature; 7 Must features, 56 criteria; 8+ new components: review_stage, review_previous, review_carried, review_weeks, review-digest.py, 3 agents; parallel batch dispatch). Accepted. |
| 2026-11-23 | Model tier: hard (override) | Classifier recommended frontier (novel_pattern=true: manifest-last stage, agent output contract; high_risks=3). Owner chose hard, as for spec 046 (no fable; opus where design judgment is needed). |
| 2026-11-23 | Plan v1.0 (opus): 9 phases, 45 tasks; validated (sonnet): NEEDS FIXES, 10 local fixes (parallel overlaps T6.2/T6.3 and T5.1/T5.2, RED gap T2.4→T2.5, missing version bump, shifted cites, unmapped new test files) | Validation pass |
| 2026-11-23 | T2.4 and T2.5 merged into one task (read + loader switch in one commit); new test_review_*.py files go into spec 047's Directory Map by the task that creates them; code review = the per-task review chain of /implement, no extra phase review | Owner (recommended) |
| 2026-11-23 | Cost KPIs are a token-volume proxy for optimising, not real spend (owner on a subscription); goal: as few tokens as possible at the best quality | Owner |
| 2026-11-23 | Specification ready: PRD v1.1, SDD v1.1 (12 confirmed ADRs), plan v1.1 (9 phases, 44 tasks); readiness HIGH | Owner approved each phase |
| 2026-11-23 | T1.2 deviation accepted: the March content days for ISO W10/W12 exist only in the quarter vault (`build_vault(quarter=True)`), so the month 2026-03 read report stays unchanged; the quarter vault is the same for the old and the new flow | Orchestrator; keeps T1.2's "week/month outputs unchanged" rule |
| 2026-11-23 | T1.3: the quarter baseline runs with one mapped section (mark suffixes render only in mapped sections, so the mark-suffix RED proof can fail); week and month stay unmapped | Orchestrator; both layouts pinned |
| 2026-11-23 | T1.5 measured 2026-Q1 (454 calls, 0 retries, day max 8.3 KB, week max 46.7 KB indented — ADR-2 day/week limits hold); `growth.created` (746 notes, ~158 KB indented) is 4× the context ceiling | Measurement (owner go) |
| 2026-11-23 | Deviation from ADR-1/2/4: vault growth (created notes) goes per week unit to the digesters; `context.json` keeps growth counts and MOC changes only; the read report stays in `manifest.json`, not proposer input | Owner (recommended): fewest tokens for the opus proposer |
| 2026-11-23 | T1.4 smoke (headless in tomo-instance): nested agent write works under acceptEdits without pre-creation; Read returns 24–40.5 KB of word-like text whole but cuts a 41 KB poorly-tokenizing file at the 25k-token cap; Kado per-path denial is a FORBIDDEN tool error (KadoToolError), not 403 | Smoke checks (owner go) |
| 2026-11-23 | Deviation from ADR-2: FILE_CEILING = 32,768 bytes (was 40,960); ADR-5 catches KadoToolError FORBIDDEN for previous notes (not KadoAuthError) | Owner (recommended) / fact correction |

## Context

Brainstorm: `docs/XDD/ideas/2026-11-22-review-chunked-read-and-previous-reviews.md`. Predecessors: spec 045 (weekly/monthly `/review`), spec 046 (template sections, quarter reviews; its close-out records the quarter Pass 1 running on partial reads). Related: #259 (skill trim, afterwards).

---
*This file is managed by the xdd-meta skill.*
