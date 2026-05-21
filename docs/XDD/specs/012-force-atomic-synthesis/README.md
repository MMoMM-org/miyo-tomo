# XDD 012 — Force Atomic Note Synthesis

**Status:** ✅ DONE — shipped 2026-04-23 (commit `08a1f22 feat(force-atomic): synthesize atomics via resolve doc (XDD 012)`, merged via `301708f`)
**Current phase:** complete — all 6 plan/phase-1 tasks (T1 suggestion-parser, T2 inbox-analyst, T3 suggestions-reducer, T4 instruction-builder, T5 inbox.md, T6 tests) shipped; 2 test files added (`tests/test_suggestion_parser_fan_resolve.py`, `tests/test_suggestions_reducer_fan_resolve.py`)
**Backlog origin:** F-33 (matched: backlog says ✅ Done 2026-04-23 — README was stale until verified during F-47 SDD coordination 2026-05-21)
**Post-ship note (2026-05-21):** F-47 PRD v1.2 introduces a `tomo:` frontmatter block on every Tomo-produced workflow doc, including 012's `*_suggestions-fan.md`. F-47.P1's producer sweep extends 012's fan-doc renderer to emit the block. No 012-specific work needed — the change lands in F-47.P1 producer pass.

## Problem in one paragraph

Pass 2 honours a `- [ ] Force Atomic Note` checkbox on a log_entry only when
the analyst already proposed a per-item atomic-note section in Pass 1
(commit `2665f81`). When the analyst emitted nothing for that source (e.g.
worthiness below the threshold), the user's explicit Force-Atomic intent
has nowhere to go — the parser warns and skips. The user then has to
either lower the threshold and re-run full Pass 1, or hand-craft an atomic
note in Obsidian, or uncheck FAN. That breaks the promise of the FAN
checkbox.

## Solution in one paragraph

When Pass 2 sees a FAN log_entry without a matching atomic proposal, it
generates a **follow-up suggestions document** (`<date>_suggestions-fan.md`)
with a freshly proposed atomic for that source — produced by a mini-Pass-1
subflow that dispatches `inbox-analyst` with a new `force_atomic=true`
input that bypasses the worthiness gate. Pass 2 then halts without
rendering instructions. The user reviews the follow-up doc, approves the
atomic proposals there, and re-runs `/inbox`. The parser now sees BOTH
docs in the inbox, merges the approved atomics from the follow-up into the
original items, and renders instructions as a single unit. This keeps the
proposal-first principle (no silent synthesis), uses the existing approved-
checkbox UI without new controls, and costs a single extra LLM hop per
resolved item.

## Files

- [requirements.md](requirements.md) — product requirements (PRD)
- [solution.md](solution.md) — technical design (SDD)
- [plan/phase-1.md](plan/phase-1.md) — implementation plan

## Tracking

- Backlog entry: `docs/XDD/backlog.md` → F-33
- Branch: `feat/inbox-tagging-fixes` (catch-all for /inbox workflow fixes)
- Live trigger: 2026-04-23 /inbox Pass 2 run, "Furano" item
