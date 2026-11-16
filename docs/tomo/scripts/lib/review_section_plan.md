# WHY: lib/review_section_plan.py

> Rationale for decisions in `tomo/scripts/lib/review_section_plan.py`.
> The module plans one kept, mapped section of a `/review` delivery into an
> existing note (spec 046 T5.1; PRD F4-AC2, F4-AC3, F4-AC4, F5-AC1, F5-AC2,
> F5-AC3, F5-AC5; Rules 3, 4, 8, 9; SDD "Runtime View / Complex Logic",
> ADR-4, ADR-10, ADR-12). It says whether the section is inserted the first
> time, replaced between its own markers, or stopped for the user's choice.
> No Kado, no clock, no file I/O.

## WHY a Module of Its Own

`review_actions.py` plans the one "Tomo Review" section of spec 045 and is
past the size guide when the section planner was added (463 lines then; 413 since the splits). The section planner is a second
concern with its own rules — marker pairs, home ranges, the off-limits
landing, the Tomo Review range — and T5.2/T5.4 compose its plans with the
Tomo Review plan. It reuses the Hashi mirror in `review_hashi_text.py`
(`JS_WS`, `fenced_mask`, `hashi_headings`, `bare`, `split_lines`,
`marker_index`, `item_lines`) instead of copying it: one parse, so the two
planners can never disagree about where a heading or a marker is. The
mirror lived in `review_actions.py` until spec 046 T5.2; it moved out
because this module and `review_actions` imported each other and both were
at their size limits (docs/tomo/scripts/lib/review_hashi_text.md, "WHY a
Module of Its Own"). This module imports `review_hashi_text`, never
`review_actions`.

## WHY Tomo Mirrors Hashi's Parse and Stops Instead of Writing Blind

Hashi resolves a heading anchor by exact text, the first match at any level
(`anchorResolver.resolveHeading`, `sectionLocator.locateSection`), and
`replace_between_markers` counts marker lines over the whole note. Tomo
cannot see Hashi's apply; it can only predict it. So every decision is made
on the note exactly as Hashi will split, fence-mask and parse it, and every
case where the prediction is not unique is a stop the user answers (Rule 9):
a heading text that occurs twice is `section-ambiguous` even when the row's
(level, parent, occurrence) would tell them apart, because Hashi's anchor
would not. Writing blind risks the user's text; a stop costs one question.

## WHY Unique End Markers and Whole-Note Counts (ADR-4)

The block is `%% tomo:<id> <period> %%` … `%% /tomo:<id> <period> %%`. A
shared end marker would pair a block whose end the user deleted with the next
block's end and wipe the user's text between them. A start or end counted
other than exactly once, or in the wrong order, is `section-broken`; nothing
targets the note's later lines.

## WHY a Hidden Copy Is Broken (step 3b)

A marker line counts only unfenced, at column 0, equal after JavaScript's
`trimEnd`. A copy inside a fence, indented, quoted (`> `) or inside other
text is no marker for Hashi — but it shows the block was moved, pasted or
edited, and a replace would then act on the wrong pair or fail at apply
time. Any line that contains the marker text beyond the counted marker
lines therefore stops as `section-broken`. Containment, not equality: an
inline code span or a quote holding the marker is a copy too.

## WHY `rstrip(JS_WS)`, Not `rstrip()`

Hashi compares `line.trimEnd() === marker`. ECMAScript's whitespace set and
Python's differ: U+FEFF is trimmed by JavaScript and kept by Python;
U+0085 and U+001C–U+001F are trimmed by Python and kept by JavaScript. A
line ending in U+FEFF is a marker for Hashi, a line ending in U+0085 is not.
The mirror uses `JS_WS` so Tomo counts the same lines Hashi will.

## WHY Item Lines Are Escaped Against Markers

Item lines run through `review_hashi_text.item_lines` (ids stripped,
`neutralised`, bullet and continuation prefix). A prefixed line can never
equal a marker line, but it can contain one — an item quoting an earlier
block — and step 3b would then call the next run's block broken. So every
`%% tomo:` / `%% /tomo:` inside an item line becomes `%% tomo\:` /
`%% /tomo\:`: the text stays readable and no line contains a marker of any
section. The count joins `item_lines`' escaped count.

## WHY Home Ranges, Not "the Nearest Heading Above" (ADR-10)

An `end` block sits after the mapped heading's last subsection; the nearest
heading above it is that subsection, not the mapped heading. The re-run
therefore asks whether the block lies in the row's home: the mapped
heading's whole range for `end`, its range and its own body for `under`,
the gap above the mapped heading for `before`. A `before` home passes over
a whole Tomo Review section that ends directly above the mapped heading,
because a later spec 045 insert `before` the same anchor puts Tomo Review
between the block and its heading.

## WHY Placement Maps to Hashi's Words

`before` → Hashi `before` (at the heading line); `under` → Hashi `after`
(directly below the heading line, above the user's own text); `end` →
Hashi `inside` (at the end of the heading's section, after any
subsections). The insert content ends with a newline, which Hashi's split
turns into one blank line after the end marker; the replace content has no
trailing newline (the contract's "lines between the markers").

## WHY Scope for `under`/`end`, None for `before`, Always on the Moved Path

With `scope`, Hashi checks that the markers lie in the range of the first
heading with that text and level — the same range Tomo checked. A `before`
block lies outside the mapped heading's range by definition; the markers are
unique in the whole note (steps 3–3b), so no scope is needed. A block the
user moved is replaced only with `--confirm-moved`, and then always scoped
to the heading it sits under, and only when that heading is Hashi's first
match by (text, level); a block in the preamble is never replaced.

## WHY the Landing Check Runs on the Note, Twice

Setup checks the template (`setup-input`), but the note may differ from it.
On a first delivery the check runs where the block would land (the heading
whose own body receives the insertion line); on a re-run where it actually
sits. The heading identity is rebuilt on the note's headings as
`review_mapping` builds it on the template (bare text, level, parent,
occurrence, ancestors) so `review_mapping.landing_off_limits` is the one
check for both. A level-1 heading or the preamble is never covered.
`place_off_limits` runs the same check on spec 045's Tomo Review placement
(`before` / `inside` an anchor), for T5.2. `review_off_limits` runs it on an
existing Tomo Review on a re-run — the heading above its marker and the
heading whose body holds that heading's line — because a re-run's replace
writes wherever the section sits now, mirroring this module's own re-run
rule (where it actually sits, not where it was planned).

## WHY a Section Never Lands In or At the Tomo Review Range (ADR-12)

Hashi runs every `insert_under_marker` before `replace_section`
(`planner.ts` `KIND_ORDER`). A section inserted inside the Tomo Review
range is wiped by that set's own Tomo Review replace. The range is the
heading above the spec 045 marker of this period, as `review_actions`
finds it (`review_hashi_text.marker_index`), to the next heading of the same or a higher
level. An insertion point strictly after that heading line and up to the
line after the range lands inside it; an insertion at the heading line
lands above it. For a new Tomo Review the caller passes its planned
insertion index (`review_at`); a section insert at the same index is
stopped, because the order of two inserts at one index decides which ends
up inside. A block already inside the range is stopped too (owner rule:
skip or Abort).

## WHY Choices Apply Only at the Stop That Offers Them

`skip` and `review` answer `section-missing` / `section-ambiguous`; `skip`
answers `section-broken`, `section-moved`, `block-in-review-section`;
`confirm-moved` answers `section-moved` (and a missing heading on a re-run
whose block is intact). A choice given where no stop arises changes
nothing: the section is planned as if no choice were given, so a stale
flag cannot drop or reroute a section that is fine. `landing-off-limits`
offers no choice (Rule 4): the user unticks the section or corrects the
setup. Whether a stale or unknown choice refuses is `review-instructions.py`'s
decision (T5.5: it refuses `choice-invalid`; docs/tomo/scripts/review-instructions.md,
"WHY Every Section Stop Refuses Until a Choice Answers It").

`SectionPlan.offers` names the choices a stop that stays offers, so the
output can list them next to the stop and the skill never offers one the
planner would ignore: the tuple the stop accepts, plus `confirm-moved` where
it opens another path — a missing heading whose block is intact (the moved
path decides from there), and a block moved under a heading (`skip` or
`confirm-moved`; moved into the preamble only `skip`, never replaced
without a scope). `landing-off-limits` offers nothing. A choice that was
taken leaves `offers` empty: the section has no stop.

### WHY No `review` Beside an Intact Earlier Block (owner decision, T5.7)

One block per section and period (Rule 8, F5-AC5). When a re-run finds
exactly one start and one end marker of the section and period, in order,
but its mapped heading is gone (`section-missing`) or stands twice
(`section-ambiguous`), `review` would put the items into "Tomo Review" and
leave the earlier block where it is: two Tomo copies of one section for
the period. So with such a block `section-missing` offers `skip` and
`confirm-moved` (replace the block where it sits), `section-ambiguous`
only `skip`; `review` stays where no earlier block exists (a first
delivery). A `--section-choice <key>=review` given there is not taken and
`review-instructions.py` refuses it `choice-invalid`.

The gate is any earlier block material of the section and period, not
only an intact pair: a start marker alone, an end marker alone, a
duplicated pair, or a textual copy of either marker. A broken block
stays in the note just as an intact one does, so `review` beside it
would equally leave two Tomo copies of the section for the period. With
broken material `section-missing` and `section-ambiguous` offer `skip`
only — `confirm-moved` needs exactly one pair to replace, so only an
intact pair keeps it at `section-missing`. A hidden copy (fenced,
indented, quoted, inside other text) never reaches these steps: step 3b
stops it `section-broken` first, which offers `skip` only, as does a
broken block whose mapped heading is found.

## WHY Notices `block-replaced` and `block-moved-confirmed`

A replace overwrites whatever the user edited inside Tomo's block; the
preview says so (`block-replaced`). A confirmed moved block is replaced
where it now sits; the preview names that (`block-moved-confirmed`).

## WHY the Set-Level Steps Live in `review_section_set` (spec 046 T5.4)

Planning every row of a delivery, the new note's routing, `routed_keys`,
the "Tomo Review" sub-parts and `splice_blocks` sat at the end of this
module until T5.4; they moved to `lib/review_section_set.py` with the
composition of the set's actions, so this module keeps room for the
per-section rules (docs/tomo/scripts/lib/review_section_set.md, "WHY a
Module of Its Own"). Their WHY sections moved with them.

## WHY `_Note.read` Keys Headings Through `review_mapping.walk_headings` (spec 046 T6.2)

A row names its heading by the identity the template analysis gave it;
the planner must compute the same identity on the note, or a heading that
is there reads as `missing`. The planner had its own copy of the walk;
since T6.2 it calls `review_mapping.walk_headings` with Hashi's heading
list and `rht.bare` as the name, so the two cannot drift. Rationale and
the golden that pins both results: docs/tomo/scripts/lib/review_mapping.md,
"WHY the Heading Walk Is Shared With the Note Planner".
