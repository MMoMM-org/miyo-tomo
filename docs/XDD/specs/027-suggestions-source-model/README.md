# Specification: 027-suggestions-source-model

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-06-30 |
| **Current Phase** | Implemented |
| **Last Updated** | 2026-06-30 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 5 Must-Have features, Gherkin ACs; F4 reconciled to hard-cutover |
| solution.md | completed | 5 ADRs; ADR-1/3/4 user-confirmed |
| plan/ | completed | 4 phases, 21 tasks; TDD; sequenced by dependency/risk |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-30 | Spec created on branch `feat/suggestions-ux-pass` | Issue #33 (F-42) Phase 1 = source-model unification; chosen full scope incl. breaking wire rename |
| 2026-06-30 | Scope split into 4 sub-pieces (a) UX unify (b) internal `keep_origin`→`keep_source` (c) BREAKING wire `origin_inbox_item` rename (d) audio-peer `.m4a` delete plumbing | Different risk tiers; (c)/(d) are cross-repo (Hashi) + constitution-gated |
| 2026-06-30 | PRD completed — 5 Must-Have features with Gherkin ACs | Locked decisions from issue #33 (2026-06-03); failure/denial cases per constitution L1 |
| 2026-06-30 | ADR-1 = additive `audio_peer` companion (not full `source_files[]` list) | Additive on hot path; `source_path` has 20+ consumers; voice is the only multi-file source |
| 2026-06-30 | ADR-3 = HARD CUTOVER (no dual-accept window); Tomo+Hashi deploy in lockstep | User: "Hashi will be in sync" — single operator deploys both. Supersedes PRD F4 backward-compat; migration = apply-pending-then-upgrade-both + Kokoro ADR + Hashi#41 handoff |
| 2026-06-30 | ADR-4 = two-box decision block (Approve + Keep source files); drop redundant "Skip" + per-atomic "Delete source" box | User feedback: un-approve IS skip; "keep in inbox/don't delete" is the real secondary intent; junk delete-only stays in skipped-items flow |
| 2026-06-30 | ADR-3 refined: bump instruction `schema_version` "1"→"2" as the cutover signal | User Q surfaced the existing version gate; `docs/instructions-json.md` requires Hashi to reject unknown versions → v2 doc on v1-only Hashi fails loud, making the lockstep window safe |
| 2026-06-30 | PLAN complete — 4 phases, 21 tasks, sequenced internal-rename → UX → audio-peer → wire-rename | Dependency/risk order; cross-repo breaking phase last; all 14 Gherkin ACs mapped; line refs alignment-verified (zero drift) |
| 2026-06-30 | Validation sweep (5-perspective /validate) — removed ~14 residual dual-accept/backward-compat/migration-window phrases from PRD+SDD; corrected ADR-2 analyst `source:` premise (analyst must ADD extraction); added multi-atomic + degraded fail-safe test cases (T3.3) | Hard-cutover (ADR-3) was confirmed but never swept through PRD/SDD bodies; alignment found the analyst does not currently read `source:`. PRD/SDD/PLAN now internally consistent with ADR-3; no L1 constitution violations |
| 2026-06-30 | Implementation complete (all 4 phases, TDD per task: tdd-guardian → spec-compliance → code-quality) | Shipped on `feat/suggestions-ux-pass`: keep_source rename, two-box UX + voice source set, audio-peer paired source-set deletion (orphaned-audio fixed), hard-cutover wire rename + schema_version "1"→"2". Suite 1843 passed/1 skipped/1 xfailed (upstream Hashi snapshot, pending Hashi#41 lockstep). Kokoro ADR draft + Hashi#41 handoff in `_outbox/`. Versions: reducer 1.21.0, parser 0.20.0, render 0.36.0, diff 0.5.5, analyst 0.20.0. Final drift+constitution validation: Excellent (F1-F5 aligned, L1/L2 pass). Commits ba6f517..bdc58f8. ⚠️ Do not merge without Hashi#41 in lockstep. |

## Context

Unify the `origin`/`source` dual naming in the `/inbox` suggestions review surface into
one **source** concept with a single keep/delete decision, and make the voice-item source
the `{audio .m4a + transcript .md}` set so one "Keep/Delete source" governs both files.

Locked product decisions (issue #33, 2026-06-03): (1) terminology `origin`→`source`
everywhere; (2) source = input file set, voice source = `{m4a + transcript}`; (3) reverse
the peer-pair exclusion so the `.m4a` joins the paired `delete_source` unless kept; (4) one
source = a single keep/delete decision, not two ambiguous per-file checkboxes. **Tomo never
deletes — it only proposes `delete_source` instructions** for Hashi/the user to apply.

Cross-repo: the wire-field rename (`origin_inbox_item`) is a constitution-L2 breaking change
needing a Kokoro migration note + Hashi coordination; the unified `{m4a+transcript}` delete
apply-side is tracked in `miyo-tomo-hashi#41`.

---
*This file is managed by the xdd-meta skill.*
