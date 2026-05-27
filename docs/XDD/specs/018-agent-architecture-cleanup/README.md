# XDD 018 — Inbox Routing Redesign & Agent Decomposition

**Status:** Implemented — 2026-05-27
**Current phase:** Implemented
**Branch:** `feat/018-inbox-routing-redesign` (PR #2, merged)
**Supersedes scope:** F-53, F-56, F-57, F-59, F-50 (iii), F-51, F-32 (partial)
**Unblocks:** F-43 operator-live-validation (013-moc-creation-skill)

## Problem in one paragraph

`/inbox` mixes routing logic with workflow execution: a long markdown
auto-discovery section reads the body of every `*_suggestions.md` file
just to check whether `[x] Approved` is ticked, then impersonates one
of two monolithic agents (`inbox-orchestrator` doing transcription +
suggestions + routing; `instruction-builder` doing instructions + fan +
moc-propose). The auto-discovery scan never matches
`*_moc-proposal-*.md`, so accepted MOC proposals are silently invisible
to both Pass 1 and Pass 2. Each /inbox run reads full doc bodies into
LLM context (~25k+ tokens) just to triage state that lives in
checkboxes and frontmatter. Agent specs are large (375–735 lines) and
re-loaded fully even when only 1/3 of the prompt is relevant to the
current branch.

## Solution in one paragraph

Move all triage to a deterministic `inbox-triage.py` script that scans
inbox state (listDir + byFrontmatter + targeted body reads for
approval/force-atomic checkboxes), materialises the relevant docs to
`tomo-tmp/inbox-cache/` for reuse downstream, and emits a
`routing-plan.json` with the next action plus typed work-buckets.
`/inbox` becomes a thin router that impersonates one of two new
conductor agents — `suggestion-conductor` (handles capture →
suggestions/MOC-proposals) and `synthesis-conductor` (handles approved
inputs → instructions + atomic notes + MOC files). Cross-cutting
knowledge moves into lazy-loaded skills (lifecycle states, kado
patterns, force-atomic handling) following the "fewer agents, more
skills" pattern. Old `inbox-orchestrator` and `instruction-builder`
agent files are deleted as part of the big-bang migration.

## Files

- [requirements.md](requirements.md) — product requirements (PRD v0.2)
- [audit.md](audit.md) — pre-existing audit from 2026-05-21 (input material, not authoritative)
- [solution.md](solution.md) — technical design (SDD v0.3)
- [plan/README.md](plan/README.md) — implementation plan (5 phases, 21 tasks)

## Tracking

- **Backlog roll-up:** F-53 (parser defaults), F-56 (phase C wrapper),
  F-57 (runtime/rationale split), F-59 (status pre-scan anchor),
  F-50 (iii) (skip-list), F-51 (state-consistency), F-32 (partial —
  Opus→Sonnet falls out of smaller conductors).
- **Sibling spec:** 013-moc-creation-skill — code shipped, operator-live
  validation blocked by Bug 1+2 (moc-proposal Pass-2 trigger missing).
  018 unblocks 013's validation; the two ship together as one user-
  visible release.
- **Input material:** `audit.md` (2026-05-21 agent inventory),
  PRD §7 token budgets from F-47, memory entries
  `[[feedback_check_inbox_for_shipped_kado_capabilities]]`,
  `[[feedback_orchestrator_impersonate_vs_dispatch]]`,
  `[[feedback_docs_in_script_not_agent.md]]`.
- **Constraint memories that apply:**
  - `feedback_vault_sot_design_for_corruption` — every discovery path
    needs failback
  - `feedback_validate_runtime_xrefs_against_container_visibility` —
    runtime agents only see `$INSTANCE_PATH` + `/home/coder`
  - `feedback_tell_how_not_what` — conductors get invocations, not prose
  - `feedback_docs_in_script_not_agent` — rationale lives in scripts
- **Architecture decisions (locked 2026-05-24):**
  - Conductor naming: `suggestion-conductor` + `synthesis-conductor`
  - Triage-script naming: `inbox-triage.py`
  - Approval truth-source stays as `[x] Approved` checkbox in body
    (UX anchor — Obsidian-visible)
  - Coverage tracked in instructions frontmatter as flat string arrays
    (`source_suggestions[]`, `source_fan[]`, `source_moc_proposals[]`)
    — no nested JSON, property-viewer-friendly
  - Migration: big-bang (no incremental dual-path)

## Open questions before SDD

See requirements.md §8 — 10 questions across skill granularity,
conductor model, routing-plan schema, drift handling, voice-transcriber
hoist, fan-resolve dispatch path, F-43 validation gating, and migration
test order.

## Notes

**F-47 schema requirement:** Any renderer that emits workflow documents
MUST emit the `tomo:` frontmatter block per
`tomo/schemas/doc-frontmatter.schema.json` using `build_tomo_block()`
from `tomo/scripts/lib/doc_frontmatter.py`. 018 extends the
`instructions` doc-type with three new optional fields
(`source_suggestions[]`, `source_fan[]`, `source_moc_proposals[]`) —
schema update is part of the spec.

**Big-bang scope reminder:** This redesign deletes
`agents/inbox-orchestrator.md` and refactors
`agents/instruction-builder.md` into `synthesis-conductor.md`.
The implementation branch ships when `/inbox` runs end-to-end on a
real vault for both Pass-1 and Pass-2 — partial merges are not
acceptable per Marcus's 2026-05-24 directive ("sonst kommt der nächste
fehler und wir machen das gleiche was wir aktuell machen").
