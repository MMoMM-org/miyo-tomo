# WHY: review-doc.py

> Rationale for decisions in `tomo/scripts/review-doc.py`.
> The script owns the review document of `/review` in the inbox (spec 045,
> T3.6 `write`, T3.7 `parse` and `replace`): it turns the read period and
> the model's `proposals.json` into `<period> Review.md`, writes it through
> Kado, records the Pass 1 counts and removes the content files (the
> stage of spec 047, loaded through `lib/review_stage.load`); later it
> reads the edited document back for Pass 2 and, on a confirmed start-over,
> writes a new document over its own.

## WHY One Script With Subcommands

SDD Internal API Changes names `review-doc.py write | parse | replace`. One
argparse parser with subparsers holds the three without a second script or
a second exception handler; the parser carries the shared `--config`,
`--profiles-dir` and `--tmp` options at the top level, and every subcommand
takes `--stem`, so the one `Refused` / `Stopped` handler in `main` can name
the stem for all of them.

## WHY `parse` Reads the Document From `meta.json`'s Path

`parse --stem S` has only the stem. The document's path was decided by
`write` (the inbox path of `<period> Review.md`) and recorded in the
content-free `meta.json`, so `parse` reads it there; the skill may hand in
`--doc-path` from the `start` listing instead (that listing finds documents
by frontmatter, renamed ones included). No `meta.json` and no `--doc-path`
is `not-found`, like a document that is gone from its path: the skill
offers to start over (SDD Error Handling). One Kado read, `kado-read
note`, is the whole cost; the document is parsed by `lib/review_doc_parse`.
Since T4.2 the read and the parse — path lookup, the note read, the
`pass1_links` map handed to the parser — live in `lib/review_doc_read`,
shared with `review-instructions.py preview` and `deliver`, so the three
commands cannot disagree on `edited` and `deleted`
(docs/tomo/scripts/lib/review_doc_read.md).

## WHY `parse` Prints Counts Only and Writes No File (ADR-9)

The skill needs counts, the Approved state and the warnings. stdout is the
skill's — and the transcript's — so it carries `items` as `{id, origin,
kept, edited}`, the four counts, `approved`, `nothing_to_deliver` and the
warnings, never a line of the document. `parse` writes nothing: no
`approved.json`, no change to `meta.json`. The first version wrote the
ApprovedReview record (kept items with their verbatim text) to the stage
for Phase 4 to read; it was dropped because the vault document is the
source of truth and may change between the parse that reports counts and
the delivery that lands text — the user ticks one more box, Obsidian
Sync brings a later edit — and a landed stale copy would contradict "Pass
2 lands what the user left". So Phase 4 reads the document fresh through
Kado at preview and at deliver time and calls the lib's
`ParsedDoc.approved_review()` in-process (SDD ENTITY ApprovedReview). A
second gain: `tomo-tmp` holds no extra content file beyond those ADR-9
already accounts for, and nothing has to delete it on a rewrite. One
`kado-read note` is the whole cost of a `parse`.

A mapped document (meta.json `pass1_sections`) adds `section_problems` and
`section_counts` (spec 046 T4.4). `section_problems` is
`SectionProblem.public()` per broken checkbox — the key and the line to
restore, never the document's heading text, which may hold the user's
words (CON-3); the skill names the section by the configured row's heading
and gives the restore line, so the user can repair the document without
Tomo quoting it. `section_counts` is per key `{ticked, kept, unticked,
added, empty}`, the numbers the later `section-dropped` / `section-empty`
notices are said from. An unmapped document's output has neither key, so
spec 045's stdout is unchanged.

## WHY `edited` Comes From `pass1_links` in `meta.json`

`write` stores, per Tomo item id, the ordered list of `[[stem]]` source
links as rendered (`pass1_links`) next to `pass1_counts`; `parse` compares
the item's current link stems with it, as an ordered, de-duplicated list.
The rationale — why a text digest was rejected (a templated habit line is
recoverable by enumerating its values), why presence is `in` and not
truthiness (a habit's entry is `[]`), and the accepted limit that a retyped
text keeping its links reads as unedited — is in
`docs/tomo/scripts/lib/review_doc_parse.md`. `pass1_links` also gives
`deleted` its exact id set. A `meta.json` from the digest version carries
`pass1_items` and no `pass1_links`; it is read like a `meta.json` without
the map: `edited` False everywhere, `deleted` from the `pass1_counts` sum.

## WHY `replace` Has Three Answers (`needs-confirm`, `--confirm`, `--abort`)

F6-AC1: starting over names the document that will be replaced and asks
again. `replace --stem S` alone answers `needs-confirm` with the
`doc_path`, computed the way `write` computes it (the kept stage's
period under the setup's inbox) — no Kado call, nothing written, the skill
asks the question. `replace --confirm` is `render_and_write` with
`allow_overwrite_review=True`: the same check, render and write as `write`,
from the stage and `proposals.json` that `write` kept on
`review-exists` (the default `--proposals` is the stage copy), so no
second read and no second model pass. A success is reported as `replaced`;
`meta.json` is rewritten by the same path (`steps_done` empty, fresh
counts and link stems — the reset); the stage content files go away as
after `write`; a non-Tomo file at the path is still `doc-name-taken`,
because the overwrite flag covers Tomo's own document and nothing else.

`replace --abort` is the user declining to start over, or (spec 047 ADR-10)
aborting Pass 1 after the read: the run that produced the kept stage and
`proposals.json` is over, and ADR-9 says content does not linger for a run
that is not going anywhere. `review_stage.discard` removes the whole stage
content (see below) and `proposals.json`; the document, `meta.json` and
`payloads.json` stay untouched, because the existing review goes on exactly
as it was. `--confirm` and `--abort` are
mutually exclusive on the parser so a mixed call is exit 2, not a guess.

## WHY the Script Does the Kado Calls and the Lib Does Not

`lib/review_doc.py` is pure: it checks and renders. The script owns the
probes and the write, so the lib is testable without a vault and the Kado
budget is visible in one place. A `write` costs at most five calls: the
flat target path, the year-subfolder path (skipped when the flat one
exists), a `byName` search when neither exists (the user may have moved the
note; F6 edge case "targets it where it is"), the document-name probe and
the write itself.

## WHY the Target Is Probed Before Writing

F4-AC1: the document states the target note and whether it exists or will
be created. The two candidate paths come from `Period.note_paths` (flat,
then the year subfolder, the same rule the reader uses). When neither
exists, one `byName` search for `<name>.md` finds a note the user moved;
only an exact filename match counts, and the document then names that path
as the target (`target_found_elsewhere`) instead of proposing a second note
beside it.

## WHY `write` Never Overwrites (`doc-name-taken`, `review-exists`)

The inbox is the user's folder too. The document-name probe reports three
outcomes, not a boolean: nothing at the path, a file that is not Tomo's
review (no `tomo.doc_type: review`), or Tomo's own review of this period.
Only the first is written. A non-Tomo file is the user's and gives
`doc-name-taken` (SDD Error Handling). Tomo's own review gives
`review-exists` with its `doc_path` — `write` never overwrites, because it
cannot tell a confirmed start-over from a second `/review` on the same
period; the skill asks before a start-over (F6-AC1), and only
`replace --confirm` (T3.7) writes over Tomo's document, from the kept
stage and `proposals.json`. That is why a refused `write` keeps both
files and leaves `meta.json` as it was: the confirmed second attempt needs
no second read and no second model pass.

The render-and-write path is one function with an explicit
`allow_overwrite_review` flag; the `write` subcommand always passes False.
`replace` (T3.7) reuses the same path with True instead of a second render
and write of its own, so the overwrite decision lives in one line that the
tests can read.

## WHY a Failed Write Is `stopped` With Nothing Reported

A refused or failed Kado write leaves the vault unchanged; the script says
`status: stopped`, `kado-write-failed`, names no `doc_path` and keeps
the stage, `proposals.json` and the previous `meta.json` so the skill can
retry without a second read. Only after Kado accepted the write are the
content files removed and the counts recorded.

## WHY the Stage Content and `proposals.json` Are Deleted Here (ADR-9, Spec 047 ADR-10)

Both hold journal content. The document in the inbox is the only copy the
user needs after Pass 1; the counts Pass 2 reports against (`pass1_counts`)
go to the content-free `meta.json`. Deleting after the write, not before,
means a failed write never loses the model's work.

The read is a stage of many files (spec 047 ADR-1): the success path and
`replace --abort` call `review_stage.discard`, which keeps only `meta.json`
and `payloads.json` and removes `days/`, `growth/`, `children/`,
`previous/`, `digests/`, `context*.json`, `weeks.json`, `condensed.json`,
`carryover.json`, the manifest, any legacy `read*.json` and temp leftovers;
`proposals.json` goes with it (also when `--proposals` named a file
elsewhere). The lib, not a list here, decides what is content, so a file a
later phase adds to the stage is discarded without a change to this
script. A refused or failed write deletes none of them, for the reason
above.

History: spec 046 T4.5 deleted the read files through
`lib/review_read_parts.stage_files` (`read.json`, or a quarter's
`read-index.json` and month parts by folder listing); spec 047 T2.4 deleted
that module.

## WHY the Read Comes Through `review_stage.load` (Spec 047 T2.4, ADR-1, ADR-3)

The stage splits the read into files an agent reads within its Read
limit. The script has no such limit, and its checks are about the period,
not about a file: `write`, `replace --confirm` and `replace`'s
`needs-confirm` take the read through `review_stage.load`, which rebuilds
the one merged result `read_period` returned (plus `previous`, `condensed`,
`carryover`). Every consumer of the read (`period_of`, the source rule
through `review_doc.Sources`, `review_sections.check` and `definitions`,
`sections-changed`, the habits over all days, `not_read`, `partly_read`)
therefore sees the whole period and none of them knows that files exist —
the consumers stay untouched, so the baseline e2e compares like with like
(ADR-1, option A). The not-read and top lines render from the manifest's
`report` and `not_read`, which `load` gives back as `report` / `not_read`.

`StageMissing` (no `manifest.json`, also a pre-047 stage that holds only
`read.json`) is `read-missing`: the manifest is written last, so a read
that died half-way looks like no read, and an old `read.json` is never
rendered — the next `review-read.py` run discards it. `StageStale` (a file
whose `read_id` is not the manifest's) is `read-stale`: material of two
reads is never mixed; the skill reads again with `--fresh`. `StageInvalid`
(an unreadable or malformed file, an unsafe name) keeps spec 046's
`read-invalid`. A period with one file gone is not reviewed from the others:
the document would name the period while each item resting on the missing
day would be rejected "outside the period" one by one, which reads like the
model's fault. Every refusal comes before any Kado call.

History: spec 046 T4.5 loaded `read.json` or a quarter's index joined with
its month parts through `lib/review_read_parts.load` (`ReadFilesMissing` →
`read-missing`, `ReadFilesInvalid` → `read-invalid`).

## WHY the Exit Codes and the Bare Class Name on stderr

Repo rule for agent-called scripts and ADR-9: 0 for every outcome the skill
can act on (`status`, `problems`, `error`), 2 for a bad invocation
(argparse, an unsafe `--stem`), 1 only for an unexpected exception, where
stderr carries the exception class name and nothing else — never a path, a
proposal or a line of the document. An unsafe `--stem` is what
`lib/review_state.safe_stem` refuses — empty, whitespace, `.`, `..`, or
carrying `/` or `\` — the same guard `review-read.py` and `read_meta` use;
`.` in particular would make `write` stage and delete files in
`tomo-tmp/review` itself (docs/tomo/scripts/lib/review_state.md, "WHY One
Stem Guard").

## WHY `--run-id` Is Optional

The skill may mint a run id before Pass 1 (as `/inbox` does) and pass it,
so the document, the cost log and the meta share one id; without it the
script mints one through `lib/run_id.generate`, the same format.

## WHY `write` and `replace` Run the Section Checks Before Any Kado Call (spec 046 T4.2)

`review_sections.check` is the second half of the proposals check: unknown
or duplicate keys, caps, double placement and marks are errors of the file
as a whole and come back as `proposals-invalid` with `errors`
(`<pointer>: <error>`), exactly like a schema error, so the skill's
rewrite-once loop handles both the same way. Both subcommands share
`render_and_write`, so `replace --confirm` runs every check `write` runs.
The checks run before the target probe: a refused file costs no Kado call
and leaves the stage, `proposals.json` and `meta.json` as they were.
Section items without a source are rejected one by one (`{section, index,
reason}`) and join `rejected` beside the group rejections.

## WHY `sections-changed` Refuses Instead of Guessing

The landing of a part comes from the configured row with the same id (see
docs/tomo/scripts/lib/review_sections.md, "WHY the Parts Take Their Landing
From the Config Rows"). A read whose section keys differ from the current
rows was made under another mapping; a document built from it would place
text by rows the user has since changed. The refusal names the cause, and
the answer is to read the period again.

## WHY `meta.json` Gains `pass1_sections` and Section Keys in `pass1_counts` (ADR-11, CON-3)

Pass 2 must know which section checkboxes the document was written with, so
a deleted checkbox stops delivery instead of dropping the section silently
(T4.3). `pass1_sections` is `[{key, count, empty}]` in document order: row
ids, counts and a flag — no heading, description or item text (CON-3).
`pass1_counts` carries the section keys beside the groups so its sum stays
the number of Tomo items written. Without a mapping `pass1_sections` is not
written at all, so an unmapped `meta.json` keeps spec 045's keys.

## WHY `write` Reads the Template for a New Mapped Note (spec 046 T5.2, F4-AC5)

A section whose heading a new note will lack lands in "Tomo Review", and
its landing line must say so before the user approves. For a new target
(and only with a mapping) `write` reads the configured template and its
`_tomo` variant (`review_delivery.template_paths`), chooses one by spec
045's rule (`review_new_note.template_choice`) and marks the parts
`review_section_set.routed_keys` names. That is one or two Kado reads per
new-note run; the template text goes nowhere but that call. An existing
note needs no read: its routing depends on the user's Pass 2 choices.

## WHY `write` Refuses `condense-incomplete` (Spec 047 T4.4, ADR-4, F6-AC1)

WHY: the proposer reads digests, never days (ADR-4). A document written
while a unit is still `pending` or `retry` would review a period of which
part was neither condensed nor named as not condensed: those days would
silently be missing from the proposals and from the top lines alike.
`write` and `replace --confirm` therefore refuse `condense-incomplete` when
`condensed.json` is missing or any unit in it is still `pending` or `retry`,
before the proposals are read and before any Kado call. Only
`review-digest.py` writes `condensed.json`, so this refusal is the one place
the two scripts meet: the skill answers it by running step 5 from `plan`
once. A unit that is `failed` is not incomplete — it is named as not
condensed (`review_digest.not_condensed` over the stage's `weeks.json` units,
`review_stage.units`) and its days are left out of `review_doc.Sources`, so
no item may rest on a day nobody condensed. The carryover's state is not
part of the gate: a carryover that never passed is `carry_failed`, which the
document names (ADR-12); it never holds the review back.

`replace`'s `needs-confirm` answer loads the read without this gate: it is a
question to the user, not a write.

WHY `replace --confirm` keeps `condensed.json` and `carryover.json`: a
`review-exists` refusal keeps the whole stage (the refusal comes before any
discard), so the confirmed start-over renders from the same condensed read
the refused `write` had; the stage content — these two files included — is
discarded only after a document was written.

## WHY the Proposals Schema Gains `carried` and `carried_ids` (Spec 047 T5.1, ADR-6)

WHY a separate field and not new values of `mark`: a section item may carry
both a child mark (`not_in_weekly`, …) and a carried mark (F5-AC2), and
group items have no `mark` at all (spec 046 CON-2). So group items
(`$defs/items`) and section items (`$defs/sectionItem`) both gain the same
two optional fields: `carried` (`done` | `still_open` | `not_mentioned`,
`$defs/carried`) and `carried_ids` (≥ 1 carryover id `^c[0-9]{1,3}$`,
`$defs/carriedIds`, the id pattern of `review-carryover.schema.json`).

WHY `dependentRequired` both ways: a mark without ids cannot say what it
carries (no coverage), and ids without a mark cannot say what became of
them. Either half alone is a malformed item, so the schema refuses it before
any document check runs; the file stays closed (`additionalProperties:
false`), so a misspelt field is refused too.

WHY the schema checks only the shape: whether an id exists in
`carryover.json`, is used exactly once, fits the group, or whether the
item's previous-note sources lie within its ids' sources needs the stage,
so `lib/review_carried.py` checks the document (ADR-6), each failure an
`errors` entry of `proposals-invalid`. The change is additive: every
proposals file of specs 045/046 still validates, and `schema_version` of
the wire is untouched (ADR-9).

Known limit: the id pattern is evaluated with Python `re.search`, where `$`
also matches before a trailing `\n`, so `"c1\n"` passes the schema. Such an
id matches no carryover id and is refused as `carried-unknown` by
`lib/review_carried.py`.

## WHY `write` Orders Overflow, Checks and Coverage as It Does (Spec 047 T5.4)

WHY `overflow` first (F4-AC10): a full section must not refuse a carried
item, and a rewrite to make it fit would cost a proposer run and could still
drop the item. With a passed carryover, `review_carried.overflow` moves the
last carried items of an over-cap section into the group of their mark
before any check, so `over-cap` is counted on what is left and stays a
refusal for non-carried items only (spec 046). Without a carryover nothing
moves: every carried item is then `carried-without-carryover` at the place
the proposer put it, so the error pointers name the proposer's own file.

WHY a move is written back to `proposals.json` on a `proposals-invalid`
refusal, and only there: every error pointer (`/sections/<i>/items/<j>`,
`/groups/<g>/<k>`) is computed on the proposals as checked, and the
proposer fixes a refused file in place by those pointers
(`review-proposer.md`, Rewrite rules). Checking the moved copy in memory
while the file on disk still held the original order made a pointer behind
a moved item name its neighbour: the proposer edited the wrong entry. The
move is deterministic, so persisting it loses nothing the proposer meant;
the file then equals what was checked exactly when a rewrite reads it. The
write goes to the file `write` loaded (`--proposals`, default the
stage's), atomically and in the stage's JSON encoding
(`review_stage_codec.encode`), just before the refusal is raised.
Everywhere else the file stays byte-identical: on success it is deleted
anyway, and on any other exit (`review-exists`, `doc-name-taken`,
`sections-changed`, `kado-write-failed`) the next run — `replace
--confirm`, a retry — must find the carried item where the proposer put it,
so its own overflow moves it again and `carried_moved` still reports the
move. A first version persisted the move before the checks on every path;
after `write` → `review-exists` → `replace --confirm` the second run found
nothing to move and the notice vanished.

WHY `coverage` runs once, after both checks: it is a rule over the whole
document (every carryover id exactly once over groups and sections), not
over an item. The errors are joined in one list — section errors, group
carried errors, coverage — and any of them refuses `proposals-invalid`.

WHY `carry_failed` is "a previous note was found and the carryover did not
pass" (F6-AC2): `write` refuses only open units (`condense-incomplete`), not
an open carryover, so a carryover still `pending` or `retry` at write time
is as absent as a `failed` one. With a found note, any state but `passed`
means the previous reviews were not taken into account, and the document
says so in one top line; no item can carry a mark then, because the
carryover is None and every carried item is refused. With no found note
there was nothing to take into account: no line.

WHY the new `written` keys are counts and names only: `previous`
(`[{kind, name, state, carried}]`), `not_condensed` (`[{unit, days}]`),
`carry_failed` and `carried_moved` (`[{key, to, count}]`) let the skill
report what the top lines say without reading the document. None carries a
proposal text, a note text or a path: the stdout privacy rule of this
script holds. Each key is present only when it has a fact (a previous row,
a failed unit, a failed carry, a moved item): a run without any of them
returns spec 046's result unchanged, which
`tests/test_046_t4_2_unmapped_doc_golden.py` pins.

## WHY `write` Builds the Vault Growth Group Itself (Spec 047 T9.3, F-R1-3)

Owner decision 2026-11-26: in the live runs T9.2 R1b and R1c the proposer built no growth group, and 10 of 43 created
notes appeared nowhere in the document. `write` now puts `lib/review_growth.group(read, candidates(stage, read))` in
the growth group after the checks and the habits, so the document always lists every created note of the period
(PRD F2-AC1). It runs on the stage `write` already loaded, before the stage is discarded, and prints nothing of it but
the count in `counts.growth`. A `growth` group in `proposals.json` is never read (`review_doc.MODEL_GROUPS` leaves it
out) and never refused; the reasons are in [review_growth](lib/review_growth.md).
