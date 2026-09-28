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

## The Instruction Document Says WHICH Note (spec 034 T5.5)

T5.1 path-qualified source links in the **suggestions** document. The
instruction document kept rendering `**Source:** [[Dresden]]` — on a
`delete_source`, with three Dresden notes in the run.

The action itself was correct: `source_path` held the resolved
`100 Inbox/Quellen/Dresden.md`, so T5.0b's addressing did its job. The defect
is in what the document SAYS, and under CON-2 that is what the user approves —
here, an irreversible delete they cannot tell the target of. It is the most
consequential place in the whole document for an ambiguous name.

`_source_wikilink` applies T5.1's form and T5.1's collision-only rule at all
three source-display sites, found by reading the file rather than by fixing the
one the report named: the `delete_source` `**Source:**`, the `move_note`
`**Source (reference):**`, and the `skip` `**Source:**`. One sentence in three
places is one defect in three places — this file family has been bitten four
times in this spec by fixing the named site alone.

### WHY the Withheld Moves Count Toward the Collision Set

`_source_display_paths` also reads `destination_clashes` and
`attachment_suppressions` from the metadata. Those moves are gone from
`actions` by the time it runs, but the "Not filed" sections above still name
them, and they are what makes a surviving namesake ambiguous: the reader sees
three Dresden notes in one document whether or not the run files all three. A
set taken from the surviving actions alone sees one and renders the bare link.

### WHY the Delete Heading Keeps the Bare Stem

`### I16 — Delete source note: Dresden` is an index entry, not a link. A path
there would make `## Source Deletions` unscannable, which is the property the
heading was given a subject for in the first place. The `**Source:**` line
directly beneath is the one the user clicks, and that is the one qualified.

## The Merge Section Is Not a "Not filed" Section (spec 034 T6.0c)

WHY the merge report gets its own heading rather than a third bullet kind under
either "Not filed" section: **nothing was withheld.** A destination clash and an
attachment suppression both mean an item the user approved was deliberately not
filed. A merge means the opposite — the MOC **is** created, once instead of
twice, with every approved proposal's tags and supporting items combined.

Describing that as a withholding would misdescribe the outcome, which is the
exact class of defect T5.5 was written to remove. The section takes the
*structure* of the clash section — a lead section before the action list, naming
both spellings, cause plus remedy — and none of its words.

WHY it sits before the action list, like the clash section: it changes what that
list contains. A reader who meets one `create_moc` where they approved two
proposals needs the explanation before the list, not after it. Under CON-2 the
user approves on what this document says.

WHY the intro is count-neutral: a group can absorb one spelling or several, and
a heading that counted them would contradict the bullets underneath it in
whichever case it did not describe — the same reasoning the destination-clash
intro records. Each record's own `reason` carries its count and, when the names
differed only in case, says so.

## "MOC Link Not Offered" Is a Skipped-Section Block, Not a Lead Section (spec 034 T6.0d)

WHY this withholding goes under `## Skipped — un-appliable actions` rather than
getting its own lead section like the destination clash and the attachment
suppression: those two withhold a **move**, so the note the user approved stays
in the inbox and the rest of the document has to be read in that light — the
explanation has to come first. A withheld MOC link changes nothing about where
the note goes; only the bullet on the MOC is missing. It belongs with the other
un-appliable actions, beside the missing daily note and the missing up-link
child, which are the same shape.

WHY each bullet carries its own remedy rather than one shared sentence: the
three causes are three different situations for the user.

| cause | what the bullet says |
|---|---|
| `absent` | MOC not found — create it, or correct the name, and re-run Pass 2 |
| `unchecked` | MOC could not be checked: Kado was not available for this run |
| `probe-failed` | MOC could not be checked: the Kado lookup failed |

Only the first says the MOC is missing. Telling an offline user their MOC does
not exist would invite them to re-create a MOC that is already there — the
document would be worse than the defect it replaced. The unrecognised-cause
branch falls through to a self-naming placeholder for the same reason the
`skipped_assets` and `dropped_sources` blocks do: a fourth cause must never
silently inherit one of the three sentences above.

### The Shared Intro Carries No Claim At All

WHY the sentence above the three bullets asserts nothing about the MOC: two of
the three bullets under it say the MOC's existence is **unknown**, so an intro
that states the MOC is absent — or that the instruction cannot be carried out —
contradicts a sibling two lines below it, in the same block, which the user reads
whole under CON-2. The first cut shipped exactly that: *"an instruction to open a
MOC that is not there is one you cannot carry out"* sitting above *"not a missing
MOC"*. Nine tests, a TDD gate and a compliance review passed it, because every
one of them read the intro beside a single cause.

The invariant: **the intro must be true beside every bullet that can appear under
it, and it must not vary by cause.** Both halves are pinned by a test that renders
all three causes into one block — `main()` cannot produce that shape (`unchecked`
needs `client is None` for the whole run), so the renderer is driven directly, on
purpose. A per-cause test cannot see a contradiction between an intro and a
sibling bullet.

Report-only: the enclosing heading `## Skipped — un-appliable actions` is
pre-existing and shared with four other blocks, and "un-appliable" is likewise
true only for the confirmed-absent cause — the other two may be perfectly
appliable once Kado answers. Changing a heading four other blocks sit under is a
separate change.

## T4.3 — A Withdrawal Nests Under Its Own Guard's Bullet, or Falls to a Catch-All

PRD F2-AC4 requires a withheld daily action (or a similarly-skipped
`add_relationship` / `link_to_moc`) and the delete it withdrew to read as
**structurally grouped**, not merely both present somewhere in the document —
`assert "I05" in md` twice would pass on the exact defect the criterion
exists to catch.

**WHY nesting, not a single unified list**: `_INLINE_WITHDRAWAL_GUARDS`
(`filter_missing_daily_notes`, `filter_unappliable_relationships`,
`filter_unresolvable_moc_links`) are the three guards whose OWN report
already renders a bullet inside THIS heading. For those three,
`_group_delete_withdrawals` buckets each withdrawal under EVERY cause's
`missing_id` that names one of these guards (not just the first cause — see
below), and the existing `skipped_daily` / `skipped_rel` /
`unresolvable_links` loops print the withdrawal bullet immediately after
each matching bullet — same visual block, one indent deeper, the same
nested-bullet shape `destination_clashes`/`attachment_suppressions` already
use for their own `dropped` sub-lists (`- `id`` under `- destination`). A
separate list naming the same id would put a reader's eye two sections apart
to confirm the connection this criterion asks to be immediate.

**WHY `validate_destinations` / `suppress_moves_for_unfiled_attachments`
attributions, `unattributed`, and undeclared withdrawals fall to a catch-all
block instead of nesting**: those two guards render under their OWN
`## Not filed —` headings above this one, not under `## Skipped`. Nesting a
withdrawal there would contradict T4.3's own test 8 ("inside the existing
`## Skipped` heading, not a new top-level section") in the other direction —
a withdrawal attributed to them still needs a home INSIDE `## Skipped`, so
`leftover_withdrawals` collects everything `_INLINE_WITHDRAWAL_GUARDS`
cannot claim (including the tripwire and undeclared cases, which have no
bullet to nest under by definition) into one `**Delete withdrawn**`
sub-block at the end of the section — inside the heading, never a sibling
heading of its own.

**WHY the "## Skipped" guard condition grew to include `delete_withdrawals`
in its `or`**: without it, a run that withdraws a delete but skips nothing
else (e.g. every cause routes to the catch-all) would open no heading at
all for the catch-all block to sit under. F6-AC1 requires the withdrawal be
reported; test 10's second half (`test_withdrawn_only_run_still_renders_
skipped_heading`) pins this directly.

**Every cause is joined, not just the first** — a withdrawal whose `depends_
on` names ids from two different missing daily notes (reachable today via
`ids_by_origin`'s multi-day accumulation in `render_actions.py`, not a
future-only case) nests under both matching bullets, deduplicated per
missing id. The full history of that correction — the code-quality review
that reproduced the defect, and why `causes[0]`-only was wrong to begin with
— is documented at the join's own definition,
`docs/tomo/scripts/lib/render_helpers.md`, "`render_md.py`'s Adjacency
Grouping Joins on Every Cause, Not Just the First", since the data shape the
join receives is a property of that module's contract, not of this file's
rendering choice.

## `_withdrawal_detail` Deduplicates — Identical Causes, Not Identical `missing_id`s

A live Pass-2 run (2026-09-18) surfaced a doubled sentence: `[[Laufrunde
Elbufer]] was **not** deleted — its daily note does not exist; its daily
note does not exist`. The withdrawal had two `causes`, `I03` and `I04`, both
`filter_missing_daily_notes` — two distinct missing daily notes, correctly
two distinct entries in `causes`. `_withdrawal_detail`'s old unconditional
`"; ".join(...)` over every cause was correct by the id: `I03 != I04`. It
was wrong by the SENTENCE, because `describe_withdrawal_cause_for_user`
(`render_helpers.py`) deliberately drops the `missing_id` (ADR-11, "no
executor internals in the rendered text") — the one field that made the two
causes distinguishable lives only in the technical sibling,
`describe_withdrawal_cause`, which stays id-bearing for stderr on purpose.
So two causes from the SAME guard collapse to the IDENTICAL user-facing
phrase, and joining them unconditionally states one fact twice instead of
once.

The fix keeps the join (a withdrawal whose causes span two DIFFERENT guards —
e.g. a missing daily note AND an unresolvable MOC link — must still show
both reasons; the user needs to fix both, not just the first one reported)
but deduplicates identical phrases, preserving first-appearance order. This
is a phrase-level dedup, not an id-level one: it lives in `render_md.py`,
downstream of `describe_withdrawal_cause_for_user`, precisely because the
loss of information that causes the collision (the id) already happened one
function earlier. Deduplicating by `missing_id` instead would have been a
no-op — the ids were never equal — and deduplicating in
`describe_withdrawal_cause_for_user` itself is impossible: that function
sees one cause at a time and has no way to know a sibling cause exists.

## The `⚠️` Marker — Matching Pass 1's Own Hard-Guard Convention

Both withdrawal renderers (`_render_withdrawal_bullet` under "## Skipped",
`_render_withdrawn_delete_notice` under "## Source Deletions") now lead with
`⚠️ **<label>:**` — `⚠️ **Delete withheld:**` and `⚠️ **Not deleted:**`
respectively. Before this change `render_md.py` used no `⚠️` marker
anywhere; `suggestions-reducer.py` (Pass 1) already had the convention for
its own hard-guard notices (`⚠️ **Target note doesn't exist** — …`, `⚠️
**Marker not found** — …`) and this file's withdrawal notice is the same
CLASS of fact in Pass 2's vocabulary: the user ticked an approval — here, a
delete — and the run did not carry it out. An unmarked bullet reads
identically to every applied-action bullet around it, so a user skimming the
document has no visual signal that this line is the one place where
"approved" and "happened" diverged. Matching the established register
(`⚠️` + bold lead-in + em-dash + explanation) rather than inventing a new
shape keeps the whole document's warning vocabulary in one place instead of
two.

## `vault_collision_held` Was Live On HEAD With No Renderer (spec 037 T4.2)

Phase 3 (spec 037) taught `_build_move_asset_actions` to emit `skipped_assets`
entries with `kind: "vault_collision_held"` for a `keep_in_inbox` remedy and
for a `rename` that degraded to one (`proposed_name: null` — SDD:292, "a
rename that lost its name"). Every Phase 3 test asserted on that `skipped_
assets` list as DATA. None of them rendered it, so the `## Skipped` loop's
`if "no_basename" / elif "collision" / else <loud placeholder>` branch — see
"The `kind` Discriminator" above — fell through to `else` for the one kind
that ships most often (rename is the ticked default; `keep_in_inbox` is what
an owner picks INSTEAD of it). A live `keep_in_inbox` conflict rendered `(no
remedy defined for skip kind 'vault_collision_held' — check render_md.py)` —
correct behaviour by the branch's own design (an unrecognised kind must not
silently inherit a wrong remedy), wrong by omission: `vault_collision_held`
was never unrecognised, just never given an `elif`. Fixed by adding the
branch; its remedy text says nothing needs doing — `reason` (already built by
`_build_move_asset_actions`) is what explains why.

## `## Skipped` Gains a Second, Independent Report For The Same Attachments (spec 037 T4.2, PRD C2/S2)

"**Attachment not filed**" (the `skipped_assets` loop above) and
"**Conflicts not resolved by rename**" (`_render_unresolved_conflict_bullet`)
both render under `## Skipped`, and a `vault_collision_held` source appears in
BOTH. That is not an oversight of the union computed for the second block —
it is drawing from a different question. The first answers "what happened to
this file" with full detail (`_build_move_asset_actions`'s own `reason`
string). The second answers "which approved conflicts did Pass 2 NOT resolve
by rename", a strictly narrower and reader-facing question the PRD (C2/S2)
asks for by name, and the ONLY place an `ignore`d conflict is reported at
all — `ignore` never touches `skipped_assets` (`render_actions.py:819-823`
emits its move unchanged and records nothing), so before this task an
`ignore`d source appeared nowhere in the rendered document. Two overlapping
answers to two different questions is not duplication in the sense CON-2
would object to; the alternative — folding "conflict remains" language into
the existing loop's `no_basename`/`collision` cases too — would make the new
sentence true of kinds that were never a conflict `ignore`/`keep_in_inbox`
choice to begin with.

### Two Different Questions, Then Two Different Sentences (owner ruling 2026-09-27)

T4.2 shipped the design above but not its consequence in the rendered text:
`_render_unresolved_conflict_bullet`'s `vault_collision_held` branch reused
`entry.get("reason")` verbatim — the exact string "Attachment not filed"
already renders for the same source — so "Conflicts not resolved by rename"
read as "Attachment not filed" minus its remedy clause. For
`100 Inbox/Scans/keep.jpg` / `Atlas/keep.jpg` that produced:

```
- ⚠️ **Conflict remains:** `100 Inbox/Scans/keep.jpg` — kept in inbox: the owner chose not to file '100 Inbox/Scans/keep.jpg' over the occupied destination 'Atlas/keep.jpg'
- ⚠️ **Attachment not filed:** `100 Inbox/Scans/keep.jpg` — kept in inbox: the owner chose not to file '100 Inbox/Scans/keep.jpg' over the occupied destination 'Atlas/keep.jpg'. no action needed — this is what the owner chose; rename the file and re-run `/inbox` to file it after all.
```

Owner ruling: keep both blocks — the design above still holds — but stop
repeating the sentence. Each bullet states only the facts its own question
needs:

- **"Conflict remains"** — that the conflict is unresolved, and what follows
  from it. For a `vault_collision_held` source (`keep_in_inbox` or a degraded
  rename alike): **it was not filed** over the occupied destination, named by
  path, and stays unmoved. For an `ignore`d conflict: the move goes out
  unchanged against the occupied destination and will be refused when the run
  is applied.

  **That sentence is passive on purpose, and the first version of this section
  got it wrong.** It read *"they declined to file it"* — and was corrected
  2026-09-27 after a code-quality review. "Declined" is true of a held
  attachment and **false of a degraded rename**, where the owner asked for a
  rename and this run could not recover the name. `render_actions.py`, at the
  site that creates this very `kind`, already said so:

  > One outcome, two reasons, and they must not be told as one: a held
  > attachment is the owner's own instruction, while a degraded rename is the
  > owner asking to file it under a name this run could not recover.
  > **Reporting the second as a choice would tell them they decided something
  > they did not.**

  The fix for the duplication had collapsed the two back into one claim about
  owner intent — trading a duplication defect for an accuracy one, on the
  sub-case its own tests did not render. The distinction is not lost, only
  relocated: `reason` says which of the two happened, and "Attachment not
  filed" is the block that carries `reason`. This block asserts nothing about
  intent, which is the only thing it cannot know from `kind` alone.
- **"Attachment not filed"** — unchanged: where the file is now (`reason`)
  and what, if anything, to do about it (the `remedy` clause).

The same fixture now renders:

```
- ⚠️ **Conflict remains:** `100 Inbox/Scans/keep.jpg` — it was not filed over the occupied destination `Atlas/keep.jpg`, so it stays unmoved
- ⚠️ **Attachment not filed:** `100 Inbox/Scans/keep.jpg` — kept in inbox: the owner chose not to file '100 Inbox/Scans/keep.jpg' over the occupied destination 'Atlas/keep.jpg'. no action needed — this is what the owner chose; rename the file and re-run `/inbox` to file it after all.
```

Both sources are still named in both blocks — nothing was removed from
either loop, and `vault_collision_held` stays in the "Attachment not filed"
loop so a reader scanning what did not get filed still finds it there — but
no sentence is now common to both. `test_conflict_remains_never_repeats_
attachment_not_filed` (`tests/test_037_t4_2_unresolved_summary.py`) pins
this by splitting each rendered bullet into sentences and asserting the two
blocks' sentence sets do not intersect, rather than comparing whole lines —
a whole-line comparison would miss a repeated clause sitting inside a longer
"Attachment not filed" line. It also pins that neither bullet lost the fact
only it carries: the remedy clause ("no action needed …") stays exclusive to
"Attachment not filed", and the destination path stays visible in "Conflict
remains".

### Two Source Lists, Not One Filter

`unresolved_conflicts` is `[s for s in skipped_assets if kind ==
"vault_collision_held"] + [r for r in attachment_conflict_remedies if remedy
== "ignore"]` — reading from BOTH transports the metadata dict carries,
not one. The single-list shortcut, `[r for r in attachment_conflict_remedies
if remedy != "rename"]`, reads as equivalent and is not: a degraded rename's
OWN `attachment_conflict_remedies` entry still says `"remedy": "rename"` —
only its `proposed_name` came back null. `_build_move_asset_actions` is what
performs the degrade (`render_actions.py:780-784`), and it performs it INTO
`skipped_assets`, not back onto the `attachment_conflict_remedies` record
that caused it. Filtering the latter on `remedy != "rename"` silently drops
every degraded rename from this report — the exact class of loss `remedy:
"rename", proposed_name: null` exists to make visible to a downstream
consumer, and this file is one. `skipped_assets` already carries the degrade
correctly (that is what the `kind == "vault_collision_held"` branch above
this one renders), so this block reads it from there instead of re-deriving
it a second way.

### Names, Never Counts (PRD/C2)

The intro sentence above the bullets states no number. C2's own words are
"names each one rather than counting them" — a count sentence
(`f"{n} conflicts remain: ..."`) is redundant the moment it agrees with the
bullets beneath it and misleading the moment it does not, and nothing forces
the two to move together the way a hand-written intro and a computed list
never do reliably. `test_no_sentence_counts_the_conflicts`
(`tests/test_037_t4_2_unresolved_summary.py`) pins this with a regex over the
whole document, not a per-sentence check, since the count could as easily
have leaked into a different sentence than the one under test.

### ADR-11 Reaches the Existing Loop Too

Fixing `vault_collision_held` touched the same bullet the other two kinds
(`no_basename`, `collision`) share, and the owner's 2026-09-27 ruling was that
ADR-11 ("no executor internals in the rendered text") applies to all three at
once: the bullet dropped its `` `move_asset` → `` prefix — a wire action name
that told the reader nothing they needed — for the `⚠️ **Attachment not
filed:**` lead-in, matching the convention above. `attachment_conflict_
remedies` entries never carried a wire action name to begin with, so the new
block's bullets (`⚠️ **Conflict remains:**`) started clean.

## Four Text Defects a Green Suite Could Not See (v0.25.0, spec 037 T4.4)

T4.4's live keep-in-inbox run put this document's "## Skipped — un-appliable
actions" section in front of an owner for the first time. Four defects were in
shipped output, and the whole suite was green through all of them. They share
one cause: every assertion checked that an expected substring was **present**,
and not one of these defects removes a substring.

### The heading asserted an intent the bullet refuses to assert

The heading read *"**Conflicts not resolved by rename** — the owner chose
otherwise, and Pass 2 did not resolve these:"*.

`_render_unresolved_conflict_bullet` was made passive in T4.2 for a specific
reason, recorded above: "the owner declined to file it" is **false for a
degraded rename**, where the owner chose `rename` and this run lost the name.
`skipped_assets` unifies keep-in-inbox and a degraded rename under one
`vault_collision_held` kind, so both render under this heading — and the heading
made exactly the claim the bullet beneath it had been rewritten to avoid.

The bullet was fixed; the heading one line above it was never revisited. It now
states the outcome only: *"Pass 2 did not file these over their occupied
destinations."* True for all three routes — held, degraded, and ignored.

This is worth naming as a shape rather than an incident: a decision applied at
the level it was raised, while the same claim survived one level up, where
nobody was looking.

### `reason` + `remedy` is two sentences, and the second began in lower case

The bullet template is `f"... — {reason}. {remedy}."`. Every remedy string
started lower case, so the rendered line read *"...karte.png'. no action
needed"*. All four branches now start with a capital, and the template carries a
comment saying why, because the requirement is invisible at the definition site.

### The block heading was the bullet's own label

*"**Attachment not filed** — these attachments were left in the inbox:"* above
bullets that each open *"**Attachment not filed:**"*. The sibling block never
did this ("Conflicts not resolved by rename" → "Conflict remains"), so the
convention already existed and only this block broke it. Now "**Attachments
still in the inbox**".

### Why the T4.2 tests were blind to all of this

`tests/test_037_t4_2_unresolved_summary.py` hand-writes its `skipped_assets`
entries, including `reason`. Defects two and three live in the **seam** between
the reason (built in `render_actions.py`) and the remedy (built here), so a
fixture supplying its own reason cannot reach them at all.
`tests/test_037_t4_4_rendered_text.py` builds through `_build_move_asset_actions`
instead, and its five mutations were measured 2026-09-28: each turns red
exactly the test that names it, and only that test.

## Neither Pass May Promise an Outcome It Cannot Know (v0.26.0, 2026-09-28)

Owner catch during T4.4: the Pass-1 `Ignore` checkbox read *"the move is sent
as-is and **will fail** — the attachment stays in the inbox"*, and the Pass-2
"Conflict remains" bullet read *"it **will be refused** when the run is
applied"*.

Both assert an outcome neither document is in a position to know. Occupancy is
observed once, in Pass 1's reducer, and re-checked nowhere: `path_exists`
appears in neither `instruction-render.py` nor `render_actions.py`. Between
Pass 1 and the Hashi apply the owner may have deleted or renamed the occupying
file — and doing exactly that is a plausible *reason* to choose `ignore` in the
first place. In that case the move succeeds, and both halves of the Pass-1
sentence are wrong: it does not fail, and the attachment does not stay in the
inbox.

Both are now conditional, and the Pass-2 bullet also says *when* the observation
was made ("the destination that was occupied in Pass 1"), because a claim about
vault state is only as good as its timestamp.

This is the same family as the four defects above: the document asserting
something it cannot know. It is recorded separately because it was found by the
owner reading the text rather than by a test, and because it sat in **two**
places — fixing the one that was noticed would have left the other.

## The Legacy Ignore Label Still Parses, and the Test for It Had to Be Rebuilt

A suggestions document rendered by reducer 1.57.2 can be sitting unapplied in a
vault. `suggestion-parser.py` matches `label.startswith("ignore")`, so the old
parenthetical still resolves — asserted rather than left to luck.

The first version of that test could not fail, and measurement is the only
reason it was caught. It ticked only the legacy `Ignore` line and asserted
`remedy == "ignore"`. Under the mutation (`label == "ignore"`) the tick is not
seen, all four flags stay False, and `_resolve_attachment_remedy` resolves zero
ticks to `ignore` by Rule 3 — the same answer. The test was measured GREEN under
the mutation it named.

The fixture now ticks **rename and the legacy Ignore line together**, where the
outcomes diverge: seen means two ticks and Rule 4's `ignore`; not seen means one
tick and Rule 2's `rename`, silently discarding the owner's override. That is
the ninth unbiteable test this spec produced, and the count is itself the
argument for measuring every named mutation rather than reasoning about it.

## An Ignored Conflict Is Annotated on Its Own Action (v0.27.0, 2026-09-28)

Owner request during T4.4: *"können wir bei conflict remains auf den
entsprechenden IXX verweisen? oder vielleicht sogar bei IXX das anmerken und
nicht am ende des dokumentes?"*

The second form was built, and the first was declined for a reason worth
recording: **the end-of-document bullet renders for three routes and only
`ignore` has an action to point at.** `keep_in_inbox` and a degraded rename
withhold the move entirely, so there is no `I0x` in the document for them. A
reference inside the bullet would therefore appear for one route and be missing
for the other two, with nothing in the text explaining the difference. An
annotation *on the action* exists exactly where an action exists, and says
nothing where none does.

`ADR-11`'s "no action id in rendered text" is not in tension with this. That rule
lives only in `_render_withdrawal_bullet`'s docstring here — it is not defined in
the SDD, and the plan cites it three times as the literal character `n` — and it
means "no executor handle dropped into prose". Action ids are already the H3
headings of this document; they are how the owner ticks "Applied" per action.
The annotation is a line inside the block that already carries its own id.

**The two sites carry different sentences, by the same 2026-09-27 ruling that
governs the two "Skipped" blocks.** The annotation states the DECISION and how to
revisit it and claims no outcome at all; the end-of-document bullet states what
applying will do. Claiming an outcome at the action would have repeated the
mistake corrected the day before, since nothing re-checks the destination between
Pass 1 and the apply.

`ignored_conflict_sources` is computed before the action loop rather than beside
the "Skipped" block that reads the same remedies, because the `move_asset` block
is rendered first.

Three mutations, measured 2026-09-28. The second one matters more than it looks:
dropping the membership test annotates EVERY `move_asset`, and the first test
passes under that mutation because its only move is the ignored one. Without a
second fixture, "annotate the right move" and "annotate every move" are
indistinguishable.
