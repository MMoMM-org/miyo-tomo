# WHY: lib/render_md.py

> Rationale for decisions in `tomo/scripts/lib/render_md.py`.
> Deterministic markdown rendering for the instruction set — turns the
> already-built actions list into `instructions.md`. Only non-obvious
> decisions are recorded here.

## `move_asset` Gets Its Own Section, Not `new_files` (spec 031)

WHY `_md_section_for` routes `move_asset` to a new `"attachments"` section
rather than the `"new_files"` bucket `move_note`/`create_moc` already share:
`_md_section_for`'s own trailing fallback is `return "new_files"` — routing
`move_asset` there too would make "explicit, intentional branch" and "branch
deleted, fell through to the accidental default" produce the identical
string, so no test could ever prove the routing decision was deliberate
rather than a coincidence of the fallthrough. A distinct target
(`"attachments"`) makes the routing provably intentional: deleting the
explicit `move_asset` branch changes the observable section, which a test
catches directly. Confirmed by mutation before shipping.

## The `kind` Discriminator, and Why an Unrecognised One Renders Loudly

WHY each entry in `skipped_assets` (from `_build_move_asset_actions`,
`lib/render_actions.py`) carries a `"kind"` field (`"collision"` |
`"no_basename"`) that this file branches on to pick the remedy sentence: the
two failure modes need OPPOSITE user instructions. A destination collision
is fixed by renaming one of two real, existing files. A no-basename skip is
a malformed inbox-index entry — there is no file to rename, and telling the
user to rename one sends them looking for something that does not exist. An
earlier version used one shared remedy string for both cases; a code-quality
review caught that it told a no-basename user to rename a file, which costs
the reader time before they discover the advice is simply wrong for their
case.

WHY the branch is `if "no_basename" / elif "collision" / else <loud
placeholder>` rather than `if "no_basename" / else <collision remedy>`: the
two-armed form makes a missing or misspelled `kind`, or a third skip reason
added later, silently inherit the collision remedy — reintroducing the exact
bug just described, but by omission instead of by design. The `else` branch
renders `"(no remedy defined for skip kind ...)"`, mirroring
`_render_action_md`'s own `"(unknown action: ...)"` convention for the
parallel failure (an action kind with no rendering branch) rather than
raising: a pure renderer crashing the entire human-readable document over one
cosmetic gap in a `## Skipped` sub-block would be a worse failure than the
one being guarded against. Pinned by
`test_unrecognized_skip_kind_never_inherits_a_remedy` in
`tests/test_031_t2_3_move_asset_md_rendering.py`, proven by mutation
(reverting the `elif` to `else` makes the unrecognised-kind case inherit the
"rename" remedy again).

`kind` is deliberately NOT projected into `instructions.json`'s
`tomo.skipped_assets` (see `docs/tomo/scripts/instruction-render.md`) — it is
a rendering-only concern. This file is where its only consumer lives.
