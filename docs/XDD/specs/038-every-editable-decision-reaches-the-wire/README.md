# Specification: 038-every-editable-decision-reaches-the-wire

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-29 |
| **Current Phase** | Initialization |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Last Updated** | 2026-09-29 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | pending | |
| solution.md | pending | |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-29 | Spec opened | Spec 037 shipped an editable decision that reaches no wire. Its consumer found the resulting data-loss path on merge day, and a second instance (`delete_source`) surfaced in the same week. The fix is consumer-coordinated, so it gets its own spec rather than a fix branch. |
| 2026-09-29 | Scope is three artefacts, not one | Owner rulings 2026-09-29: the wire must carry the attachment-conflict remedy; the rename target must be editable on both surfaces; and the parity inventory ships as a vendored JSON file rather than as prose in handoffs. |

## Context

**The invariant being restored** is written in our own schema, and spec 037
violated it: `suggestions-wire.schema.json` says *"every editable decision the
markdown offers is carried here."*

### Why this is a spec and not a patch

The change is consumer-coordinated. Hashi vendors our suggestions wire schema
and builds editor controls against it, so a field we add alone is a field they
cannot read. Their issues [#140](https://github.com/MMoMM-org/miyo-tomo-hashi/issues/140)
and [#141](https://github.com/MMoMM-org/miyo-tomo-hashi/issues/141) are the
consumer side of this work.

### The three artefacts

1. **The wire field for the attachment-conflict remedy.** Today
   `suggestion-parser.py:492` hardcodes `"attachment_conflict_remedies": []` in
   `build_from_wire`, so an `emit_digest` mismatch (ADR-026) silently converts
   the owner's chosen remedy into `ignore` — the most destructive of the three.
   Reproduced in `tests/test_037_remedy_lost_on_the_wire_path.py`.
2. **An editable rename target, on both surfaces.** Today neither surface can
   rename; ours is worse, because it renders the computed name inside a checkbox
   label and then discards anything typed over it
   (`tests/test_037_typed_rename_target_is_ignored.py`). Needs sanitisation, a
   freeness check, and a defined answer when the typed name is also taken.
   Explicitly forbidden: falling back to the computed name.
3. **The parity inventory, as a vendored file.** One row per editable markdown
   decision with its wire field — or `null`. Hashi vendors it and joins it to
   their own coverage map in CI, so a row their map does not mention fails their
   build. `wire_field: null` is the signal neither side had at 037's design time.

### Decided before this spec opened — do not re-derive

| Decision | Source |
|---|---|
| Validation is split: Hashi validates in the editor for immediate feedback; Pass 2 checks, surfaces, and **records in the instruction document — nothing more**. No repair, no substitution, no blocking. | Owner 2026-09-29; Hashi agreed, same reasoning as their destination check |
| Pass 2 must **never** fall back to the computed name when the typed one is unusable | Owner 2026-09-29 — that is the defect being fixed, wearing a different hat |
| Join on `item_key`, not on a stem | Hashi, after the spec 034 namesake collision |
| The remedy enum defaults the way the markdown pre-ticks it | Hashi's shape, accepted |
| The inventory excludes read-only fields and per-field docs | Hashi's request, accepted |

### Known-good facts this spec can build on

- `(decision, keep_source, delete_source)` semantics are measured, not inferred —
  `tests/test_delete_source_flag_triple.py`. `delete_source` is the **skip** leg
  and is inert under `approve`; `(skip, keep_source, delete_source)` all true
  **deletes**, because `build_from_wire` never copies `keep_source` into a
  skipped entry.
- The two Pass-2 paths normalise `delete_source` differently — the markdown
  parser forces it `False` on approve, `build_from_wire` does not. Inert only
  because nothing reads a confirmed item's copy.
- An absent remedy source is byte-identical to an explicit `ignore`
  (`_build_move_asset_actions`), which is why the loss is silent on both sides.

### Full brief

`docs/XDD/backlog.md`, entry *"spec 037's remedy does not survive Pass 2's
JSON-only path, and silently becomes `ignore`"* — including the parity audit
table, the two gaps and how they differ, and both corrections Hashi's reply
earned.

---
*This file is managed by the xdd-meta skill.*
