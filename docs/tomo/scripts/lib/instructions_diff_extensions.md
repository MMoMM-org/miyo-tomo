# WHY: lib/instructions_diff_extensions.py

> Rationale for decisions in `tomo/scripts/lib/instructions_diff_extensions.py`.
> The per-member check of `extend_moc` items. Split out of
> `instructions-diff.py` (#216). See `docs/tomo/scripts/instructions-diff.md`
> for the module map.

## Why a Separate Module

WHY: an `extend_moc` item has no file action. The per-item move/create check in
`run_diff` does not apply to it. Instead, each member is checked against the
renderer's `tomo.extensions` record. That is a different join and a different
report section, so it gets its own module. `_reconcile_extensions` returns
`(lines, notes, hard_fail)`, and `run_diff` splices those into its report.

The rationale for the per-member rules (deduplicated members, case-insensitive
`already_linked` and `no_relationship`, `add_relationship` kept out of the count
table) is in `docs/tomo/scripts/instructions-diff.md` under "An Extension Is
Checked Per Member, Not as a Move".
