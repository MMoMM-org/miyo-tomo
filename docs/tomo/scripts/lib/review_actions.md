# WHY: lib/review_actions.py

> Rationale for decisions in `tomo/scripts/lib/review_actions.py`.
> The module turns an approved review document into the instruction set a
> `/review` delivery writes (spec 045 T4.1; PRD F4-AC7, F5-AC3 to F5-AC7,
> F6-AC3, Edge Cases; SDD "the review section and the heading-level rule",
> ADR-3, ADR-8, ADR-11, ADR-13).

## WHY a Pure Library

`review-instructions.py preview` and `deliver` (T4.2) build the same plan: the
preview shows the section as it will land, the delivery writes it; a resumed
delivery rebuilds the set and compares it with the file already in the inbox
(`lib/staged_delivery.py`, ADR-11). The tests build it too, to validate every
set against the producer schema and Hashi's copy. One builder that reads only
its arguments — the ApprovedReview record, the target note's text, the
template texts, the setup — makes those three builds byte-identical. Nothing
in here reads the clock, a file or Kado; `generated` and `run_id` come from
`meta.json` through the caller.

## WHY the Marker Line Decides Between Insert and Replace

The target is searched for the exact line `%% tomo-review <period> %%`. That
line, not the heading text, is Tomo's signature (ADR-3): a user who renames
the heading keeps the section (`heading-renamed`, still replaced), and a user
who writes a heading with Tomo's text by hand keeps their own section
(`user-heading-collision`, nothing emitted). A text match would do the
opposite in both cases, and the second one deletes the user's writing. The
marker is an Obsidian comment, invisible in reading view, and it carries the
period so a monthly note that quotes a weekly review's marker cannot match.

The marker search covers the note's lines outside code fences by Hashi's
fence rule (docs/tomo/scripts/lib/review_hashi_text.md), the same lines
Hashi's heading parser sees; a marker inside a fence is quoted text.

The marker counts only at column 0. Tomo writes it there and nowhere else;
an indented copy is something else — most likely a landed item's
continuation line (`item_lines` indents continuations by two spaces and
`review_doc.neutralised` does not escape `%%`, so a user who pastes the
marker text into an item lands it verbatim, indented). A `strip()` match
read that copy as the signature: with the real marker deleted the rerun
"found" the marker under the item's heading and replaced that section.
Hence `line.rstrip() == marker`: no leading whitespace, trailing whitespace
tolerated (a CRLF note keeps its `\r`, and the marker is still Tomo's line).

## WHY Matching Is Tolerant and Emission Exact

Every heading is read by the Hashi mirror in `lib/review_hashi_text.py`
(docs/tomo/scripts/lib/review_hashi_text.md, "WHY Headings Are Parsed by
Hashi's Rule, Not `review_md`'s"); `bare` is how two headings compare.

Matching is tolerant, emission exact. A configured anchor or `setup.heading`
of `Woche` matches a note heading `Woche ##` (both sides compared after
stripping closing hashes and trailing whitespace — the user wrote the same
heading either way), and the emitted `anchor.value` and the reported place
are Hashi's text, `Woche ##`, which Hashi resolves exactly. The tolerant
first match is also what Hashi's exact first match resolves to: an earlier
heading with exactly the emitted text would have matched tolerantly first.
The shadowing check for a replace (the heading above the marker must be the
first with that text) stays exact, because it asks what Hashi will do with
the value this module emits, not what the user meant. `heading-renamed` and
`user-heading-collision` compare tolerantly: `Tomo Review ##` is Tomo's
heading, not a rename, and a user's `Tomo Review ##` without the marker is a
collision.

## WHY replace_section Anchors the Heading Above the Marker

Hashi's `replace_section` is heading-scoped: it keeps the heading line and
replaces the body down to the next heading of the same or a higher level
(`Hashi/src/actions/replaceSection.ts`). So the action's anchor is the heading
directly above the marker, whatever its text and level, and the content is
the body only — marker, groups, items, one blank line — never the heading.
Hashi resolves a heading anchor to the FIRST heading with that text
(`anchorResolver.ts:100`). When an earlier heading carries the same text, the
replace would land in the wrong section, so that case is refused as
`user-heading-collision` too: the rule "never swallow the user's section" is
checked against what Hashi would do, not against what Tomo meant.

A marker with no heading above it has no section Hashi could address; it is
reported as `place-missing` with the note's headings, and nothing is emitted.

Every refused replace reports what it found, not what the setup said. The
marker proves the run is a rerun, so the plan's mode is `replace` and its
place is the heading above the marker — its Hashi text and level — whether
the refusal is `place-too-deep`, `user-heading-collision` (an own section,
or a heading an earlier heading of the same text shadows) or `place-missing`
(then anchor and level are `None`, with the note's headings beside them). The
setup's anchor and placement never took part in a replace, so reporting them
would send the user to fix a place the plan did not use.

## WHY the Content Is the Section Body Hashi Will Compare

Hashi skips an `insert_under_marker` whose block is already in the note and a
`replace_section` whose body equals the content (`blockInsert.ts`,
`replaceSection.ts`). Both compare line arrays from `content.split("\n")`.
The content therefore ends with exactly one `\n`: split, that is the one
blank line that separates the section from what follows, and after the first
insert the section body Hashi sees on a rerun — marker to blank line — is
line-for-line the replace content. A resumed delivery or a rerun of an
unchanged review is a no-op in Hashi, without Tomo keeping any state.

## WHY `before` or `inside`, Never `after`

Hashi's `after` on a heading inserts directly below the heading line — above
that heading's own body (`anchorResolver.ts:38-40`). The user's text under the
anchor would become part of Tomo's section and a rerun's `replace_section`
would delete it. `before` lands immediately above the anchor's heading line;
`inside` appends at the end of the anchor's section. `review_config` refuses
`after` at setup; this module refuses it again through `place_level`.

## WHY the Heading Levels Come From `review_config.place_level`

The review heading sits at the anchor's level (`before`) or one deeper
(`inside`); its groups one deeper still. The level is what makes
`replace_section` stop at the user's next heading: a level too deep makes the
following user section part of Tomo's. `place_level` is the single owner of
that rule (T2.1), including the refusal above level 5 (`place-too-deep`, with
the note's headings so the user can pick another place). A replaced section
keeps the heading the note already has, so its level comes from that heading;
above level 5 it is refused the same way, and the place reported with the
refusal is that heading and its level — the place at fault — not the setup's
anchor, which the replace never used.

## WHY Landed Item Lines Come From `review_hashi_text.item_lines`

Escaping and id stripping of every landed line are the line handling both
planners share; their rationale is in docs/tomo/scripts/lib/review_hashi_text.md
("WHY Every Item Line Is Escaped Again, Idempotently", "WHY Ids Are Stripped
and the Text Is Otherwise Verbatim"). The count of escaped lines this module
reports is theirs (F5-AC2).

## WHY Only Kept Items Land and an Empty Group Leaves No Heading

Unticked and deleted items are absent from the ApprovedReview record already
(F5-AC6). A group whose items were all unticked would otherwise land as a bare
heading — noise the user did not approve. An item whose text is empty lands
nothing.

## WHY Unlanded Items Are a Named Problem, Not a Silent Omission

Items under a heading the parser did not recognise (`unknown`, warned as
`unknown-group`) have no label to land under, so they cannot land. Leaving
them out silently would make the preview the only place that shows it, and
a user who ticked an item under a heading of their own and reads "1 item
lands" has no way to tell a parser miss from a deliberate omission. So the
plan counts the kept non-empty items of `unknown` (`unlanded`, in the
preview) and names the problem `unlanded-items` whenever that count is above
zero — also next to `nothing-to-deliver`, when the only kept items are the
unlanded ones, so the user learns why nothing lands. The problem does not
refuse: the landed items still land, the user decides whether to move the
others under a known heading first.

## WHY Own Sections Are Never the Anchor Tomo Writes Into

`own_sections` names the user's sections (PRD Rule 4). `before` one of them is
fine — the SDD example places the review before "In my own words". `inside`
one of them, or a marker found under one of them (the user moved the marker
line), would make Tomo write into or replace the user's section; both are
refused as `user-heading-collision`.

## WHY the Target Choice Is a Function of the Candidate Paths

`locate_target` takes `Period.note_paths` in order (flat folder, then the year
subfolder), the texts of those that exist, and the by-name hits elsewhere. The
first existing candidate is the target; a second existing candidate is named
as a duplicate so the preview can say so; a hit elsewhere becomes the target
and is reported as `target_moved` (Edge Cases); with nothing anywhere the
first candidate is the destination of a new note. Keeping that rule here, not
in the script, keeps "which note is the target" testable without Kado and
identical between `review-doc.py write` and the delivery. The hits elsewhere
come from a Kado search whose order is the index's, not a promise; they are
sorted by path before the first is taken, so two builds of the same plan —
the preview and the delivery, or a resume — pick the same note whatever
order the search answered in.

## WHY the New Note's Text Is Composed in `review_new_note`

Which template text a new note is built from (ADR-8), the plain note, the
splice of the blocks and the stamp live in `lib/review_new_note.py`; the
rationale is in docs/tomo/scripts/lib/review_new_note.md ("WHY a New Note
Follows ADR-8 in This Order"). This module still decides where "Tomo Review"
goes in that text (`_insertion`, shared with an existing note), plans the
sections on it (`_sectioned`) and emits the `move_note`: those steps read and
write `ReviewPlan`, so they stay beside it.

## WHY the Set Holds One Action per Landing Part (spec 046 T5.4, ADR-12)

Without a mapping an existing target gets one `insert_under_marker` or one
`replace_section`; a new note gets one `move_note` — the section (and with
a mapping every spliced block) is already inside the note. With a mapping
an existing note gets one action per section that lands as its own block
(`insert_under_marker` or `replace_between_markers`), in mapping order,
then the "Tomo Review" action when anything is left for it, numbered
`I01…In` by `review_section_set.compose` (docs/tomo/scripts/lib/review_section_set.md,
"WHY Ids Are Dense Over the Emitted Actions"). The section actions are
composed on every path that does not refuse the "Tomo Review" part —
also when "Tomo Review" itself emits nothing (`review-section-kept`, or no
content for a new one), because a section's block does not depend on it.
A refused "Tomo Review" part (a plan problem) leaves the set empty: the
delivery is refused as a whole, as in spec 045.
Hashi's `move_note` refuses when source and destination both exist
(`moveNote.ts:71`), which is the "the user created the note in the meantime"
guard of F6-AC4; Tomo's side of it is choosing the existing note at delivery
time, which `locate_target` does.

## WHY `pick_headings` Names the Pick List Outside a Refusal (fix #258)

A place problem hands the skill the note's headings for the heading pick
(`_refuse` fills `plan.headings`): the target note's, or the chosen
template's for a new note, as `hashi_headings` reads them. A resume of a
delivery that began with a picked heading needs the same list without a
refusal — the re-plan at the configured anchor may be clean —
(docs/tomo/scripts/review-instructions.md, "WHY a Picked Anchor Is Recorded
as a Flag and Asked Again"). `pick_headings(setup, target, template)` is that
one definition, built from the same `review_new_note.template_choice` and `split_lines`
the planner uses, so the list the resume offers is the list the first pick
offered; a plain note (no template) has none. A plan that always carried
`headings` was rejected: `preview` prints them only on a place problem (SDD
Interface `headings?`), and the privacy allowlist names them for that case.

## WHY `_gate` Refuses `section-checkbox-missing` (spec 046, F3-AC6)

`_gate` refuses a document with `section-checkbox-missing` the way it refuses
a missing Approved line. A broken section checkbox makes that section's state
unknowable, and the parser's column-0 grammar may then file the section's
items under another key (the `%%s3%% %%s1%%` case); delivering nothing is the
only safe outcome. The check sits after `approved-line-missing` and before
`not-approved`, so a document that cannot be read is named as such before the
Approved line is judged. The loop is line-neutral on purpose:
`review_actions.py` is over its size guide, so the refusal extends the
existing tuple instead of adding a branch.

## WHY Mapped Sections Are Split From the Groups (spec 046 T5.2)

The ApprovedReview record files a section's items under its key, next to
the groups. Before spec 046 any key outside `review_doc.GROUPS` was
`unlanded`; a configured row's key is not: its items land in their own
block (an existing note: the per-section plans in `ReviewPlan.sections`,
composed into actions by the set builder; a new note: spliced into the
note) or in "Tomo Review" (analysis rows, routed sections). So the
configured keys are taken out before `landed_groups` runs, and only a key
neither a group nor a row stays `unlanded-items`. Without rows nothing is
taken out and spec 045's output is byte-identical (CON-2).
`nothing-to-deliver` refuses only when neither a group nor a section has a
line to land.

`escaped_lines` counts every escaped line that lands: the groups', the
"Tomo Review" sub-parts', and on a new note the blocks spliced into it
(`SectionPlan.escaped_lines` of every `insert`), because those blocks are
written with the note. It is recomputed from the groups' count on every
planning, so the fallback that re-plans a new note on the plain note counts
each line once. An existing note's `insert`/`replace` blocks land as actions
of their own (T5.4), so their escapes count too
(`review_section_set.landed_escapes`; docs/tomo/scripts/lib/review_section_set.md,
"WHY Every Landed Block's Escapes Are Counted Once").

## WHY "Tomo Review" Holds Analysis Rows, Routed Sections, Then the Groups

An analysis row's heading is script-only (dataview, tracker); writing into
it would be overwritten or break the query, so its material lands as a
sub-heading inside "Tomo Review" (F2-AC12). A routed section has no
heading in the note to land under. Both become sub-parts at the Tomo
Review level + 1 in mapping order, before spec 045's groups; the habits
stay a group and so stay in "Tomo Review" (F2-AC7). The sub-parts are built
by `review_section_set.review_parts`.

## WHY Sections Are Planned Before the "Tomo Review" Insertion Point

Whether "Tomo Review" is written at all depends on what lands in it, and
routing depends only on missing or doubled headings, never on where Tomo
Review goes. So the sections are planned first with `review_at=None`; when
Tomo Review has content and is new on an existing note, they are planned
again with `review_at` set to its insertion index (what `_insertion`
returns), so a section insert at that same index stops as
`block-in-review-section` — Hashi orders two inserts at one index by kind,
not by Tomo's intent. When Tomo Review already exists, `plan_section`
finds it by its spec 045 marker and `review_at` stays None.

## WHY `review-section-kept` and No `replace_section`

On a re-run whose Tomo Review receives nothing (every group empty, no
analysis or routed material), a `replace_section` with only the marker
would delete the earlier review. The section stays as it is, no action is
emitted for it, and the notice `review-section-kept` tells the user;
removing it is the user's choice. The notice is a name only — no heading,
no text (CON-3). Without rows this case is still spec 045's
`nothing-to-deliver`.

It sits in `ReviewPlan.notices`, not in `problems`: `review_delivery.classify`
refuses every problem name it does not list, and listing a name there
requires the skill's wording for it (`test_review_skill_pass2`), which is a
later task's (T5.5 wires the notice into the output, T5.6 words it). The
constant lives in `review_section_plan` beside the other spec 046 notice
names, so the guard that every problem constant of this module is
classified keeps meaning "every spec 045 problem".

## WHY the "Tomo Review" Placement Is Checked Against Off-Limits Rows

`landing-off-limits` (`review_section_plan.place_off_limits`) runs where
"Tomo Review" is inserted — an existing note without the marker and a new
note's template — so neither the Tomo Review heading nor an analysis or
routed sub-heading lands in an off-limits section (ADR-8). It is a refusal
without a heading pick: the fix is the setup's place. The name is
`review_section_plan.STOPS`' `landing-off-limits`, the same stop a section
gets; `classify` refuses it as an unlisted name until T5.5 lists it. With no off-limits
rows the check finds nothing and spec 045's plans are unchanged.

A re-run is checked too (`review_section_plan.review_off_limits`), because
the re-run's `replace_section` rewrites the whole section — now with
analysis and routed sub-headings — wherever it sits, and that place can be
off limits by then: the user marked the heading off limits after the first
run, or moved the section under an off-limits heading. Checking only at
insert time would let the 0-writes-to-an-off-limits-section rule (PRD
Rule 4) hold on the first run and break on every later one. The rule
mirrors the section planner's re-run rule (check where it actually sits):
the existing section is off limits when a row covers the Tomo Review heading
itself, or the heading whose body holds that heading's line (its parent, or
the earlier sibling whose body it follows — the landing an insert at that
spot would get). A `with_subsections` row covers both through their
ancestors. The check runs after `review-section-kept` (a re-run with nothing
for the section writes nothing there, so there is nothing to stop) and
before the collision checks; it refuses without a heading pick, like the
insert's.
## WHY Two Modules Were Split Out (spec 046 T5.2, owner decision 2026-11-16)

`review_actions.py` reached its 500-line limit and `review_section_plan.py`
its 350, with T5.4/T5.5 still to add, and the two imported each other: the
section planner needed the Hashi mirror this module owned, this module
needed the section planner. The Hashi mirror moved to
`lib/review_hashi_text.py` and the new note's text composition to
`lib/review_new_note.py`; imports now go one way —
`review_actions` → `review_new_note` → `review_section_plan` →
`review_hashi_text` — and no compatibility names are re-exported here, so a
caller names the module that owns what it uses. T5.4 added
`lib/review_section_set.py` between `review_new_note` and
`review_section_plan` for the set-level steps and the composition
(docs/tomo/scripts/lib/review_section_set.md, "WHY a Module of Its Own").
