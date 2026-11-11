# WHY: lib/review_period.py

> Rationale for decisions in `tomo/scripts/lib/review_period.py`.
> The module owns reading a period for `/review` (spec 045, T3.3; PRD
> F3-AC5, F3-AC6, F3-AC7, F3-AC9; SDD Complex Logic "month reading"):
> finding the dailies of every day (flat and year folders, duplicates), the
> daily of the day after the period, the link stems a day asks for, the
> living task notes, the weekly notes a month overlaps and their day blocks,
> the two link differences, vault growth, and the per-source part of the
> report `review-read.py` prints. Reading one day is `lib/review_day.py`'s;
> parsing a weekly note is `lib/review_weekly.py`'s; reaching Kado is
> `lib/review_reader.py`'s on `lib/review_pacer.py`.

## WHY the Day Readers Are Injected as One Value

WHY: the wave-B seam. `review_day` (T3.2) and `review_period` (T3.3) were
built at the same time against a coordinator-fixed contract (`read_day`,
`yesterday_fields`, `attribute_yesterday`, later `task_note_tasks` and
`done_in_period`). `read_period` takes the five as one `DayReaders` value
and imports them from `lib.review_day` only when none is given
(`DayReaders.default()`), so its tests run on stubs and never re-implement
day reading, and one test wires the real functions through the period
reader on the fake vault to prove the seam holds. The module never looks
into a day entry beyond the SDD's `ReadResult.days[]` keys (`dailies`,
`has_content`, `partly_read`, `links`, `linked`, `problems`, `fields`,
`tasks`).

## WHY One Folder Listing Finds the Dailies (Not a Glob per Day)

WHY: the owner's vault keeps older dailies in `<folder>/<YYYY>/` and the
current ones flat; a day may exist in both (a duplicate the user wants named,
F3-AC8). One `list_dir(folder, depth=2)` shows every candidate at once — a
flat listing would miss the year folders, a glob per day would cost 32 calls
for a month and still not show which of the two paths exist without reading
both. The rendered names (`review_weekly.daily_name`) are matched against
the listing by `vault_paths.path_key` (NFC, casefold), the one comparison key
for vault paths. The weekly folder of a month is listed the same way, and
`Period.note_paths` supplies the flat and `<folder>/<week year>/` candidates
so the year rule is written once, in `lib/period.py`.

A listing that returns nothing — `Path not found` or `[]` — is `kado_empty`
with the `check-key-access` advice, never "no dailies" or "no weekly notes":
Kado answers the same for an empty folder and for one the key may not reach
(memory rule: an empty Kado search hides a denial). "No weekly notes found"
(`weekly_status: none-found`) is said only when the listing had entries and
none matched a week; a listing the pacer could not get is `not-read`.

## WHY the Day After the Period Is Read for Its Yesterday Fields Only

WHY: SDD same-day reading, step 5. `yesterday_fields` of a daily describe
day−1, so the period's last day would always be "missing" for those trackers
unless the next daily is read. The module reads that daily (both copies when
duplicated, first path wins per field), hands `yesterday_fields(text)` to
`attribute_yesterday` as `after_period`, and uses nothing else of it: no day
entry is dated after the period, its links and tasks are not counted, and
`review_habits` receives fields already attributed. When that daily is absent
or unreadable, the last day's value stays missing — the honest answer.

## WHY `read_day` Gets `reader.target`, Not `reader.note`

WHY: `read_day` calls `read_note` with the link stem as written in the daily
(`DP-2026-03-26`), not a vault path, and reports that stem in `linked[].path`
and `problems[].path`. The period reader hands it `PacedReader.target`, which
resolves the stem once per period and reads the note; the result adds
`vault_path` to every `linked` item and the report carries `{name, path,
state}` per linked note, so the document can cite a vault path (Proposals:
"sources: [vault path]") while the day entry keeps the seam's shape.

## WHY Task Notes Are Read Here and Land by Done Date

WHY: SDD same-day reading, steps 1 and 6. A living task note (`Next Todos`)
is shared by all days; `read_day` excludes its stem from the same-day targets
and the period reader reads it once (`settings.task_notes`, the paths
`day_settings` built). `task_note_tasks` labels the open ones "open today";
`done_in_period` keeps the done ones whose ✅ date lies in the period, and
each lands in the `tasks` of the day entry dated its done date — "whichever
file holds it" — so a day's tasks are complete in one place. Open tasks are
`open_tasks` at the top level, never on a day: they are open today, not open
on a past day (F3-AC3).

## WHY Week-Level Text Is Tagged With Week and Overlap

WHY: SDD month reading, step 2. Each weekly entry carries its week name and
`overlap_days` (days of the week inside the month), so the model can weigh a
one-day overlap (W09 for March) against a full week, and `duplicate` when
the week's note exists flat and in the year folder (both are read, like
dailies). The day-block and own-section rules are `review_weekly`'s.

## WHY the Link Differences Ignore Periodic Names and Same-Day Notes

WHY: SDD month reading, steps 3–4. `only_in_weekly_links` = links in the
kept weekly text − links in any daily of the month; `dailies_not_in_weekly`
= content links of a daily − links in the weekly note of its week, only for
days whose weekly note was read (a missing weekly note is reported as such,
not as 31 days of "not mentioned"). Links to daily and weekly notes
themselves are navigation — `[[2026-03-25]]`, `[[2026-W13]]` — and are left
out of both lists; a weekly's day headings link every daily by design. A
daily's `links` also hold the same-day notes it read or missed
(`DP-2026-03-23`): those are structure the weekly never mentions, so they
are not "left out" either. Targets compare by `review_weekly.link_key`.

## WHY Growth Is Two Listings, Not a History

WHY: F3-AC7 ("vault growth, not a history of edits") and Kado's filter.
Created notes come from one `listNotes` over the vault root with
`createdAfter`/`createdBefore` (Unix ms, inclusive, local-day bounds from
`period_bounds_ms`) and `fields: ["links"]`, followed across pages. MOCs come
from one listing per configured MOC folder (`concepts.map_note` through
`lib/moc_folders`), which carries every MOC's `modified` stamp: a MOC changed
in the period is one whose stamp lies within the same bounds, and a MOC
linked by a new note is one whose stem a created note's link targets name.
Kado's `links` field holds raw link text (`metadataCache` outlinks, not
resolved paths), so without the MOC listing a bare-stem link could not be
recognised as a MOC; filtering that listing by `modifiedAfter` would lose
exactly the MOCs the new notes link to. A created query that returns nothing
is `kado_empty: created` ("Kado returned none"), an empty MOC listing
`kado_empty: mocs`; no configured MOC folder means no MOC query and
`moc_folders: 0` in the report.

## WHY the Module Calls `finish()` and Re-Runs Incomplete Days

WHY: F3-AC12. A linked note read inside `read_day` cannot be patched from
outside, so the period reader collects every Kado call of the run first
(dailies, the day after, task notes, weekly notes, the growth queries), then
calls `PacedReader.finish()` once, then re-runs `read_day` for the days whose
reads had been pending — from the cache, at no call — and only then
attributes the yesterday fields, splits the weekly notes and assembles
growth. The report marks a daily or linked note `failed` when its path is in
`not_read` and `missing` otherwise. `review-read.py` therefore calls
`pacer.summary(result["not_read"])` and never `finish()` again.

## WHY `sources_from_config` Lives Here

WHY: a month read needs the weekly setup (folder, format, own sections) next
to the monthly one, the daily folder and format, and the MOC folders — five
config lookups `review_config` already owns the keys for (`folder_for`,
`configured_formats`, `get_path`). Building `PeriodSources` here keeps
`review-read.py` a CLI over the libs and keeps the key paths in one place;
the defaults (`YYYY-MM-DD`, ISO) match `vault-example.yaml`.
