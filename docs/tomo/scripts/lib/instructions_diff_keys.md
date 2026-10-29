# WHY: lib/instructions_diff_keys.py

> Rationale for decisions in `tomo/scripts/lib/instructions_diff_keys.py`.
> Identity and parsing helpers for the Pass-2 coverage audit. Split out of
> `instructions-diff.py` (#216). See `docs/tomo/scripts/instructions-diff.md`
> for the module map.

## Why a Leaf Module

WHY: every other `instructions_diff_*` module joins expected entries to rendered
actions through `_keys_match`, `_confirmed_key`, `_daily_key` and
`_same_note_as_any`. One copy of those join rules (ADR-1) keeps the expected side
and the actual side keyed the same way. The module imports only `lib.item_key`,
so any of the others can import it without a cycle.

## Why `_parse_supporting_items` Is Not `lib.supporting_items`

WHY: the two parsers differ on an edge case. The audit filters out empty tokens
before it strips brackets, so a token such as `[]` survives as an empty string.
The shared parser filters after stripping and drops that token. The #216 split
moved code without changing behaviour, so the audit kept its own copy. Unifying
the two is a separate change, and it needs its own byte-diff of the audit output.

The rationale for each join rule (`_keys_match`'s trailing-segment tolerance,
`_same_note_as_any`'s symmetry, the `item_key` preference) is in
`docs/tomo/scripts/instructions-diff.md`.
