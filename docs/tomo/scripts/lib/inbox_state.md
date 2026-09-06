# WHY: lib/inbox_state.py

> Rationale for decisions in `tomo/scripts/lib/inbox_state.py`.
> The module replays the append-only `tomo-tmp/inbox-state.jsonl` run-state log
> into a per-item view. It exposes `last_state_per_item_key(state_path)` and
> `display_stem(entry, item_key)`.

## Why This Module Exists At All (spec 034 T2.3)

WHY the replay was extracted instead of fixed in place: it existed **twice** —
`suggestions-reducer.py` and `mark-captured.py` each carried their own
`last_state_per_stem`, and both keyed on the bare filename. With a recursive
inbox, two notes sharing a filename in different subfolders collapse onto one
entry: the later line wins, one item's status masks its namesake's, and that
namesake silently drops out of the run. `mark-captured.py`'s copy is the worse
of the two — it drives a `write_frontmatter` call, so a collision there mutates
the wrong note in the user's vault.

Patching both copies would have left the same defect that produced #165: one
identity computation living in two places, free to drift, with a regression
test that only covers one of them. There is now one replay, and both readers
call it.

## Keyed on `item_key`, Not `stem` (ADR-1 / ADR-2)

WHY the dict key is `item_key`: it is the item's vault-relative path, verbatim,
which stays unique across subfolders. `stem` is a bare filename and is
display-only. `state-entry.schema.json` requires both fields, so every entry a
current `state-update.py` writes can be replayed on the key.

WHY entries without an `item_key` are passed over rather than falling back to
`stem`: a stem fallback would quietly reintroduce the collision this module
exists to remove. In practice no such entry reaches a live run — `--item-key`
is a required argument of `state-update.py`, and the `run_id` filter applied by
both callers already scopes the work list to entries this run wrote.

## Fail-Open on a Missing or Malformed Log

WHY an absent file yields an empty replay, and an unparseable or non-object
line is skipped rather than aborting: this preserves the behaviour the
reducer's copy already had. A single corrupt line in an append-only log —
a half-written record from an interrupted run, say — must not take down a run
that can still process every other item. The items affected by a skipped line
do not vanish quietly: they never enter the work list, and the caller's own
missing-result reporting names anything that was expected and is not there.

## `display_stem` Never Returns a Path

WHY the fallback for an entry with no `stem` is the key's **basename** rather
than the key itself: the returned value goes straight into note titles and
`[[wikilinks]]` in the reducer. Returning the key would write
`100 Inbox/Places/Dresden` into the user's vault as a title, or emit a broken
`[[100 Inbox/Places/Dresden]]`, and nothing would error. The basename is wrong
in the same way the missing `stem` was wrong, but it is not *destructive*.
