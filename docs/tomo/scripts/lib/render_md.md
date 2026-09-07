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

## The Destination-Clash Block Leads the Document (spec 034 T5.3)

`destination_clashes` renders **before** every action section, unlike
`skipped_daily`, `skipped_rel`, `skipped_assets` and `dropped_sources`, which
all sit in the trailing `Skipped — un-appliable actions` block.

The placement is the point. Those four are skips the user can act on whenever
they get to them. This one is the only place where an item the user *approved*
was deliberately not filed, and ADR-4 drops **both** claimants, so two approved
items are missing from the action list below. A reader who stops after the first
section must still have seen it.

The block names each claimant by its source note, states that those sources are
untouched in the inbox, and gives the remedy — rename one and re-run Pass 2,
without restarting the run. It never folds or normalises a name for display:
the reason sentence shows each destination spelled the way its author wrote it,
so a user told their name collides sees the name they actually typed.

### The Heading Must Not Count Claimants

`validate_destinations` produces two kinds. A `run_collision` names two
claimants; a `vault_collision` names one, because the second claim belongs to a
note already in the folder. The heading and intro are therefore kind-neutral —
"a destination is claimed twice", "choosing between them would be a guess" —
and each bullet's own reason says which kind it is.

An earlier version read `## Not filed — two items claim one destination`, which
sat directly above a single bullet whenever the clash was with the vault. Under
CON-2 the user approves on what this document says, so a report that miscounts
what it withheld is a wrong basis for approval even when the withholding itself
is right — the same class of defect as T5.0b's reason strings, which credited
one note with another's daily entry. One section covers both kinds in a run
that hits both, which is why the wording has to be true of each on its own.

## `attachment_suppressions` Gets Its Own Section (spec 034 T5.4)

Rendered immediately after the destination-clash block, above the action
sections, for the same reason that one sits there: a note the run refused to
file is what the reader must see before approving anything else.

WHY a separate section rather than a second bullet kind under
`## Not filed — a destination is claimed twice`: the two withholdings have
different remedies. A destination clash is resolved by renaming a **note**; an
attachment that could not be filed, by renaming a **file**. Under CON-2 the
user approves on what this document says, so a reader who cannot tell which
happened cannot act on either. The reason line names the attachment, not just
the note, so the file to rename is in the document.

The `skipped_assets` block further down still lists the attachment itself under
`**Attachment not filed**`. That is deliberate and not a duplicate: it reports
files that were not filed, some of which belong to no moving note at all, while
this section reports the notes held back. `owner_source_items`, the field
`_build_move_asset_actions` added to link the two, is not rendered — the
skipped-asset bullets are byte-identical to before.

## "Withdrawn With It" Is Count-Neutral (spec 034 T5.5)

`_withdrawn_links_note` appends one sentence to both "Not filed" intros when a
withholding took a `link_to_moc` with it. The user approved that bullet in
Pass 1, so its absence from the action list is a change to what was agreed and
has to be stated rather than left silent.

It counts nothing, for the reason the two intros above it are already
kind-neutral: a run collision names two claimants and a vault collision one, so
a sentence that counted would contradict the bullets underneath it in whichever
case it did not describe. It is also omitted entirely when nothing was
withdrawn — a reader told about a consequence that did not happen has to go
check whether it did.

## The Delete Heading Names the Note, the `reason` Names the Cause (spec 034 T5.5)

`_render_action_md`'s `delete_source` branch hardcoded the heading "Delete
source note (content captured in daily note)". `_build_delete_source_actions`
has **five** emission sites with five different `reason` strings, so four out
of five deletes were headed with a cause their own body contradicted:

```
### I16 — Delete source note (content captured in daily note)
- **Action:** Delete the note from the inbox — Origin consumed by 1 atomic.
```

Pre-existing — introduced by the `#113` refactor (`6d15fa9`), not by spec 034 —
and fixed here anyway: under CON-2 the user approves deletions on this
document, and a heading that misstates why a note is being deleted is the same
class of defect as the one T5.3 shipped and corrected in `76ae8be`.

WHY neutral-plus-subject rather than a heading derived from `reason`: deriving
it would put the cause in two places, and the second place is the one that goes
stale — which is exactly how the hardcoded parenthetical survived four new
reason strings. `reason` stays the single statement of the cause, on the
`**Action:**` line, where the user reads it before ticking the box. For
`I12` — the one genuine daily capture — the old heading was not wrong, merely
redundant with the line beneath it; nothing is lost by dropping it.

The heading instead names its subject, `Delete source note: Root Note`, which
is what the other sections already do (`Move note: …`, `Move attachment: …`,
`Skip — …`). That makes `## Source Deletions` an index of which notes leave the
inbox — information the section did not previously carry at heading level, and
the thing a user actually scans this section for.
