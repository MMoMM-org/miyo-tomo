# Memory Index — Tomo

> Routing rules are in CLAUDE.md (root). This file is the index only.
> Budget: ≤ 200 lines. Archive entries when stale. Run /memory-sync to check.

## Files
- [general.md](general.md) — conventions, style, naming [updated: 2026-10-02]
- [tools.md](tools.md) — CI, build, local dev [updated: 2026-10-03]
- [domain.md](domain.md) — business rules, data models [updated: 2026-07-01]
- [decisions.md](decisions.md) — architecture choices [updated: 2026-09-04]
- [context.md](context.md) — current focus [updated: 2026-06-30]
- [troubleshooting.md](troubleshooting.md) — known issues [updated: 2026-07-03]

## Archive
<!-- Archived entries live in archive/YYYY-MM/. Not loaded at session start. -->
<!-- memory-cleanup manages archive creation. Do not list archive files here. -->
- archive/2026-06/ — resolved troubleshooting + context bug-fix entries (cleanup 2026-06-29); R11/R13 resolved + 2026-05 open blocks relocated (cleanup 2026-06-30)

## Critical Documentation
- [Spec 039 close-out](../../XDD/specs/039-attachment-conflict-hardening/close-out.md) — all 53 PRD criteria traced to 170 node ids that ran together in ONE pytest invocation (306 passed); the trace found four gaps, all closed by tests or documents rather than production code (F4-AC7 had been asserted through an extractor production never calls, so it was re-traced through triage's real embed resolver); F1-AC7's proviso was amended by the owner; F6-AC2 rests on live runs and the consumer's test; F3-AC6 (a Kado listing that errors instead of `Path not found`) has never happened live and stays open.
- [Spec 038 close-out](../../XDD/specs/038-every-editable-decision-reaches-the-wire/close-out.md) — all 38 PRD criteria traced to node ids executed in ONE pytest invocation (95 passed); the trace itself found F4-AC4 asserted by no test that could fail, the second spec running where the close-out rule caught a real gap rather than confirming the work; C1 stays deliberately unticked with the capability delivered twice; and the inventory's two never-exercised columns (`editable: false`, `wire_field: null`) named rather than read as proven.
- [Spec 038 Phase 1 findings](../../XDD/specs/038-every-editable-decision-reaches-the-wire/phase-1-findings.md) — all 20 Phase 1 discrepancies grouped by disposition (resolved/withdrawn/backlog/accepted-limitation), each with a concrete recommendation; none came from a failing test — every one came from counting or executing something a document asserted.
- [Spec 036 close-out](../../XDD/specs/036-delete-outlives-its-justification/close-out.md) — all 25 F1–F6 criteria mapped to tests that were executed rather than to tasks, the two consumer-owned criteria that Tomo structurally cannot prove, and the finding that the handoff's structural diff is blind to the contract's prose.
- [Spec 036 close-out](../../XDD/specs/036-delete-outlives-its-justification/close-out.md) — all 23 PRD criteria in F1–F6 traced to a test that was executed rather than quoted; the two consumer-owned criteria named as an OPEN obligation (T4.5 never went out); the three measured data-loss paths closed in one end-to-end run, with P3 recorded as a build-time guard that would pass even with the withdrawal pass gutted.
- [Spec 035 close-out](../../XDD/specs/035-wire-schema-versioning/close-out.md) — all 33 PRD criteria traced (the plan said 28; F9 arrived mid-phase), which six are evidenced by the consumer's reply rather than a test and why that is stronger, the L2 violation caught in flight, and the closing condition reached: detection at zero across all three wires.
- [Spec 034 close-out](../../XDD/specs/034-recursive-inbox-discovery/close-out.md) — the SDD quality table and all 40 PRD acceptance criteria mapped to named green tests or to the live run, plus the two live-coverage gaps recorded rather than hidden (audio namesake, per-item token cost).
<!-- Add important docs here when created — Claude loads these on demand -->
<!-- - [Architecture Overview](../architecture/overview.md) -->
- [Inbox Change Detection & Pass Routing](../../XDD/reference/tier-2/workflows/inbox-change-detection.md) — how triage detects what changed (new/drift/coverage) + the determine_action routing tree + flag semantics (--pass2 vs --force). Mermaid flowchart + state diagram. (#74/#78)
