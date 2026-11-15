# WHY: lib/review_read_parts.py

> Rationale for decisions in `tomo/scripts/lib/review_read_parts.py`.
> The module owns the layout of the files a period read leaves for the model
> (spec 046, T3.4; ADR-7; SDD Quality Requirements "no `read*.json` part above
> 256 KB", Data Storage): one `read.json` for a week or a month, or
> `read-index.json` plus one `read-<YYYY-MM>.json` per month for a quarter;
> the compact encoding; writing them into the stage folder; and the loader
> that joins them back into the one result `read_period` returned.

## WHY a Quarter Is Split, and Per Month

WHY: ADR-7 and the T3.4 measurement. The model reads the file with its Read
tool, and that tool takes at most 256 KB per call. 2026-Q1 on the test
vault measured 710,106 bytes as one compact `read.json` (2026-11-15, recorded
in `plan/phase-3.md` under T3.4) — almost three times the limit. The days are
526,025 of those bytes (179,969 / 164,293 / 181,763 per month), so the month
is the natural seam: each month's days alone stay under the limit, and the
model reads a quarter as the index plus three months in turn, the way a
person reads it. A week and a month stay one `read.json` (ADR-7): a month
measured 275 KB before the compact encoding and fits after it, and splitting
it would give the skill a second branch for no gain.

## WHY Every Non-Day Entry Goes to the Month It Belongs To

WHY: the measurement's headroom. An even third of the 184,081 non-day bytes
added to March's days gives about 243 KB — under the limit, but with little
room. Putting each entry into the month it belongs to keeps a month's part
at its own size, and keeps what the model reads together (a month's days,
its weekly notes, its monthly note) in one file. The rule per key:

- `days` → the month of the entry's `date`.
- `monthly` → the entry's own `month` (the monthly note of that month).
- `weekly` → the month holding most of the week's days inside the quarter
  (the week is rebuilt from its `week` name under the configured week rule);
  on a tie, the earlier month. A week has seven days, so a tie can only come
  from a week clipped by the quarter's edge — and such a week has all its
  in-quarter days in one month — so the tie rule is there to make the choice
  total, not because a tie is expected. The majority month, not the first
  month, because a week like 2026-W05 (Jan 26 – Feb 1) is six days January
  and its day blocks are mostly January text.
- `period`, `report`, `sections`, `open_tasks`, `growth`, `not_read`,
  `only_in_monthly_links`, `dailies_not_in_monthly` → the index. None of them
  carries a date of its own: open tasks are not done, so they have no done
  date (done tasks already sit in their day's `tasks`); growth lists created
  notes and changed MOCs by path; the two mark lists are link targets without
  the day they came from; `report` describes the whole run. They are small
  next to the days, and the index is the file the model reads first, so they
  are what it should know before the months.

Because every list is kept in its own chronological order and the month a
day, a week or a monthly note goes to never decreases along that order,
concatenating the parts in the index's order gives back the original lists.
The loader relies on that and the loader-equality test proves it.

## WHY the Index Lists Its Parts, and Always All Three Months

WHY: the model and `review-doc.py write` (T4.5) must know which files belong
to the read without listing the folder — a listing would also find a part
left by an earlier run. `parts` names one file per month of the quarter in
order, also for a month with no content (its part then holds empty lists),
so the shape of a quarter's read does not depend on the vault. Every part
carries every split key the unsplit result had (`days`, `weekly`, `monthly`),
and `month`, which the loader checks against the part's name.

## WHY Writing Clears the Other Layout First, Index First, and Writes the Index Last

WHY: a stale file must never be mistaken for the current read. The stage
folder is named by the stem, and `--stem` can be reused, so a quarter run can
meet a `read.json` from an earlier unsplit run (before T3.4) and a week run
can meet a quarter's index. `write` therefore deletes every `read*.json` of
the stage first — the index before anything else — then writes the new
files, the index last. An index on disk thus always lists parts of the same
run: if the run dies between the parts and the index, no index exists and
the loader reports the read as missing instead of joining old parts. Parts
of a different quarter (`read-2025-12.json` under a reused stem) are deleted
the same way. Only names this module writes are deleted (`read.json`,
`read-index.json`, `read-YYYY-MM.json`); `proposals.json` and `meta.json`
stay.

## WHY the Loader Refuses Both Layouts at Once and Unsafe Part Names

WHY: with the write rule above, `read.json` and `read-index.json` never
stand together after a run of this code; if both are there, something else
wrote one of them and the loader cannot know which is current, so it raises
`ReadFilesInvalid` rather than guessing. A part name in the index must match
`read-YYYY-MM.json`: the index is a file on disk, and a name like
`../../config/x.json` would make the loader read outside the stage folder.
A listed part that is missing, unreadable, not an object, or whose `month`
does not match its name is `ReadFilesInvalid` too; no file at all is
`ReadFilesMissing`. The two exceptions map to `review-doc.py`'s existing
`read-invalid` and `read-missing` (T4.5).

## WHY the Encoding Lives Here

WHY: one owner for the bytes. `review-read.py --measure` reports the bytes
each file would have, and those must be the bytes `write` puts on disk; the
size test reads the written files. Keeping `encode` (compact separators,
ASCII-escaped, one trailing newline — `docs/tomo/scripts/review-read.md`
"WHY `read.json` Is Written Compact") next to `files_of` means the measured
and the written text come from the same function.

## WHY No Size Check at Run Time

WHY: the SDD names the 256 KB limit as a quality requirement measured on the
data shape, and its Technical Debt names the lever if a part is still too
large: a quarter-level character budget, an owner decision. A run-time check
could only stop the review or cut text, and both are that decision. The test
`test_review_read_parts.py` pins every part of a fixture scaled to the
measured bytes under 256,000 bytes (the conservative reading of "256 KB").
