# WHY: lib/review_digest.py

> Rationale for decisions in `tomo/scripts/lib/review_digest.py`.
> The module owns the file-level checks of the condensing step of `/review`
> (spec 047, T4.2; PRD F1-AC1, F6-AC1, F6-AC2; SDD ADR-4 and "Application Data
> Models"): a unit's digest and the carryover file are checked against the
> stage before anything reads them, and the `condensed.json` job state moves
> by one rule. Pure: the caller (`review-digest.py`, T4.3) reads the files and
> writes `condensed.json` and a settled `carryover.json`; this module does no
> file I/O beyond loading the two schemas, calls no Kado and no model.

## WHY a Script Checks Every Agent File Before the Proposer

ADR-4: everything a script can check about an agent's file is checked before
the opus step. A digest is a haiku agent's condensation of up to 128 KB; the
proposer then trusts it as "the unit". A digest that silently leaves out a day,
or cites a day of another unit, would turn into a document that claims to
cover the period while it does not (F1-AC1). The check cannot prove fidelity
(that the digest says what the days say) — only that it is well-formed and
stays inside its unit. Fidelity rests on the digester prompt and the owner's
quality comparison.

## WHY `days` Must Equal the Unit's Taking-Part Days, Not Just Be Inside Them

F1-AC1 asks that every read day reaches the proposer. "Inside the unit" alone
would let a digest name three of six days and pass. Equality in both
directions refuses a left-out day (the loss the spec removes) and a day beyond
it (an empty day that does not take part, or another unit's day — the digester
was not given it, so it cannot have read it). Taking part is the same
`review_weeks.takes_part` rule `review_stage` used to set the unit's
`takes_part`, fed with the day entry and that day's created-note count, so the
unit packer and the digest check never disagree about which days count.

## WHY Sources Resolve Through `review_doc.Sources`

A source is a daily of the unit, by path or stem — the exact resolution the
document check later applies to the proposer's items (`review_doc.Sources.of`
and `daily_of`). Using the one resolver means a source the digest check
accepts is one the document check can link, and a source it refuses (a W14
day in W13's digest, a created-note path, an unknown stem) would have been
refused or dropped later anyway. Every such source is `source-outside-unit`:
the agent is told where it went wrong (the pointer), not why the stem is
unknown, because the remedy is the same.

## WHY the Weekly-Note Stem Is a Source of `child_notes` Only

`child_notes` records what the unit's own weekly note says; its source is that
note's stem (path or stem, as `review_doc` resolves weeklies). Everywhere else
the weekly stem is refused: a `done` item sourced only by the weekly note
would carry no day, and today's groups require one (`check_item`, `NO_SOURCE`).
A `child_notes` entry may still name a day of the unit beside or instead of
the stem — the schema's `sources` description allows "day stems or paths of
the unit, or the unit's weekly note stem", and refusing a day there would buy
nothing. The weekly note is the first `weekly` child entry of the unit's
`week`, and only when `weeks.json` names a `weekly_note` for the unit — the
same first-entry rule `review_stage` uses to name `weekly-<week>.json`.

## WHY Growth Candidates Follow the Day-Source Rule

ADR-4 (amended 2026-11-23): a growth candidate's `sources` are creation days
and its `notes` are the created-note paths. The proposer copies the
candidate's sources into the "Vault growth" group, which `check_item` checks
like every non-child group: at least one daily of the period. So a source is
first a daily of the unit (else `source-outside-unit`), then a day on which at
least one of the candidate's own notes was created (else
`growth-source-not-created-day`) — a link to a day that did not create the
notes would point the user at the wrong day. `notes` must be among the
unit's created notes (`growth-note-outside-unit`): a note created in another
unit belongs to that unit's digest, and a path never created in the period is
invented. The created notes come from the loaded `growth.created` entries with
their `day`, the same files the digester read.

## WHY Errors Are Pointers and Codes, Never Text

Errors go back to the agent verbatim on the retry and appear in the script's
stdout. They hold a JSON pointer (indices and field names of the closed
schema) and a fixed code, never a value from the file: an echoed source or
text would put note content into the transcript twice and into the session
log (Constitution L2, metadata only). Schema errors use the form
`schema (<pointer>)` with the pointer of the offending value — for an unknown
key that is the enclosing object, so the key itself is never echoed.
File-level failures (`digest-missing`, `not-json`, `schema (…)`,
`digest-too-large`, `carryover-too-large`) have no field to point at and are
the bare code; field-level ones are `<pointer>: <code>`, the form spec 046's
section errors use.

`digest-missing` names a missing carryover file too: the SDD error list has
one missing-file code, and the carryover agent's retry prompt names the file.

## WHY the Digest Cap Measures the Compact Digest Without Its Paths

The caps bound what the opus proposer reads (`digest_cap`, 8,192 B down to
7,168 B per unit; 12,288 B for carryover). A file over its cap is retried like
any other failure.

The carryover cap counts the UTF-8 bytes of the file as written. The digest
cap (amended 2026-11-26, owner, T9.2 R1a / T9.3) counts `digest_bytes`: the
UTF-8 bytes of the digest as compact JSON (`separators=(",", ":")`, no
indentation) without the growth `notes` arrays and without every `sources`
list (entries of `done`, `open`, `notable`, `child_notes`, `themes`, section
items and growth). Why: the digester can shorten a text but never a path, and
paths are what the proposer links. In R1a (2026-W13) the digest was 9,871 B
raw / 9,404 B compact against 8,192 B, with 3,243 B of growth note paths (43
notes, 8 groups) and 3,160 B of `sources`; without them it was 2,871 B. The
quarter's per-unit cap (114,688 // 15 = 7,645 B) would have failed the same
way, so raising the constant alone was no fix. Indentation does not count
because the digester's layout is not content.

The paths left out of the measure are bounded by the data instead. Each is
already bound to the unit (`source-outside-unit`, `growth-note-outside-unit`);
two count checks add the rest:

- `source-duplicate` — a path that appears a second time in one `sources`
  list, at the pointer of the second occurrence (compared after `strip()`).
- `growth-note-duplicate` — a created note listed a second time in `growth`,
  in another group or in the same one, at the pointer of the second
  occurrence.

So the paths of a digest are at most the unit's dailies (path and stem) and
weekly note per `sources` list, and each created note of the unit once.
`digest-too-large` keeps its name and stays a bare file-level code; the size
is measured only once the text parses as JSON (`not-json` alone otherwise,
as before).

## WHY the Carryover Has Two Failure Levels

Error Handling, ADR-4: a carryover that is missing, not JSON, schema-invalid,
stale, names other notes than the found previous notes, or is over its cap is
a whole-file failure — nothing in it can be trusted, so after the retry the
carryover is `failed` and the review says the previous reviews could not be
taken into account (F6-AC2). An item-level failure (a source that is no found
previous note, a duplicate id) taints only the notes that item rests on: the
item's sources that are found notes. After the retry those notes are `failed`
and `settle_carryover` removes every item resting on one of them; the other
note's items are carried (walkthrough (d)). An invalid item resting on no
found note (all its sources unknown) fails no note and is removed alone. When
every found note failed, the carryover as a whole is `failed`.

`settle_carryover` keeps the `notes` list (it must still equal the found
notes, so a later `plan` re-validation of the settled file passes) and
recounts each note's `items`. It returns a new dict; writing it is the CLI's.

## WHY One State Model With Counted and Uncounted Checks

`condensed.json` holds per job `{state, attempts}` (carryover also `notes`).
`check` counts one attempt per job not passed: the first counted failure is
`retry` (the skill re-dispatches once with the errors), the second is
`failed`, final for the run. `plan` validates files already present without
counting (walkthrough (c)): a valid file passes without an attempt, an
invalid or missing one leaves the job as it was, so an interrupted session
neither loses a good digest nor spends a retry on a file the agent never got
to write. `passed`, `failed` and the carryover's `none` (no found previous
note, nothing to dispatch) are never moved by `advance`. Reopening a job
failed in an earlier session is `plan`'s decision (T4.3), not a transition of
this model.

Only taking-part units get a job: a unit with no day taking part has nothing
to condense and is neither dispatched nor "not condensed". `not_condensed`
names a failed unit with all its days — the days whose content did not reach
the document. `nothing_condensed` is every job failed, which stops the review
(F6-AC8); `ready` is no job pending or in retry.
