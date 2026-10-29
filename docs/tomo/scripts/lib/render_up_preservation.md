# WHY: lib/render_up_preservation.py

> Rationale for decisions in `tomo/scripts/lib/render_up_preservation.py`.
> Rule 4.x: add_relationship actions that keep a child note's existing parent link, plus the related:: aggregation per target note.

## Split Out of `render_actions.py` (#216)

WHY this module exists: `render_actions.py` had grown to 2682 lines. It was split verbatim along its natural seams, and `render_actions.py` re-exports every name moved here. The full module map is in `docs/tomo/scripts/lib/render_actions.md`, section "Module Layout".

Rule 4.x is one self-contained rule set, read by both the MOC-proposal path and the extend_moc path. It lives on its own so both can use it without pulling in each other.

The decisions baked into this code are explained in `docs/tomo/scripts/lib/render_actions.md`:

- An Existing `up::` Target Is Checked Against Obsidian's Link Graph (#82, v0.31.0)
- No User-Written `up::` Is Dropped — Rule 4.3 Retired (spec 042 T5.3d, v0.33.0)
