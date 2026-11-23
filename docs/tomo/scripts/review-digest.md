# WHY: review-digest.py

> Rationale for decisions in `tomo/scripts/review-digest.py` and the two agent
> file contracts it checks: `tomo/schemas/review-digest.schema.json` and
> `tomo/schemas/review-carryover.schema.json` (spec 047 ADR-4, SDD Application
> Data Models). The script itself (`plan`, `check`, `condensed.json`) is
> described here once it exists (spec 047 T4.3).

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
`notes` equal to the found previous notes, ids unique, the byte cap — is
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
script's, since it depends on the number of units.

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
