# WHY: lib/instructions_diff_reconcile.py

> Rationale for decisions in `tomo/scripts/lib/instructions_diff_reconcile.py`.
> Subtracts the renderer's deliberate withholdings from the expected tallies.
> Split out of `instructions-diff.py` (#216). See
> `docs/tomo/scripts/instructions-diff.md` for the module map.

## Why the Subtractions Are One Module

WHY: each `_subtract_*` removes one kind of deliberate withholding that the
renderer records in `instructions.tomo`: a skipped daily note, a guard-withheld
move, a withdrawn delete, an unfiled asset or an unconfirmed MOC link. They
share one contract: mutate `expected` in place, never go below zero, and return
the count removed. They also depend on each other's ordering. For example,
`_subtract_withdrawn_deletes` skips the guards that `_subtract_withheld_moves`
already handled. Keeping them together keeps that ordering contract in one place.

`_CLASH_WITHDRAWAL_GUARDS` and its subset assertion against
`render_helpers.WITHDRAWAL_GUARDS` moved with `_subtract_withdrawn_deletes`, its
only reader. The assertion still runs at import time.

`_unresolvable_link_notes` lives here, next to `_subtract_unresolvable_links`,
because the garden mode and the suggestions report both use it.

The rationale for each subtraction is in
`docs/tomo/scripts/instructions-diff.md`.
