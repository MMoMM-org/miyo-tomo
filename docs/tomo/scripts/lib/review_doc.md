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
`themes`, `growth` and `not_in_weekly` needs at least one source that is a
daily of a day in the period, a `weekly_only` item needs a weekly note the
reader listed, a theme needs two distinct days. An item that fails is not
silently dropped and not silently kept: it goes to `rejected` with its
group, index and reason, so the skill can tell the user how many proposals
had no footing, and `counts` names what landed. A source may be given as the
vault path the reader listed or as the note's stem (`2026-03-24`) — the
model sees both in `read.json` and either resolves to the same day; it is
rendered as `[[stem]]`, the link form the owner's notes already use.

Growth items follow the same rule although their facts come from the growth
listing: the SDD rule names only dailies (and weekly notes for
`weekly_only`), and a growth proposal that no day of the period mentions is
a listing, not a review observation. An open question for the owner is
recorded in the task report.

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
no group a model could put it in. The habits items arrive already rendered
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
