# WHY: lib/review_sections.py

> Rationale for decisions in `tomo/scripts/lib/review_sections.py`.
> The module owns the Pass 1 section side of `/review` (spec 046, T4.1;
> PRD F1-AC3, F1-AC4, F1-AC5, F1-AC6, F1-AC9, F1-AC10, Rules 5 and 6; SDD
> ADR-1, ADR-2, "Runtime View / Double placement"): it reads the section
> definitions `read.json` carries and checks the `sections` the model wrote
> into `proposals.json` beside spec 045's `groups`; from T4.2 it also builds
> the section parts from the configured rows and renders them (heading,
> checkbox, landing line, mark suffix). No Kado, no model, no file I/O.

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
whitespace collapsed, the `%%t<n>%%` ids removed whole and then any other
`%%`, before the trailing link list) so a copy that differs only in case
or spacing is still a copy.

Of the links, only the link list goes: the parenthesised list of wiki links
at the end of a line, `([[a]], [[b|Mon]], [[c#Log]])`, the form
`review_doc.item_lines` renders after the item text from its sources. A model
that copies that list into `text` has still written the same finding, and its
sources are compared separately. A wiki link inside the sentence is part of
the finding: "Talked with [[Anna]] about the offer" and "Talked with [[Bert]]
about the offer" are two findings, and stripping every link would make them
one and refuse the whole file. So an inline link is reduced to its target
(`[[a|b]]` → `a`, `[[a#h]]` → `a#h`, `![[x]]` → `x`): different targets
stay different, and the same target under another alias is still the same.
A text that is nothing but a link list normalises to nothing and is skipped
here: it holds no finding text to repeat.

Items of a `sections` entry refused as `unknown-section` or
`duplicate-section` do not take part. The entry is already refused and the
model rewrites it as a whole; its items reported a second time as
`double-placement` would point the model at items it must drop anyway, not
at a second place to merge. Sources are compared as the set of
their note stems, so a path and a bare stem of the same note are one source.
The check runs over every item of the accepted section entries and every
group item in document order (sections first, then the groups in their table
order) and names the later one, so the model keeps the first place. It runs
only with a mapping: spec 045's groups are checked exactly as before
(F1-AC10). An item whose text normalises to nothing is skipped here:
whitespace-only text is rejected as `empty-text` by the source rule, and a
link-list-only text holds no finding text a second item could repeat.

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

## WHY a Section Part Looks the Way It Does (spec 046 T4.2, ADR-11, F1-AC8, F3-AC2, F3-AC3)

`## <heading> %%sN%%`, then `- [x] <label> %%sN%%`, then an italic landing
line, then the items. The id on the heading keeps the section recognisable
when the user edits the heading text, and keeps a user section named like a
group label ("Done") from being read as that group; the same id on the
checkbox ties the checkbox to its part. The id is the row key itself: it is
opaque (assigned at save, never derived from text, CON-3). The checkbox
label is the positive wording (`Abschnitt übernehmen`, `Use this section`):
ticked means "deliver it", so the user's one click is the natural reading of
the line. An empty section's checkbox starts unticked and shows the
nothing-found bullet: there is nothing to deliver, and a ticked empty
section would say otherwise (F1-AC8). The landing line has no column-0
structure (it starts `*`), so the parser ignores it; it exists so the user
sees where the section lands before approving (F3-AC3).

## WHY the Landing Line Names Heading, Placement, Level and Parent

A heading text can occur twice in a note ("Notes" under two parents); the
level and the parent the row was mapped with say which one is meant. The
wording follows the placement: `before` → "vor „X“" / `before "X"`, `under`
→ "direkt unter" / "right under", `end` → "am Ende des eigenen Texts von" / "at the end of the own text of" (since T6.3, `end` lands before the first sub-heading).
An analysis row (`review`) and a routed section (its heading missing in a
new note, set by delivery planning in Phase 5) land inside Tomo's own section
under a sub-heading named after them, so their line says "im Abschnitt „Tomo
Review“ unter „X“" without level or parent — the user's heading is not where
anything goes. The divider's line says where the "Tomo Review" section
itself goes (`place.anchor` and `place.placement`, the words the info callout
already uses). German uses „…“, English straight quotes as the callout does.
All words live in `review_doc._LABELS`, one table for the document.

## WHY a Mark Renders as a Suffix of the Item Text (F1-AC9)

A month or quarter item keeps its mark in whichever section it lands
(`· nur im Wochenrückblick`, `· in keinem Wochenrückblick`, the quarter's
monthly equivalents). It is rendered after the link list and before the id,
as part of the item's text: the user can edit or delete it, it is delivered
as written, and the parser does not need to read it back.

## WHY the Parts Take Their Landing From the Config Rows

`read.json`'s SectionDefinitions carry no placement on purpose: where a
section lands is not the model's to weigh (`review-read.py`,
`section_definitions`). `review-doc.py` reads the vault config anyway for the
setup, so `parts` builds each part from the configured row of the same id —
heading, level, parent, placement — and takes only the order and the keys
from `read.json` (template order, as `match` offered and the user confirmed
the rows). When the keys of `read.json` and the configured rows differ, the
mapping changed between the read and the write (a row added, removed, the
mapping dropped or added). Guessing a placement for a section the config no
longer has, or silently leaving out one it now has, would put text where the
user did not confirm it or drop a part the delivery expects; `parts` raises
`SectionsChanged` and the write is refused `sections-changed`, so the period
is read again under the current mapping.

## WHY the Double-Placement Normaliser Strips the Ids First (T4.2)

The rendered form of an item ends `([[stem]], …) %%tN%%`. A model that
echoes such a line into `text` used to keep its link list: removing every
`%%` left `… ([[a]]) t1`, and the list was no longer trailing. The ids
(`%%t<n>%%`) are now removed whole first, then any other `%%`, and only then
is the trailing link list taken off, so an echoed line normalises to its
finding text like any other copy.

## WHY Headings Are Display-Neutralised in the Document (T4.2)

Section headings, the "Tomo Review" heading, a row's parent and the place
anchor are user text from the vault config, kept verbatim (ADR-9), and only
`setup.heading` is checked, as non-blank. Placed raw, a heading with a line
break (`"X\n## y %%s9%%"`) would emit a second column-0 heading or checkbox,
and a heading holding `%%…%%` (`"A %%review%%"`) a second id the T4.3 parser
reads as structure. A real template heading with an Obsidian fold comment
(`Habits %% fold %%`) would put two `%%` marks on the heading line.
`display_heading` therefore collapses all whitespace to single spaces (one
line, no forged line), drops every `%% … %%` span (the fold comment, any
id-shaped text) and folds any leftover `%%` run to one `%`, so no id can form;
`Habits %% fold %%` reads `Habits`. `[[…]]` is left alone: a link in a heading
is legitimate Obsidian text, starts no column-0 structure and is not an id.

It is display only. The parts, the config rows, `read.json` and everything
delivery planning reads keep the original text; a section is identified by
its `%%sN%%` key, never by the heading shown, so the delivered heading is
matched against the template as configured.

The info callout (`review_doc._callout`) shows the anchor too, and it is
neutralised there only in a mapped document, the one rendered with section
parts: only that document is read back by the T4.3 section parser, so only
there could a forged `## z` line or `%%s7%%` id pass for structure. An
unmapped document keeps the anchor raw, because CON-2 holds it byte-identical
to the document spec 045 shipped (pinned by
`tests/test_046_t4_2_unmapped_doc_golden.py` and by
`test_the_unmapped_callout_keeps_the_anchor_raw_as_spec_045`). `render_document`
picks the anchor and hands it to `_callout`; it calls `display_heading` through
the `review_sections` module it already imports locally, since
`review_sections` imports `review_doc` at module level and a top-level import
the other way would be a cycle.

## WHY a Routed Part Keeps Its Template Place but Opens the Divider (T5.2)

A routed part (`routed`, set by `review-doc.py write` for a new note
whose template lacks the heading) renders where its row stands in the
template order, with the landing line naming "Tomo Review": the user reads
the sections in the order they configured them. Its items land in Tomo
Review, so the divider with Tomo Review's own landing line is rendered
whenever any part lands there — an analysis part, a routed part or a
non-empty group.

## WHY the Section Check Has a Carried Branch (Spec 047 T5.4, 0.3.0)

A section item may be carried (ADR-6). The mark-fits-the-period check of
spec 046 (`group_reason` → `mark-not-allowed`) still runs first, exactly as
it runs ahead of `check_item`: `review_carried.check` checks whether a mark
may sit on a carried item, not whether the mark fits the period, so without
this order a `not_in_monthly` carried item could slip into a month review.
Then a carried item goes to `review_doc.check_carried` with
`in_section=True` and its mark; every failure is an `errors` entry, never a
`rejected` row (see review_doc.md, "WHY the Carried Branch Sits in
`check_items`"). An accepted carried item keeps `carried` beside `mark`.

WHY the suffix order is carried label, then child mark (F5-AC2):
`part_items` builds `" · " + carried label` then `" · " + mark label`. The
carried mark says where the item comes from, the child mark what the child
notes say about it; the owner chose this order.

WHY the cap is counted after `review_carried.overflow`: `review-doc.py write`
runs `overflow` on the proposals before this check, so a section the
carried items made full has already moved them to their groups, and
`over-cap` is left for non-carried items only (F4-AC10).

WHY an off-limits heading never receives a carried item (F4-AC5): the
off-limits rows of `review_mapping` leave such a heading out of the offered
headings, so it never becomes a configured row, never a SectionDefinition
in `read.json`, and a proposal naming a key for it is `unknown-section`.
The proposer places the item in the next fitting section or its group.

WHY `section_cap` is public: `review_carried.overflow` needs the same cap
rule; a second copy would drift. It is imported at call time there because
this module imports `review_doc`, which imports `review_carried`.

See also: [review_doc](review_doc.md), [review_carried](review_carried.md), [review_doc_parse](review_doc_parse.md).
