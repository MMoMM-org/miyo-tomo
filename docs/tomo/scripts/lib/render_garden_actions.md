# WHY: lib/render_garden_actions.py

> Rationale for decisions in `tomo/scripts/lib/render_garden_actions.py`.
> Garden-audit action assembly: `build_garden_audit_actions` and the edit_note_text / edit_frontmatter builders.

## Split Out of `render_actions.py` (#216)

WHY this module exists: `render_actions.py` had grown to 2682 lines. It was split verbatim along its natural seams, and `render_actions.py` re-exports every name moved here. The full module map is in `docs/tomo/scripts/lib/render_actions.md`, section "Module Layout".

Garden-audit confirmed_items are semantic fix items, not the suggestions manifest, and `build_actions` never reaches them. Keeping them apart leaves the Pass-2 hot path untouched. The `_construct_edit_frontmatter_fields` contract is in its docstring.
