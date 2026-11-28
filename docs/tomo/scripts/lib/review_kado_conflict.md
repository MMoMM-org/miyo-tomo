# WHY: lib/review_kado_conflict.py

> Rationale for decisions in `tomo/scripts/lib/review_kado_conflict.py`.
> The module reads a `KadoError` a `/review` delivery caught: whether Kado
> refused the write guard and why, as a name (spec 045 ADR-11, P6 live
> walk; split out of `lib/review_delivery.py` at spec 046 T6.2). It imports
> the exception classes only; no Kado call.

## WHY a Module of Its Own (spec 046 T6.2)

`review_delivery.py` stood at 348 lines against its 350-line cap and
Phase 6 still adds to the delivery. Its docs had named a resume lib as the
split; the guard reading is the cleaner seam: it depends on nothing else in
the delivery (no `ReviewMeta`, no step names, no plan) and has one caller,
`review-instructions.py` (the document mark's `doc-changed` and `drop`'s
`set-changed`). The resume record, by contrast, shares the step names and
`ReviewMeta` with the rest of `review_delivery` and is called by tests
under its current module, so moving it would have meant re-exports or an
import back into `review_delivery`. The functions and their constants
moved unchanged; the delivery report tests run unchanged.

## WHY the Code Decides, and the Message Only Names the Reason

`is_conflict` is true for the client's `KadoConcurrencyError` and for a
tool error whose payload `code` is `CONFLICT` — the JSON field, or the
exact token `"code":"CONFLICT"` (no spaces, as `JSON.stringify` emits it)
when the payload is not JSON. A message that merely says "CONFLICT" is an
ordinary write failure: an earlier version matched loose substrings
(`CONFLICT`, `mismatch`) anywhere in the text, which would report a
`VALIDATION_ERROR` as `doc-changed` and send the user into a resume that
fails the same way (docs/tomo/scripts/review-instructions.md, "WHY the
Refused Guard Is Recognised by Kado's Error Code").

`conflict_reason` reads the message only once the code said "conflict",
and returns a name, never the message: `open-unsaved` for Kado's
dirty-editor refusal (`EDITOR_PHRASE`), `changed-since-read` for the write
guard (`GUARD_PHRASE`) and for `KadoConcurrencyError`, `unknown` for any
other. Kado's message can carry the note's path; stdout carries the name
only (docs/tomo/scripts/review-instructions.md, "WHY the `doc-changed` Stop
Carries a `reason`").

## WHY `error_of` Lives Here (Spec 047 Walk F-R5-2)

`review-doc.py write` reported a failed write as `{kind, code?}`: the
exception's class name, plus Kado's code only when it is a closed uppercase
token. `review-doc.py discard` (through `lib/review_discard.py`) reports a
failed mark the same way. One function in the module that already reads
Kado's error code keeps the two outputs identical; a second copy of the
token check would drift.
