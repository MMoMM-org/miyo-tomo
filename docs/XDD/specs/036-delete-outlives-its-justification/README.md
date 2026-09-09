# Specification: 036-delete-outlives-its-justification

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-09 |
| **Current Phase** | Initialization |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Last Updated** | 2026-09-09 |

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
| 2026-09-09 | **Successor to spec 034's T6.0b, which was never accepted and is now measured as data loss** | 034 is `Implemented`; an unaccepted task cannot be reopened there. T6.0b was written as a missing comparison between two action kinds. Following the chain to its end shows it terminates in a deleted source note, which is a different severity and deserves its own spec. |
| 2026-09-09 | **Scoped as "a delete must not outlive the action that justified it", not as "move_note carries its delete"** | Coupling the delete to `move_note` closes one of four emission sites. Two of the other three have the same shape with different partners — see the table below. Scoping to the shape covers all of them and does not need revisiting when a fifth partner appears. |
| 2026-09-09 | **Route 1 now, route 2 with spec 035 — routes chosen** | Route 1 is a one-line change to `validate_destinations`' claimant filter (`render_actions.py:989`): `create_moc` carries the same `destination` field as `move_note`, and `_paired_delete_candidates` returns `[]` for a claimant with no `source_inbox_item`, so the existing withdrawal machinery applies unmodified. It closes the data-loss path with no cross-repo dependency, which a data-loss path should not wait on. Route 2 generalises to sites 2 and 4 and is a wire change, so it rides spec 035's release alongside the daily-side `item_key` — one re-vendor for Hashi instead of two. (Corrected 2026-09-09: this is two bumps on two documents, not one — the suggestions and instructions wires carry independent counters. One release, one changed-fields list; not one bump.) Route 3 is not rejected: route 2 supplies the data their `buildDependencies` would need, so it becomes their natural follow-on rather than a competing option. |
| 2026-09-09 | **The Hashi handoff is written after the route is chosen, not before** | Whether Hashi needs a dependency edge at all depends on which side we close the gap on. Asking them now would be asking them to hold an opinion on a design that does not exist yet. |

## Context

### The measured chain

Two claims on one path, and nothing compares them. Measured 2026-09-09 with the real
`build_actions` plus both guards, smallest input that expresses it:

```
I01  create_moc     -> Atlas/200 Maps/Travel (MOC).md
I02  move_note      -> Atlas/200 Maps/Travel (MOC).md
I03  delete_source  -> 100 Inbox/Notizen/Reise.md   ("Origin consumed by 1 atomic.")

destination_clashes reported : 0
attachment_suppressions      : 0
```

`_build_create_moc_actions` dedups `create_moc` against `create_moc` only;
`_build_move_note_actions` has no destination guard; T5.2's Pass-1 check compares atomics against
atomics; `validate_destinations` groups `move_note` only (`render_actions.py:989`). No pass sees
both kinds.

What Hashi then does, **read from its source, not executed**:

| Step | Evidence | Outcome |
|---|---|---|
| `create_moc` runs first | `planner.ts:39` — `KIND_ORDER[0]` | the MOC is written at the path |
| `move_note` runs next | `moveNote.ts:76` — `srcExists && dstExists` | **failed**, "Inconsistent state — both source and destination present" |
| `delete_source` runs anyway | `KIND_ORDER[14]`; `buildDependencies` emits only `link_to_moc → create_moc` and `add_relationship → create_moc` | **the user's inbox note is deleted** |

There is no dependency edge from `delete_source` to `move_note`. The failed move does not block
its paired delete, and the note it was supposed to become was never written.

This is the failure class T5.3's guard exists to prevent — that guard withdraws the paired delete
when it drops a move. Here Tomo never drops the move, so nothing is withdrawn; Hashi drops it, and
the withdrawal machinery is on the wrong side of the boundary.

**Reachability**: an atomic needs a title matching an approved MOC proposal and a `location` of
the MOC folder. Both are user-editable fields in the suggestions document, and no guard rejects
the combination.

### Why the scope is the shape, not `move_note`

`_build_delete_source_actions` (`render_actions.py:1562`) emits from **four** sites. Three of them
are conditional on another action succeeding, and only one of those three is `move_note`:

| # | Site | Partner action | Delete is wrong if the partner fails? |
|---|---|---|---|
| 1 | `skipped[]` with `disposition == "delete_source"` | none | **No** — the user asked for the delete itself |
| 2 | Daily-only origin (`reason: "Content fully captured in daily note."`) | `update_tracker` / `update_log_entry` / `update_log_link` | **Yes** — if the daily write fails the content is nowhere |
| 3 | `move_note` origin, plus its audio peer | `move_note` | **Yes** — this is the chain above |
| 4 | Tag-handler group source (`reason: "Source consolidated into … by … handler."`) | `insert_under_marker` | **Yes** — if the insert fails the captures are lost |

A rule written as "`move_note` carries its `delete_source`" closes site 3 and leaves 2 and 4 with
the same hazard and no obvious prompt to revisit them.

### Tomo already has this idea — on the wrong side of the boundary

Site 3 carries the **OQ6 completion gate** (`render_actions.py:1691`): the delete is deferred until
every expected atomic for that origin is represented in `move_notes`. So "do not delete until the
thing that replaces it exists" is already the rule — it is just evaluated at **build** time, over
actions Tomo intends to emit, rather than at **apply** time, over actions that actually succeeded.
Same for T5.3's withdrawal. Both are correct and both stop at the wire.

### Three routes — decided 2026-09-09: 1 now, 2 with spec 035

1. **Close it at the source (Tomo).** Group `create_moc` alongside `move_note` in
   `validate_destinations`, dropping both claimants per T5.3's precedent, which inherits the paired
   delete withdrawal and the `link_to_moc` withdrawal (`_orphaned_link_titles`) for free. Closes
   this instance; leaves sites 2 and 4 exposed to *their* partners failing.
2. **Close it at the boundary (wire).** Make the dependency explicit in the instruction set, so a
   delete names the action that justifies it and cannot be executed without it. Covers all three
   conditional sites and any future one. Costs a wire change — see spec 035 on what that now
   requires.
3. **Close it at the executor (Hashi).** A dependency edge per conditional delete. Defence in
   depth at the right place, but Tomo would still be emitting two claims on one path, and the user
   would still lose the run.

They are not exclusive. The plan's original note that "closing it cascades" was written on
2026-09-08, before T6.0d shipped `filter_unresolvable_moc_links` — the cascade machinery now
exists, so route 1 is smaller than it was when the task was proposed.

**Decision: 1 first, then 2 with spec 035.** Verified before choosing, not assumed:

- `create_moc` actions carry `destination` under the same key `move_note` does
  (`_build_create_moc_actions`, `render_actions.py:585`), so the grouping loop needs only its
  claimant filter widened.
- `_paired_delete_candidates` (`:830`) reads `source_inbox_item` and `audio_peer` via `.get`;
  `create_moc` has neither, so a MOC claimant contributes no withdrawal and cannot break the pass.
- The withdrawal the fix depends on is the *move* claimant's, and that is unchanged — dropping
  both claimants withdraws the move, which withdraws its paired delete. That is the chain that
  currently ends in a deleted note.
- Route 2's wire cost is one new field on `delete_source`, which today carries only `action`,
  `applied`, `id`, `reason` and `source_path` (`hashi-instructions.schema.json`) — nothing on it
  names the action that justifies it.

Route 3 is deferred rather than declined: once route 2 puts the dependency on the wire, Hashi's
`buildDependencies` has something to consume, so the edge follows from the data instead of needing
to be specified separately.

### Also in scope — same boundary, found in the same live run

- **A staging note survives a *failed* action, not only a withheld one.** Spec 034's T6.4c stops
  the upload when *Tomo* withholds a move. When Tomo emits the move and *Hashi* fails it, the
  staging note is uploaded and stays in the inbox as `pending-move` with nothing to move it. Same
  residue, other side of the boundary, and the T6.0b chain produces one every time.

### Recorded, not yet scoped — decide in the PRD

Two observations from the 2026-09-09 live apply. Both may belong here, may belong elsewhere, may
be nothing:

- **A new MOC section landed above the note's H1.** `link_to_moc` with a `[!connect]` callout
  anchor and `placement: after` inserted `## Geologie` between the callout and
  `# [[Elbsandstein & Tschechien 2026 (MOC)]]`. Contract-correct — "after the matched callout" —
  but the result reads wrong. T5.2/ADR-3 territory.
- **The instruction set stays `pending-apply` after a complete apply.** 11 of 11 applied, and
  `tomo.state` did not advance. No functional effect: coverage keys on `tomo.sources`
  (`inbox-triage.py:1338`) and discovery queries `tomo.doc_type=instructions` state-independently
  (`:377`), so nothing re-synthesises. But nothing marks the set done either.

### The Hashi handoff

The route is now chosen, so the handoff is unblocked. It carries the measured chain above —
Hashi's own guards are correct and did their job; what is missing is one edge nobody had a reason
to add — and it is written **once route 2's wire shape is settled in spec 035's PRD**, so it can
ship as one schema file with one changed-fields list covering both the daily-side `item_key` and
the delete's new dependency field. Sending it before that shape exists would ask Hashi to vendor
twice, which is the outcome the batching decision exists to avoid.

### Refs

- `docs/XDD/specs/034-recursive-inbox-discovery/plan/phase-6.md` — T6.0b as originally proposed
  (2026-09-08, never accepted), and T5.3's precedent for dropping both claimants
- `docs/XDD/specs/034-recursive-inbox-discovery/close-out.md`
- `docs/XDD/specs/035-wire-schema-versioning/` — required reading before any wire change (route 2)
- MiYo Constitution, Privacy & Security L1 and Testing L1: filesystem/vault-mutation paths need
  tests for the denial case, which is exactly the case missing here

---
*This file is managed by the xdd-meta skill.*
