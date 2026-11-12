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

The marker counts only at column 0. Tomo writes it there and nowhere else;
an indented copy is something else — most likely a landed item's
continuation line (`item_lines` indents continuations by two spaces and
`review_doc.neutralised` does not escape `%%`, so a user who pastes the
marker text into an item lands it verbatim, indented). A `strip()` match
read that copy as the signature: with the real marker deleted the rerun
"found" the marker under the item's heading and replaced that section.
Hence `line.rstrip() == marker`: no leading whitespace, trailing whitespace
tolerated (a CRLF note keeps its `\r`, and the marker is still Tomo's line).

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

The mirror is exact down to the character classes, because Python's `re`
and ECMAScript read the same two regexes differently in three places, and
each difference makes Tomo emit an anchor Hashi cannot resolve:

- Line terminators. Hashi splits the file on `\n` only, so a CRLF note
  keeps its `\r` at the end of every line, and ECMAScript's `.` does not
  match `\r` (nor U+2028, U+2029) while its `$` without the `m` flag matches
  only at the end of the string — `## Woche\r` is NOT a heading to Hashi.
  Python's `.` matches `\r` and `str.strip()` removes it, so the naive mirror
  found `Woche` and emitted it, and Hashi answered `anchor not found`. The
  text group is therefore `[^\r\n  ]*`, anchored with `\Z`, and the
  split stays `\n` only: a CRLF target has no headings at all, which the
  plan reports as `place-missing` (with an empty heading list) instead of
  emitting an anchor that fails downstream. The same holds for a heading
  line that contains U+2028 or U+2029.
- Whitespace. ECMAScript's `\s` and `String.prototype.trim` share one set:
  WhiteSpace (U+0009, U+000B, U+000C, U+FEFF and Unicode `Zs`) plus
  LineTerminator (U+000A, U+000D, U+2028, U+2029). Python's `\s` and
  `str.strip()` use `str.isspace()`, which adds U+001C to U+001F and U+0085
  and lacks U+FEFF. So a BOM after the hashes is whitespace to Hashi (the
  heading is found, the BOM trimmed) but text to Python, and a NEL or a
  file separator is the opposite. `JS_WS` holds the ECMAScript set as a
  literal (the `Zs` members have been stable since Unicode 6.3 dropped
  U+180E; a test compares the literal with `unicodedata` so a drift shows),
  both regexes use it in place of `\s`, and the heading text is trimmed with
  `str.strip(JS_WS)`. The V8 oracle for every edge character is in the test
  file's docstring.
- Only the mirror uses `JS_WS`. Tomo's own marker match (`line.rstrip() ==
  marker`, column 0) stays Python's: the marker line is Tomo's signature,
  not something Hashi resolves.

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
identical between `review-doc.py write` and the delivery. The hits elsewhere
come from a Kado search whose order is the index's, not a promise; they are
sorted by path before the first is taken, so two builds of the same plan —
the preview and the delivery, or a resume — pick the same note whatever
order the search answered in.

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

The stamp goes through `doc_frontmatter.merge_tomo_block_into_markdown`,
which refuses two template shapes with `FrontmatterMergeError`: a
frontmatter that already holds a top-level `tomo:` key (the merge would
write a duplicate key, which a YAML reader silently resolves to one of the
two) and a leading `---` fence that never closes (there is no frontmatter
to merge into). Both came out of the template the user
configured, not out of the review, so neither refuses the delivery: the
plan falls back to the plain note — the same note a missing template
yields — and records the notice `template_unmergeable`, holding the merge
helper's reason, so the preview can say which of the two shapes to fix
(T4.2 shows it as a notice, like `variant_missing`). One notice name, not
two: both shapes share the consequence (the template was dropped for this
delivery) and the fix site (edit the template file); the reason text
already tells them apart, and a second flag would duplicate that. The
fallback resets `templater_hint` (the plain note holds no Templater code)
and keeps `variant_missing` (it is still true of the variant). A template
whose frontmatter carries `tomo:` is not the variant convention — the
variant replaces Templater tokens, nothing else.

The template's text is taken by the exact bytes: `_split_lines` mirrors
Hashi's `content.split("\n")`, and the rebuilt note ends with a newline
only when the template did. A note whose template lacks the final newline
lands without one; adding it would make the plain-vs-template byte
promise above false for that template.

## WHY the Set Holds One Action

An existing target gets one `insert_under_marker` or one `replace_section`;
a new note gets one `move_note` — the section is already inside the note.
Hashi's `move_note` refuses when source and destination both exist
(`moveNote.ts:71`), which is the "the user created the note in the meantime"
guard of F6-AC4; Tomo's side of it is choosing the existing note at delivery
time, which `locate_target` does.
