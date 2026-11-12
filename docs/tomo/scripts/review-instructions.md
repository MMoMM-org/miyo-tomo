# WHY: review-instructions.py

> Rationale for decisions in `tomo/scripts/review-instructions.py`.
> The script is Pass 2 of `/review` (spec 045 T4.2; PRD F5-AC1, F5-AC2,
> F5-AC8 to F5-AC11, F6-AC2, F6-AC4; SDD Internal API Changes, Runtime View,
> ADR-3, ADR-6, ADR-11, ADR-13): `preview` shows what an approved review
> document would land, `deliver` writes the instruction set (and a new
> periodic note) resumably, `drop` neutralises a set Tomo already wrote,
> `status` names the review's state.

## WHY `preview` and `deliver` Read the Document Fresh, Through One Reader

The document in the inbox is the source of truth (ADR-2): the user ticks,
edits and saves between the `parse` that reported counts and the delivery
that lands text. Both subcommands therefore read `<period> Review.md`
through Kado at call time and parse it in-process; nothing text-derived is
kept in `tomo-tmp` (ADR-9). They parse through `lib/review_doc_read.read_document`,
the same path `review-doc.py parse` uses, because the reader is the only
place that knows to hand `meta.json`'s `pass1_links` to the parser — without
the map every Tomo item reads as unedited and `deleted` degrades to a count.
Three private copies of "read the note, look up the map, parse" would drift
the day one of them forgot the map; a test fails when either script parses
without it.

## WHY Problems Are Split Into `problems` and `notices`

The plan builder (`lib/review_actions`) reports everything it noticed in one
list. The skill needs two answers from it: what stops the delivery (the user
must change something first) and what the user should merely know before
choosing Deliver or Abort. `lib/review_delivery.classify` is the one place
that sorts the names: `not-approved`, `approved-line-missing`,
`nothing-to-deliver`, `place-missing`, `place-too-deep`,
`user-heading-collision` and `set-exists` refuse — `deliver` writes nothing
when any is present; `heading-renamed`, `unlanded-items`,
`variant_missing`, `templater_hint` and `template_unmergeable` are notices —
shown, delivery proceeds. The plan's boolean flags join the notices as names
so the skill reads one list. A name the classification does not know is
treated as refusing: a new problem added to the builder stops a delivery
until someone decides it may proceed, never the other way round. A test
pins every name to its side.

## WHY the Second Set Is Refused Before Anything Is Built

F6-AC2 and Rule 5: one instruction set per period. `deliver` probes
`<inbox>/<stem>_instructions.json` first. A file there that this delivery
did not write — `meta.json` neither recorded `set_json` as done nor as the
step in flight — is `set-exists`: refused, nothing written. A delivery whose
`doc_mark` is recorded is complete; running `deliver` again is the same
refusal, because the only honest second answer would be "nothing to do", and
the SDD chose the refusal so the skill says the set waits for Hashi. A set
this delivery wrote and did not finish is the resume case, not a second set.

## WHY the Steps Are `note → set_json → set_md → doc_mark` (ADR-11)

The order is the order of harm. The new note (only in `new-note` mode) is
the file whose absence makes the set unapplicable, so it lands first; the
set JSON is what Hashi executes; the MD peer is what a user without Hashi
reads; the document mark is last because it is the signal "delivered" — a
mark before the set would tell the next `/review` the review is done while
nothing waits for Hashi. `lib/staged_delivery.StagedDelivery` runs the
uploaded steps with `/note`'s rules (in-flight mark before every upload,
identical text counts as done, a done step is never rewritten); the step set
and the targets are this script's. `meta.json` is the dict `review-doc.py
write` created; `lib/review_delivery.ReviewMeta` lends it the attributes the
loop records (`steps_done`, `failed_step`, `run_id`, `generated`) and the
script persists it atomically after every change.

## WHY a Done Step Is Skipped on Resume, Not Compared

`/note` compares a done step's target with the rebuilt payload because its
payloads cannot change between runs. A review's payload is a pure function
of the document (ADR-3) — and the document may change between a failed
delivery and its resume: the SDD's `doc-changed` row says "resume after
saving; payloads already written count as done" (F5-AC10). So a step in
`steps_done` is skipped; a step marked in flight (the upload may or may not
have landed) still goes through the loop's compare-or-upload. Nothing is
written twice; a landed file is never overwritten with a rebuilt one.

## WHY `generated` and `run_id` Come From `meta.json`

A resumed delivery must rebuild the set JSON, the MD peer and the new note
byte-identically, or the loop would report its own earlier upload as a
foreign file. `generated` is Pass 1's timestamp recorded by `review-doc.py
write`, `run_id` the document's; the tomo blocks pin `updated_at` to
`generated` through `staged_delivery.stable_block`. No clock is read for any
payload.

## WHY the Mark Is One Guarded `write_note`, Last

F5-AC11: the document shows in its first line that it was delivered, and its
`tomo.state` becomes `approved` (SDD ReviewDoc). Kado offers no rename, so
the first body line (the title) carries the word; `lib/review_doc.mark_delivered`
produces the marked text (idempotent). The whole text is written once with
`expected_modified` set to the `modified` the reader saw when it parsed the
document — the one guard that matters: the delivered set was built from
exactly that text. A refused guard (Kado's `CONFLICT`, or the client's
`KadoConcurrencyError`) is `doc-changed` with `failed_step: doc_mark`: the
user saved in between, the set already landed and stays valid, the resume
re-reads and marks. Any other failure on the mark is `kado-write-failed`,
resumable the same way. A document already marked (the write landed, the
record did not) is recorded without a second write.

Two writes — a guarded frontmatter merge for the state, then a note write
for the title — were rejected: the second write would need the first one's
rendering of the frontmatter, and a kill between them leaves a state the
resume has to reconstruct. One write, one guard.

## WHY `drop` Withdraws Instead of Deleting (ADR-13)

Kado offers Tomo no delete. A review dropped after a partial delivery may
have left `<stem>_instructions.json` in the inbox, and Hashi would apply it.
`drop` rewrites that file with an empty `actions` list — still a valid
instruction set, so Hashi lists and validates it and finds nothing to do —
and rewrites the MD peer to say "withdrawn — delete these files", naming
every file the delivery left (the staged new note too). `meta.json` stays,
with `withdrawn: true` and the failed step cleared, so the state function
can leave the review unlisted (SDD Complex Logic step 3; T4.3). Without a
recorded set there is nothing in the vault to neutralise and the stage
directory is simply removed.

## WHY `--place-anchor` Exists

F5-AC7: when the configured place is missing, the preview offers the note's
headings. The user picks one in the dialogue; the skill passes it as
`--place-anchor`, and the plan is built with that anchor instead of the
setup's. The setup is not changed — the next period's note may have the
configured place.

## WHY `status` Classifies Without the Set JSON Until T4.3

`status` reads the document's frontmatter and `meta.json` and asks
`lib/review_state.review_state`. Steps 3–7 of the state algorithm (the set
JSON and the probes) arrive in T4.3; until then an approved, delivered
review reads `failed-delivery` here as in the `start` listing — the SDD's
documented interim answer.

## WHY the Exit Codes and the Bare Class Name on stderr

As in `review-doc.py`: 0 for every outcome the skill can act on, 2 for a
bad invocation, 1 for an unexpected exception with its class name alone on
stderr. The delivery loop's stderr line names the step and the error class.
Nothing of the document, the section or the note reaches stdout or stderr
except through the SDD's preview field `section_md`, which the skill prints
to the user on purpose (F5-AC2).

## Kado Calls

`preview`: the document (1), the target candidates (1–2), a by-name search
when neither exists (1), the template and its variant for a new note (0–2),
the set probe (1). `deliver`: the same, then per uploaded step one probe and
one write, and the document mark (1). A week stays well under the budget.
