# WHY: lib/review_section_report.py

> Rationale for decisions in `tomo/scripts/lib/review_section_report.py`.
> The module holds what a `/review` delivery reports and records of its
> mapped section plans besides the actions: the per-section output, the
> `delivered_plan.sections` record, the choices no plan took, the dropped
> and empty sections and the names and fields of all that (spec 046 T5.5,
> split out at T6.2). No Kado, no clock, no file I/O.

## WHY a Module of Its Own (spec 046 T6.2)

`review_section_set.py` stood at 199 lines against its 200-line cap after
T5.5 added these readings, and Phase 6 still adds code. The readings are a
seam of their own: `review_section_set` plans and composes (what the set
*writes*), these functions only *read* finished plans for the delivery
output and the record. Nothing in `review_section_set` calls them, and
their only caller is `review_delivery` (`classify`, `section_report`,
`plan_record`, `replan_differs`). So they moved here unchanged, with the
three names they emit (`choice-invalid`, `section-dropped`,
`section-empty`), and `review_delivery` imports this module instead of
`review_section_set`. The move is behaviour-neutral: the delivery tests
run unchanged.

Imports go one way: `review_delivery` → `review_section_report` →
`review_section_plan`; this module never imports `review_section_set`,
`review_actions` or `review_new_note`, and `review_section_plan` never
imports it (`tests/test_review_section_plan.py`, `FORBIDDEN`). It imports
the planner alone because a report needs only `SectionPlan` and the
planner's choice and notice names.

## WHY the Report Names the Configured Placement, and the Record Hashi's

`report`'s `placement` is the row's configured one (`before`, `under`,
`end`), carried on `SectionPlan.placement`; the preview lists it per
section (F4-AC6). `record` keeps `hashi_placement`, which only an insert
has (None for a replace, a stop, a skip or a routed section), because the
record exists to compare what the delivery wrote with a re-plan. Both are
enums, so naming the placement costs no privacy.

## WHY Only Sections With Lines Are Reported and Recorded

A section without lines gets no action and no id whatever its mode; the
dropped and empty notices name it instead. Leaving it out of `report` and
`record` means a heading of it removed between a stop and the resume
changes nothing the resume writes, and must not refuse `replan-differs`.

## WHY `untaken` Compares the Plan, Not the Choice

A choice is taken when the plan it answered shows it: `skip` / `review`
when the section's mode is that choice, `confirm-moved` when the plan
carries `block-moved-confirmed`. The planner applies a choice only at the
stop that offers it, so a choice for a section without that stop leaves
the mode as it was, and comparing the result catches every such case
without repeating the planner's rules (docs/tomo/scripts/review-instructions.md,
"WHY Every Section Stop Refuses Until a Choice Answers It").
