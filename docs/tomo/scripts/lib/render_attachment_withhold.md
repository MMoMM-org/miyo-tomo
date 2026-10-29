# WHY: lib/render_attachment_withhold.py

> Rationale for decisions in `tomo/scripts/lib/render_attachment_withhold.py`.
> Keeps a note in the inbox when its attachment could not be filed, and drops the staging notes no surviving action claims.

## Split Out of `render_actions.py` (#216)

WHY this module exists: `render_actions.py` had grown to 2682 lines. It was split verbatim along its natural seams, and `render_actions.py` re-exports every name moved here. The full module map is in `docs/tomo/scripts/lib/render_actions.md`, section "Module Layout".

This guard is the destination guard's sibling, and it runs after `build_actions` for the same reason. It reuses the withdrawal machinery in `render_withhold.py` and does not copy it.

The decisions baked into this code are explained in `docs/tomo/scripts/lib/render_actions.md`:

- An Attachment Clash Keeps Its Note in the Inbox (spec 034 T5.4)
- T6.4c — Why a Withheld Move Also Withholds Its Staging Note
- `_attachment_suppression_reason` Reads Its Remedy From K16 (spec 039 T5.4)
