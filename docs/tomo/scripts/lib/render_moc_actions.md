# WHY: lib/render_moc_actions.py

> Rationale for decisions in `tomo/scripts/lib/render_moc_actions.py`.
> The create_moc, link_to_moc and extend_moc action builders.

## Split Out of `render_actions.py` (#216)

WHY this module exists: `render_actions.py` had grown to 2682 lines. It was split verbatim along its natural seams, and `render_actions.py` re-exports every name moved here. The full module map is in `docs/tomo/scripts/lib/render_actions.md`, section "Module Layout".

Every action that creates a MOC or writes a bullet into one lives here. The link_to_moc dict is built in one place (`_link_to_moc_action`), so every path that writes a bullet produces the same shape.

The decisions baked into this code are explained in `docs/tomo/scripts/lib/render_actions.md`:

- `_build_create_moc_actions` Keys by `path_key` Too (spec 039 W7, v0.29.3)
- `source_note_title` Is Display Text, `source_note_stem` Is the Vault Key
- An Accepted Extension Expands Into Existing Action Kinds (spec 042 T4.4, ADR-6, v0.32.0)
