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

## WHY the Schema Has No Version Header

JSON carries no comment; Tomo's schemas are versioned by the scripts that
read them (repo rule: JSON schemas have no version header).
