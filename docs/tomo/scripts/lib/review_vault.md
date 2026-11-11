# WHY: lib/review_vault.py

> Rationale for decisions in `tomo/scripts/lib/review_vault.py`.
> The module owns the Kado access of `review-session.py` (spec 045, T2.2,
> ADR-9): the `Vault` wrapper that maps every Kado failure onto the SDD's
> error kinds, the `Stopped` exception the script turns into `status:
> stopped`, and the helpers that read a weekly note's evidence (its start
> date from the frontmatter, its headings, the week its day headings cover).

## WHY the Wrapper Left the Script (T2.2 review)

WHY: `review-session.py` crossed 600 lines with only `match` and
`setup-input` in it, and T2.3 adds `start`, which needs the same Kado calls
(listing, frontmatter and note reads, the folder probe) and the same date
helpers. The Constitution caps dense files at ~300–500 LOC, and a second copy
of the error mapping in `start` would let the two subcommands stop for
different reasons on the same Kado failure. The wrapper is one module so that
every subcommand stops the same way; the inference that uses it lives in
`lib/week_rule_inference.py`, because deriving a week rule is a different
responsibility from reaching the vault.

## WHY Every Kado Failure Maps to One of Three Outcomes

WHY: SDD Error Handling for `match`. The skill acts on `error.kind`:
`kado-unreachable` (no base URL, no connection, a tool error on the listing)
and `kado-auth` (a refused key) stop the preview as a whole, because evidence
gathered a moment earlier would be stale next to a dead connection. Any other
failure on a single read is a per-note answer: `frontmatter`/`note` return
None (the note counts as "no dates"), `template` returns `unreadable` and the
script adds the no-access hint. `_guard` is the one place that decides which
failure stops and which degrades, so a change to that policy is one edit.

`list_notes` returns None both for a `Path not found` and for an empty
listing: Kado answers the same way for an empty folder and for a folder the
key may not reach (memory rule: an empty Kado search hides a denial), and the
script reports `folder_listing: kado-none` for both. The listing goes two
levels deep (`depth=2`), because the owner's vault keeps older periodic
notes in year subfolders; a flat listing would miss them and the format
would be matched against the current year alone.

`folder_listed` probes a folder through `lib/vault_folder_lookup` (one
`list_dir`, the result cached per lookup) and re-raises a dead connection
that the lookup swallowed as `unanswered`: the lookup is built for the inbox
reducer, where a failed listing reads as empty; for the preview an
`unanswered` probe must still stop the run when the cause is the connection.

## WHY `journal-end-date` Counts as Start − 6

WHY: ADR-7 and F1-AC6: the week rule comes from the notes' own dates. The
owner's weekly template writes `journal-start-date` and `journal-end-date`;
older notes carry only the end. A week is seven days, so the start is the end
minus six, and the inference sees one start per note either way. Only the
first ten characters of the value are parsed, because Obsidian stores the
keys as dates but the user may have typed a datetime.

## WHY Day-Heading Dates Count Only as a Full Week

WHY: a weekly note without frontmatter dates may hold day headings for only
the days the user wrote. Taking the earliest linked date as the week's start
would read a note that starts on Wednesday as a Wednesday-first week and,
with no other dated note, propose that rule as `inferred`. The heading dates
count only when seven distinct dates span six days; anything else is "no
dates" for this note and the next note decides, or the dialogue asks.

Headings inside code fences are skipped (a `dataview` block may hold a `#`
line), the same way `lib/structural_headings` reads a note; the helper is
local because the review needs the heading levels together with their text
and no section bodies.
