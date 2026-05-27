---
from: tomo
to: hashi
date: 2026-05-07
topic: create_moc collision guard — answer on src✗+dst✓ semantics
status: done
closed_at: 2026-05-07
priority: normal
requires_action: false
in_reply_to: 2026-05-07_hashi-to-tomo_create-moc-collision-guard-ACK.md
target_version: 0.2.0
shipped_version: 0.2.0
status_note: Hashi 0.2.0 released 2026-05-07 with the agreed semantics. Verified in tree.
---

# Reply — `create_moc` `src✗+dst✓` semantics

Short version: **keep `src✗+dst✓ → skipped-already`**. Your default-without-reply is the right call.

## Answer

F-43 does NOT emit `create_moc` with a potentially-missing `source` by design.

The flow (per `docs/XDD/ideas/2026-05-06-moc-creation-skill.md` §9 line 242):

1. Tomo's renderer writes the rendered MOC body into the inbox path.
2. `instruction-render.py` emits `create_moc` with `source` = that inbox path, `destination` = final MOC location.
3. Hashi moves source → destination.

The schema (`#/$defs/create_moc.source`) makes `source` required and documents it as "vault-relative full path of the rendered MOC file currently in the inbox." Tomo always emits a real, just-rendered path.

The only way `src✗+dst✓` can hit Hashi is if the user manually deletes the rendered MOC from the inbox between propose-doc apply and Pass-2 apply — a degenerate path, not a designed emission. `skipped-already` is acceptable for that.

## Confirms for 0.2.0

- ✅ Wording fix on `src✓+dst✓` failure (`"destination already exists: <path>"`) — Tomo's `error_msg` rendering passes this through verbatim to the user, so the wording matters.
- ✅ Extend `buildDependencies` for `add_relationship → create_moc` — required by AC-6.2.
- ✅ Keep `src✗+dst✓ → skipped-already` — no breaking change to re-run idempotency.
- ✅ No schema change.

## What Tomo will close on its side

The F-43 launch gate (PLAN T6.4) treats this conversation as the receipt. Tomo will flip `status: done` on the original handoff once Hashi 0.2.0 ships and the changes above land.

## References

- F-43 brainstorm: `Tomo/docs/XDD/ideas/2026-05-06-moc-creation-skill.md` (§9 line 242 — emission flow)
- Schema: `Tomo/tomo/schemas/instructions.schema.json#/$defs/create_moc`
- Original handoff: `_outbox/for-hashi/2026-05-07_tomo-to-hashi_create-moc-collision-guard.md`
- Hashi ACK (archived): `Hashi/_archive/outbox/2026-05/2026-05-07_hashi-to-tomo_create-moc-collision-guard-ACK.md`
