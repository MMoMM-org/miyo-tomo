# WHY: lib/render_source_actions.py

> Rationale for decisions in `tomo/scripts/lib/render_source_actions.py`.
> The tag-handler insert_under_marker builder and the delete_source builder, with the target gate they share.

## Split Out of `render_actions.py` (#216)

WHY this module exists: `render_actions.py` had grown to 2682 lines. It was split verbatim along its natural seams, and `render_actions.py` re-exports every name moved here. The full module map is in `docs/tomo/scripts/lib/render_actions.md`, section "Module Layout".

ADR-5 made `_tag_handler_group_has_resolvable_target` the single predicate both builders consult. A test patches it once and expects both builders to see the patch. A function resolves names in its own module, so the gate and both builders must live in the same module. That is why the delete builder sits here and not in `render_inbox_actions.py`, and why the test's patch target is `lib.render_source_actions`.

The decisions baked into this code are explained in `docs/tomo/scripts/lib/render_actions.md`:

- WHY the Origin's Delete Waits for Its Attachment Moves (spec 039 T5.2, ADR-10, #186)
- The Delete Bookkeeping Joins on the Note, Not the Filename (spec 034 T5.0b)
