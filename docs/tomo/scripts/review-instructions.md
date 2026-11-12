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
`user-heading-collision`, `set-exists` and `already-applied` refuse —
`deliver` writes nothing when any is present (`already-applied` is `drop`'s
refusal, see below; it sits in the same tuple so the one pin test covers
it); `heading-renamed`, `unlanded-items`,
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
step in flight — is `set-exists` while any action in it waits: refused,
nothing written. A delivery whose
`doc_mark` is recorded is complete; running `deliver` again is the same
refusal, because the only honest second answer would be "nothing to do", and
the SDD chose the refusal so the skill says the set waits for Hashi. A set
this delivery wrote and did not finish is the resume case, not a second set.
The one set that is not a second set is a finished one — every action
applied — of an earlier run of the period; see the next section.

### WHY a Fully Applied Set Is Written Over, Not Refused (T6.1 fix round)

Owner decision 2026-11-12. A rerun of a period (F6-AC3: `review-doc.py
replace --confirm`, a fresh document, a fresh `meta.json` with no step done)
finds the first run's set still in the inbox, because Kado offers Tomo no
delete and Hashi leaves the applied set where it is. Refusing `set-exists`
there sent the user to delete two files by hand before the rerun could land
— the e2e walk of T6.1 had to script that deletion, which is how the gap
was found. Once *every* action in the set carries `applied: true`
(`review_state.all_applied`; Hashi writes the flag atomically and
monotonically, ADR-6) the set is history: the vault holds its effect and
nothing of it waits. So `deliver` writes the new set JSON and MD over it.
The set JSON write is guarded by the `modified` the probe read
(`review_state.read_set`, the same read `drop` guards with): a set Hashi
rewrote between read and write — the one way it could stop being fully
applied — refuses with Kado's `CONFLICT`, reported as `kado-write-failed`
(resumable: the resume reads the stamp afresh; no new problem name, so the
skill's step 8 lines hold). The MD peer is Tomo's own file, written plain,
as `drop` writes its withdrawn MD. The overwrite steps go through the same
`StagedDelivery` records (`mark_in_flight`, `record`, `fail`) as an upload,
so a failure among them resumes like any other; the loop's own
`deliver_step` is not used for them because its rule "other text at the
path is `name-taken`" is right for a user's note and wrong here.
`meta.json` keeps `set_replaced: true` from the first write on, because a
resume must also overwrite the old MD after the new set JSON landed
(`set_json` done, `set_md` not) — the probe then reads the new, unapplied
set and could not tell a rerun from a fresh delivery. On that resume the
set JSON step compares the set at the path, its `applied` flags stripped,
with the rebuilt payload: Tomo's own landed set is recorded done, never
rewritten (a rewrite would clear a flag Hashi may have set meanwhile).

A set with no action applied, or with some, stays `set-exists`: the
listing shows the stem as `delivered`, the skill says the set waits for
Hashi. A withdrawn set (`meta.withdrawn`) stays `set-exists` as before; it
is never fully applied (its `actions` list is empty, and `all_applied`
needs at least one action). After the rerun's delivery the new set waits
unapplied, so the stem reads `delivered`, then `applied` once Hashi applied
it; between `replace --confirm` and the delivery a fresh record over the
old applied set reads `open` (docs/tomo/scripts/lib/review_state.md, "WHY a
Fresh Record Over a Fully Applied Set Reads `open`").

### WHY an Emptied Set on a Begun Stem Is `set-withdrawn`, Not Resumed (P5)

Owner decision, spec 045 Phase 5 cleanup. `drop` writes the empty set
before the MD and marks `meta.json` last, so a drop whose MD write failed
leaves a begun stem with an emptied set and an unmarked meta; the listing
offers it again as `failed-delivery` (docs/tomo/scripts/lib/review_state.md,
"WHY an Emptied Set Withdraws Only Without a Begun Record"), and Resume runs
`deliver`. On that set `deliver` misbehaves twice over: a delivery stopped
before `doc_mark` has `set_json` in `steps_done`, so the loop skips the set
as done, writes the MD with the actions and marks the document — the inbox
then holds an empty set beside an MD that lists actions, and the state
function reads the empty set as `applied`; a delivery whose `set_json` was
in flight finds other text at the path and refuses `name-taken`, naming the
set JSON as if it were the user's note. The probe of the set is therefore a
read (`review_state.read_set`, the same reader `drop` and `stem_state` use;
one call, as `path_exists` was), and a set with an empty `actions` list on a
stem whose delivery began and whose meta is not marked withdrawn refuses
`set-withdrawn` before `set-exists` is considered: nothing written, and the
skill offers Drop, which completes the withdrawal. Once the mark is written
the drop is finished and a later `deliver` stays `set-exists`, as the SDD
says for a withdrawn review — the skill then says the set waits, which is
wrong for an emptied set, but the review is unlisted and no step leads there. A begun delivery never writes an empty set itself
(`nothing-to-deliver` refuses before a set is built), so on a begun stem the
signature is `drop`'s. On a stem whose delivery never began the same file
stays `set-exists` — a file this delivery did not write, whatever it holds.

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
exactly that text. A refused guard is `doc-changed` with `failed_step:
doc_mark`: the user saved in between, the set already landed and stays
valid, the resume re-reads and marks. Any other failure on the mark is
`kado-write-failed`, resumable the same way. A document already marked (the
write landed, the record did not) is recorded without a second write.

### WHY the Refused Guard Is Recognised by Kado's Error Code

`KadoClient.write_note` never raises `KadoConcurrencyError` — only
`write_frontmatter` does. A refused guard on a note write arrives as a plain
`KadoToolError` whose text is the client's `kado-write returned an error: `
followed by Kado's MCP error payload, a JSON object with `code` and
`message`. The live refusal of the write guard is, verbatim:

```
kado-write returned an error: {"code":"CONFLICT","message":"File was updated in the background. Re-read before retrying."}
```

Kado sends `code: CONFLICT` for two causes: the write guard (the file's
`modified` is not the `expectedModified` the write carried) and the refusal
to write a note that is open and dirty in an editor. Both mean the same
thing for the review — the user is or was editing the document, so the
delivered text is not the text in the vault; the honest next step for both
is "save, then resume", which re-reads and marks. Both therefore map to
`doc-changed`; the script does not tell them apart.

The classification parses the JSON after the client's prefix and compares
`code` with `CONFLICT`. When the payload is not parseable JSON (Kado wraps
it in prose one day), the exact token `"code":"CONFLICT"` is the fallback —
the token `JSON.stringify` emits, no spaces. An earlier version matched the
loose substrings `CONFLICT` or `mismatch` anywhere in the text: `mismatch`
appears nowhere on Kado's note-write path, but it does appear in other
error messages (a `VALIDATION_ERROR` whose message says what mismatched),
and such a failure would have been reported as `doc-changed` — telling the
user to save and resume when the resume would fail the same way. The
`KadoConcurrencyError` branch stays, so a client that one day raises it on
note writes too is classified the same.

### WHY the Kado Stop Mapping Is One Helper

The reads of this script (the target note, the set probe, the by-name
search) and the shared document reader all stop a run the same way: a
refused key is `kado-auth`, any other Kado failure `kado-unreachable`
(SDD Error Handling). Four hand-written copies of the same two `except`
clauses would let one of them stop for a different reason the day someone
edits three; `lib/review_vault.kado_stops` is the one context manager they
share, next to `Stopped` itself. A `KadoNotFoundError`
that is an answer (nothing at the path) is caught inside the block by the
caller, because only the caller knows whether "not found" is an answer or
a failure.

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
can leave the review unlisted (SDD Complex Logic step 3; T4.3) — the meta
mark is what withdraws; a drop that failed before it is listed again by the
next `/review` (P5, docs/tomo/scripts/lib/review_state.md, "WHY an Emptied
Set Withdraws Only Without a Begun Record"). A delivery that never began (no
step done, none in flight) left nothing in the vault to neutralise, and the
stage directory is simply removed.

### WHY Any Started Delivery Is Withdrawn, Not Only One With a Set

The first step in `new-note` mode is the note. A delivery killed after the
note landed — before `set_json` was recorded, or before it was even marked
in flight — leaves `<inbox>/<period>.md` in the inbox with nothing in
`meta.json` beyond `note` done or in flight. An earlier version withdrew
only when `set_json` was done or in flight; for this case it removed the
stage and answered `dropped`, and the new note stayed in the inbox with
nothing telling the user. `drop` now withdraws whenever `meta.started()`:
the same withdrawn set JSON and MD are written and the MD names the note
with the set's files, so the user is told what to delete through the one
channel the SDD gives `drop`. Returning `dropped` with the note's path was
the alternative; it would have added a second shape for the skill to
handle, while the withdrawn path already exists and names every file the
delivery left. The cost is two inbox files for a delivery whose first write
never landed (a Kado error on the note, nothing in the vault) — the same
cost the design already accepts for a `set_json` in flight; `meta.json`
cannot tell a failed first write from a kill after it landed, and probing
the note would read a denied path as absent (memory rule: an empty Kado
answer hides a denial).

### WHY `drop` Reads the Set First and Refuses on Any `applied` Action

Coordinator decision 2026-11-12 (T4.4 fix round). A delivery that reached
`doc_mark` is a set Hashi may already have executed, in full or in part:
Hashi's `executor/jsonAppliedWriter.ts` rewrites `<stem>_instructions.json`
with `applied: true` per action it ran (monotonic, batched once per source
after the run). An earlier `drop` rewrote the set without looking — the
applied record was erased, `status` read the review as withdrawn while its
section sat in the periodic note (or its note had been moved), and the
withdrawn MD told the user to delete files Hashi had already moved. `drop`
now reads the set JSON at its path through Kado before it writes. One
action with `applied: true` is enough to refuse (`already-applied`): there
is no partial withdrawal — the actions Hashi ran cannot be undone by a set
with nothing in it, and a set that lists only the unapplied remainder as
withdrawn would still erase the record of what ran. The stage, the meta and
both inbox files stay as they are, and the answer names no content; the
user resolves the applied review by hand (the `applied` state offers that).

The set is read through `lib/review_state.read_set`, the same reader
`stem_state` uses, made public for this — a second parser would decide
"applied" differently one day. Absent (`KadoNotFoundError`) means nothing
landed at the path — a delivery killed before `set_json`, or a set the user
already deleted — and the withdrawal proceeds as before. Any other Kado
failure on that read stops the run through `kado_stops` (`kado-auth`,
`kado-unreachable`), never as absent: a key that cannot read the inbox would
otherwise withdraw over a set it was not allowed to see (memory rule: an
empty Kado answer hides a denial).

### WHY an Unreadable Set Still Withdraws

A file at the set path that is not JSON, not an object, or whose `actions`
is not a list of objects is not proof that Hashi applied anything — Hashi's
writer keeps the set a valid instruction set, so a broken file was broken
by something else. Refusing would leave a review nobody can close: `status`
reads such a set as `delivered` (docs/tomo/scripts/lib/review_state.md,
"WHY an Unreadable Set JSON Reads as `delivered`"), Hashi's validator
rejects it, and `drop` would be the only way out. So `drop` proceeds as it
did before this fix: the withdrawn set replaces the unreadable file. The
guard below still applies, so a file that changed under the read is not
overwritten blind.

### WHY the Set Write Is Guarded (`set-changed`)

Hashi may write `applied` between `drop`'s read and its write — the user
runs Hashi and `/review` in the same minute. The set JSON is therefore
written with `expected_modified` set to the `modified` the read returned,
the same guard the document mark uses. A refused guard (Kado's `CONFLICT`,
recognised by `_is_conflict` exactly as on the mark) is `set-changed`:
`status: stopped`, nothing written, the stage and the meta unchanged,
resumable by running `drop` again — the second run reads the set as it is
now and refuses or withdraws on what it finds. Any other failure stays
`kado-write-failed`. The MD peer is not guarded: `drop` holds no `modified`
for it, and a read only for the guard would cost a call for a file Hashi
never rewrites (its peer sync ticks boxes through Obsidian, not the set
path). A set absent on the read is written without a guard, as before.

## WHY `--place-anchor` Exists

F5-AC7: when the configured place is missing, the preview offers the note's
headings. The user picks one in the dialogue; the skill passes it as
`--place-anchor`, and the plan is built with that anchor instead of the
setup's. The setup is not changed — the next period's note may have the
configured place.

## WHY `status` Goes Through `review_state.stem_state` (T4.3)

`status` reads `meta.json` for the document's path, the document's
frontmatter through Kado, resolves the inbox (config over profile — the
only part of the setup it needs, so an incomplete setup does not hide the
state) and hands the five inputs to `lib/review_state.stem_state`, the one
function that reads the set JSON and runs the probes (ADR-6). `start` hands
the same function the same inputs per listed document, so the two cannot
disagree about a stem; a test records both scripts' calls and compares
them. `status` prints the state as classified — `applied` stays `applied`
here even after `start` reported it once, because the "offered once" rule
belongs to the listing, not to a direct question — and `state: null` for a
withdrawn review, which the listing never shows. An inbox that nothing
names is `inbox-not-configured`, as in `preview`.

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
the set read (1; its `actions` decide `set-withdrawn`). `deliver`: the same, then per uploaded step one probe and
one write, and the document mark (1). `drop` on a begun delivery: the set
JSON (1), then the two writes. `status`: the frontmatter (1), the set
JSON for an approved document (1), then for a waiting set one probe (insert
or replace: the target) or one to two (move: the source, then the
destination only while the source exists). A week stays well under the
budget.
