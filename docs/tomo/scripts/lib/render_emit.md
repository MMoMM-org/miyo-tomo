# WHY: lib/render_emit.py

> Rationale for decisions in `tomo/scripts/lib/render_emit.py`.
> The id, inbox-path and wikilink helpers every action builder shares.

## Split Out of `render_actions.py` (#216)

WHY this module exists: `render_actions.py` had grown to 2682 lines. It was split verbatim along its natural seams, and `render_actions.py` re-exports every name moved here. The full module map is in `docs/tomo/scripts/lib/render_actions.md`, section "Module Layout".

These helpers sit in a leaf module so each builder module can import them. If they stayed in `render_actions.py`, a builder module would have to import the facade, and the facade imports the builders, which is a cycle.

The decisions baked into this code are explained in `docs/tomo/scripts/lib/render_actions.md`:

- Every Inbox Path Goes Through One Resolver (spec 034 T5.0)
- The Delete Bookkeeping Joins on the Note, Not the Filename (spec 034 T5.0b)
