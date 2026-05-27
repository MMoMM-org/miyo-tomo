---
from: tomo
to: kokoro
date: 2026-05-09
topic: F-43 — Tomo↔Hashi create_moc.destination_exists_check protocol
status: done
status_note: Pinned in ADR-017 — verbatim error wording, cascade across add_relationship/link_to_moc, src✗+dst✓ skipped-already preserved; also cross-linked from 06-miyo-tomo-hashi.md §6.4.
priority: normal
requires_action: true
---

# F-43 — Tomo↔Hashi `create_moc` destination-collision protocol

## Summary

Tomo spec 013-moc-creation-skill (F-43, `/moc-propose`) introduced a cross-component
protocol between Tomo and Hashi: Tomo emits `create_moc{source, destination}` actions
via `instruction-render.py`, and Hashi 0.2.0 enforces a destination-collision guard
that returns `applied: false` with `error_msg: "destination already exists: <path>"`.

Please record this protocol in Kokoro, either as an updated cross-component note
or as a new ADR (Kokoro's choice on shape).

## Cross-component invariant

**Tomo side (`instruction-render.py`):**
- Emits `create_moc` with `source` (vault-relative path to the primary child note)
  and `destination` (vault-relative path for the new MOC file, derived from
  vault-config `concepts.map_note.paths`).
- Does NOT pre-check destination existence — the vault state can change between
  proposal and apply, and the user may rename the proposed title in the
  suggestions doc.
- Actions are emitted in dependency order: `create_moc` before its dependent
  `add_relationship` / `link_to_moc` actions.

**Hashi side (`createMoc.ts`, shipped in 0.2.0):**
- Pre-flight check on `destination` before any write.
- On collision: fails the `create_moc` action with `applied: false` +
  `error_msg: "destination already exists: <path>"`.
- Cascade: dependent `add_relationship` / `link_to_moc` actions referencing
  the failed `create_moc.id` also fail with `applied: false` (no partial application).
- On success (destination absent): proceeds with write as normal.

**Tomo error consumption:**
- Tomo reads per-action `applied: false` + `error_msg` from the Hashi result.
  The error is surfaced in the session for the user to resolve (rename proposed
  title in proposal-doc and re-run). This is the existing `applied: false`
  rendering path — no new UI needed.

## Context

This protocol emerged during F-43 Phase 1 when the discovery scan was found capable
of proposing a MOC title matching an existing file. Without a guard, `create_moc`
would silently overwrite the existing MOC — unacceptable given that MOCs often anchor
dozens of `up::` links across the vault.

F-43 SDD records this as ADR-3 and CON-9. The cross-repo handoff that requested
the guard from Hashi is archived at:
`Tomo/_archive/outbox/2026-05/2026-05-07_tomo-to-hashi_create-moc-collision-guard.md`

Hashi 0.2.0 confirmed receipt and shipped the guard on 2026-05-07
(`createMoc.ts:40`, `planner.ts:217`).

## Why this needs a Kokoro record

Per MiYo Constitution L2 Architecture: "Any change that affects interactions between
MiYo components must be reflected in MiYo Kokoro as an updated design note or ADR
— before or alongside the implementation."

The `create_moc` collision protocol is a stable cross-component contract. Any future
Tomo or Hashi work that touches `create_moc` action semantics should be able to find
this contract in Kokoro without reading the full F-43 spec.

## References

- Tomo spec: `Tomo/docs/XDD/specs/013-moc-creation-skill/`
  - requirements.md Feature 6 (lines 164–171)
  - solution.md ADR-3, CON-9
  - plan/phase-1.md T1.1 (cross-repo handoff task)
- Hashi archived handoff: `Tomo/_archive/outbox/2026-05/2026-05-07_tomo-to-hashi_create-moc-collision-guard.md`
- Action schema (immutable for F-43): `Tomo/tomo/schemas/instructions.schema.json` (`#/$defs/create_moc`)
