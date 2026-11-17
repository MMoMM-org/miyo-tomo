# WHY: lib/review_delivery.py

> Rationale for decisions in `tomo/scripts/lib/review_delivery.py`.
> The module holds what `review-instructions.py` (spec 045 T4.2) needs
> besides the plan builder and the staged loop: the problem classification,
> the `meta.json` adapter the loop records into, the paths of the set, the
> MD peer and the withdrawn set.

## WHY the Classification Is a Pure Table

`classify(plan)` returns `(problems, notices)`: the refusing names and the
notices, in the plan's order, the plan's boolean flags added as names. The
two tuples `REFUSING` and `NOTICES` are the whole rule, so a test can pin
every name to its side and the reviewer reads one place. An unknown name
refuses — the safe default for a problem nobody has classified yet.
Rationale for the split: docs/tomo/scripts/review-instructions.md, "WHY
Problems Are Split". `ALREADY_APPLIED` (`already-applied`) is `drop`'s
refusal, not the plan's; it lives in `REFUSING` so the pin test names it
with the others and no script spells it on its own. `SET_WITHDRAWN`
(`set-withdrawn`, P5) is `preview`'s and `deliver`'s refusal of an emptied
set on a begun stem (docs/tomo/scripts/review-instructions.md, "WHY an
Emptied Set on a Begun Stem Is `set-withdrawn`"); it lives beside
`SET_EXISTS` for the same reason. `REPLAN_DIFFERS` (`replan-differs`) and
`ANCHOR_NEEDED` (`anchor-needed`, both fix #258) are `deliver`'s refusals of
a resume — the re-plan contradicts the recorded `delivered_plan` while a set
step is undone; a delivery begun with a picked heading is resumed without
`--place-anchor` (docs/tomo/scripts/review-instructions.md, "WHY a Resume
Refuses a Re-Plan That Differs From the Record" and "WHY a Picked Anchor Is
Recorded as a Flag") — never handed to `classify`, listed in `REFUSING` so the
one pin test and the skill's coverage test name them with the others.
`SECTION_CHECKBOX_MISSING` (`section-checkbox-missing`, spec 046 T4.4) is the
parser's warning for a section checkbox it cannot read (deleted, broken,
moved out of its part, doubled; docs/tomo/scripts/lib/review_doc_parse.md).
`lib/review_actions._gate` refuses it right after `approved-line-missing`
and before `not-approved`: both are documents whose state the parser cannot
read without guessing, and a guessed section state could land a section the
user dropped (F3-AC6). It sits in `REFUSING` so `preview` and `deliver`
stop on it and the skill's coverage test demands its stop line. Only the
gate stops a heading that carries another expected key first
(`## <heading> %%s3%% %%s1%%`): the parser files the items under `s3`,
which may be ticked, and only the warning keeps them from landing.

Spec 046 T5.5 widens the table, not the rule. `REFUSING` gains the six
section stops (`review_section_plan.STOPS`: `section-missing`,
`section-ambiguous`, `section-broken`, `section-moved`,
`block-in-review-section`, `landing-off-limits` — the last also the plan
problem of a "Tomo Review" place that would land off limits), `choice-invalid`
and `choices-needed`; `NOTICES` gains `block-replaced`,
`block-moved-confirmed`, `review-section-kept`, `section-dropped` and
`section-empty`. `classify(plan, extra, counts, choices)` reads them where
they arise: the stop of every section of `ReviewPlan.sections` whose block
holds lines, the sections' notices and `ReviewPlan.notices`, the parsed
document's `section_counts` (`counts`) for dropped and empty sections, and
`choices` against what the plan took (`review_section_report.untaken`); a plan
with no refusing problem and no action is `nothing-to-deliver`. Each name is
listed once, in the order found. The rationale for each rule is in
docs/tomo/scripts/review-instructions.md, "WHY Every Section Stop Refuses
Until a Choice Answers It". `section_report` gives the output fields that
go with the names (`sections`, `dropped`, `empty`, `choices_invalid`), so
the names and their detail come from one reading of the plan.

## WHY `second_set` Takes Whether the Set at the Path Is Applied (T6.1 fix round)

Owner decision 2026-11-12 (spec 045 T6.1 finding: the PRD said F6-AC3 "a
rerun replaces the section" while the SDD said every set at the path is
`set-exists`, and the e2e walk had to delete the applied set by hand to get
the rerun through). `second_set(set_exists, any_applied)` (first named `set_applied`, when it was fed
`all_applied`) now reads: a
complete delivery (`doc_mark` recorded) or a withdrawn one is always a second
set; a set this delivery did not write (`wrote_set()` false) is a second set
*unless every action in it is applied* — then it is the finished set of an
earlier run of the same period, the vault already holds its effect, and the
rerun's `deliver` writes the new set over it
(docs/tomo/scripts/review-instructions.md, "WHY a Fully Applied Set Is
Written Over"). A set with no action applied stays `set-exists`: Hashi may
still be working on it. Since spec 046 T5.5 (ADR-12) the caller passes
`review_state.any_applied` as the flag, so a partly applied set — one
section failed at Hashi — is written over as well instead of leaving the
review stuck (docs/tomo/scripts/review-instructions.md, "WHY a Partly
Applied Set Is Written Over"). The predicate is `review_state`'s — an
empty `actions` list never counting (that is `drop`'s signature, see
`SET_WITHDRAWN`) — so the state function and the delivery cannot drift. The flag is an argument, not a read inside `ReviewMeta`,
because the adapter holds no set and no Kado.

## WHY `ReviewMeta` Wraps the Dict

`meta.json` of a review is a plain JSON object `review-doc.py write`
created and `review_state.read_meta` returns as a dict. `staged_delivery`
and `note_meta.mark_step_*` record through attributes (`steps_done`,
`failed_step`) and `stable_block` reads `run_id` and `generated`. A thin
adapter over the same dict — the list is shared, not copied — lets the loop
run unchanged and the script persist the dict it read, with every other key
(`pass1_links`, `withdrawn`, `mode`, …) untouched. A dataclass of the review
meta was rejected: it would have to enumerate and re-serialise every key
the Pass 1 writer and the state function own.

### WHY `META_FILE` Comes From `note_meta`, and `set_json_path` Exists (T4.3)

`review_state` reads a begun delivery through `ReviewMeta.started()`
(coordinator decision 2026-11-12), so it imports this module; this module
imported `META_FILE` from `review_state`, and the two edges made a cycle.
The file name is not `review_state`'s: `meta.json` is the stage file of
every staged delivery, and `lib/note_meta.META_FILE` already owns it for
`staged_delivery`. `save_meta` now takes it from there, and the back edge
is gone. `set_json_path(inbox, stem)` names the set's inbox path from the
inbox folder alone, because the state function has an inbox and a stem but
no `ReviewSetup` (a listing must not require a complete setup to say where
a set lives); `set_paths` uses it so the two cannot spell the suffix
differently.

## WHY the MD Peer Comes From `render_md`

The readable instructions are what `/inbox` and `/note` write
(F5-AC9): the same renderer gives the `### I01 — …` heading and `- [ ] Applied`
box Hashi's peer sync ticks, the target, the anchor, the placement and the
copy-ready fenced block, or the move with its destination and the Templater
line when the note keeps Templater code. The tomo block is merged afterwards
through `stable_block` so a rebuild is byte-identical.

## WHY the MD Peer Carries `tomo.sources` — and Never the Review Target (spec 046 T6.3)

WHY: owner decision 2026-11-17, from the Hashi joint run round 1. Hashi's
cleanup after a full apply (Hashi ADR-018 §4, #146, `cleanupAfterFullApply`)
takes `tomo.sources[]` from the peer's frontmatter as its only source of truth:
it merges `tomo.state: applied` into the peer, **trashes every
`sources[].path`**, then the peer, then the set JSON. A peer without the array
makes Hashi write and trash nothing ("no cleanup: no tomo.sources"), so review
sets stayed in the inbox after every apply while `/inbox` sets left.

What `set_md` lists, in this order (`peer_sources`):

1. the review document (`<inbox>/<period> Review.md`) — `meta.json`'s
   `doc_path`, the same path `review-instructions.py` read the plan from, so
   the list needs no extra argument and no Kado call;
2. for a new-note delivery, the new note's inbox copy (`plan.note_path`) —
   after the move it is already gone, which Hashi only warns about. It is
   Tomo's own file: the `note` step is delivered before `set_md`, so the
   peer is never written unless the copy at that path is Tomo's.

**Never the review target** (the week, month or quarter note). Hashi trashes
every listed path, and the target is the user's own note. Neither listed path
is the target by construction (both sit in the inbox, the target in the
calendar folders), and `peer_sources` still drops any path equal to
`plan.target`: one comparison is cheap beside a trashed note. Entry shape is the `/inbox`
peer's (`render_md._build_tomo_block_for_instructions`): `{path}` objects,
`sources` after `updated_at`, validated by `build_tomo_block` against
`doc-frontmatter.schema.json`. The optional `checksum` is left out: the
`/inbox` checksum feeds triage's coverage record, and nothing reads a review
peer's sources but Hashi's cleanup. A meta without `doc_path` gives
`sources: []` — still valid for Hashi, which then trashes only the pair.

The withdrawn peer (`withdrawn_md`) lists nothing: `sources: []`. A drop
consumes no input. The document stays for the user (a drop is not a finished
review), and the new note's inbox copy is not listed because a drop may follow
a `note` step that failed in flight, where Tomo cannot prove the file at that
path is its own; the withdrawn MD already names it under "delete these
files", so the user decides. With `[]` a cleanup removes only the set pair,
the files the MD asks the user to delete anyway.

Resume note: the peer changes bytes. A `set_md` landed before this change
(no `sources`) and resumed after it is reported `name-taken` at `set_md`, the
ordinary "an earlier set waits" path; it only concerns sets delivered by a
pre-release build.

## WHY the Withdrawn Set Is Built From `meta.json`

`drop` may run on a document that is no longer readable or approved; the
withdrawn set must not depend on the plan. `withdrawn_set` needs only the
stem, `generated` and the profile — the envelope with an empty `actions`
list — and `withdrawn_md` the list of files the delivery left. Both validate
like any instruction set, so Hashi lists them and finds nothing to apply
(ADR-13).

## WHY the Guard Reading and the Resume Record Live Here (#260)

They moved out of `review-instructions.py` (630 lines) because none of them
needs the script's `Run`: each takes the plan, the meta, the problems or the
exception it reads. `tool_error_payload`, `tool_error_code`, `is_conflict` and
`conflict_reason` read a `KadoError` the delivery caught — the module imports
the exception classes only, it makes no Kado call. `plan_record`,
`replan_differs`, `resume_refusal` and `report_delivered_plan` are the
`delivered_plan` record of `meta.json` and what a resumed run does with it
(docs/tomo/scripts/review-instructions.md, "WHY a Resume Refuses a Re-Plan That
Differs From the Record"); `DELIVERED_PLAN` and `ANCHOR_PICKED`, the key and
the flag of that record, moved with them. Passing `configured_anchor` and
`anchor_picked` instead of the `Run` is what keeps the lib free of an import
cycle. `delivery_paths` and `public_paths` sit with the other path functions.
At 348 lines (cap 350) the module stays one responsibility (what a delivery needs
around the plan); a split such as a resume lib is the move before anything is added.
Spec 046 T6.2 made that split along the cleaner seam: the guard reading
(`tool_error_payload`, `tool_error_code`, `is_conflict`, `conflict_reason`
and their constants) depends on nothing else here and has one caller, so it
moved unchanged to `lib/review_kado_conflict.py`; the resume record stays,
since it shares the step names and `ReviewMeta` with the rest of the module.
Spec 046 T5.5 adds `sections` and `choices_given` to the record
(`plan_record(..., choices_given)`), the section comparison to
`replan_differs` and `choices-needed` to `resume_refusal`; the per-section
helpers they call (`record`, `report`, `untaken`) live in
`review_section_report` (in `review_section_set` until T6.2), so this
module stays under that line.

