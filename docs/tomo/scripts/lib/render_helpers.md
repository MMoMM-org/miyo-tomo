# WHY: lib/render_helpers.py

> Rationale for decisions in `tomo/scripts/lib/render_helpers.py`.
> Pure, cross-module primitives for instruction rendering — stem helpers and,
> since spec 036 T4.3, the delete-withdrawal cause join. Only non-obvious
> decisions are recorded here.

## Why This Module Is the DAG Leaf, and What That Buys T4.3

The module docstring already states the design goal: "no dependency on any
other render module (keeps the module graph a DAG)." `render_actions.py`
imports `bare_stem` from `render_md.py` (`from lib.render_md import
bare_stem`), which means `render_md.py` cannot import anything from
`render_actions.py` without completing a cycle. `render_helpers.py` imports
from neither, and both of the others already import from it — it is the one
place in the render_* graph that is safely importable by every sibling.

That constraint is what put the spec 036 T4.3 withdrawal-cause join here
instead of next to `withdraw_unjustified_deletes` in `render_actions.py`
(where it conceptually reads more naturally, as the join over that
function's own output): `instruction-render.py`'s stderr block and
`render_md.py`'s markdown "## Skipped" section both need to format the same
cause, and only this module can be imported by both without restructuring
the render_actions/render_md relationship — a change out of scope for a
reporting task.

## `attribute_withdrawal_causes` Takes Pre-Normalised `drop_sources`, Not the Five Guards' Raw Reports

The five action-dropping guards report in three different shapes:
`validate_destinations` and `suppress_moves_for_unfiled_attachments` nest a
`dropped` list of dicts inside each clash/suppression record;
`filter_unresolvable_moc_links`, `filter_missing_daily_notes` and
`filter_unappliable_relationships` each return a flat list of skipped action
dicts. `attribute_withdrawal_causes` does not know any of this — its
signature is `dict[str, list[str]] -> ...`, a name-to-ids mapping the CALLER
(`instruction-render.py`, where all five reports already exist as local
variables right after the guards run) builds by projecting each shape's own
`.get("id")`. Keeping the join itself shape-blind means adding a hypothetical
sixth drop site later costs one new dict entry at the call site, not a new
branch inside the join — and a site that is *forgotten* at the call site
degrades gracefully into the `"unattributed"` tripwire below rather than a
crash or a silent misattribution.

## Three-Way Distinction: `guard=None` (undeclared) vs. `guard="unattributed"` (tripwire) vs. `guard=<name>` (resolved)

`depends_on_declared: False` (the delete never named a justification at all)
and a missing id that resolves to no guard's dropped-id list (every guard
ran, and none of them dropped this id) are different failure shapes with
different implications for the reader, and were kept lexically
non-collidable on purpose:

- `guard=None` reads "nothing was ever declared" — not a join failure, a
  declaration failure. `missing_id` is also `None` here; there is no id to
  have looked up.
- `guard="unattributed"` reads "something WAS declared, named a real id, and
  no guard's report says it dropped that id" — structurally unreachable
  today (`withdraw_unjustified_deletes` runs after all five guards, so every
  id it can name either was dropped by one of them or never existed in the
  set). Kept as a tripwire against a future sixth drop site that removes an
  action without reporting what it removed. `unattributed` is a plain
  string, not `None`, specifically so it can never be mistaken for the
  undeclared case above by an `is None` check.
- `guard=<one of WITHDRAWAL_GUARDS>` is the resolved, expected case.

## The Five Guards Are Structurally Disjoint — No Collision Handling Needed

`validate_destinations` and `suppress_moves_for_unfiled_attachments` drop
`move_note`/`create_moc` ids; `filter_unresolvable_moc_links` drops
`link_to_moc` ids; `filter_missing_daily_notes` drops daily-action ids;
`filter_unappliable_relationships` drops `add_relationship` ids. Each
governs one action kind, and the kinds are disjoint by construction, so one
id can never appear in two guards' dropped-id lists in the same run.
`attribute_withdrawal_causes`' `id_to_guard.setdefault(...)` (first match
wins) exists for defensive determinism only — there is no reachable input
that exercises the "second guard" branch, and no test asserts one (see
`tests/test_036_t4_3_withdrawal_reporting.py`'s "NOT a test" comment).

## `render_md.py`'s Adjacency Grouping Assumes One Withdrawal, One Guard

`render_md.py._group_delete_withdrawals` (PRD F2-AC4) reads only
`causes[0]` — the first cause — to decide where a withdrawal nests. This is
sound only because every `_build_delete_source_actions` emission site names
ids from exactly ONE guard's action kind (SDD "Complex Logic": site 2 names
only daily-action ids, site 3 names only move ids, site 4 names exactly one
insert id), so a withdrawal's `causes` share one guard in every reachable
case today. If a future emission site ever declared `depends_on` mixing ids
from two different guards' action kinds on one delete, that withdrawal would
render only at its first cause's location, not split across two — a
narrowing this module accepts explicitly rather than leaves implicit; see
`docs/tomo/scripts/lib/render_md.md` for the rendering-side half of this
decision.
