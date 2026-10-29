# WHY: lib/instructions_diff_expected.py

> Rationale for decisions in `tomo/scripts/lib/instructions_diff_expected.py`.
> Both sides of the Pass-2 coverage comparison: `derive_expected` and
> `summarize_actual`. Split out of `instructions-diff.py` (#216). See
> `docs/tomo/scripts/instructions-diff.md` for the module map.

## Why Both Sides Live Together

WHY: `derive_expected` rebuilds what the renderer should emit from
parsed-suggestions.json alone, and `summarize_actual` flattens instructions.json
into the same shape. The count table compares the two, so they must agree on
shape and key conventions. A change to one side usually needs the matching
change on the other, and keeping them in one file makes that pairing visible.

## Why `tag-handler-group.py` Is Loaded Here

WHY: `derive_expected` keys tag-handler deletes on `group_id`, the same slug the
renderer uses. `tag-handler-group.py` is a hyphenated script, so it is loaded
via importlib, resolved relative to `scripts/lib/` the way
`lib/render_actions.py` does it. `group_id` is re-exported from the CLI.

The rationale for each counting rule (the four delete sources, the audio peer,
attachment dedup, extend_moc members) is in
`docs/tomo/scripts/instructions-diff.md`.
