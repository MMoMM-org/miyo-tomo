# WHY: lib/review_doc.py (and schemas/review-proposals.schema.json)

> Rationale for decisions in `tomo/scripts/lib/review_doc.py` and the
> proposals schema `tomo/schemas/review-proposals.schema.json`.
> The module owns the Pass 1 review document of `/review` (spec 045, T3.6,
> PRD F4, SDD ENTITY Proposals / ReviewDoc, ADR-2, ADR-9, ADR-12, ADR-13):
> it checks the model's `proposals.json` against the period that was read,
> renders the document with its frontmatter, and names what it rejected.
> No Kado, no model, no file I/O beyond reading the schema.

## WHY the Model's Output Is Checked Here, Not Trusted (ADR-12, Rule 3)

The PRD's Rule 3 — Tomo never makes a proposal without a source link inside
the period — is the one guarantee that keeps a review from reading as a
generic summary (PRD risk 2). The model writes `proposals.json` and nothing
else; a prompt asking for sources produces sources most of the time, which
is not a rule. `check_items` is the rule: every item in `done`, `open`,
`themes` and `not_in_weekly` needs at least one source that is a
daily of a day in the period, a `weekly_only` item needs a weekly note the
reader listed, a theme needs two distinct days. An item that fails is not
silently dropped and not silently kept: it goes to `rejected` with its
group, index and reason, so the skill can tell the user how many proposals
had no footing, and `counts` names what landed. A source may be given as the
vault path the reader listed or as the note's stem (`2026-03-24`) — the
model sees both in `read.json` and either resolves to the same day; it is
rendered as `[[stem]]`, the link form the owner's notes already use.

Growth items were checked by the same rule until spec 047 T9.3; since then
the growth group is not the model's (`MODEL_GROUPS` leaves it out, as it
leaves out habits) and `review-doc.py write` builds it from the created
notes per folder and the MOC lists ([review_growth](review_growth.md)).

An item whose `text` is empty after cleaning (whitespace only, or nothing
but `%%` marks) passes the schema's `minLength: 1` yet has nothing to
render; it is rejected with `empty-text` instead of producing a bare
checkbox line with links and an id.

## WHY Links Come Only From Resolved Sources, Never From the Model's String

The first version rendered every source string as `[[<basename>]]`. Two
things went wrong with that. A source is a model string, and a string such
as `x\n## Hacked\n- [ ] Approved` rendered as a link spanning three lines —
a forged column-0 heading and a second Approved line that Pass 2 would
read. And a source outside the period (`Secret/Medical`) was linked,
unchecked, as long as one other source of the item was in the period, so
the document could point at any note the model named.

Now a link is made only from a source that **resolves**: to a daily of a
day in the period, or (for `weekly_only`) to a weekly note the reader
listed. The link text is the stem of the note `read.json` lists — a vault
path the reader got from Kado — never the model's string. Resolved sources
are deduplicated in source order; a source that does not resolve is dropped
from the links silently (it still counts for nothing: the item needs at
least one resolved source to be accepted, and that rule is unchanged). The
model's string is used as a lookup key only, so the worst a bad source can
do is not appear.

## WHY a Structural Marker at the Start of an Item Line Is Escaped

The document is Markdown that Pass 2 parses by line shape: `- [x]` /
`- [ ]` lines are items, `## ` lines are group headings, `- [ ] Approved`
is the gate. The model's `text` is split into lines and every line after
the first is indented by two spaces — indentation alone neutralises
nothing: `  - [ ] Approved`, `  ## Done`, an unclosed code fence, `  > x`
and `  ---` all render as structure (or swallow the rest of the document,
in the fence's case) and a parser that strips whitespace reads them as
Tomo's lines.

So every item line — the first one too — that starts (after optional
spaces) with a heading (`#` followed by space, `#` or end of line), a
checkbox bullet (`- [`, `* [`, `+ [`, `1. [`), a quote (`>`), a fence
(``` or ~~~) or a thematic break (`---`, `***`, `___`, also spaced forms
like `- - -`) gets a leading backslash. CommonMark and Obsidian render
`\#`, `\-`, `\>`, `` \` ``, `\~`, `\*` and `\_` as the plain character, so
the text stays readable and the line is no longer structure. Everything
else in the text stays verbatim; `#tag` at a line start is a tag, not a
heading, and is left alone. `\r` and every other line separator Python's
`splitlines` knows (` `, `\x0c`, …) end a line, so a separator that
is not `\n` cannot smuggle an unescaped second line past the check.

The T3.7 parser unescapes nothing: it keeps the item text verbatim, backslash
included, because the text is the user's editing surface and the escape is
part of what they see. Phase 4's landing (writing the approved items into
the weekly/monthly note) has its own escaping decision; this one is about
the review document only. The predicate is public as `neutralised` (0.2.2)
because `review_actions` runs the same one over every landed line: one
predicate on both sides is what makes the second pass idempotent — a line
this module escaped starts with a backslash, which no marker pattern
matches, so it lands with exactly one.

## WHY Habits Never Come From `proposals.json`

`review_habits` computes the habits (T3.5, ADR-12). A `habits` key in
`proposals.json` would let a counted "5 of 7 days" and a hallucinated one
look the same in the document, so the schema sets `additionalProperties:
false` on `groups` and the whole file is refused (`proposals-invalid`) when
the key is present. The same closed key set is what enforces F4-AC7: there
is no way to write text for one of the user's own sections because there is
no group a model could put it in. Spec 046 (ADR-1) opens exactly one door:
`sections: [{key, items}]`, where `key` is a row id (`^s[0-9]{1,3}$`) and
never heading text, so the model can fill a section the user mapped but
cannot name a new one; `review_sections` refuses a key without a definition
in `read.json`. The optional `mark` is defined on section items only, so the
group items' schema is spec 045's unchanged. The habits items arrive already rendered
(`text`) from the habits module; this module only gives them an id and a
line, so the number and its wording keep one owner. An item whose `value`
is `None` ("no clear average") renders like any other, from its `text`.

## WHY Every Tomo Item Carries `%%t<n>%%` on Its Checkbox Line (ADR-13)

Pass 2 must tell Tomo's items from the user's after edits (engagement KPI,
Rule 3 for user items which need no source). The Obsidian comment `%%t<n>%%`
is invisible in reading view and survives retyping the text. It sits at the
end of the checkbox line, not after the last continuation line: the parser
identifies an item by the line that starts `- [x]`, and the user edits that
line most; continuation lines (two-space indent, from a multi-line `text`)
follow and belong to the item above. `%%` sequences inside the model's text
are removed before rendering so no text can forge or break an id, and ids
are numbered over the whole document, so they stay unique across groups.

The id's form (`ID_PATTERN`) and the heading labels of every language
(`group_labels`) are exported from this module (0.2.1) because
`review_doc_parse` reads the document back by exactly these shapes; one
owner for the vocabulary means the writer and the parser cannot drift.

## WHY the "Nothing Found" Line Is a Plain Bullet

F4-AC4: an empty group shows one line and that line never lands. A
checkbox line would be an item the parser has to special-case by text in
every language; a plain `- …` bullet is not an item in the parser's
grammar at all (items are `- [x]`/`- [ ]` lines), so the rule needs no
exception. The growth group with `report.growth.kado_none` set shows the
same line without an access hint: the reader already reported `kado_none`
and the document is the user's editing surface, not the place for Kado
diagnostics.

The habits group is the one exception to F4-AC4: F8-AC3 says a vault
without trackers or without a value has no habits item or no habits group
at all, and the more specific rule wins — a "nothing found" under
"Gewohnheiten" would tell a user without trackers that something was looked
for.

## WHY the Month-Only Groups Depend on Weekly Notes, Not on the Kind Alone

`weekly_only` and `not_in_weekly` exist for a month (F4-AC2). The SDD month
algorithm adds: no weekly notes at all → those groups absent. So the two
groups are rendered only when the read is a month **and** the reader listed
at least one weekly note; items the model put there anyway are rejected
with `month-only-group` (a week) or `no-weekly-notes` (a month without
weekly notes) rather than rendered under a heading that claims a weekly
review was read.

## WHY the Groups Come From a Table Per Kind (spec 046 T4.1, F6-AC4)

The quarter has its own pair of marks: `monthly_only` (only the monthly
reviews hold it, no daily of the quarter does) and `not_in_monthly` (the
dailies held it, no monthly review mentions it). A flat group list with a
"month groups" flag cannot say which pair belongs to which kind, so the
groups come from `KIND_GROUPS`: the week's five, the month's five plus
`weekly_only` / `not_in_weekly`, the quarter's five plus `monthly_only` /
`not_in_monthly`. The week and month order is unchanged, so their documents
stay byte-identical. One rule decides a child group's fate everywhere
(`group_reason`): a group of another kind is rejected with
`month-only-group` / `quarter-only-group`, a group of the right kind whose
child notes were not read with `no-weekly-notes` / `no-monthly-notes` — a
heading that claims a monthly review was read must not appear when none was.
`has_child_notes` names those notes per kind (`weekly` for a month,
`monthly` for a quarter); the quarter's weekly notes are sources, not the
reviews it marks against. `Sources` therefore also resolves the `monthly`
entries, and a `monthly_only` item needs one of them, as a `weekly_only`
item needs a weekly. `check_item` and `group_reason` are public because
`review_sections` applies the same rule to section items with their mark as
the group: one rule, not two copies.

## WHY the Unmapped Document Keeps Its Own Code Path (spec 046 T4.2, F1-AC10, CON-2)

Without a mapping (`DocInput.sections` is None) `render_document` runs the
group loop it ran in spec 045: every group of the kind, the nothing-found
bullet for an empty one, the same ids. The section side is a second branch,
not a generalisation of the first, so a user who never maps a section gets
the document spec 045 shipped, byte for byte. `tests/test_046_t4_2_unmapped_doc_golden.py`
pins that against a recording of the pre-T4.2 head (week and month); a
change there is a regression, not a stale golden.

## WHY the Mapped Document Is Assembled From Parts (spec 046 T4.2, ADR-11, F1-AC7, F3-AC1)

With a mapping the document mirrors the user's note: the section parts in
template order, then the "Tomo Review" part — a divider heading
`## <review heading> %%review%%` with its landing line, the analysis parts
(rows with placement `review`, F2-AC12), then the groups. The parts are
rendered in `review_sections` (one owner for a section's heading, checkbox,
landing line and mark, and for `group_parts` / `part_items`, which both
documents use, so a group renders the same way in each); this module keeps
the frame (title, callout, Approved line, frontmatter), the item line
(`item_lines`, which takes the mark as a suffix) and the label table. The
move also keeps this file under the L2 size guide (≤ 450 lines). Empty groups are left out with a mapping: the user's own
sections already answer "what happened", and a column of "nothing found"
groups under "Tomo Review" would be noise (F1-AC7). When no group and no
analysis part is left, the divider goes too: an empty "Tomo Review" part
would promise a section the delivery never writes. The habits stay a group,
so they stay in the "Tomo Review" part. Every part stays at `##`, so the
parser's column-0 grammar does not change. The ids stay global over the
whole document (`%%t1%%` … across sections and groups): the parser and
`pass1_links` key on them, and two parts may not share one.

`counts` gains one entry per section key beside the group counts. Group keys
are words and section keys are row ids (`s<n>`), so the two never collide,
and the sum of `counts` stays the number of Tomo items in the document —
what `review_doc_read` hands the parser as `pass1_total`.

## WHY the Child Groups Render By What Was Accepted (spec 046 T4.2)

`month_groups` used to be set from `weekly_only in accepted`, which is true
only for a month with weekly notes. A quarter's `monthly_only` /
`not_in_monthly` would never render, although `check_items` accepted them.
The flag is now "a child group of this kind was accepted" (the group table of
the kind decides which), so a quarter that read monthly notes shows its pair
and a week or month is unchanged.

## WHY the Review Keys Are Top-Level Frontmatter (ADR-2 Amendment)

`doc-frontmatter.schema.json` closes the `tomo:` block to `doc_type`,
`state`, `run_id`, `updated_at` and `sources`. The period, kind, target and
language the parser and the state listing need therefore live as plain
`review_*` keys beside the block; `build_tomo_block` keeps the block
schema-valid, and the keys are dumped with `sort_keys=False` so the document
reads in a fixed order.

## WHY the Label Table Lives Here

Group headings, the callout's words and the "nothing found" line come from
one small de/en table with English for every other language (SDD
System-Wide Patterns i18n, F4-AC5). The habits lines have their own table in
`review_habits` because they belong to the numbers; the two tables do not
overlap. One table per module keeps each under the size limit; a shared
label module would be a third file for twelve strings.

## WHY `mark_delivered` Lives Here (spec 045 T4.2, F5-AC11)

The delivered mark changes two things in the document this module
rendered: `tomo.state` becomes `approved` (SDD ReviewDoc) and the first body
line — the `# <period> Review` title — gets ` — delivered` / ` — geliefert`
from the same label table as the rest of the document. The function is pure
and idempotent (a marked text comes back unchanged), so the delivery can
decide from its result whether a write is still needed and a resumed mark
never stacks a second word. It parses the frontmatter the way
`review_doc_parse` does (the first `---` block, `yaml.safe_load`) and
serialises it back with `yaml.safe_dump` — a round trip of Tomo's own
frontmatter, never a regex edit; only the `tomo` block changes, the
top-level `review_*` keys are rewritten as read. The run id stays the
document's: the mark is the same run's last step, not a new run. Why the
whole text is written once with one guard rather than a frontmatter merge
plus a title write: docs/tomo/scripts/review-instructions.md, "WHY the Mark
Is One Guarded write_note, Last".

## WHY the Schema Has No Version Header

JSON carries no comment; Tomo's schemas are versioned by the scripts that
read them (repo rule: JSON schemas have no version header).

## Known Limits

- An inline `[[...]]` or `![[...]]` in the model's item text stays verbatim:
  only the links the script renders from resolved sources are checked. The
  user reviews the text before approval.

## WHY the `end` Landing Line Says "the Text Under" the Heading (spec 046 T6.4, 0.5.2)

Since spec 046 T6.3 (`end_own_text`), `end` at a heading that has sub-headings lands at the end of the heading's own
text, before its first sub-heading, not at the end of its whole subtree. "At the end of "H"" read as the subtree end
and so promised the wrong place. The `end_h` label now says `at the end of the own text of "H"` /
`am Ende des eigenen Texts von „H“`. Tests: `test_046_t4_2_doc_sections.py`, `test_046_t5_2_new_note_sections.py`.
The owner chose the wording (2026-11-19): "the text under H" still read as covering the sub-headings.

## WHY `Sources` Leaves Out the Days of a Not-Condensed Unit (Spec 047 T4.4, 0.5.4)

WHY: F6-AC1, ADR-4. A unit that failed its retry was condensed by nobody: the
proposer never saw its days, so an item citing one of them can only be
invented. `Sources.of` drops the dailies of every day listed in the read's
`not_condensed` (`[{unit, days}]`, set by `review-doc.py` from
`condensed.json` and `weeks.json`) and an item resting only on such a day is
rejected exactly as spec 045 rejects a source outside the period — no new
reason, the user sees the same rejection. The rule keys on `not_condensed`,
which only `review-doc.py` sets: `review-digest.py` builds `Sources` from the
plain loaded read, so when it offers a failed unit again on a continued read
that unit's own digest is checked against its own days.

## WHY the Carried Labels and the Top Lines (Spec 047 T5.2, 0.6.0)

`Sources`, `previous_of` and the one source resolver `resolve_sources` moved
to `lib/review_sources.py` in the same version (CON-5); `review_doc`
re-imports them. Their WHY: docs/tomo/scripts/lib/review_sources.md.

WHY the carried labels live in `_LABELS` (F5-AC1): every other mark of an
item line comes from this table, EN and DE, English for any other language.
The wording is the owner's: "done (previous review)", "still open (previous
review)", "not mentioned again (previous review)" / "erledigt (letzter
Rückblick)", "noch offen (letzter Rückblick)", "nicht mehr erwähnt (letzter
Rückblick)". The suffix itself is built by the section parts (T5.3/T5.4).

WHY the top lines are continuation lines of the info callout (ADR-12): the
callout is already the place the document says what it read and did not
read (spec 045 F3-AC13). The first line stays byte for byte, so a document
without previous notes, failed units or a failed carry is unchanged; new
facts are `> ` lines under it. One plain line per previous note,
`Previous review · <kind> <name>: <state>` / `Letzter Rückblick · …`, in the
record shape `lib/review_previous` produces, plus the carried count:
"found, n carried" or "found, nothing carried" (F3-AC11), ", read in part"
appended when the note was cut at the reading limit (F3-AC10), "empty",
"no note found for <name>" — no error tone, it is also every user's first
review (F3-AC6; an empty folder listing is this state, PRD v1.2), "<kind>ly
notes are not set up" (F3-AC8, no setup question), "not read: Kado refused
it" / "not read: Kado did not return it" (F3-AC9) and a bare "not read" for a
row without a cause. One `Not condensed: <unit> (<first> – <last>)` line per
failed unit (F6-AC1) and one "The previous reviews could not be taken into
account." line when the carry failed as a whole (F6-AC2). Pass 2 is
unaffected: `review_doc_parse` reads nothing above the first `## ` but the
column-0 `- [ ] Approved` line, and no top line starts with a checkbox.

WHY a found or empty previous note is a link (owner, T9.2 R1b, spec 047
T9.3 F-R1-2, 0.6.3): the user wants to open the previous review from the
inbox document. The line names such a note as `[[<stem>]]`, the stem of the
read's `path` (`previous_rows` carries it; `review-doc.py`'s
`written.previous` copies a fixed key list, so stdout is unchanged):
`Letzter Rückblick · Woche [[2026-W12]]: gefunden, 16 übernommen`. A missing,
not-set-up or not-read note keeps its plain name — there is no note to open,
or none Tomo read. The link is never a source: `review_doc_parse` collects
link stems from item lines only, and the callout lines are no items.

WHY a blank line before and after the callout (same owner request): the
title, the callout and the Approved box read as three blocks in Obsidian.
The parser and the delivered mark skip blank lines (`is_delivered` and
`mark_delivered` take the first non-blank line as the title).

## WHY the Carried Branch Sits in `check_items` (Spec 047 T5.4, 0.6.1)

WHY an explicit branch at the call site (ADR-6): a carried item follows
other rules than a found one — it must rest on a previous note within its
carryover ids, `not_mentioned` forbids a day, and the two-day theme rule does
not apply. Folding those into `check_item` would change the spec 045/046
behaviour every existing test pins. So `check_items` asks `item["carried"]`
first and sends a carried item to `check_carried` (which runs the
`empty-text` test `check_item` uses, then `review_carried.check` with
`in_section=False`); every other item goes through `check_item` unchanged.
`review_sections.check` uses the same `check_carried` with `in_section=True`
and the item's mark, so the empty-text test exists once.

WHY carried failures are `errors`, never `rejected`: a rejected row is
dropped from the document and only counted. A carried item exists because
the previous review left it open; dropping it silently would lose exactly
what the carry is for. An error refuses the whole file (`proposals-invalid`)
and the skill re-dispatches the proposer once with the errors verbatim.
That is why `check_items` now returns `(accepted, rejected, errors)`: a third
value no caller can overlook, rather than a list a caller could forget to
read. A carried item in a group its kind does not render (a child group of
another kind, growth) is an error too (`carried-not-allowed (<group>)`),
not a group-wide rejection.

WHY the carryover comes from the read: `review_stage.load` puts
`carryover.json` into the read only when its state is `passed`, else None.
A carried item without it is `carried-without-carryover` — the proposer
cannot have seen a carryover that never passed.

WHY `previous_rows` counts carried items by link: a top line says how many
items were carried from one note (F3-AC11). An accepted carried item links
the previous notes it rests on, so the count per found note is the number of
accepted carried items (groups and sections) whose links hold that note's
stem. A not-found note carries nothing and shows no count.

WHY a single-day not-condensed unit shows the day alone: "(2026-03-02 –
2026-03-02)" reads as a range that is not one. A unit of one taking-part day
renders "Not condensed: W10 (2026-03-02)".

## WHY a Found Note Can Say "Not Taken Into Account" (Spec 047 T5.4, 0.6.2)

WHY: F6-AC2, owner 2026-11-24. When the carry of one previous note fails
(its own state in `condensed.json`'s carryover `notes` is `failed`) while
the carryover passed for the other, that note's top line says "found, not
taken into account" / "gefunden, nicht berücksichtigt"; the other note's
items stay carried. When the whole carryover did not pass (`pending`,
`retry`, `failed`), every found note says the same, beside the one
carry-failed line: "found, nothing carried" would claim the note held
nothing to follow up, which nobody checked. `previous_rows` sets
`carry_failed` on such a row; `review-doc.py write` reports it in
`previous`.

See also: [review_sources](review_sources.md), [review_carried](review_carried.md), [review_sections](review_sections.md), [review_doc_parse](review_doc_parse.md).
