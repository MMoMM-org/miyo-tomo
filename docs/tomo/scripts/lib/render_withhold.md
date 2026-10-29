# WHY: lib/render_withhold.py

> Rationale for decisions in `tomo/scripts/lib/render_withhold.py`.
> The Pass-2 destination guard, the shared paired-delete / MOC-bullet withdrawal machinery, and `withdraw_unjustified_deletes`.

## Split Out of `render_actions.py` (#216)

WHY this module exists: `render_actions.py` had grown to 2682 lines. It was split verbatim along its natural seams, and `render_actions.py` re-exports every name moved here. The full module map is in `docs/tomo/scripts/lib/render_actions.md`, section "Module Layout".

Both guards withdraw through one mechanism (`_drop_moves_with_paired_deletes`). The attachment guard imports it from here, so the withdrawal has one copy and cannot drift.

The decisions baked into this code are explained in `docs/tomo/scripts/lib/render_actions.md`:

- The Pass-2 Destination Guard (spec 034 T5.3)
- A Withheld Move Takes Its MOC Bullets With It (spec 034 T5.5)
- The Path-Keyed Delete Withdrawal Retires (spec 036 T2.3, ADR-4)
