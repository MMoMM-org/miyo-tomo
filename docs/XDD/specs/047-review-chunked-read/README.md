# Specification: 047-review-chunked-read

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-11-22 |
| **Current Phase** | SDD |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Model tier** | {{MODEL_TIER}} |
| **Last Updated** | 2026-11-22 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | v1.1 (2026-11-22): 8 features (F1–F7 Must, F8 Should), 56 criteria; validation fixes worked in |
| solution.md | in_progress | |
| plan/ | pending | |

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

## Context

Brainstorm: `docs/XDD/ideas/2026-11-22-review-chunked-read-and-previous-reviews.md`. Predecessors: spec 045 (weekly/monthly `/review`), spec 046 (template sections, quarter reviews; its close-out records the quarter Pass 1 running on partial reads). Related: #259 (skill trim, afterwards).

---
*This file is managed by the xdd-meta skill.*
