# Specification: 030-garden-audit

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-07-18 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-07-19 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 5 Must features, 18 Gherkin ACs, MoSCoW + edge cases + risks. No clarification markers. |
| solution.md | completed | 6 ADRs (all user-confirmed), interfaces (edit_note_text, exclusion config, wire, graph_audit, /inbox), directory map, runtime flows, gotchas. |
| plan/ | completed | 6 phases, 18 tasks, TDD (Prime/Test/Implement/Validate). Manifest + phase-1..6.md. Parallel tags + dependency graph. |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-18 | Spec scaffolded from brainstorm design | Source: `docs/XDD/ideas/2026-07-18-garden-audit-skill.md` (validated + spec-reviewer approved). GitHub #30 / F-44, roadmap item 2. |
| 2026-07-18 | Cross-repo dependency pre-resolved before PRD | The vault-wide link-graph op (`kado-graph-audit`) was requested, contract-confirmed, AND shipped by Kado (v1.2.0, #98/#99) during the brainstorm — so the spec plans against a real, live tool, not a pending dependency. |
| 2026-07-18 | Research correction: check 3 (broken `up::`) is cache-only | `up_state=="broken"` + `up_target` are already computed in the discovery cache (`moc-tree-builder.py:280-289,422`). Check 3 needs NO `kado-graph-audit` call — corrects the brainstorm's "cache / graph". |
| 2026-07-18 | Research correction: check 1/2 fix = two actions | Filing an unparented/orphan note needs BOTH `link_to_moc` (MOC-side bullet) AND `add_relationship marker="up::"` (the note's own `up::` line). The brainstorm named only `link_to_moc` (half). Both builders exist (`_build_link_to_moc_actions` + `emit_up_preservation_actions`). |
| 2026-07-18 | Hashi gap handled example-driven (user decision) | No shipped Hashi action edits/removes a free-text body `[[link]]` or removes a broken `up::` line. Decision: Tomo BUILDS the full feature and emits a COMPLETE JSON wire encoding the fix intent for checks 4 + 3-remove as a NEW body-edit action Tomo defines. When Tomo is done, the real complete JSON example IS the Hashi handoff — Hashi builds its editor + the new action against a concrete example ("ohne ein Beispiel wird das nichts"), not a spec string. Producer-defines-contract-by-example, same posture as ADR-026. Advisory-only stays for checks 5+6 (need human judgment). |
| 2026-07-18 | PRD completed | `requirements.md`: 4 Must features (6-check scan, report+wire, approve-and-apply, trustworthy scan), 14 Gherkin ACs, MoSCoW + edge cases + risks. Grounded in 2 research passes + spec-reviewer. Ready for SDD. |
| 2026-07-19 | PLAN completed → spec Ready | `plan/`: 6 phases, 18 tasks. P1 foundations (graph_audit, exclusions, seed+update-script protection CON-4) · P2 scan · P3 render+wire · P4 apply (edit_note_text + parser + /inbox 4th-type) · P5 agent/command/wizard/docs · P6 cross-repo handoffs (Kokoro ADR + Hashi example-driven) + integration/E2E/live-vault. TDD throughout; parallel tags + dependency graph. Ready for /implement. |
| 2026-07-19 | SDD completed | `solution.md`: 6 user-confirmed ADRs — (1) /inbox 4th upstream type, (2) skill-owned instance exclusion config (seed), (3) one `edit_note_text` match/replace Hashi action, (4) garden-audit-wire mirrors ADR-026, (5) check→action + data-source split, (6) new pipeline components mirror /moc-propose. Interfaces + directory map + runtime flows + gotchas (update-script config protection CON-4; L2 Kokoro/Hashi cross-contract). Ready for PLAN. |
| 2026-07-19 | PRD revised from user annotations (4 notes) | (1) **Feature 5 added — scoped exclusions** (note/path/tag; per-check or complete; permanent = Must, temporary ~90d push-back = Should); skill-owned config `config/garden-audit-exclusions.yaml` (instance-local — corrected: `vault-config.yaml` is NOT in the vault), managed only inside the skill, never via `/inbox`. (2) Broken-`up::` **removal** moved OUT of Won't-Have INTO v1 (full fix intent in the wire; Hashi builds against it post-v1 — no Tomo revisit). (3) First-run wizard + `--configure` re-invocation detailed spec (resolves the "how to re-invoke" question). (4) `/inbox` burden **analysed → none**: garden-audit rides the same skip-analysis + accepted-state pickup as `/moc-propose` (zero Pass-1 cost), joining `_UPSTREAM_TYPES` as the 4th peer. |

## Context

Knowledge-Garden Audit skill: a user-invoked, whole-vault health scan surfacing six checks
(unparented, orphan, broken `up::`, dead wikilink, duplicate stems, stale MOC) into a prioritised
review document + JSON wire (ADR-026), with the fixable subset applied through the existing 2-pass
/ Hashi machinery. Roadmap item 2 (`docs/XDD/roadmap-obsidian-power.md`), predecessor MOC-creation
track shipped. Full brainstorm design + approaches + parking lot:
`docs/XDD/ideas/2026-07-18-garden-audit-skill.md`.

---
*This file is managed by the xdd-meta skill.*
