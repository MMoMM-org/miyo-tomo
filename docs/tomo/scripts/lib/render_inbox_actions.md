# WHY: lib/render_inbox_actions.py

> Rationale for decisions in `tomo/scripts/lib/render_inbox_actions.py`.
> The move_note, move_asset and daily-update action builders.

## Split Out of `render_actions.py` (#216)

WHY this module exists: `render_actions.py` had grown to 2682 lines. It was split verbatim along its natural seams, and `render_actions.py` re-exports every name moved here. The full module map is in `docs/tomo/scripts/lib/render_actions.md`, section "Module Layout".

These are the actions that file an inbox item's own content. They are grouped because each one addresses its origin by item_key (ADR-1).

The decisions baked into this code are explained in `docs/tomo/scripts/lib/render_actions.md`:

- `_build_move_asset_actions` Returns `(actions, skipped)`
- The Move Builder Is a Projection of the Attachment Plan (spec 039 T4.3)
- `_resolve_daily_path`'s Fallback Does Not Trust the Config Value (standalone fix, 2026-09-17)
