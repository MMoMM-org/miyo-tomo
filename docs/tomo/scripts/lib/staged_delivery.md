# WHY: lib/staged_delivery.py

> Rationale for decisions in `tomo/scripts/lib/staged_delivery.py`.
> The module owns the staged, resumable deliver loop that `note-instructions.py
> deliver` ran inline until spec 045 (spec 044 ADR-2; spec 045 ADR-11), so that
> `/note` and `/review` write their vault files with one set of rules.

## WHY the Loop Left note-instructions.py (spec 045, ADR-11)

`/review` delivers a review document, an instruction set and its MD peer the
way `/note` delivers a note and its set: in a fixed order, resumable after a
failure or a kill, never writing a second copy of a file that already landed.
Those rules are the hardest-won code path of spec 044 (the in-flight mark, the
identical-text comparison, the never-rewrite rule for a done step) and each
was fixed after a live failure. A second copy for `/review` would drift from
the first the next time either learned something. The loop moved as it was:
`_deliver_step`, `_mark_in_flight`, `_record`, `_fail` and `_stable_block`
became `StagedDelivery.deliver_step`, `mark_in_flight`, `record`, `fail` and
the module function `stable_block`, with their bodies unchanged. `/note`'s
whole suite ran before and after the move with the same result, which is the
proof the move preserved behaviour; the refactor is its own commit so that
proof can be checked on one diff.

## WHY the Caller Supplies the Steps, the Targets and the Persist Callable

Three things differ between the two commands and nothing else does: which
steps exist and in which order, which vault path each uploaded step targets,
and how the record of done and failed steps is written to disk. So the
constructor takes exactly those: `steps` (distinct, non-empty names, in
delivery order), `targets` (step → vault path, for the steps `deliver_step`
uploads), the `meta` object with `steps_done` and `failed_step`, and `save`,
the callable that persists it. A step may be declared without a target: the
caller performs it itself (`/note`'s `source_mark` is a guarded frontmatter
merge, not an upload) and uses `record` and `fail` for the bookkeeping.

`save` is a callable rather than an imported `write_meta` because the lib must
not know where the caller's state lives. `/note` keeps `meta.json` through
`lib/note_meta.write_meta`; `/review` keeps its own. A callable also keeps
`/note`'s existing test that fails the record write by patching
`note-instructions.write_meta` valid: the caller's closure resolves that name
at call time, so the patch still reaches the loop.

The targets are a mapping, not a callable, because they are fixed for the
whole delivery: a resumed `/note` delivery runs on a frozen title and
destination (`lib/note_meta.is_frozen`), so recomputing the paths per step
could never give a different answer.

## WHY an Undeclared Step Is Refused

`steps_done` is validated on read against the caller's step set
(`lib/note_meta.read_meta` for `/note`), so a step name the loop records that
the caller never declared would make the next read reject the whole file as
stale, dropping the draft. `deliver_step`, `record`, `fail` and
`mark_in_flight` therefore raise `ValueError` for a name outside `steps`, and
the constructor refuses a `targets` key outside `steps` so a typo cannot
produce an upload no step can record. The error names the problem class only:
a step name comes from the calling script, but the same rule as everywhere in
the `/note` scripts keeps caller-supplied values out of messages that reach
the model.

The step checks themselves stay in `lib/note_meta.mark_step_done` and
`mark_step_failed`, which now take the step set as a keyword argument
(`steps=`, default `/note`'s `STEPS`). The lib calls them with its own
`steps`, so the freeze rule, the done-once-in-order rule and the
clear-the-failed-step-it-completes rule exist once, in the module that
documents them.

## WHY stable_block Is a Module Function, Not a Method

`/note` stamps the note (`_checked_note`) before it has a Kado client and
therefore before a `StagedDelivery` exists. The function needs only the meta's
`run_id` and `generated`, so it takes the meta object and no delivery. What it
does and why (a rebuilt payload must be byte-identical to the landed one, so
`updated_at` is pinned to `generated`) is in
`docs/tomo/scripts/note-instructions.md`, "WHY Every Generated File Is
Byte-Stable".

## WHY the stderr Line Carries the Caller's Script Name

The failed-step line (`<script>: delivery failed at <step> (<ErrorClass>)`)
is the line the skill mirrors quote and the privacy walk audits. It must read
as the calling script's, so the constructor takes `script` and the line is
byte-for-byte what `note-instructions.py` printed before the move.

## WHY the Rules Are Documented Where They Were Found

The behaviour of each rule (compare, never rewrite a done step, mark in flight
before the upload, fail open on nothing, normalise one trailing newline) is
explained in `docs/tomo/scripts/note-instructions.md` under "WHY a Step Is
Recorded as In Flight Before Its Upload", "WHY a Resume Compares Instead of
Skipping or Overwriting" and "WHY Some Probes Are Check-Then-Act or Fail
Open". Those sections are the record of the live failures that shaped the
rules; they stay with the script whose history they describe, and this file
only explains the extraction. A rule that changes for both callers is changed
here and its reason recorded there.
