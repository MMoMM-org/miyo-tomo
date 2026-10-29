# WHY: lib/render_contested_links.py

> Rationale for decisions in `tomo/scripts/lib/render_contested_links.py`.
> Qualifies the MOC bullets for a filename this run files at more than one destination.

## Split Out of `render_actions.py` (#216)

WHY this module exists: `render_actions.py` had grown to 2682 lines. It was split verbatim along its natural seams, and `render_actions.py` re-exports every name moved here. The full module map is in `docs/tomo/scripts/lib/render_actions.md`, section "Module Layout".

The contested set is taken before the guards run, but the rewrite runs after them. Those two timings are why this is a separate pass and not a choice made when the bullet is emitted.

The decisions baked into this code are explained in `docs/tomo/scripts/lib/render_actions.md`:

- A MOC Bullet Outlives the Run That Wrote It (spec 034 T5.5)
