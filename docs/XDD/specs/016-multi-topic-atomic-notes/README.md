# XDD 016 — Multi-topic detection for atomic-note-worthy items

**Status:** PRD draft — 2026-05-07
**Current phase:** requirements.md (PRD)
**Backlog origin:** F-41 (Should)
**Triggering incident:** 2026-05-01 /inbox run, voice memo
`Apothekerpfädchen 11__2026-04-22 10-14-41.md` — 183-sec transcript with
two distinct threads (medical appointment + Tomo/PKM architecture);
analyst emitted only `update_daily`, the architecture thread was lost.

## Problem in one paragraph

A single inbox item can carry multiple conceptually distinct,
individually atomic-note-worthy threads. Today the analyst's Step 7
worthiness gate fires once per item and Step 8 emits at most one
`create_atomic_note` action — collapsing multi-thread items into a
single classification. The 2026-05-01 voice memo case made this acute:
a 183-sec memo combining a daily-log-relevant medical thread with an
atomic-note-worthy architecture thread emitted only the daily-log
action, losing the architecture thread completely. XDD 012 (Force
Atomic Note) recovers the single-thread case but still emits one
atomic per source.

## Solution in one paragraph

A new topical-segmentation phase between Steps 7 and 8 of the
inbox-analyst identifies distinct threads in an item (LLM-driven, with
a length pre-check to avoid penalising short items). Each thread gets
its own per-thread worthiness score and metadata; threads scoring
≥ 0.5 emit independent `create_atomic_note` actions with thread-scoped
title / MOC match / tags / source-stem provenance. Downstream cardinality
(suggestions-reducer, suggestion-parser, instruction-render) widens
from N=1 to N≥1 atomic per source. FAN resolve subflow respects this
expansion. Voice-transcript audio cleanup waits until all derived
atomics commit.

## Files

- [requirements.md](requirements.md) — product requirements (PRD), draft
- solution.md — technical design (SDD), pending
- plan/phase-N.md — implementation plan, pending

## Tracking

- Backlog entry: `docs/XDD/backlog.md` → F-41
- Triggering incident: 2026-05-01 voice memo Apothekerpfädchen 11
  (real failure, not synthetic)
- Branch when implementation starts: `feat/f-41-multi-topic-atomic-notes`
- Related specs: F-33 / XDD 012 (Force Atomic Note — workaround for
  the single-thread case); XDD 009 (voice-memo transcription —
  produces the multi-thread inputs that surface this gap most often);
  XDD 015 (MSP Condition B accumulation — adjacent inbox-analyst
  enhancement).
- Cost-budget constraint: ≤ 10% increase on Pass-1 main-thread cost
  (F-32 baseline ~$26/run on opus).

## Open questions before SDD

See requirements.md §8 (OQ1–OQ8). Tentative leans noted; stakeholder
input required before SDD locks the surface — particularly OQ4
(daily-log emission semantics in mixed-mode items) and OQ7
(length-precheck token budget).

## Notes

**F-47 schema requirement (2026-05-21):** Any new renderer this spec introduces that emits workflow documents (suggestions-fan, instructions docs, or similar pipeline outputs) MUST emit the `tomo:` block per `tomo/schemas/doc-frontmatter.schema.json` (F-47 Phase 1 SoT). Use `build_tomo_block()` from `tomo/scripts/lib/doc_frontmatter.py`. When this spec reaches SDD/plan phase, renderer-touch tasks must include "emits `tomo:` block per F-47 schema". See `docs/XDD/specs/017-tomo-lifecycle-tags/solution.md` §Data Models for the canonical field definitions.
