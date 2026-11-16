# WHY: lib/review_mapping.py

> Rationale for decisions in `tomo/scripts/lib/review_mapping.py`.
> The module reads a periodic-note template and says, per heading, whether
> `/review` may offer it as a section to fill and, when not, why (spec 046,
> T1.2; PRD F2-AC3, F2-AC5, F2-AC11; SDD ADR-8, ADR-9, ADR-10; SDD
> "Implementation Examples / Template analysis"). It also owns heading
> identity, the off-limits landing check, row ids and the `dropped` list.
> No Kado, no model, no file I/O.

## WHY the Analysis Is a Script, Not the Model

F2-AC4 refuses a left-out heading when the user adds it, so a heading wrongly
left out is a heading the user can never map. A model verdict would differ
from run to run and could not be pinned by a test on the owner's templates;
deterministic rules can (ADR-9). The model only words descriptions,
keywords and group hints on the headings this module offers.

## WHY First Rule Wins, in This Order

`templater`, `link`, `per-period-parent`, `off-limits`, `automatic` (ADR-9).
The order goes from "the heading text itself cannot be found again" to "the
section has nothing to write into":

- a heading whose text holds Templater code (`<%`) renders differently in
  every note, and one with a link (`[[`) usually names the period's own
  note — neither can be resolved in the delivered note by its template text;
- a heading under such a heading, a heading that repeats with the same level
  and text under three or more parents (the day sub-headings of a week), and
  a container whose own body is empty and whose sub-headings are all left
  out for these reasons exist once per day, not once per note: there is no
  single place to write into;
- off-limits is the user's mark and is checked only after the structural
  rules, so the reason shown is the structural one when both apply — the
  heading is left out either way;
- `automatic` comes last because it is the only content judgement.

## WHY `automatic` Is Conservative

A section is left out as `automatic` only when its own body has at least one
automatic line and no own-writable line, or when its own body is empty and
every sub-heading is left out as `automatic` (the "Overview" of a week whose
children are all tracker and dataview blocks). Anything else is offered:

- a section with both automatic and own-writable lines gets the flag `mixed`
  and is offered and never refused (F2-AC4) — "Reflections" carries inline
  fields the user fills next to their own task lines;
- `tp.file.cursor` placeholders, blank lines, `%% … %%` comment lines and
  the lines of a `[!type]` callout block are neutral: they are template
  skeleton, not content, so a section of nothing but a cursor ("What Went
  Well This Week?") is empty and offered;
- a line that mixes words with an inline query ("This week I was grateful
  for: `` `=this.days.gratitude` ``") is own-writable — the words are the
  user's template prose;
- a thematic break `---` is own-writable. It is not in the neutral list of
  ADR-9, and calling it neutral would turn a section of a button and a
  `---` into `automatic`, a left-out the user could not undo. The cost is
  that "Plan" of the monthly templates (button, `---`, METADATA) is offered
  as `mixed`, which the user can simply not map.

The automatic line classes are the fences in `review_md.AUTOMATIC_FENCES`,
an embed line (`![[…]]`, also when Templater builds the opening bracket with
`<%"["%>`), an inline field `Name:: v`, a line of nothing but inline queries,
non-cursor Templater spans and the links they build, a `BUTTON[` line, and a
line inside a multi-line Templater block.

## WHY a Callout Line Is Neutral Before Anything Else

A callout title line (`> [!sun] Rise....`) closes most sections of the
owner's templates; it is the heading of the next part as decoration. Its
quoted continuation lines go with it. A METADATA callout holds inline fields
that would be automatic; classifying the block neutral first keeps one rule
for every callout. A plain quote without a `[!type]` title is the user's text
and stays own-writable.

## WHY a Heading Is (Text, Level, Parent, Occurrence)

F2-AC5: "In my own words" sits at two levels in some templates, and the same
heading can repeat under one parent. The text alone is ambiguous; the level
and the nearest higher heading tell the user which one is meant, and the
1-based occurrence among identical (text, level, parent) separates true
duplicates. Level-1 headings are the note title — Templater-built in all
the owner's templates — so they are never offered and never a parent: a
level-2 heading has parent `null`. The text is kept verbatim, `%% fold %%`
included, because Hashi resolves the heading by its exact text.

## WHY the Template's Lines Are Split as `template_syntax` Splits Them

The Templater-block mask comes from `template_syntax.templater_inner_line_indexes`
over the whole text, split on `\n`. `review_md.body` uses `splitlines()`,
which also splits on `\x0b`, `\x0c`, `\x1c`–`\x1e`, `\x85`, U+2028 and
U+2029; on such a text the mask would point at the wrong lines. The module
therefore splits once on `\n` (like `template_syntax`), drops a frontmatter
block opened on line 1, and hands those lines to `review_md.headings`, so
the heading index and the mask index are the same line.

A heading-looking line inside a `<%* … %>` block (a JavaScript comment
`// ## x` cannot start a heading, but a template literal line can) or in the
frontmatter is no heading. A frontmatter that a leading Templater block
includes (`<% tp.file.include("[[x_frontmatter]]") %>`) has no `#` lines in
the owner's templates; YAML keys are never headings.

## WHY Off-Limits Is One Landing Function

F2-AC11 / ADR-8: nothing is off-limits by default; a row names a heading by
its full identity and protects the heading only or, with
`with_subsections: true`, every heading below it. `landing_off_limits` is the
single answer to "would writing here land in a protected section": a row
names the heading, or a `with_subsections` row names one of its ancestors.
`setup-input` asks it on the template and `plan_section` on the delivered
note (Phase 5), so the two cannot disagree. Under a heading-only row a
sub-heading is still offered, flagged `under-own`, so the proposal can show
that its parent is protected. Off-limits rows compare level and parent;
`own_sections` (spec 045) compares bare text and is a different setting —
the module never reads it.

## WHY the Outline Is Split at the Off-Limits Rule (T2.2)

`setup-input` checks rows offline against what `match` saw (ADR-3), and the
user may mark headings off-limits in the same Correct step. The rules before
off-limits (templater, link, per-period parent) depend on the template text
only; off-limits and `automatic` depend on the off-limits rows (an off-limits
sub-heading keeps its parent from being an automatic-only container).
`outline(text)` therefore stores the headings after the structural rules —
key, line, ancestors, body kind, structural reason — and `from_outline(data,
off_limits)` runs the last two rules on it. `analyse_template` is the same two
steps on the text, so `match` and `setup-input` classify a heading the same
way. A stored shape `outline` never writes raises `ValueError`; the caller
treats it as no evidence.

## WHY the Landing Is Computed on the Outline

ADR-8 / SDD Complex Logic: a `before` block becomes part of the body of the
heading above the mapped one; an `end` block (and the "Tomo Review" section
placed `inside` an anchor) part of the body of the last heading inside the
mapped heading's range, sub-sections included; `under` lands in the mapped
heading. `landing(heads, top, line, placement)` names that heading from the
template's lines, level-1 headings included as boundaries (`top`): a level-1
heading ends every range and its body is never coverable (rows have levels
2..6), so a landing there or in the preamble is None. `plan_section` applies
the same rule to the note at delivery (Phase 5); the template check is the
earlier refusal, the note check the one that guards the actual write.

## WHY Row Ids Never Reuse a Number

ADR-10: a row keeps its id when it is corrected and when the template keeps
the same heading identity, so the `%%sN%%` markers already in delivered notes
still name the same section. A new row gets the next number above every id
in the previous and the current rows. Taking the lowest free number would
give a removed section's id to a new one, and an old block in a note would
then be read as the new section's own block.

## WHY `dropped` Compares (Text, Level, Parent)

ADR-13 / F7-AC3: after a template change the user must see the rows the new
template no longer has. Occurrence is left out of the comparison: a new
duplicate earlier in the template shifts occurrences without removing the
heading the user mapped, and that case is a correction, not a loss.

## WHY the Heading Walk Is Shared With the Note Planner (spec 046 T6.2)

`walk_headings` turns a heading list into identities — text, level,
parent, occurrence among identical (text, level, parent) — and ancestors.
`_tree` uses it on the template's headings; `review_section_plan._Note.read`
uses it on the note's headings as Hashi reads them. Until T6.2 the planner
carried its own copy of the loop, and the two copies are what decide
whether a row the setup saved (from the template) finds its heading in the
note: a fix to one walk — how a level-1 heading ends a branch, from which
number occurrences count — would have silently stopped matching the other.
One walk keeps the identity the same on both sides.

What differs stays at the callers, as parameters and inputs: the heading
list (this module's `headings` after Templater spans, frontmatter offset
applied by `_tree`; Hashi's `hashi_headings` for a note), and `name`, the
text the identity holds (verbatim here, `rht.bare` — closing hashes off —
in the planner). A level-1 heading yields no key: the template analysis
lists it as a top line, the planner gives it occurrence 0, never a row. The
walk lives here because this module defines `HeadingKey`;
`review_section_plan` already imports it, and this module never imports
the planner (`tests/test_review_section_plan.py`, `FORBIDDEN`). The change
is pinned by a golden of both walks recorded before it
(`tests/test_046_t6_2_heading_walk.py`).
