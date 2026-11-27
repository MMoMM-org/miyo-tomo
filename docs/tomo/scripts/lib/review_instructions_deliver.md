# WHY: lib/review_instructions_deliver.py

> Rationale for decisions in `tomo/scripts/lib/review_instructions_deliver.py`.
> Split out of `review-instructions.py` at spec 046 T6.4. Why each delivery
> rule exists (step order, resume, stored payloads, the guarded mark) is in
> `docs/tomo/scripts/review-instructions.md`; this page records only why the
> code is a lib.

## WHY the Write Side Is a Lib

The delivery steps are a unit: they need a loaded `Run` and the Kado client
it carries (`run.vault.client`) and nothing of the CLI. Moving them out took
the script from 510 lines to 242 (constitution L2: 300 to 500) without
touching a rule; the resume, overwrite and mark behaviours are the same code
under the same tests.

## WHY the Constants Are Here

`DOC_CHANGED`, `KADO_WRITE_FAILED`, `NAME_TAKEN`, `NEXT` and `SCRIPT` are the
delivery's own outputs. The script re-reads `KADO_WRITE_FAILED` from here for
`drop`, so the token has one definition.

## WHY `deliver_run` Is Split Into a Refusal Helper and the Fresh Path

`_refusal_output` holds the two refusals that precede a fresh write (a resume
that no longer matches its record, the plan's own problems), so the function
that builds and writes the payloads stays a straight line. The order is the
original's: stored-payload resume first, then the refusals, then the write.

## WHY `_overwrite_step` Reads the MD's `modified`

Kado refuses an overwrite of an existing file without `expectedModified`
(CONFLICT), and the delivery's probe reads only the set JSON, so the MD over
an earlier run's set costs one frontmatter read for its stamp
(`review_state.md_modified`) right before the write (F-R3b-2).
