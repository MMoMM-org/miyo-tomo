# WHY: review-digest.py

> Rationale for decisions in `tomo/scripts/review-digest.py` and the two agent
> file contracts it checks: `tomo/schemas/review-digest.schema.json` and
> `tomo/schemas/review-carryover.schema.json` (spec 047 ADR-4, SDD Application
> Data Models). The script's two subcommands, `plan` and `check`, and the
> job state it keeps in `condensed.json` follow (spec 047 T4.3, ADR-4, ADR-8).

## WHY the Agents' Files Have Closed Schemas

WHY: ADR-4. The digesters (haiku) and the carryover agent (sonnet) write data
files, not prose; `review-digest.py check` decides per file whether it passed,
needs the one retry, or failed. A closed schema (`additionalProperties: false`
at every level) makes that first decision machine-checkable and gives the retry
an error the agent can act on: an invented field, an empty text or an entry
without sources is refused by path, never silently dropped. The schemas mirror
the closed style of `review-proposals.schema.json` (draft 2020-12).

## WHY the Schema Checks Shape and the Script Checks Meaning

WHY: one home per rule. The schema holds what a file can say on its own —
field names, types, caps, id and key patterns, enums. What needs the stage —
`read_id` equal to the read, `unit` equal to the file name, `days` equal to the
unit's taking-part days, every source inside the unit, section keys among
`context.sections`, growth notes among the unit's created notes, carryover
`notes` equal to the found previous notes, ids unique, no path twice in one
`sources` list or created note twice in `growth`, the byte cap — is
`lib/review_digest.py`'s, because a schema cannot see the stage. Neither layer
repeats the other.

## WHY Every Digest Group Is Required, Even When Empty

WHY: the walkthrough (b) digest writes every group, empty ones as `[]`. A
missing group would be ambiguous — "nothing found" or "forgot to look" — and
the proposer reads every group of every unit. Requiring all ten keys makes an
omission a retry error instead of a silent gap.

## WHY These Caps

WHY: ADR-2 and ADR-4. `done` and `open` ≤ 25, `notable`, `themes`,
`child_notes` and growth candidates ≤ 15, items per section ≤ 30, carryover
items ≤ 30. The item caps keep a digest near its byte cap (`min(8192, 114688 //
units)`) so the proposer's input stays ≤ 112 KB; the byte cap itself is the
script's, since it depends on the number of units. The byte cap measures the
compact digest without the growth `notes` and the `sources` lists, because a
digester cannot condense a path; those paths are bounded by the unit and by
`source-duplicate` / `growth-note-duplicate` instead
([lib/review_digest](lib/review_digest.md), amended 2026-11-26).

## WHY a Single-Day Theme Is Allowed in a Digest

WHY: a digest covers one unit (a week or part of one). A theme that shows on
one day of this unit may show on another day of the next; only the proposer,
which sees all units, can apply the two-day rule (`review_doc` checks it on
`proposals.json`). Refusing single-day themes in a digest would lose exactly
the cross-unit themes.

## WHY Growth Candidates Carry Their Notes

WHY: v1.2 (owner deviation after the T1.5 measurement). Vault growth no longer
travels whole to the proposer; the digester condenses each day's created
notes into candidates `{text, sources, notes}`. `notes` (1–10 created-note
paths) is what the "Vault growth" group links; `sources` (≥ 1 day stem) is the
day-source rule the growth group already meets in `review_doc.check_item`. A
candidate without notes has nothing to link and is refused.

## WHY Carryover Ids and Types Are Closed

WHY: carryover ids (`^c[0-9]{1,3}$`) are the identity the proposer cites in
`carried_ids` and `lib/review_carried.py` checks for coverage; a free-form id
could collide with a section key (`^s…$`) or be unparseable in the document
check. `type` is `open`, `intention` or `theme` because only those three can
be carried (a theme is never carried as done); `done` is not a carryover type.
Note `kind` is `week`, `month` or `quarter` — the previous-note kinds
`lib/review_previous.py` reads.

## WHY a Script Plans and Checks the Agents' Work

WHY: ADR-4, ADR-8. The skill dispatches the digesters, the carryover agent and
the proposer from the main session; nothing in the main session may read a
stage file (the spec 046 walk: a grep fallback and four self-started helpers
for $2.83). `plan` therefore hands the skill every job ready-made — the
agent, its input files as stage-relative paths, its `out` path and its byte
cap — and `check` gives a per-job verdict and the errors to pass on verbatim.
The skill decides nothing about content; it only sends what `plan` and
`check` list.

## WHY the Job State Lives in condensed.json and Only This Script Writes It

WHY: ADR-4. Attempts must survive between `check` calls (the 2nd failure is
final) and between sessions (a continued read condenses only what is not
done, F6-AC4). One owner keeps the counting in one place: `review-digest.py`
writes it, `review_stage.load` reads it (read-id-checked) for `review-doc.py`'s
`condense-incomplete` gate. It holds metadata only — unit names, states,
attempts, previous-note paths — and stays under the privacy leak guard.

## WHY plan Validates Present Files Without Counting an Attempt

WHY: walkthrough (c). After an interrupted session some digests are already
on disk. Re-dispatching them wastes a model run; counting them as an attempt
would punish the interruption. `plan` checks every present file of an open
job with `count=False`: a valid file passes at 0 attempts, an invalid one
changes nothing and its job is dispatched again.

## WHY a Unit Failed in an Earlier Session Is Offered Again

WHY: ADR-4. `failed` is final for one run, not for the read. A continued read
is a new run: `plan` resets every `failed` job (units and a whole-file failed
carryover) to `pending` with 0 attempts, so it gets one attempt and one
retry again. The cause of a failure (throttling, a model slip) is often gone
in the next session; naming a week as not condensed forever would shrink the
review for nothing. A carryover that passed with one note failed is final —
its file was already settled.

## WHY plan Deletes a Leftover proposals.json

WHY: ADR-4. The proposer is always dispatched once the jobs are ready. A
`proposals.json` on disk may predate the interruption or a refused rewrite;
reasoning about whether it still fits the digests costs more than one
proposer run. No `proposals_present` state exists.

## WHY Rounds of At Most MAX_PARALLEL (16)

WHY: ADR-8. All jobs go out in one message; a quarter is 14–16 units plus the
carryover. 16 covers the usual quarter in one round; above it `plan` splits
into a second round. If the live walk shows throttling at 16, the constant
drops to 8 — the skill text names rounds, not a number, so it does not
change.

## WHY Only Taking-Part Days Are Dispatched

WHY: F1-AC1, F1-AC6. A digest's `days` must equal its unit's taking-part days
(`review_digest.taking_part_days`); the job names exactly those days and their
day files, so the digester is never asked to condense an empty day nor
handed a day outside the period. A unit without a taking-part day has no job
at all. `growth_files` are the unit's own creation-day files from `weeks.json`.

## WHY a Digester Job Names Its `section_files`

WHY: a digest's `sections` keys must be row ids of the read's section
definitions (`unknown-section` otherwise), and the definitions live in the
context, not in the job. A bare `context.json` is no safe address: when the
context is over the file ceiling, `review_stage` spills its lists into
`context-<n>.json` parts and the head keeps only `read_id` and `period`, so on
a large quarter `sections` sits in a part and a digester reading the head sees
no keys at all. So `plan` names the file(s) that hold a non-empty `sections`
list as `section_files` (stage-relative, in the manifest's context order) when
the job's `sections` is true, else `[]`; the digester reads exactly those and
takes only `sections` from them, never a context file by fixed name. That also
keeps every other context list (open tasks, link lists, field aggregates) out
of the digesters, which need none of it. No new stage file: the parts already
are the stage's own files under the same ceiling.

## WHY the Proposer's Inputs Are Listed by the Script, in Read Order

WHY: ADR-1, ADR-8. The proposer reads `context*.json` first (period, mapping,
counts), then the passed digests in unit order, then the passed carryover,
then the child notes of the level the kind marks against (`review_period.CHILD`:
a month's weekly notes, a quarter's monthly notes; a quarter's weekly notes
already went to their unit's digester). Never `manifest.json` — the report
lives only there and is not proposer input — and never a `days/` or
`growth/` file: the digests are the whole-period material, which is what
keeps the proposer under its byte budget. `carried` is true only when the
carryover passed; a failed or absent carryover tells the proposer to carry
nothing (F6-AC2). `check` repeats the `proposer` object because only after
the last check are the passed digests known.

## WHY check Counts One Attempt per Open Job

WHY: ADR-4. Each `check` call follows one dispatch, so every job not yet
`passed` or `failed` spends one attempt: the 1st failure is `retry` with its
errors (one re-dispatch in one message), the 2nd is `failed`. A missing file
counts like an invalid one — an `Agent()` call that errors or returns without
a file is a failed attempt (throttling, SDD Error Handling).

## WHY a Failed Unit Is Named, Never Sampled

WHY: F6-AC1, F1-AC1. A unit that failed its retry appears in `not_condensed`
with all its days, which the document names at the top like days Kado did not
return; the review is built from the rest. No fallback reads the days in the
main session. Every taking-part unit failed → `stopped nothing-condensed`
naming every unit, no document, the stage kept for a later continue (F6-AC8).

## WHY check Rewrites carryover.json After a Per-Note Failure

WHY: F6-AC2, walkthrough (d). Invalid items of one previous note fail that
note only, after the retry; the other note's items are carried. The script
removes the failed note's items (and any invalid item) from `carryover.json`
(`review_digest.settle_carryover`) so the proposer and `review-doc.py` read
only what passed — no second filter downstream. A whole-file failure after
the retry is `carry_failed`; the proposer gets `carried: false`.

## WHY the Refusals Are stage-missing, stage-invalid, read-stale

WHY: one loader. Both subcommands start with `review_stage.load`; its three
exceptions map one to one to the three refusals, so the skill's handling
(run step 4, with `--fresh` for `read-stale`, once) is the same as for
`review-doc.py`. A refusal, a stop and an ok all exit 0 with one ASCII JSON
object; an unexpected exception prints only its class name (exit 1); a bad
`--stem` is a bad invocation (exit 2). No note text reaches stdout or stderr:
errors carry pointers and codes, jobs carry paths.

## WHY condensed.json Is Written Before the Settled carryover.json (Spec 047 T4.4)

WHY: crash safety (T4.3 code-review leftover). `check` used to rewrite
`carryover.json` first and `condensed.json` after it. A crash between the two
writes left the cleaned file and no record of the failed note: the next
`check` validated the cleaned file as fully passed and the note-failed marker
was lost. Now `condensed.json` (the settled job state, with `notes {path:
failed}`) is written first, then `carryover.json` is settled: the invalid
items and every item of the notes they belong to are removed. A `check` after
a crash between the writes finds the job already passed with its failed note
recorded and the uncleaned file still holding that note's invalid items, so
it settles the file again from the same check — the settling is idempotent, a
settled file has no invalid item and is left as it is. The settling reads
only the file's own check, not the recorded `notes`: a file with no invalid
item holds no failed note's items, so the record adds nothing. The rewritten
`carryover.json` goes through `review_stage_codec.encode` like every other
agent-read stage file (indented, UTF-8, one encoder).

## WHY a Growth-Only Digest Error Drops the Candidates, Not the Unit (Spec 047 T9.3, F-R3-2)

WHY: live walk R3 (2026-Q1, owner decision). Unit 2026-W04a failed twice with
only `schema (/growth)`, so its four days were never condensed and the
document named them "not condensed". The digest's `growth` candidates are
only a grouping hint: `review-doc.py write` builds the Vault growth group
from the read itself (`lib/review_growth.py`), and a note without a candidate
is still listed. Losing the whole unit for a bad hint lost content for
nothing. So when every error of a digest lies under `/growth`, `check`
rewrites the digest with `growth: []` (`review_stage_codec.encode`; ASCII
escapes only when a lone surrogate leaves UTF-8 no way to write it) and the
unit passes on that same check with `notices: ["growth-dropped"]`. No retry
is spent: the digester would be asked to fix a hint the document does not
need. A digest with any error outside `/growth` keeps the retry → failed
rule unchanged and the file untouched.

The notice is stored on the unit's job in `condensed.json` (`{state, attempts,
notices}`), so every later `check` reports it again for the passed unit; a
second `check` rewrites nothing. The skill needs no action for it: the unit
passed and is in the proposer's inputs. The digest is rewritten before
`condensed.json` is saved: a crash between the two leaves a clean digest and
an open job, which the next `check` or `plan` passes — only the notice is
lost, never content, and never a passed job whose file still holds the bad
candidates. `review_growth.candidates` reads the rewritten file and finds no
candidate of the unit. `plan` does not drop: a present invalid file stays
pending there, as before, and the next `check` decides.
