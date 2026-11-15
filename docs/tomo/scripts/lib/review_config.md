# WHY: lib/review_config.py

> Rationale for decisions in `tomo/scripts/lib/review_config.py`.
> The module owns the `/review` setup (spec 045, T2.1): reading it from
> `vault-config.yaml` layered over the profile, validating it, the writer-input
> contract (`tomo/schemas/vault-config-review.schema.json`) and the mapping of
> a confirmed setup onto config keys, the heading-level rule of the place, and
> the inbox-path guard every review write goes through.

## WHY One Owner for the Key Layout

The setup lives in four config sections (`concepts.calendar.granularities`,
`naming.calendar_patterns`, `templates.mapping`, `review`) because three of
them already exist for other features and the profile already names the
weekly and monthly folders. A reader (`review-session.py start`) and a writer
(`vault-config-writer.py review`) that each spelled those paths would drift —
the same three-way drift spec 038 found between spec, schema and consumer. So
`review_setup()` reads the keys and `writer_edits()` produces the edits for
the same keys from one module; the writer applies edits, it does not know
what a review setup is.

## WHY Config Over Profile, and What "Missing" Means

`concepts.calendar.granularities.<weekly|monthly>` falls back to the profile
(`tomo/profiles/miyo.yaml` carries both folders), so a vault on the MiYo
profile needs no folder answer when the folders are where the profile says.
Nothing else falls back: the name format and the review section are the
user's confirmation and the profile has no opinion on them. A setup counts as
*present* for a kind when the config holds `naming.calendar_patterns.<kind>`
and `review.<weekly|monthly>` with a heading and a place; `review_setup()`
returns None otherwise, so `start` can report `setup: missing` and the skill
runs Feature 1 first (F2-AC8). A granularity with `enabled: false` is treated
as no folder: the user switched those notes off.

`folder_for(config, profile, granularity)` is public because the setup
preview (`review-session.py match`) resolves the same folders before any
setup exists: the weekly or monthly folder to list and the daily folder to
probe for the spelling fix. The script carried its own copy at first, and the
two had already diverged on a blank path (`path: "   "`): the copy returned
the blank string, this one returns None. One function, these semantics: a
config entry that is disabled or whose path is blank is *no folder* and hides
the profile — the user wrote something there, so the profile's folder is not
what they meant.

A present setup that is broken (a placement that is not `before`/`inside`, a
week rule outside its range, a format that `period.check_format` refuses, no
inbox) raises `SetupInvalid` with JSON pointers into the config, never a
`KeyError`: the skill shows what to fix and `/review setup` repairs it.

Defaults when a present setup leaves a key out: ISO week rule, language `en`,
no daily sections, 12000 chars per day. These mirror the SDD's example
config; the language default `frontmatter locale of the dailies` is the
setup preview's job (`match`), not the reader's.

## WHY `writer_edits` Writes Only What the Input Carries

`/review setup` "saves only what the user confirms" (F1-AC2) and "no other
setting changes" (F1-AC9). The writer input therefore names the confirmed
values and nothing else: an optional key absent from the input produces no
edit, and the daily-path correction is an edit only when the input holds
`daily_path_fix`. A `null` template or template variant removes the config
key, because a mapping that names a file the user just said is not the
template would be read back as the template on the next run — absent and
null are the same to the reader, so the key goes.

## WHY the Schema Is Validated Here, Not in the Writer

The other writer subcommands carry hand-written validators because they
predate `jsonschema` being a Tomo runtime dependency (it is in the Docker
image and the venv). The review input is nested (`place`, lists, a `kind`
that decides whether the week rule is required), and a hand-written mirror
of that would be the third copy of the contract. `input_problems()` runs the
schema and returns JSON pointers (`/place/placement`), which is what the
setup dialogue needs to ask again (SDD Error Handling: "refused with
pointers"). The name format is checked in the same call through
`period.check_format` under the input's own week rule, so a format that is
schema-valid text but unusable as a name (`YYYY-[W]WW`, a `/` literal) is
refused before anything is written, with pointer `/format` and the problem
kinds.

## WHY `place_level` Is the Only Owner of the Level Rule

Hashi ends a section at the next heading of the same or higher level, so a
review heading at the wrong level swallows the user's next section and a
rerun's `replace_section` deletes it (SDD Implementation Examples). The rule —
`before` places the heading at the anchor's level, `inside` one level deeper,
`after` is never accepted, the review heading may not exceed level 5 (its
groups stay ≤ 6) — is three lines, and three copies of three lines would
drift. The cap is 5, not 6, because the review section's group headings
(`Erledigt`, `Offen`, …) sit one level below the review heading and must
stay valid Markdown headings; a review heading at level 6 would put its
groups at level 7, which Markdown renders as literal `#######` text.
`review_actions` (planned, Phase 4 T4.1) calls it and reports a refusal as
`place-too-deep`; the setup schema refuses `after` at input time so the
question never reaches delivery. `ReviewSetup.place_level(target_headings)` finds the anchor among
the target's headings case-sensitively, because Hashi matches headings
case-sensitively and the first match wins; a missing anchor raises
`PlaceMissing`, which the preview reports as `place-missing` with the
headings it did find (F5-AC7).

## WHY `inbox_path` Refuses by Shape and by Result

Every review write goes to the inbox (CON-security: inbox-only writes
enforced in code). The name is refused when it contains `/`, `\` or `..`, and
the joined path is normalised and must still start with the inbox folder.
Both checks, because each alone has a hole: a name of `.` passes the
character check and resolves to the folder itself; a path check alone would
accept `sub/..name` whose meaning depends on the resolver. An empty inbox
configuration is refused too — joining onto `""` would put the file at the
vault root.

The inbox folder is normalised (`posixpath.normpath`) *before* the
comparison, and the joined path is compared against that normalised base.
The first version normalised only the joined path, so an inbox configured
as `./Inbox` or `a/./b` — both legitimate spellings of a folder inside the
vault — produced `Inbox/x.md` and `a/b/x.md`, which no longer started with
the raw base, and every review write was refused as "outside the inbox".
`..` and `\` are still refused in the folder itself before normalising, so a
base that climbs out of the vault never reaches the comparison; a base that
normalises to `.` (the vault root) is refused as not configured.

## WHY the Session Shapes Live Here (T2.3)

`review-session.py` passed the Constitution's ~500-line mark once `start`
joined `match` and `setup-input`. The helpers that only turn the config into
a shape — `configured_formats` (`naming.calendar_patterns` per kind, the
`formats` both `period.parse_args` and `review_state.open_reviews` take),
`inbox_folder` (config over profile, the lookup `review_setup` already made
inline), `current_setup` (the saved setup of one kind in the proposal's
shape, None without one, `{"invalid": [pointers]}` when broken) and
`request_dict` (the SDD request shape plus the period's first and last day)
— need neither Kado nor argparse, so they belong with the setup model they
read rather than with the subcommands that print them. Moving them keeps the
script to its wiring and lets the next reader of the setup (`review-read`,
planned for Phase 3; `review-instructions`, planned for Phase 4) take the
same shapes from one place. `inbox_folder` replaced the inline lookup in `review_setup` so the two
cannot disagree on what "no inbox" means. Behaviour is unchanged; the
script's tests still cover every shape through `start`.

## WHY Tracker Types Are Read, Not Stored

F8 sums tracker fields by their configured type. The types already live in
`trackers.daily_note_trackers` (`today_fields`, `yesterday_fields`) and
`trackers.end_of_day_fields`, written by the trackers wizard; copying them
into `review:` would be a second place to keep in step. `tracker_types()`
returns `{name: type}` over all three lists; a type change the setup proposes
goes through the existing `trackers` writer subcommand (SDD Data Storage).

## WHY `GRANULARITY` Names the Quarter Before Its Setup Exists

`GRANULARITY` maps a period kind to its config key (`weekly`, `monthly`,
`quarterly`) and every reader iterates `period.KINDS` through it
(`configured_formats`, `setup_present`, the `start` listing). When the quarter
joined `KINDS` (spec 046 T1.4) the mapping had to name it in the same change,
or every `review-session.py start` would fail with a `KeyError` before the
quarterly setup itself is implemented (T1.3). With the key named and nothing
configured under it, the quarter reads as `missing`, which is exactly what it
is.

## WHY Only the Configured Template's Rows Are Read (spec 046, T1.3)

`review.<g>.sections` and `review.<g>.off_limits` are mappings keyed by
template name. `review_setup` reads the entry of the template
`templates.mapping.<g>` names and nothing else: the rows of the work
variant, or of a template the user switched away from, never apply to the
configured one (PRD F2-AC8), and they stay stored so switching back finds
them. Without a configured template the setup has no rows — spec 045
behaviour. Rows of another template are not validated either: a broken
row there cannot block a review that does not use it.

## WHY Invalid Rows Are Pointers, Checked Against the Writer's Schema

The rows are the user's confirmed text and are written only through the
writer, but the file can be edited by hand. A present row the reader
cannot use raises `SetupInvalid` with pointers into the config
(`/review/weekly/sections/t_week_privat.md/0/cap`, the template name
escaped per RFC 6901), like every other broken setup key. The reader does
not keep its own copy of the row rules: it validates the rows by wrapping
them in a synthetic writer input (`kind`, `template`, the rows) and keeping
only the schema errors under the rows' key, so the writer and the reader
cannot disagree on what a valid row is. The same duplicate check —
heading key twice, an id twice — runs for the writer input
(`input_problems`) and for the stored rows: a duplicate key would map one
template heading twice, a duplicate id would make two sections share one
pair of markers (ADR-10).

## WHY Row Defaults Are Filled at Read Time

The writer stores a row as the user confirmed it (F2-AC10): an omitted
`cap`, `keywords` or `groups` stays omitted in the file. `ReviewSetup.
sections` fills `cap` 8, `keywords` [] and `groups` [] on a copy, so every
later reader (`review-read`, the proposal check) sees one shape and none of
them spells the default again.

## WHY `writer_edits` Writes One Template's Entry

`sections` and `off_limits` edit `review.<g>.sections.<template>` and
`review.<g>.off_limits.<template>` — the one leaf under the named
template — never the whole `sections` mapping. Saving the mapping of one
template therefore cannot change another's (F2-AC10, "no other setup value
changes"), and an empty list removes only that template's entry (T1.1:
`[]` removes a key).
