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
already past the size guide (463 lines). The section planner is a second
concern with its own rules — marker pairs, home ranges, the off-limits
landing, the Tomo Review range — and T5.2/T5.4 compose its plans with the
Tomo Review plan. It reuses the Hashi mirror that `review_actions.py` owns
(`JS_WS`, `fenced_mask`, `hashi_headings`, `bare`, `split_lines`,
`marker_index`, `item_lines`) instead of copying it: one parse, so the two
planners can never disagree about where a heading or a marker is.

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

Item lines run through `review_actions.item_lines` (ids stripped,
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
(`before` / `inside` an anchor), for T5.2.

## WHY a Section Never Lands In or At the Tomo Review Range (ADR-12)

Hashi runs every `insert_under_marker` before `replace_section`
(`planner.ts` `KIND_ORDER`). A section inserted inside the Tomo Review
range is wiped by that set's own Tomo Review replace. The range is the
heading above the spec 045 marker of this period, as `review_actions`
finds it (`marker_index`), to the next heading of the same or a higher
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
decision (T5.5).

## WHY Notices `block-replaced` and `block-moved-confirmed`

A replace overwrites whatever the user edited inside Tomo's block; the
preview says so (`block-replaced`). A confirmed moved block is replaced
where it now sits; the preview names that (`block-moved-confirmed`).

## WHY a New Note Runs the Same `plan_section` (spec 046 T5.2, F4-AC5)

A new note is built by Tomo, not by Hashi: the set holds one `move_note`
and the note text already carries every block. `plan_new_note` still runs
`plan_section` on the text `review_actions` chose by spec 045's Templater
rule (the `_tomo` variant, else the template as it is), so a new note and
an existing note answer "where does this section go" by one rule, and the
block Tomo splices is the block the next run finds with both markers. The
splice index is `SectionPlan.insert_at` — the line Hashi's `before` /
`after` / `inside` would insert at — so the spliced note is the note Hashi
would produce from the same insert.

## WHY a New Note Routes Instead of Stopping

On an existing note a missing or doubled heading is a stop the user
answers (Rule 9). A new note has no user text yet; its headings are the
template's. A heading the template lacks, holds twice (Hashi's anchor and
the next run's scope would take the first), or holds only inside a
multi-line Templater span (`template_syntax.templater_inner_line_indexes`:
the heading does not exist until Templater runs, and splicing there would
write into Templater code) is routed to "Tomo Review" without a question:
`plan_section` is called with the choice `review`, so the stop answers
itself, and an `insert` whose heading sits in a Templater span becomes
`review` too. Only an explicit `skip` from the user overrides the routing.
Without a template (a plain note) every section placed in the note routes.
Every other stop (`landing-off-limits`, `section-broken`) stays a stop: the
template was checked at setup, but the variant can differ.

## WHY `review_at` Is None on a New Note, and Blocks Go Above "Tomo Review"

`review_at` exists because Hashi orders two inserts at one index by kind,
not by Tomo's wish. On a new note Tomo splices every block itself, so it
decides the order: at the same index a section block goes above the "Tomo
Review" section. Everything below the Tomo Review heading up to the next
heading of its level or higher is Tomo Review's body, so a block placed
below it would sit inside the range its own `replace_section` rewrites on
the next run (and the next run would stop it as `block-in-review-section`).
`splice_blocks` applies the inserts from the last index to the first, so
earlier indexes stay valid, and keeps the order it is given at one index.

## WHY `routed_keys` Exists for Pass 1

The landing line of a section part says where it lands before the user
approves anything (F4-AC5: "naming them in their landing lines before
delivery"). For a new note Pass 1 already knows everything routing depends
on — the template text and the rows; items play no part — so
`review-doc.py write` calls `routed_keys` on the chosen template and marks
those parts `routed`. For an existing note routing depends on stops the
user answers in Pass 2 (`--section-choice <key>=review`), so Pass 1 leaves
`routed` false and the Pass 2 preview names the stop. Pass 2 is the
authority either way: the note may be created, or the template changed,
between the two passes, and the preview shows the plan Pass 2 built.

## WHY the "Tomo Review" Sub-Parts Are Built Here

`review_parts` turns the analysis rows (placement `review`, F2-AC12) and
the routed sections into the sub-parts `review_actions.render_section`
renders under the Tomo Review heading at its level + 1, like the groups.
Mapping order, analysis and routed rows interleaved as configured, then
the groups: the rows are the user's order (ADR-12), the groups are spec
045's. The sub-heading is the row's heading through
`review_sections.display_heading` (one line, no `%%` span), so config text
never forms an id or a marker. Item lines go through `block_lines`, which
escapes marker text: a routed item quoting a section marker would
otherwise make that section's next run `section-broken`. An empty section
leaves no sub-heading, like an empty group.
