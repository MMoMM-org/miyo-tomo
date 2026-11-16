# WHY: lib/review_section_set.py

> Rationale for decisions in `tomo/scripts/lib/review_section_set.py`.
> The module handles the mapped sections of one `/review` delivery as a set:
> every row placed in the note planned on an existing or a new note, the
> "Tomo Review" sub-parts, the blocks spliced into a new note, and the
> instruction set's actions composed in their fixed order with their ids
> (spec 046 T5.2, T5.4; PRD F4-AC1, F4-AC5, F2-AC12; SDD ADR-12). No Kado,
> no clock, no file I/O.

## WHY a Module of Its Own (spec 046 T5.4)

`review_section_plan.py` answers one question — where one section goes in
one note text — and reached its 350-line limit at T5.2. The set-level
steps sat at its end: plan every row (`plan_existing`, `plan_new_note`),
name the routed keys for Pass 1 (`routed_keys`), build the "Tomo Review"
sub-parts (`review_parts`), splice a new note's blocks (`splice_blocks`).
T5.4 adds one more set-level step — composing the actions — and T5.5 still
adds helpers to `review_section_plan`. So the set-level steps moved here
and the composition joined them; the per-section planner keeps its room.
Imports go one way: `review_actions` → `review_new_note` →
`review_section_set` → `review_section_plan` → `review_hashi_text`
(`tests/test_review_section_plan.py`, `FORBIDDEN`). No old names are
re-exported from `review_section_plan`: a caller names the module that
owns what it uses.

## WHY Ids Are Dense Over the Emitted Actions (ADR-12)

ADR-12 numbers the set `I01…In` in a fixed order: the sections in mapping
order, then "Tomo Review". A section that does not land — a stop, a `skip`,
a section routed into "Tomo Review", an empty section — emits no action and
takes no id; the next emitted action takes the next number, and "Tomo
Review" takes the last. The order is a function of the rows' order in the
setup only, never of the order of the items dict or of the choices dict,
so two runs over the same inputs produce byte-identical sets.

An empty section (no item lines) emits no action in either mode (F4-AC1:
"one action per kept non-empty section"; F3-AC5: "that section receives
nothing"): a first delivery writes no empty marker pair into the user's
note, and a re-run leaves an earlier block as it is instead of emptying it
— the same rule as `review-section-kept` for "Tomo Review". Removing an
earlier block is the user's edit. The rule holds for both paths through one
predicate, `lands` (mode in the given modes and the block holds lines):
`compose` uses it for an existing note's actions, `landed_escapes` for the
escapes, and `review_actions._templated_note` for the blocks spliced into a
new note (modes `insert` only). A new note therefore carries no empty marker
pair either, and the next run finds no block for that section: it plans a
first `insert` once the section has items, nothing while it stays empty.
One predicate, not three filters, because the new-note splice once tested
the mode alone and wrote an empty pair the other two paths did not count.

The alternative — an id fixed per mapping position, leaving gaps where a
section stopped — was rejected. It would make a section's id stable across
runs with different stops, but nothing reads ids across runs: Hashi writes
`applied` by id inside one set, and a new delivery replaces the whole set.
A resume (#258, `lib/staged_delivery.py`) needs the rebuilt `set_json`
payload byte-identical to the landed one, and that holds for dense ids
whenever the same sections land — which `delivered_plan.sections` and
`replan_differs` (T5.5) guarantee, because a different stop is a different
mode and refuses the resume first. Gaps would also make `I01…In` false
for the count of actions, which the SDD and Hashi's run log read as one.

## WHY Composition Keeps the Plannable Sections and Leaves the Stops Visible

On an existing note a stop of one section (`section-missing`,
`section-ambiguous`, `section-broken`, `section-moved`,
`block-in-review-section`, `landing-off-limits`) does not change where any
other section goes: each section is planned on the note as it is, and
Hashi resolves every action on its own. So the sections that plan an
`insert` or `replace` are composed, and a stopped section stays in
`ReviewPlan.sections` with its mode. Whether a stop refuses the delivery
until the user answers it is the user-facing rule of T5.5
(`review-instructions.py`), which reads the stops from `ReviewPlan.sections`;
composing only what is plannable keeps that decision in one place. A
refusal of the "Tomo Review" part (`place-missing`, a collision,
`landing-off-limits` on its place) is a plan problem and leaves the set
empty, as in spec 045: the delivery is refused as a whole.

## WHY Every Landed Block's Escapes Are Counted Once

`escaped_lines` is what the preview tells the user Tomo changed in their
text. A section that lands as its own block (`insert` or `replace` on an
existing note, `insert` spliced into a new note) carries its block's escapes
in `SectionPlan.escaped_lines`; a routed section's escapes are counted by
`review_parts` with the "Tomo Review" content. `landed_escapes` sums the
landing modes for the delivery's kind, and `review_actions._sectioned`
adds it to the groups' base, not to the previous total, so the count stays
right when the sections are planned twice (a new "Tomo Review" re-plans
with `review_at`; an unmergeable template re-plans on the plain note).
A new note counts `insert` only: its text is spliced from inserts, and a
`replace` planned on a template text that already carries markers writes
nothing.

## WHY a New Note Runs the Same `plan_section` (spec 046 T5.2, F4-AC5)

A new note is built by Tomo, not by Hashi: the set holds one `move_note`
and the note text already carries every block. `plan_new_note` still runs
`plan_section` on the text `review_new_note.template_choice` chose by spec
045's Templater rule (the `_tomo` variant, else the template as it is), so
a new note and an existing note answer "where does this section go" by one
rule, and the block Tomo splices is the block the next run finds with both
markers. The splice index is `SectionPlan.insert_at` — the line Hashi's
`before` / `after` / `inside` would insert at — so the spliced note is the
note Hashi would produce from the same insert.

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
never forms an id or a marker. Item lines go through
`review_section_plan.block_lines`, which escapes marker text: a routed item
quoting a section marker would otherwise make that section's next run
`section-broken`. An empty section leaves no sub-heading, like an empty
group.
