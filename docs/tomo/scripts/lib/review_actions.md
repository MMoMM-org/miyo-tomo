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
fence rule (next section), the same lines Hashi's heading parser sees; a
marker inside a fence is quoted text.

## WHY Headings Are Parsed by Hashi's Rule, Not `review_md`'s

Every heading this module emits as an anchor value, or matches a configured
anchor, `setup.heading` or an own section against, must be the heading Hashi
will resolve — otherwise a plan that passes every check here fails in Hashi
with `anchor not found`, or lands under a different heading. Hashi's reading
is `Hashi/src/actions/markdownStructure.ts`: `parseHeadings` takes the text
after the hashes, trimmed, and KEEPS closing hashes (`## Woche ##` is
`Woche ##`); `fencedLineMask` toggles on every line that opens with optional
whitespace and ``` or ~~~, whatever the fence character or its length, with
no `>` prefix (a quoted fence is not a fence to Hashi). `anchorResolver.ts`
(`resolveHeading`) and `sectionLocator.ts` then take the FIRST heading whose
text equals the anchor value exactly, over the whole file content including
the frontmatter — a YAML comment `# x` in the frontmatter is a level-1
heading to Hashi, so it is one here too.

`review_md.headings` reads for `review_day` — a CommonMark-shaped parser that
strips closing hashes and closes a fence only with its own character. Its
reading of a daily is never handed to Hashi, so it stays as it is; feeding
its headings into an anchor would emit `Woche` for a note whose heading Hashi
reads as `Woche ##`. The two parsers differ exactly where notes differ in the
wild (closing hashes, a ``` opened and ~~~ closed, a fence inside a
blockquote), so this module carries its own mirror of Hashi's two regexes
(`hashi_headings`, `fenced_mask`) and uses nothing else for the target, the
marker search and the template of a new note. The mirror has no behaviour of
its own: when Hashi's parser changes, this one changes with it.

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

## WHY Every Item Line Is Escaped Again, Idempotently

The landed section is Markdown Hashi later re-parses for headings and
sections. An item line that starts with `#`, `- [`, `>` or a fence would be a
heading, a checkbox, a quote or an open fence inside the periodic note — and
a heading would end Tomo's section early. `review_doc` escaped such lines
when it wrote the document; the user may have added lines since. The same
predicate (`review_doc.neutralised`, made public for this) runs over every
landed line, first and continuation lines alike, and a line that already
starts with the backslash is not structure, so it passes through unchanged:
one backslash, never two. The count reported is of the lines this module
escaped (F5-AC2).

## WHY Ids Are Stripped and the Text Is Otherwise Verbatim

`%%t<n>%%` is the document's bookkeeping (ADR-13); the periodic note gets the
text the user left (Rule 2) without it. Continuation lines are re-indented by
two spaces under their bullet — the document's own indentation — and nothing
else changes: links stay, wording stays, a line the user escaped stays
escaped.

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
identical between `review-doc.py write` and the delivery.

## WHY a New Note Follows ADR-8 in This Order

Variant text present → the note is built from it. A variant configured but
not readable → the raw template with `variant_missing`, so the user learns
the convention file is gone instead of silently getting Templater code.
No variant → the raw template; a raw template holding `<%` sets
`templater_hint` so the readable instructions tell the user to run Templater
after the move. No template, or an unreadable one → a plain note: the title
as H1 and the review section at level 2. The section is placed by the same
before/inside rule as in an existing note, on the template's own headings;
an anchor the template lacks is `place-missing` with those headings.

The new note is stamped `rendered-note` / `pending-move` with
`updated_at = generated`, like `/note`'s draft (`note-instructions.py`), so a
resume rebuilds the same bytes and Hashi strips the block on the move.

## WHY the Set Holds One Action

An existing target gets one `insert_under_marker` or one `replace_section`;
a new note gets one `move_note` — the section is already inside the note.
Hashi's `move_note` refuses when source and destination both exist
(`moveNote.ts:71`), which is the "the user created the note in the meantime"
guard of F6-AC4; Tomo's side of it is choosing the existing note at delivery
time, which `locate_target` does.
