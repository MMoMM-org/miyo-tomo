# Specification: 047-review-chunked-read

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-11-22 |
| **Current Phase** | Ready |
| **Decomposition tier** | Incremental |
| **Model tier** | hard |
| **Last Updated** | 2026-11-24 |

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
| 2026-11-23 | T2.5 measured 2026-Q1 on the new stage: 0 over the ceiling; the bulk-import day 2026-01-19 (86 KB growth) makes `2026-W04a` 92.9 KB, over the 80 KB unit budget; context.json 86 KB in 4 files, mostly per-day `fields` | Measurement (owner go) |
| 2026-11-23 | Deviation from ADR-2: `UNIT_BUDGET` = 131,072 B (128 KB); `context.json` carries per-tracker aggregates (days with a value, min/max/mean, per unit) instead of raw per-day `fields` | Owner (recommended): fewest opus tokens, no special case for bulk days |
| 2026-11-23 | T3.2: one `previous/<kind>-<name>.json` per previous period (non-found files hold metadata only), as SDD Data Storage Changes says; the plan's "found only" applies to `sections` | Orchestrator; SDD governs |
| 2026-11-23 | A previous-note folder whose listing answers empty is `missing` ("no note found", no error tone), not `not-read`/`kado-none`; amends PRD F3-AC9, ADR-5, ADR-12. Accepted trade-off: a key denial that shows as an empty listing also reads "no note found" | Owner (recommended): spec 045 Rule 6, the dailies were read |
| 2026-11-23 | Model escalation: T4.1 sonnet → opus | Trigger: second review FAIL (nested `required` lists untested after the cap fix) |
| 2026-11-23 | Model escalation: T4.1 opus → opus@max | Trigger: second review FAIL at opus (pattern anchors `^`/`$` unguarded after the sweep) |
| 2026-11-23 | Known limitation accepted: the digest/carryover schema patterns use `$`, which in Python's `re` also matches before a final newline, so `"2026-03-30\n"`, `"s1\n"`, `"c1\n"` validate; dates and section keys are refused downstream (`days-mismatch`, `unknown-section`), carryover ids are only compared with each other | Orchestrator; no schema change |
| 2026-11-23 | An open carryover (pending/retry) at document write is not refused; it renders as carry-failed (`carry_failed` = found previous notes and carryover state not `passed`), wired in T5.4 | Orchestrator, after the T4.4 spec review: the SDD gate names units only; no silent drop of the top line (F6-AC2) |
| 2026-11-23 | T5.2 deviation (owner, choice A): `Sources`, `Resolved`, `resolve_sources`, `note_stem` and the child-mark constants move to new `lib/review_sources.py` 0.1.0; `review_doc` re-exports them | `lib/review_doc.py` reached 493 lines against the ≈ 470 cap (CON-5) before T5.4's carried branch; the resolver is the natural seam and `review_carried` imports it from a small module. `review_doc` 412 lines |
| 2026-11-23 | Owner: the German top-line wording proposed in T5.2 is kept ("Letzter Rückblick · …: gefunden, n übernommen", "keine Notiz für X gefunden", "…notizen sind nicht eingerichtet", "nicht gelesen: Kado hat sie verweigert / nicht geliefert", "Nicht verdichtet", "Die letzten Rückblicke konnten nicht berücksichtigt werden.") | Top lines follow `review.language` like every fixed line (spec 045: DE/EN, English otherwise); only shown in German reviews; may be revised in the Phase 9 walk |
| 2026-11-24 | T5.4 (owner): the shared fixture carryover (`tests/review_privacy_fixture.py`) has no items by default ("found, nothing carried"); an opt-in adds one item plus a matching carried proposal, used by the privacy walk and the carried-write tests | F4-AC1 coverage correctly refused every walk (`carried-missing`) because the fixture carried items no proposal listed; default-empty keeps the baseline counts and links, the opt-in keeps the privacy marker in `carryover.json` and one carried item end to end |
| 2026-11-24 | T5.4 (owner): plan deviation, the T8.1 mechanism is brought forward: `test_047_baseline_e2e` compares with `allowed={"top_lines"}` from Phase 5 on; goldens stay byte-identical, every other key strict | The previous-note top lines (T5.2) are an ADR-11 allowed difference; keeping the test strict until Phase 8 would leave Phases 5–7 without a green suite gate |
| 2026-11-24 | T5.4 (owner): F6-AC2 partial case wording, a found previous note whose carry failed reads EN "found, not taken into account" / DE "gefunden, nicht berücksichtigt" | Same pattern as the other top-line states, no error tone; closes the gap that no state named a note whose carry failed |

## Context

Brainstorm: `docs/XDD/ideas/2026-11-22-review-chunked-read-and-previous-reviews.md`. Predecessors: spec 045 (weekly/monthly `/review`), spec 046 (template sections, quarter reviews; its close-out records the quarter Pass 1 running on partial reads). Related: #259 (skill trim, afterwards).

---
*This file is managed by the xdd-meta skill.*
