---
from: tomo
to: hashi
date: 2026-05-07
topic: create_moc destination-collision guard (F-43 dependency)
status: done
received_by: hashi (Claude session, 2026-05-07)
received_at: 2026-05-07
closed_at: 2026-05-07
target_version: 0.2.0
shipped_version: 0.2.0
status_note: Hashi 0.2.0 released 2026-05-07. Verified in Hashi tree — createMoc.ts:40 emits `"destination already exists: <path>"` on src✓+dst✓; planner.ts:217 cascades add_relationship→create_moc; src✗+dst✓ keeps skipped-already (per Tomo reply). F-43 launch gate (PLAN T6.4) satisfied.
priority: normal
requires_action: true
target_version_requested: ">=0.2.0 (Hashi to confirm exact version)"
references:
  - tomo/docs/XDD/specs/013-moc-creation-skill/requirements.md#feature-6
  - tomo/docs/XDD/specs/013-moc-creation-skill/solution.md#ADR-3
  - tomo/docs/XDD/specs/013-moc-creation-skill/solution.md#CON-9
  - tomo/schemas/instructions.schema.json (#/$defs/create_moc)
  - tomo/docs/XDD/specs/013-moc-creation-skill/plan/phase-1.md#T1.1
---

# Hashi-side `create_moc` destination-collision guard — F-43 dependency

## TL;DR

Tomo spec **013-moc-creation-skill** (F-43, `/moc-propose`) emits standard `create_moc` actions that Hashi already understands. F-43 PRD/SDD records **one new Hashi requirement**: a pre-flight check that fails the `create_moc` action with `applied: false` if `destination` already exists in the vault, and cascades that failure to all dependent `add_relationship` / `link_to_moc` actions for the same MOC. **F-43 launch is gated on Hashi confirming this guard ships.** No schema change, no new action type — just a pre-write existence check on the existing `create_moc` action.

## Context — what is F-43?

`/moc-propose` is a new Tomo skill that scans the vault for under-organised topic clusters (atomic notes that share a tag/folder/classification) and proposes a new MOC with N children. It writes a proposal-doc to the inbox folder; the user reviews, ticks Accept on clusters/children, then runs `/inbox`. Pass 2 emits standard actions:

- 1× `create_moc` — creates the new MOC at `Atlas/200 Maps/<Title>.md` (MiYo profile) or `Maps/<Title>.md` (LYT profile)
- N× `add_relationship` — `up::` / `related::` markers per accepted child
- M× `link_to_moc` — adds child links into the new MOC's section structure

All vault writes go through Hashi; F-43 reuses the existing `create_moc`/`add_relationship`/`link_to_moc` action surface unchanged.

## Why this requirement exists

F-43's discovery scan can suggest a MOC title that **already exists** in `Atlas/200 Maps/` (or wherever the user's MOC location is configured). The user can also edit the proposed Title between proposal and apply, conflicting with another existing file. Without a destination-exists guard, `create_moc` would either silently overwrite the existing MOC or produce a duplicate file, depending on Hashi's current write semantics — both outcomes are unacceptable for a MOC, which often anchors dozens of `up::` links across the vault.

We searched current Hashi docs and could not find an explicit destination-exists guard for `create_moc`. Rather than assume it's there, F-43 records it as a NEW Hashi-side requirement (PRD Feature 6, SDD ADR-3, SDD CON-9).

## The requirement

**Hashi MUST**, when processing a `create_moc` action:

1. Resolve the action's `destination` field (vault-relative path, e.g. `Atlas/200 Maps/Decision-Making (MOC).md`) to an absolute vault path.
2. Verify the resolved path does **not** already exist before performing the write.
3. On collision:
   - Fail the `create_moc` action with `applied: false` and a non-empty `error_msg` indicating filename collision (e.g. `"destination already exists: Atlas/200 Maps/Decision-Making (MOC).md"`).
   - Cascade: `add_relationship` and `link_to_moc` actions whose target depends on this MOC also fail with `applied: false` and an `error_msg` referencing the failed `create_moc.id` (no partial application).
4. On success (destination absent): proceed with the write as today.

The schema reference is `tomo/schemas/instructions.schema.json#/$defs/create_moc` — fields used: `id`, `action`, `source`, `destination`, `title`. No schema change is requested or required.

## Acceptance Criteria (mirrors PRD Feature 6 AC)

| ID | Given | When | Then |
|----|-------|------|------|
| AC-6.1 | `create_moc` action whose `destination` resolves to an existing file | Hashi processes the action | Action fails with `applied: false` + `error_msg` indicating filename collision |
| AC-6.2 | A failed-collision `create_moc` action | The same instructions.json is processed | Dependent `add_relationship` and `link_to_moc` actions for that MOC also fail (no partial application) |
| AC-6.3 | A `create_moc` action whose `destination` does not exist | Hashi processes the action | Action succeeds; dependent `add_relationship` / `link_to_moc` actions for that MOC proceed normally |

## Dependency dependency-graph note

Tomo's renderer emits actions in dependency order — the `create_moc.id` is referenced by downstream `add_relationship.target` / `link_to_moc.moc_id` (or equivalent linkage; see schema). The guard's "cascade dependent actions" requirement assumes Hashi already has some form of action-dependency awareness. If Hashi does not currently track action dependencies, the minimum bar is: any action that targets a non-existent MOC file (because its `create_moc` failed) must itself fail with `applied: false` rather than creating a phantom link.

## What Tomo will do on its side

- Tomo's discovery / proposal logic does **not** pre-filter on destination existence (the user may rename in the proposal-doc, and the vault state can change between proposal and apply). The guard belongs at write time, in Hashi.
- Tomo's instruction-render emits actions in dependency order so Hashi sees `create_moc` before its dependents.
- F-43 PRD Feature 6 publishes the user-facing contract; SDD ADR-3 records the cross-repo dependency; PLAN phase 6 launch gate (T6.4) checks for receipt of this handoff before flipping F-43 to Ready.

## Out of scope (not part of this handoff)

- Any new MCP tool, new action type, or schema change.
- Backup-on-overwrite semantics — the guard is hard-fail, not "rename existing and proceed".
- Surfacing the collision to the user in Tomo's review UX — Tomo consumes the `error_msg` from the per-action result and displays it; that's already how `applied: false` results render.
- Coordinating MOC writes with Obsidian Sync / live UI updates — Hashi's existing write semantics apply.

## Receipt protocol — please confirm one of these before F-43 ships

F-43 Phase 6 has a launch gate (PLAN T6.4) that blocks ship until Hashi acknowledges. To unblock, please do **either** of:

**(A)** Edit this same file in your `_inbox/from-tomo/` (it's a symlink — your edits write back here). Set:
```yaml
status: received
received_by: <hashi maintainer or session id>
received_at: 2026-MM-DD
target_version: <semver Hashi will ship the guard in, e.g. 0.4.0>
status_note: <optional: ETA, follow-up questions>
```

**(B)** Send a sibling reply handoff `_outbox/for-tomo/2026-MM-DD_hashi-to-tomo_create-moc-collision-guard-ACK.md` that surfaces a Hashi version commitment and any clarifications.

Either path works; (A) is lighter weight if no follow-up is needed.

## Reference

- Tomo PRD: `Tomo/docs/XDD/specs/013-moc-creation-skill/requirements.md` — Feature 6 (lines 164–171), edge case in Feature 4 (line 240).
- Tomo SDD: `Tomo/docs/XDD/specs/013-moc-creation-skill/solution.md` — ADR-3 (lines 1074–1077), CON-9 (line 65), externalIntegrations table (line 43).
- Tomo PLAN: `Tomo/docs/XDD/specs/013-moc-creation-skill/plan/phase-1.md` — T1.1 (cross-repo handoff task), `Tomo/.../plan/phase-6.md` — T6.4 (launch gate that checks for this receipt).
- Action schema (immutable for F-43): `Tomo/tomo/schemas/instructions.schema.json` (`#/$defs/create_moc`).
