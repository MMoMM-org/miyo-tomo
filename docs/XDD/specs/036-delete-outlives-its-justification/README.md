# Specification: 036-delete-outlives-its-justification

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-09 |
| **Current Phase** | Ready |
| **Decomposition tier** | Incremental |
| **Last Updated** | 2026-09-10 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 7 features, 25 Gherkin criteria, 4 open questions |
| solution.md | completed | 6 ADRs confirmed, 16 EARS criteria, responsibility matrix run |
| plan/ | completed | Incremental — 4 phases, 17 tasks, 75 spec refs |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-09 | **Successor to spec 034's T6.0b, which was never accepted and is now measured as data loss** | 034 is `Implemented`; an unaccepted task cannot be reopened there. T6.0b was written as a missing comparison between two action kinds. Following the chain to its end shows it terminates in a deleted source note, which is a different severity and deserves its own spec. |
| 2026-09-09 | **Scoped as "a delete must not outlive the action that justified it", not as "move_note carries its delete"** | Coupling the delete to `move_note` closes one of four emission sites. Two of the other three have the same shape with different partners — see the table below. Scoping to the shape covers all of them and does not need revisiting when a fifth partner appears. |
| 2026-09-09 | **A dangling `depends_on` id fails closed at the executor too — our claim that it could not was wrong** | We told Hashi a dangling id was structurally undetectable on their side. True of `failedIds`, which only ever holds ids that ran and failed; **not** true of them — the whole set is in hand at plan time. They will check it and **skip** the delete. Their argument, adopted: *a guard that opens when it cannot read its own precondition is not a guard.* The producer invariant stays ours and the audit still gets built; theirs is what happens on the day one ships. Same error shape as the withdrawn rename — reasoning outward from one mechanism to a whole system's capability. |
| 2026-09-09 | **`depends_on` contract settled by the consumer: required with explicit `[]`, snake case, union semantics** | Asked rather than assumed. Their sharpening of the required-vs-optional argument replaces ours as the recorded rationale: for a join key absence degrades a feature; for a delete gate absence is indistinguishable between "nothing justifies this" and "everything does", which have opposite correct behaviours. Union over override was decided by the F-43 case — a `depends_on` on an `add_relationship` would, under override, silently retire their collision-guard edge without anyone revoking it. They will read the field on any action kind, not only `delete_source`. |
| 2026-09-10 | **Four phases: Declare → Collect → Unreachable cases → Contract** | Phase 1 emits `depends_on` and changes no behaviour, so the data is independently testable before anything consumes it; Phase 2 is then a pure behaviour change and is where P1 and Bug A stop happening. Phase 3 is **independent** of 1 and 2 — the tag-handler defects share no code with the `depends_on` machinery — and its two tasks are the plan's only genuine parallel opportunity. Phase 4 carries the wire, the audit, reporting and the integration proof. The guards-before-wire constraint binds the **release**, not the phase order: under ADR-1 a guard cannot drop a partner without amending the deletes naming it, because the withdrawal *is* the amendment. |
| 2026-09-10 | **23 of 25 PRD criteria map to tasks; the other 2 are a recorded decision** | F7 (destructive actions read as destructive) is `Could Have` and deliberately not designed — a pure rendering change with no interaction with the withdrawal mechanism. Written into the plan's coverage table as a decision rather than left as an apparent gap, so a reviewer does not read it as an oversight. |
| 2026-09-10 | **Decomposition tier: Incremental** | Classifier recommended Incremental and it was accepted. Signals read from the two documents: `change_type=fix`, `feature_count=5` (Must-Have F1–F5), `ac_count=25`, `component_count=2` (new surface only — `withdraw_unjustified_deletes`, `assert_no_dangling_dependencies`), `parallel_markers=false`. Rule 1 fires on both its clauses and precedes rule 2, so breadth vetoes the `change_type=fix` escape that would otherwise have routed this to Direct. Noted for accuracy: `tag_handler_group_is_appliable` is a third new function but appears only in an implementation example, not the Building Block View, so the mechanical count is 2. |
| 2026-09-09 | **ADR-1: one id-keyed withdrawal pass — the guard and the wire field are one mechanism** | Every conditional delete declares its partner ids at build time; a single post-pass drops any delete whose declaration no longer resolves. Chosen over extending the existing path-keyed join, which would build the same relation twice with nothing keeping the halves in step — the cost that helper's own docstring records from T5.0c. The dangling-id invariant then holds **by construction**: the pass cannot leave a delete naming an absent id, because that is exactly what it removes. Same rule Hashi runs at plan time, so both sides evaluate one contract at two moments. |
| 2026-09-09 | **The pass covers P1 and Bug A but NOT Bug B — stated, not papered over** | It handles a partner that was emitted and later dropped. Bug B's `insert_under_marker` is **never built** (`render_actions.py:1836-1839` skips a null target), so no id exists for the delete to name. Bug B therefore needs the two loops to share one appliability predicate (ADR-5). A design claiming to subsume all three would have left Bug B open while looking complete. |
| 2026-09-09 | **There are five action-dropping guards, not three** | Found while placing the pass: `validate_destinations` (`:567`), `suppress_moves_for_unfiled_attachments` (`:585`), `filter_unresolvable_moc_links` (`:646`), `filter_missing_daily_notes` (`:713`) and `filter_unappliable_relationships` (`:728`, defined in `render_resolve.py:829`). They are split across two modules, which is why the fifth went unnoticed. The pass runs after all five; anywhere earlier is a latent instance of the bug being fixed. |
| 2026-09-09 | **ADR-4 retires the delete half of T5.3's path-keyed withdrawal; ADR-6 aborts on a dangling id** | Retiring rather than coexisting, because two relations for one fact is the drift being designed out — the `link_to_moc` title-keyed half stays, being genuinely different in kind. A dangling id aborts the run with exit 2 rather than degrading, matching `_validate_action_paths`: under ADR-1 the audit is vacuous, so a violation is an unknown-shaped bug, and emitting a set whose delete semantics cannot be trusted is worse than emitting nothing. |
| 2026-09-09 | **Consent is in scope, not only emission** | The site-4 group whose target cannot be resolved renders its Approve box **pre-checked** — `annotate_tag_handler_group_guards` returns early on a null target before it can set the guard that would suppress it. Owner decision: approval collected under a false premise is the same failure as the emission it authorises, so both are fixed here. The through-line is justification — a delete must have a live one, and the user's approval of one must be informed. |
| 2026-09-09 | **Tomo must never consume the executor's results** | Owner constraint, and it eliminated a feature that was about to be written. Reading applied-flags back is the only reliable way to detect a staging note stranded by a failed action, and it makes Tomo depend on Hashi — abandoning the user who applies the markdown by hand. The residue item is dropped from this spec with the rejected design recorded, so it is not re-proposed. |
| 2026-09-09 | **The wire dependency is not a generalisation of the guards — it is the only cover for TOCTOU** | Owner observation: a user can create a note at a claimed destination *between* generation and application. That clash does not exist when Tomo looks, so no build-time guard reaches it at any price. Route 1 covers what Tomo can see; route 2 covers what only the executor can see. This re-weights route 2 from optional generalisation to load-bearing. |
| 2026-09-09 | **One release — the guards and the wire field ship together** | Owner decision, against the recommendation to ship guards first. The guards are prerequisites for the wire field rather than companions to it: a guard that drops a partner without amending the deletes naming it produces a dangling dependency id. **Amended 2026-09-10**: as first written this row said "the executor cannot detect one". That holds only for its *failure list*, which contains only ids that actually ran; the consumer confirmed on 2026-09-09 that their plan-time check does catch a dangling id and **skips** the delete. The constraint stands on its own — we do not lean on their catch for a case we can prevent — but the reason as written was wrong, and this row was the last place it survived after the PRD and SDD were corrected. Retitled from "One phase" for the same reason: it constrains the **release**, not the phase order, and the plan has four phases. |
| 2026-09-09 | **Route 1 now, route 2 with spec 035 — routes chosen** | Route 1 is a one-line change to `validate_destinations`' claimant filter (`render_actions.py:989`): `create_moc` carries the same `destination` field as `move_note`, and `_paired_delete_candidates` returns `[]` for a claimant with no `source_inbox_item`, so the existing withdrawal machinery applies unmodified. It closes the data-loss path with no cross-repo dependency, which a data-loss path should not wait on. Route 2 generalises to sites 2 and 4 and is a wire change, so it rides spec 035's release alongside the daily-side `source_item_key` (spec 035's field — distinct from `item_key` on `suggestions[]`, which spec 034 shipped) — one re-vendor for Hashi instead of two. (Corrected 2026-09-09: this is two bumps on two documents, not one — the suggestions and instructions wires carry independent counters. One release, one changed-fields list; not one bump.) Route 3 is not rejected: route 2 supplies the data their `buildDependencies` would need, so it becomes their natural follow-on rather than a competing option. |
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

**Sent 2026-09-09** as a *question*, not the finished design:
`_outbox/for-hashi/2026-09-09_tomo-to-hashi_delete-source-depends-on-your-call-on-required.md`.

The earlier plan was to write this only once route 2's wire shape was settled. That was inverted
deliberately: the PRD's one blocking open question is whether `depends_on` should be required with
an explicit `[]` or optional, and that is Hashi's contract to decide, not ours to settle and then
announce. Building the emission rule first and asking afterwards would have made the answer
expensive. The handoff asks five questions and commits to nothing.

Verified in Hashi's source before sending, so the ask is grounded rather than inferred:

| Claim | Evidence |
|---|---|
| The skip mechanism exists and runs before every action | `InstructionExecutor.ts:394-400` — step 8b, `findDependencyFailure`, sets `{kind: "skipped-dependency", dependsOn}` |
| It already handles a **list** of dependencies | `:688-698` iterates `dependsOnIds`; `depMap` is `Map<string, string[]>` (`:677-686`) — a list-shaped field needs **no shape change** on their side |
| `skipped-dependency` is fully wired end to end | `state.ts:29`, `runLog.ts:276`, `outcomeSource.ts:308-309`, `sections.ts:72`, own tally bucket |
| A failure does not halt the run | every failure path ends in `continue` — `:403-410`, `:414-420`, `:445-451`, `:453-458`; only cancellation breaks (`:385-392`) |
| Only the *input* is missing | `buildDependencies` (`planner.ts:208-245`) **derives** edges structurally from `create_moc.destination`; it has never read a dependency off the wire |
| An already-applied partner is safe | `buildFileRecords` filters `a.applied !== true` (`:178-180`), so it never runs, never enters `failedIds`, and the delete proceeds — the wanted behaviour for a partial re-run, confirmed as a question rather than assumed |

The finished 036 handoff — schema files plus changed-fields list — still waits until the shape is
settled, and ships with spec 035's release.

### Refs

- `docs/XDD/specs/034-recursive-inbox-discovery/plan/phase-6.md` — T6.0b as originally proposed
  (2026-09-08, never accepted), and T5.3's precedent for dropping both claimants
- `docs/XDD/specs/034-recursive-inbox-discovery/close-out.md`
- `docs/XDD/specs/035-wire-schema-versioning/` — required reading before any wire change (route 2)
- MiYo Constitution, Privacy & Security L1 and Testing L1: filesystem/vault-mutation paths need
  tests for the denial case, which is exactly the case missing here

---
*This file is managed by the xdd-meta skill.*
