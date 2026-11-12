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
`SET_EXISTS` for the same reason.

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

## WHY the Withdrawn Set Is Built From `meta.json`

`drop` may run on a document that is no longer readable or approved; the
withdrawn set must not depend on the plan. `withdrawn_set` needs only the
stem, `generated` and the profile — the envelope with an empty `actions`
list — and `withdrawn_md` the list of files the delivery left. Both validate
like any instruction set, so Hashi lists them and finds nothing to apply
(ADR-13).
