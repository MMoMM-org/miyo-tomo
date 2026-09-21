# WHY: lib/render_helpers.py

> Rationale for decisions in `tomo/scripts/lib/render_helpers.py`.
> Pure, cross-module primitives for instruction rendering — stem helpers and,
> since spec 036 T4.3, the delete-withdrawal cause join. Only non-obvious
> decisions are recorded here.

## Why This Module Is the DAG Leaf, and What That Buys T4.3

The module docstring already states the design goal: "no dependency on any
other render module (keeps the module graph a DAG)." `render_actions.py`
imports `bare_stem` from `render_md.py` (`from lib.render_md import
bare_stem`) — one-directional; `render_md.py` imports nothing from
`render_actions.py`. `render_helpers.py` imports from neither, and both of
the others already import from it — it is the one place in the render_*
graph that is safely importable by every sibling.

**Corrected 2026-09-17 (code-quality review):** an earlier version of this
note claimed the withdrawal-cause join "cannot live in either"
`render_actions.py` or `render_md.py`. That overstated the constraint. Only
`describe_withdrawal_cause` is called directly by `render_md.py` itself
(its markdown "## Skipped" section) — so ONLY that one function cannot live
in `render_actions.py`: `render_md.py` would then have to import it back
from `render_actions.py`, completing the cycle `render_md -> render_actions
-> render_md`. `attribute_withdrawal_causes` and
`build_delete_withdrawal_reports` are consumed solely by
`instruction-render.py` (never called from inside `render_md.py` or
`render_actions.py` themselves), and `instruction-render.py` already
imports from both files without cycle risk — so either of those two could
equally have lived in `render_actions.py`, next to
`withdraw_unjustified_deletes`, where the join conceptually reads more
naturally as the join over that function's own output.

Grouping all three in `render_helpers.py` is therefore a **cohesion
choice** — one module owns the whole withdrawal-cause join, so
`instruction-render.py`'s stderr block and `render_md.py`'s markdown
section format the same cause from the same place — not a placement the DAG
left no other option for.

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

## `render_md.py`'s Adjacency Grouping Joins on Every Cause, Not Just the First

`render_md.py._group_delete_withdrawals` (PRD F2-AC4) originally read only
`causes[0]` — the first cause — to decide where a withdrawal nests, on the
claimed grounds that a withdrawal's `causes` always share one guard. That
claim was wrong: `_build_daily_update_actions`'s `ids_by_origin`
(`tomo/scripts/lib/render_actions.py`) accumulates one origin's
daily-action ids across every day that origin touches, so a single
`delete_source`'s `depends_on` can legitimately name two different
`update_tracker`/`update_log_entry` ids for two different missing daily
notes — the SAME guard (`filter_missing_daily_notes`), two different
`missing_id`s. That case is reachable through the code shipped today, not
merely a hypothetical future emission site mixing two guards' ids — a
code-quality review (2026-09-17) reproduced it: a delete withdrawn because
two daily notes were both missing rendered nested under only the first
daily bullet, leaving the second silent about it, exactly the F2-AC4
adjacency failure this task exists to prevent. `_group_delete_withdrawals`
now joins on EVERY cause naming an inline-guard id, nesting the withdrawal
under every matching bullet (deduplicated per missing id, so a cause
repeating an id already seen does not double-render); see
`docs/tomo/scripts/lib/render_md.md` for the rendering-side half of this
decision.

## `WITHDRAWAL_GUARDS` Is Now Validated at Its Three Duplicate Sites, Not Just Documented

`WITHDRAWAL_GUARDS` reads as the single source of truth for the five guard
names — the "unattributed" tripwire above points readers at it — but until
2026-09-17 nothing actually imported or checked against it. The same five
names were independently duplicated three times: `drop_sources`' dict keys
(`instruction-render.py`), `_INLINE_WITHDRAWAL_GUARDS` (`render_md.py`), and
`ALL_GUARDS` (`tests/test_036_t4_3_withdrawal_reporting.py`). A sixth guard
added to one copy without updating the other two was caught by nothing
(code-quality review advisory). Fixed by making all three import
`WITHDRAWAL_GUARDS` and validate against it:

- `tests/test_036_t4_3_withdrawal_reporting.py`'s `ALL_GUARDS` is now
  `WITHDRAWAL_GUARDS` itself (an alias, not a re-typed copy) — equality by
  construction.
- `render_md.py` asserts `_INLINE_WITHDRAWAL_GUARDS <= set(WITHDRAWAL_
  GUARDS)` at module load — a SUBSET relation, deliberately, not equality:
  only the three guards whose own report already renders inside "## Skipped"
  belong here; `validate_destinations` and `suppress_moves_for_unfiled_
  attachments` render under their own "## Not filed" headings and are
  correctly absent.
- `instruction-render.py` asserts `set(drop_sources) == set(WITHDRAWAL_
  GUARDS)` right after building the dict — equality, not subset: every one
  of the five guards' drops must be attributable to a report, so none may be
  missing and none extra.
