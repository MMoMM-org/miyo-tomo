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

`kado_empty` and the `check-key-access` advice come from these two folder
listings ONLY. A daily folder the key cannot list leaves nothing to review,
so an empty listing there is an access problem worth a hint. The growth
queries (created notes, the MOC listings) are not: see "WHY Growth Is Two
Listings". The advice is therefore `[check-key-access]` exactly when
`kado_empty` is non-empty, and a quiet week with every daily found never
carries it.

## WHY a Month Always Says Something About Its Weekly Notes

WHY: F3-AC6 ("the report says no weekly notes were found") and the review
of T3.3. A month read without a weekly folder or weekly name format in the
config used to emit no `weekly_status` at all, which the skill could only
read as "the reader forgot" — indistinguishable from a week. A month now
always carries `weekly: []`, `weekly_notes: []` and a `weekly_status`; the
states are:

| `weekly_status` | meaning |
|---|---|
| `not-configured` | no weekly folder or format in the config; no Kado call was made for weekly notes |
| `found` | at least one weekly note of an overlapping week was read |
| `none-found` | the folder listed entries, none matched an overlapping week |
| `kado-empty` | the listing returned nothing (`kado_empty: weekly`, access hint) |
| `not-read` | the listing failed and the end pass did not recover it |

`not-configured` is distinct from `none-found` because the remedy differs:
the first asks for setup, the second for writing weekly notes. The two
link-difference lists (`only_in_weekly_links`, `dailies_not_in_weekly`) are
present only when a weekly note was read, in every state.

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
exactly the MOCs the new notes link to. No configured MOC folder means no
MOC query and `moc_folders: 0` in the report.

### WHY an Empty Growth Part Is Not an Access Problem

WHY: review of T3.3. A week in which nothing was created is the normal
case, and a MOC folder that holds no MOC is a setup oddity, not a denial
worth the `check-key-access` hint — but Kado still cannot tell "nothing"
from "not permitted" (Rule 6), so the wording stays "Kado returned none",
never "no notes were created". The two are kept apart by where they are
reported: an empty created query or MOC listing lands as a name in
`report.growth.kado_none` (`created`, `mocs`; the list is always present,
`[]` when every query answered with items), while `kado_empty` and the
advice are reserved for the daily and weekly listings. A growth query the
pacer could not get is in `not_read`, not in `kado_none`.

### WHY the MOC Listing Is Unfiltered and Uncapped (Cost)

WHY: Kado's `links` field holds raw link text, so a created note's
`[[Topic MOC]]` can be recognised as a MOC only against a list of the MOC
stems — the whole folder, every time. The cost is one `listNotes` call per
configured MOC folder per 500 MOCs (Kado's page limit; pages are followed).
Measured on the test vault (spec 045 review of T3.3): 30 notes in its one
MOC folder `Atlas/200 Maps/` out of 5447 notes in the vault → one page at
limit 500 → one call. A vault would need more than 500 MOCs in one folder
before the listing costs a second call, which is why there is no cap: a cap
would drop exactly the MOCs it did not fetch from `mocs_linked_by_new`
silently. The created query pages the same way over the notes created in
the period, which a week or month keeps small.

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
