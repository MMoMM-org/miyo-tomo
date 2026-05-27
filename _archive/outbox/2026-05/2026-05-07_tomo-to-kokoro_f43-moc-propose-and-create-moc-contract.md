---
from: tomo
to: kokoro
date: 2026-05-07
topic: F-43 /moc-propose skill launch + create_moc Tomo↔Hashi contract refinement
status: done
status_note: Captured as ADR-017 (create_moc collision/cascade) + F-43 roadmap entry in 00-overview.md §8 Phase 3.
priority: normal
requires_action: true
references:
  - tomo/docs/XDD/ideas/2026-05-06-moc-creation-skill.md
  - tomo/docs/XDD/roadmap-obsidian-power.md
  - tomo/schemas/instructions.schema.json#/$defs/create_moc
  - tomo/_outbox/for-hashi/2026-05-07_tomo-to-hashi_create-moc-collision-guard.md
  - tomo/_outbox/for-hashi/2026-05-07_tomo-to-hashi_create-moc-collision-guard-reply.md
  - hashi/_archive/outbox/2026-05/2026-05-07_hashi-to-tomo_create-moc-collision-guard-ACK.md
---

# F-43 launch + `create_moc` cross-component contract refinement

Two related items that warrant capture in Kokoro per the MiYo constitution rule on cross-component contract changes (Architecture L2 — *"changes that affect interactions between MiYo components must be reflected in Kokoro as an updated design note or ADR — before or alongside the implementation."*).

## 1. F-43 — `/moc-propose` skill (new Tomo entry point)

A new proactive MOC-creation skill in Tomo. Today MOCs surface only as a side-effect of inbox processing (existing Conditions A/B/C in `tier-3/lyt-moc/new-moc-proposal.md`). F-43 adds a **standalone** path: the user invokes `/moc-propose` against a topic-area / whole-vault / specific-title and gets a MOC proposal landed in the inbox folder for review and Pass-2 application.

- **Brainstorm spec:** `Tomo/docs/XDD/ideas/2026-05-06-moc-creation-skill.md` (next step: promote to full XDD `013-moc-creation-skill/`).
- **Roadmap track:** #1 in `Tomo/docs/XDD/roadmap-obsidian-power.md` — foundation for F-44 (Garden-Audit), F-45 (Weekly Review), F-46 (Tag-Audit).
- **Reuses 2-pass pipeline unchanged:** proposal-doc → `/inbox` Pass 2 → `instruction-render.py` emits existing `create_moc` + `add_relationship` + `link_to_moc` actions → Hashi applies. No new action types, no schema change.
- **Status:** brainstorm complete; PRD/SDD/PLAN drafting pending (queued behind 013 promotion).

**Suggested Kokoro action:** capture F-43 as a roadmap entry (Obsidian-power track #1) in the system-level overview docs. Full ADR is premature — promote when 013 PRD lands.

## 2. `create_moc` Tomo↔Hashi contract refinement

F-43 surfaced a real cross-component contract gap that's now resolved. The outcome is ADR-worthy because it pins down `create_moc` failure-and-cascade semantics across the two repos.

### Decisions captured

**Destination-collision guard (Hashi-side requirement):**
- Hashi MUST verify `create_moc.destination` does not exist before writing.
- On collision (`src✓+dst✓`): `applied: false`, `error_msg = "destination already exists: <path>"` (verbatim wording — Tomo's UI passes it through unchanged).
- Cascade: `add_relationship` and `link_to_moc` actions whose target depends on the failed `create_moc.id` also fail with `applied: false`. No partial application.
- `src✗+dst✓` keeps current `skipped-already` semantics (idempotent re-run); no breaking change. Tomo confirmed it never intentionally emits a missing `source`.

**Hashi-internal change with cross-component implication:**
- `buildDependencies` (Hashi planner) now tracks `add_relationship → create_moc` edges, in addition to the existing `link_to_moc → create_moc` edge. This is what makes AC-6.2 cascade work end-to-end.

**Schema unchanged:** `instructions.schema.json#/$defs/create_moc` stays as-is. `source` remains required, `destination` remains required, semantics described in field `description` strings remain authoritative.

### Implementation status

- **Hashi:** PR #3 merged to main on 2026-05-07 (commit `40b7383`). Awaiting 0.2.0 release cut (manifest/version bump + tag).
- **Tomo:** unchanged on the wire. F-43 launch gated on Hashi 0.2.0 ship + receipt confirmation (PLAN T6.4 in spec 013 once promoted).

### Kokoro placement suggestions

Two natural homes — feel free to consolidate:

- **System-level instruction-set contract notes** (if Kokoro maintains a `tomo↔hashi-contract.md` or similar): add a `create_moc` failure-and-cascade section pinning the wording and cascade rules above.
- **ADR (new):** `ADR-XX_create-moc-collision-and-cascade.md` — context (F-43 surfaced it), decision (collision = hard fail with verbatim wording; cascade across `add_relationship`/`link_to_moc`; preserve `skipped-already` idempotency), consequences (Hashi 0.2.0 ships the guard; no schema change; F-43 launch gate satisfied).

## What Tomo is asking from Kokoro

1. Capture F-43 as a roadmap-tracked feature (light entry, full ADR later).
2. Land an ADR (or design-note update) for the `create_moc` collision/cascade contract — alongside implementation per the L2 constitution rule.
3. Ack receipt so the loop closes (no specific deliverable from Kokoro beyond capture).

## References

- F-43 brainstorm: `Tomo/docs/XDD/ideas/2026-05-06-moc-creation-skill.md`
- Roadmap: `Tomo/docs/XDD/roadmap-obsidian-power.md`
- Schema: `Tomo/tomo/schemas/instructions.schema.json#/$defs/create_moc`
- Tomo→Hashi handoff (original): `Tomo/_outbox/for-hashi/2026-05-07_tomo-to-hashi_create-moc-collision-guard.md`
- Tomo→Hashi reply (semantics): `Tomo/_outbox/for-hashi/2026-05-07_tomo-to-hashi_create-moc-collision-guard-reply.md`
- Hashi ACK (archived): `Hashi/_archive/outbox/2026-05/2026-05-07_hashi-to-tomo_create-moc-collision-guard-ACK.md`
- Hashi PR #3 / commit `40b7383`
