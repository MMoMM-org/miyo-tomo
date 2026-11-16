# WHY: lib/review_sections.py

> Rationale for decisions in `tomo/scripts/lib/review_sections.py`.
> The module owns the Pass 1 section side of `/review` (spec 046, T4.1;
> PRD F1-AC3, F1-AC4, F1-AC5, F1-AC6, F1-AC9, F1-AC10, Rules 5 and 6; SDD
> ADR-1, ADR-2, "Runtime View / Double placement"): it reads the section
> definitions `read.json` carries and checks the `sections` the model wrote
> into `proposals.json` beside spec 045's `groups`. Rendering a section part
> joins it in T4.2. No Kado, no model, no file I/O.

## WHY a New Module, Not More of `review_doc.py`

`review_doc.py` already holds the proposals schema check, the group source
rule, the rendering and the delivered mark (about 400 lines). The section
checks and, from T4.2, the section rendering are a second concern of the same
document; the constitution's L2 size guide and the SDD component table put
them in their own module. The group source rule stays where it is and is
called from here (`review_doc.check_item`, `review_doc.Sources`), so a
section item and a group item meet one rule, not two copies of it.

## WHY a Mapping Is "read.json Has a `sections` Key"

`review-read.py` writes `sections` only when the period kind has mapped rows
(SDD Internal API: absent key = no mapping). The check takes that as its one
signal and never reads the vault config again (ADR-1: the model and the
scripts read one file). Without a mapping, proposals without `sections` are
spec 045's and pass and fail exactly as before (F1-AC10): `check` returns
nothing, and no double-placement check runs on the groups. A `sections`
entry the model wrote anyway has no definition to match and is refused as
`unknown-section`, so text for the user's own headings still cannot reach a
document whose kind has no mapping.

## WHY Keys Only, and Why an Unknown Key Is Refused

The model names a section by its row id (`s1`), never by its heading text
(ADR-1). A heading the model invented or reworded would otherwise become a
section part the user never mapped. The schema checks the key's shape
(`^s[0-9]{1,3}$`); this module checks that it is one of the definitions.
A key named twice in `sections` is refused as `duplicate-section`: two
entries for one section would split its cap and its items without either
being wrong on its own, and silently merging them would hide that the model
lost track of the section.

## WHY Refusals for Shape, Per-Item Rejections for Sources

Two kinds of failure, two answers, as in spec 045:

- `unknown-section`, `duplicate-section`, `over-cap`, `double-placement` and
  `mark-not-allowed` are errors of the proposals as a whole: something the
  model must decide differently (which section, which item to merge, which
  place to keep). They come back as `errors` (`<pointer>: <error>`, the
  pointer into `proposals.json` as the model wrote it) and the write is
  refused, so the skill's rewrite-once loop lets the model fix them (SDD
  Error Handling: `proposals-invalid` with `errors` per item).
- An item without a source in the period (`no-source-in-period`) or without
  text (`empty-text`) is rejected on its own and listed with its section,
  index and reason, like a group item. That is spec 045's rule for the
  groups; dropping such an item loses nothing the period showed.

## WHY Caps Are Refused, Never Truncated (ADR-2, Rule 6)

Truncating to the cap would keep whichever items the model happened to write
first, not the ones that matter. `over-cap` names the section: the pointer
to its items plus its key in parentheses (`/sections/0/items: over-cap (s1)`,
SDD F1-AC5), so the model sees which of its sections to merge without
counting entries; the model merges on the rewrite. Only `over-cap` carries
the key: the other refusals point at the key itself (`unknown-section`,
`duplicate-section`) or at one item (`mark-not-allowed`,
`double-placement`), where the item, not the section, is what to change. The count is of the items the model proposed for the
section, before the source rule: a refusal that depended on how many items
later fail their sources would let the same file be refused or accepted by
the source check, and the model could not tell from the error what to cut.

## WHY Double Placement Is Checked Mechanically, and Only So Far (ADR-2, Rule 5)

Rule 5 (one finding, one place) is semantic; whether two differently worded
items are "the same finding" stays the model's (the skill says so). What a
script can refuse without guessing is the plain repeat: the same text, or
the same sources with the same first line. Text is normalised (casefold,
whitespace collapsed, `%%` marks and wiki links / a parenthesised link list
removed) so a copy that differs only in case, spacing or the links the
script renders anyway is still a copy. Sources are compared as the set of
their note stems, so a path and a bare stem of the same note are one source.
The check runs over every section item and every group item in document
order (sections first, then the groups in their table order) and names the
later one, so the model keeps the first place. It runs only with a mapping:
spec 045's groups are checked exactly as before (F1-AC10). An item whose
text normalises to nothing is skipped here; `empty-text` rejects it.

## WHY a Section Item Uses the Group Source Rule, With Its Mark as the Group

F1-AC3 / F1-AC4: a section item links a daily of the period, or, for what
only a weekly or monthly review of the period holds, that note. The item
says which case it is by its mark: `weekly_only` (month) or `monthly_only`
(quarter) is exactly "only that review holds it", the same meaning those
groups have in spec 045. So the check calls `review_doc.check_item` with
the mark as the group: a `weekly_only` / `monthly_only` item needs a listed
weekly / monthly note, every other section item (no mark, or
`not_in_weekly` / `not_in_monthly`) needs a daily of the period. The theme
two-day rule does not apply to section items: a section is the user's
heading, not the themes group. A weekly note cited by a quarter item counts
for nothing on its own (F6-AC4: the quarter's weekly notes are read as
sources, not as a review the item can rest on alone).

## WHY a Mark Is Checked Like Its Group (ADR-2, F1-AC9)

A month or quarter item keeps its spec 045 / F6-AC4 mark in whichever
section it lands. A mark is allowed only where its group would be: the
month marks on a month that read weekly notes, the quarter marks on a
quarter that read monthly notes (`review_doc.group_reason`). Anything else
(a mark on a week, a month mark on a quarter, a mark on a period whose
child notes were not read) is `mark-not-allowed`, a refusal rather than a
silent drop, because the label it would render claims a review was read
that was not.
