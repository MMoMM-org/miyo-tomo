# WHY: lib/source_link.py

> Rationale for decisions in `tomo/scripts/lib/source_link.py`.
> The collision rule and the `[[path|display]]` link form, shared by the
> suggestions document and the instruction document. Only non-obvious
> decisions are recorded here.

## WHY a Module at All (spec 034 T5.1 → T5.5)

T5.1 solved this once, inside `suggestions-reducer.py`, for the **suggestions**
document: recursive discovery lets two inbox notes in different subfolders
share a filename, and a bare `[[Dresden]]` resolves by name, so the vault picks
one of them.

T5.5 found the same defect at three more sites in the **instruction** document
(`render_md`'s three source displays) and at one in the action list
(`render_actions`' MOC bullet). Copying the rule would have made four copies of
one decision in a file family that has already had to repair two:
`_drop_moves_with_paired_deletes` was consolidated for exactly this reason, and
T5.0c existed because a second copy of a join had drifted.

So the two primitives moved here and `suggestions-reducer` imports them. T5.1's
own two helpers moved with them unchanged in behaviour, so the suggestions
document is untouched.

## WHY `colliding_names` Counts Distinct Paths, Not Occurrences

T5.1's original counted **occurrences** of a stem, which is right where each
entry is one work item. It is wrong at the instruction document's sites: one
note is routinely displayed twice there — a `move_note`'s source reference and
its own `delete_source` both name the origin — and an occurrence count calls
that a collision and qualifies a link that was never ambiguous.

Counting distinct paths is correct for both callers, so it is the rule that
moved. The reducer's behaviour changes only where an item_key appeared twice in
one run, and there the old count over-qualified.

## WHY Qualification Is Collision-Only

The path form always resolves, so qualifying everything would also be correct —
and it is what a first attempt reaches for. It is rejected because a run with no
namesakes must render byte-identically: the goldens pin that, and a document
that suddenly shows paths everywhere reads as a regression to the user who has
been reading bare names for months. Over-qualification is cheap but not free.

## WHY `qualified_target` Drops `.md`

Obsidian resolves a wikilink to a note, not to a file. `[[Atlas/202 Notes/
Dresden.md|Dresden]]` is a different, non-existent target. The helper owns that
detail so no caller has to remember it — `render_md`, `render_actions` and the
reducer all format the same link through it.
