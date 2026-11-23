# WHY: lib/review_previous.py

> Rationale for decisions in `tomo/scripts/lib/review_previous.py`.
> The module owns the previous review notes of a period read (spec 047, T3.1;
> ADR-5 amended v1.3; PRD F3-AC1..F3-AC5, F3-AC7..F3-AC10, F4-AC9, F6-AC7):
> which previous periods a review kind reads, whether a kind is set up,
> finding and reading each previous note through the period read's
> `PacedReader`, its one state, and its text cut at a heading boundary.
> Calling it inside the period read and writing `previous/<kind>-<name>.json`
> is `lib/review_period.py`'s and `lib/review_stage.py`'s (T3.2).

## WHY a Module of Its Own

WHY: CON-5. `lib/review_period.py` stands near the Constitution's file-size
guide; new logic goes into new modules and the period read gets call sites
only. The shape follows `lib/review_children.py` (find, prefetch before the
end pass, read after it), so a previous note is reached the way a child note
is.

## WHY These Previous Periods

WHY: F3-AC1..F3-AC3 and the SDD table "Previous periods per kind". A week
reads the previous week and the month before the month in which the WEEK
STARTS (owner decision, Rule 3): 2026-W14 starts on 2026-03-30, so its
previous month is 2026-02, not 2026-03 (the month before April). A month
reads the previous month and the quarter before its quarter; a quarter reads
the previous quarter. `Period.previous` and `Period.containing` compute
them, under the configured week rule for weeks, so a Sunday / one-day rule
gets its own previous week.

The period's own note is never among them: every previous period ends before
the period starts, so no name equals the period's name (F6-AC7). A start
over runs the same code and reads the previous notes anew; nothing is cached
across reads.

## WHY Found Only Through the Folder Listing

WHY: F3-AC4. A previous note is found the way weekly and monthly child notes
are: the setup's folder for that kind (`review_config.folder_for`, config
over profile) and its name format (`configured_formats`), the candidates of
`Period.note_paths` (flat first, then the year subfolder — the week year for
weeks), matched against one listing of the folder (depth 2). No search by
name: a note under another name, for example after the name format changed,
is `missing` rather than guessed. When both candidates exist the flat one is
read, so one note costs one read.

The listing goes through the reader's cache, so a folder that is also a child
level's folder (a month's weekly folder) is listed once for both. A week
review costs at most four calls: two listings and two reads.

## WHY Five States and Three Causes

WHY: F3-AC5, F3-AC9 and the document's top line per note (F3-AC6). Every
previous note ends in exactly one of `found`, `empty`, `missing`,
`not-set-up`, `not-read`, and the review continues in all of them — a
previous note is context, never a reason to stop. `not-read` names why,
because the user acts differently on each cause:

- `refused` — Kado denied the path. Kado's per-path denial (and its tag
  rules, Kado #81) is a tool error carrying the error code `FORBIDDEN`
  (`{"code":"FORBIDDEN",...}` in the `KadoToolError` text), not an HTTP
  status: verified in T1.4, ADR-5 v1.3. The client has no error code field,
  so the text is matched — on the quoted code `"FORBIDDEN"`, not the bare
  word, so an unrelated message that merely contains the word is not taken
  for a denial (T3.2 review). It is caught per
  previous-note call, the listing and the read each, and remembered on the
  note so the read after the end pass does not ask again (Kado says a denial
  is permanent: do not retry the same path).
- `failed` — the read was still turned away after the reader's end pass.
- `kado-none` — the folder listing came back with nothing (also "Path not
  found"). On a live Kado a denied folder lists as empty, so the line names
  the key as a possible cause (spec 045 Rule 6) instead of saying `missing`.

Not caught: a `KadoAuthError` (HTTP 401/403 means the token is wrong, so
every later call fails too; the read stops as it does today) and any other
`KadoToolError` (an unknown failure is not a denial; turning it into
`refused` would hide a bug). The period's own dailies are not read here, so
a refusal on them still stops the read.

`not-set-up` costs no Kado call and asks no question (F3-AC8): the review
runs with what the setup has; the setup flow is where a folder or format is
added.

## WHY Empty Means "Nothing Beyond the Skeleton"

WHY: F3-AC7. A previous note created from its template but never written
holds headings, prompts, empty bullets, Templater placeholders and inline
fields without values. `review_day.has_content` is the one test of "a written
line beyond the template skeleton" the daily read already uses, so the same
note is judged the same way in both places. It runs on the cleaned body: a
line of the user's, or a Tomo block of an earlier review (its items are
lines), makes the note `found`.

## WHY the Text Is the Whole Cleaned Body

WHY: ADR-5 and F4-AC5. The carryover agent decides what is still open; this
module does not pick sections. The body (frontmatter left out) loses what is
not the user's writing — query and embed fences, inline queries, embed lines,
METADATA callouts, navigation lines and thematic breaks with their trailing
navigation (the `review_md` rules) — and keeps every heading, off-limits
headings included: an off-limits heading is never a section Tomo writes into
(`review_mapping`), but its text is a valid source of what the user meant to
carry on.

The note is read as it stands now (F4-AC9): an item the user removed after
applying is not in the text, so it cannot be carried.

## WHY the Cut at a Heading Boundary

WHY: F3-AC10 and the one cutter rule (SDD Building Block View). A previous
note larger than `max_chars_per_day` is cut by `review_day.cut_at_boundary`
with one `section` unit per heading block: whole blocks while they fit, and
only a first block over the limit is cut hard. `partly_read` says so, and the
note's line says "read in part". The limit is clamped to at least 1 so a bad
value cannot make the cutter keep nothing silently.

`sections` maps a heading to its lines (text before the first heading under
`""`); a heading that repeats gets its lines appended, so nothing is lost by
the mapping.

## WHY the Kept Lines Come From `review_md.kept_lines`

WHY: one rule, one place. Dropping the lines a breaks-and-navigation mask
marks, METADATA callouts, embed lines and navigation-only lines is the same
filter a same-day linked note gets in `review_day`; both call
`review_md.kept_lines` (T3.2 review: the two copies had already drifted only
in the day arguments). A previous note passes no day: its navigation is
judged without the day's own date.

## WHY `report_rows`

WHY: CON-3 and the SDD's `report.previous`. The report printed on stdout and
stored in `manifest.json` names every previous note with kind, name, role,
path, state, cause and `partly_read`, never its text; `report_rows` drops
`sections` here, next to the rows' shape, so the period read does not need to
know which keys carry text.
