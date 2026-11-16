# WHY: lib/review_new_note.py

> Rationale for decisions in `tomo/scripts/lib/review_new_note.py`.
> The module composes the text of a new periodic note a `/review` delivery
> builds in the inbox: which template text it starts from, the plain note,
> the blocks spliced in, the rendered-note stamp (spec 045 ADR-8; spec 046
> T5.2, F4-AC5). No Kado, no clock, no file I/O.

## WHY a Module of Its Own (spec 046 T5.2)

`review_actions.py` was at its 500-line limit with T5.4/T5.5 still to come.
The new note's text is a concern of its own — template choice, splice, stamp —
that reads no `ReviewPlan`. The steps that do (where "Tomo Review" goes,
planning the sections, the `move_note`) stay in `review_actions`, because
`_insertion` and `_sectioned` serve the existing note too; moving them here
would make this module import `review_actions` while `review_actions` calls
it, the cycle the split removes. So this module takes plain values and
returns text: `review_actions` → `review_new_note` → `review_section_set` →
`review_section_plan` → `review_hashi_text`, never back (the splice helper
`splice_blocks` lives in `review_section_set` since T5.4). Pass 1 (`review-doc.py`) and Pass 2
(`review-instructions.py`) build the `Template` record and use
`template_choice` from here, so both passes pick the same text.

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

The template's text is taken by the exact bytes: `split_lines` mirrors
Hashi's `content.split("\n")`, and the rebuilt note ends with a newline
only when the template did. A note whose template lacks the final newline
lands without one; adding it would make the plain-vs-template byte
promise above false for that template.
