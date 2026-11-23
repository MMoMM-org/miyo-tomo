# WHY: review-read.py

> Rationale for decisions in `tomo/scripts/review-read.py`.
> The script is the deterministic reading step of `/review` (spec 045, T3.4;
> PRD F3-AC8–F3-AC13; SDD Internal API Changes, Runtime View step 4, Error
> Handling rows for `review-read`): it reads one finished period through
> `lib/review_period.py` under `lib/review_pacer.py`, writes the stage
> (`lib/review_stage.py`, spec 047 T2.4) for the agents and the scripts after
> it, and prints the per-day report with the pacing summary.

## WHY a Script Reads the Period, Not the Model

WHY: ADR-1 and ADR-12. Which dailies exist, which linked notes could be read,
how many calls were retried and what is still missing are facts the model
must not have to establish by reading the vault itself — done that way they
differ between runs and the report cannot be tested. The script does every
Kado read, writes what it read to the stage, and prints only counts, paths,
dates and states. The model's steps come after: they read the stage files
and write `proposals.json` (`review-doc.py write` takes it from there). The reading itself lives in `lib/review_period.py` (WHY:
`docs/tomo/scripts/lib/review_period.md`) and `lib/review_day.py`; the script
owns the wiring: config and profile, the period from the argument, the
client, the pacer, the stop rules, the file and the stdout shape.

## WHY One Client, Built Before the First Call, Under One Pacer

WHY: PRD F3-AC12 asks for *how many calls were retried and how long Tomo
waited* in this run. The counters live in the client (`call_count`,
`attempt_count`, `retry_wait_s`, `pace_wait_s`; ADR-4), and they are
absolute: `ReviewPacer.summary()` reports them as they stand, the way
`inbox-triage.py` snapshots `observed_call_count` around its stages. So the
script builds exactly one `KadoClient` per run, before any call is made, and
hands it to one `ReviewPacer`; every read of the run goes through that pair,
and nothing else uses the client. A second client, or a call made before the
pacer was installed, would print a summary that covers a different set of
calls than the report next to it. The fake-vault tests pin this: the factory
is called once and `report.calls` equals the fake's own count.

## WHY the Period Comes From the Argument Under the Configured Rule

WHY: `review-session.py start` already parsed the user's request, checked
that the period is finished and printed its canonical name (`2026-W13`,
`2026-03`) with its first and last day. This script takes that name and the
kind, nothing else: no second argument grammar, no `@` notes, no "last
finished" default. The name is resolved with the configured week rule
(`review.week`), because `2026-W13` names different days under a Sunday
rule than under ISO (F2-AC9) and the read must cover the days `start`
printed. A name that does not fit the kind is a usage error (exit 2): the
skill passed the wrong thing, there is nothing for the user to decide.

WHY `--kind` still offers only the kinds `_PERIOD_RE` can parse: the
choices and the name patterns are one table, so a kind can never be accepted
by argparse and then fail in `period_from` with a KeyError. Spec 046 T1.4
added `quarter` to `lib.period.KINDS` before the period read could handle it,
and the table kept `--kind quarter` refused (exit 2) until T3.2 taught
`read_period` the quarter (ADR-6). T3.3 added `QUARTER: ^(\d{4})-Q([1-4])$`
to the table, which re-opened the kind; `2026-Q5` does not match and is
exit 2 like `2026-W60`.

WHY `period_from` goes through `period.build`: the kind → constructor
choice (`Period.week` under the rule, `Period.month`, `Period.quarter`) has
one owner in `lib/period.py`; a second `if kind == ...` chain here would be
the place a fourth kind is forgotten.

## WHY the Setup Is Required

WHY: F2-AC8 — the setup runs before the first review of a kind, so by the
time this script runs the daily sections, skip sections, task notes and the
per-day cap are confirmed values in `vault-config.yaml`
(`review_config.review_setup` → `review_day.day_settings`). Reading without
them would read every heading of every daily, which the user did not ask
for. A missing or invalid setup is therefore `status: stopped` with
`problems: [setup-missing]` / `[setup-invalid]` (plus the pointers), exit
0, nothing read, nothing written — the same words `review-doc.py` uses, so
the skill handles them once. A daily folder that neither the config nor the
profile names is `problems: [daily-not-configured]` for the same reason: a
period read without a daily folder would list the vault root.

## WHY the Daily Folder in `not_read` Stops the Run

WHY: F3-AC11/12 and the one-list rule of `lib/review_period.py`. When the
daily folder listing is turned away for the whole run and still fails in the
end pass, no daily of the period was read — `read_period` returns seven (or
thirty-one) empty days without `kado_empty` and without the access hint,
because Kado never answered. A review built from that would be a document
about nothing that looks like a quiet period. The script therefore stops
(`status: stopped`, `problems: [dailies-not-read]`), keeps `advice:
raise-kado-limit` in the printed report so the skill says why, and writes no
stage file: a review without its dailies is never built. A weekly folder
that stays in `not_read` does not stop the run — the month is still built
from the dailies and `weekly_status: not-read` says what is missing (F3-AC6,
F3-AC13).

## WHY "Nothing to Review" Writes Nothing and Says the Access Hint on the Advice Only

WHY: F3-AC9 and PRD Rule 6. `nothing_to_review` is true when no day of the
period has content beyond the template skeleton (`has_content` from
`review_day`): no stage file is written, so the document step finds
nothing to build (`review-doc.py write` → `read-missing`). A new read
discards the stage's earlier content before it calls Kado (see "WHY a New
Read Discards First"), so an empty period also leaves nothing an earlier run
stored — there is nothing to continue, and the next run reads anew (F2-AC5).
The status stays `ok`: Kado was reached and answered; it is the period that
holds nothing.

The first version appended `check-key-access` to the advice whenever nothing
was to review, "because the script cannot tell a quiet period from a denied
folder". It can: `lib/review_period.py` sets `kado_empty` and the advice
exactly when a folder listing Kado answered came back empty (`[]` or `Path
not found`), and a listing that returned notes — of other dates — is a
folder the key reaches. In the Phase 6 live walk the test vault's dailies end
2026-09-12, and a later week got the access hint although Kado had listed
the daily folder with notes; the user was told to check a key that worked.
Now the script leaves the advice to the lib: nothing is appended on
`nothing_to_review`, `check-key-access` appears only with a non-empty
`kado_empty`, and the skill says the hint only on that token (owner
decision, Phase 6). A period whose dailies were all found but empty, or
whose dates are missing from a folder that holds other dates, is reported
as quiet — the per-day report names each day with its dailies, so the user
sees which dates were found. A denied folder still gets the hint, because
Kado answers it with an empty listing and that listing is `kado_empty`.

## WHY a `stopped` Output Never Carries `nothing_to_review`

WHY: T3.8 tidy from the T3.4 code review. `nothing_to_review: true` tells
the skill "the period is empty, say so and name the access hint". A stop is
the opposite statement: the period was *not* read (the daily listing stayed
in `not_read`, Kado was unreachable, the key was refused). The first version
of the dailies-not-read stop raised `Stopped(**out)` after the empty-period
flag had been computed over seven never-read days, so that stop printed
`status: stopped` next to `nothing_to_review: true` — a consumer keying on
the flag would have read a refused listing as an empty period and told the
user to check key access. The flag is therefore computed only after the
not-read stop has been passed, so every `status: stopped` output lacks the
key (the Kado stops never had it: they stop inside `_read`, before `out`
grows). The rule is one the skill can rely on: `nothing_to_review` present
means the period was read; `stopped` means it was not.

## WHY the Section Definitions Ride in `context.json`, and Only With a Mapping

WHY: spec 046 ADR-1, PRD F1-AC1. With a confirmed mapping the model must know,
for each mapped section of the period kind's template, what to look for in
the notes it reads. Those definitions go into the file it already reads —
key `sections` of the read result, which `lib/review_stage.write` stores in
`context.json` (spec 047; before it, `read.json` / `read-index.json`) — so no
file is read for the definitions alone and no extra path has to be named in
the skill. Each entry is the SDD's
`SectionDefinition`: `key`, `heading`, `level`, `parent`, `description`,
`keywords`, `groups`, `cap`, taken from `ReviewSetup.sections` (the rows
stored for the configured template, defaults filled by
`review_config.template_rows`), in the rows' order.

`key` is the row's `id` (`s1`, `s2`, ...), copied unchanged. The id is the
row's opaque, stable name (spec 046 ADR-10): it survives a heading rename or
a correction in the setup, so the `key` the model writes into
`proposals.json` (`sections: [{key, items}]`) is the same token
`review-doc.py` looks the row up by. The name differs because the model's
files call it `key` throughout (proposals, the document parts); the value
does not.

`occurrence` and `placement` are left out: both say *where* a section's
lines land in the note, and that is the document and delivery steps' (which
read the rows from the config themselves), not the model's. Analysis rows
(placement `review`, F2-AC12) are included like every other row — the model
still writes their items under their `key`; the landing is decided later
from the config row. They carry one extra key, `analysis: true` (spec 046
T4.4), and only they do: the model writes an analysis row's items as an
overview of what the period's values show, and nothing else in the
definition tells it which row is one — the description is free text the
user may correct to anything. A flag rather than `placement` keeps where a
section lands out of the model's file; absent rather than `false` on the
other rows keeps their definitions as T3.3 wrote them.

Without a mapping (no template configured, or no rows stored for it) there
is no `sections` key at all, not an empty list: CON-2 keeps the unmapped
read as spec 045 wrote it, and the skill branches on the key being present.
The same definitions give the manifest's `sections_digest` (see "WHY a
Stored Read Continues"), so a changed mapping is a new read.

## WHY the Read Is Written as a Stage (Spec 047 T2.4, ADR-1)

WHY: spec 047 ADR-1/ADR-2. A quarter as one file was ≈ 710 KB and as three
month parts still ≈ 243 KB each — more than an agent reads in one call, and
the spec 046 walk showed the model falling back to grep on it. The read is
therefore written through `lib/review_stage.write`: one day file per day of
the period, the created notes per creation day under `growth/`, one file per
child note, `context.json`, `weeks.json` (the units the condense step
dispatches) and `manifest.json` last, every file stamped with one `read_id`.
How files are cut, encoded and loaded back is the lib's (WHY:
`docs/tomo/scripts/lib/review_stage.md`, which also carries the history of
`read.json`, the quarter's `read-index.json` split and its module
`review_read_parts`). stdout names the stage folder (`stage`), the
`read_id`, `read_at` and the number of `units`, and no longer `read_path` /
`read_parts`: no consumer reads one file any more, and a key naming a file
that does not exist would invite the skill to read it. `review-doc.py` loads
the same stage through `review_stage.load`, so the document is built from
exactly what was read. The read `report` is printed as before and stored
only in `manifest.json`, where the scripts render the not-read and top lines
from it; no agent file carries it.

## WHY a Stored Read Continues (F6-AC4, F6-AC5, ADR-3)

WHY: owner decision (PRD Rule 9). An interrupted Pass 1 — the session ended
while the agents condensed — must not cost a second read of ≈ 460 Kado calls
for a quarter. Without `--fresh`, when `manifest.json` names layout 1, the
same period and kind and the same `sections_digest` as the current setup
(`review_stage.can_continue`), the run loads the stage through
`review_stage.load` (every file checked against the manifest's `read_id`)
and prints `continued: true` with the stored `read_id`, `read_at` and
report, with no Kado call; the client is never built. `read_at` is the first
read's, so the skill can say how old the material is: a continued read does
not see vault edits made since, and Start over (`--fresh`) reads anew.

Anything else reads anew, and says why in `discarded` when a stored read
was thrown away: `fresh` (`--fresh`, the skill's Start over and its answer
to `read-stale`), `sections-changed` (the mapping changed since the read —
its proposals would be checked against definitions the stage does not hold),
`stage-invalid` (a manifest that cannot be read, of another layout or
period, or a stage file `load` refuses as invalid or stale). A pre-047 stage
(`read.json`, no manifest) is not a stored read of this layout: it is
discarded without a `discarded` key. Only the mapping invalidates a stored
read among the setup values — PRD names the mapping only; other setup edits
(daily sections, `max_chars_per_day`) apply to the next new read.

## WHY a New Read Discards First (F2-AC5, F6-AC4, ADR-10)

WHY: a new read calls `review_stage.discard` before its first Kado call,
not after a successful read. The manifest is written last, so a read that
stops (Kado unreachable, key refused, dailies not read) or finds nothing to
review leaves no manifest: nothing can continue on material of an earlier
read mixed with nothing of this one, and with `--fresh` the stored read the
user chose to drop is gone even when the new read stops. `discard` keeps
`meta.json` and `payloads.json` (Pass 2's records of a written document)
and removes everything that may hold note content, legacy `read*.json` and
temp leftovers included. The stops before the read (setup missing or
invalid, no daily folder) leave the stage untouched: they cannot tell
whether the stored read still fits, and they write nothing either.

## WHY `--measure` Writes No File and Prints Only Counts

WHY: spec 046 ADR-7, spec 047 ADR-2. The owner measures a period on the test
vault without a model run: how many Kado calls, how long the pacer waited,
how many bytes each stage file would hold. `--measure` runs the same read
through the same client and pacer and the same stop rules, then prints
`measure` — `calls`, `retried`, `waited_s`, `not_read` (a count), `bytes`
per stage file the run would write (stage-relative names, `growth/` files
and context parts included; the texts come from `review_stage.render`, the
function `write` writes, so the measured bytes are the written bytes),
`units` (`{unit, bytes}`, a unit's bytes being its day files plus its
growth files — the weight the unit budget is applied to), `over_ceiling`
(files still over 32,768 B after every cut) and `over_budget` (units over
81,920 B) — next to `status`, `stem`, `period` and `nothing_to_review`. It
neither continues nor discards a stored read and writes no file, so a
measurement never leaves content in `tomo-tmp` for a later session to pick
up and never destroys an interrupted review; the per-day report is left out
because the measurement is about size and pacing, not about which notes
exist. CON-3: a byte count is the only trace of the content; no note text
reaches stdout or stderr (the privacy assertion of the script tests runs
over the measured output too).

## WHY Reads After a Recovered Listing Run at 2 s

WHY: T3.4 decision on `ReviewPacer.finish()` (WHY:
`docs/tomo/scripts/lib/review_pacer.md`). When the end pass recovers the
daily folder listing, the whole period is read *after* the end pass, on a
Kado that refused that listing for the entire run. Those reads must be sent
at the widest spacing, which is why `finish()` no longer restores the saved
interval; the script leaves the `with ReviewPacer(...)` block only after
`read_period` returned, so the restore happens once the last read is done.

## WHY the Stage Lives Under `tomo-tmp/review/<stem>/` and stdout Holds No Text

WHY: ADR-9 (spec 045), ADR-10 (spec 047). The stage holds daily text,
tracker values, task lines and linked-note text — content. It rests where the SDD puts the stage files of a
review (`tomo-tmp/review/<stem>/`, `<stem>` = `<period-name>_review`, the
same stem `review_state` derives and `review-doc.py --stem` takes), is
written atomically file by file, and its content is discarded by
`review-doc.py write` once the document exists. stdout prints the report: paths, dates, states, counts, the advice —
and `stage`, so the skill never composes the path. stderr carries the
exception class name on an unexpected error and nothing else; the privacy
test over the script asserts that a marker from a daily's text reaches neither
stream. `--stem` is accepted (the SDD's `[--stem S]`) and refused when it
contains `/`, `\` or `..`, as `review-doc.py` refuses it. It is also refused
when it is empty, whitespace or exactly `.`: those pass the
marker check but do not name a folder *under* `--tmp` — `Path(tmp) / "."` is
`tomo-tmp/review` itself, so the stage would land beside every other
review's stage folder and `review-doc.py write --stem .` would delete it
from there. A stem is a plain folder name or it is a usage error (exit 2).
The check is `lib/review_state.safe_stem`, shared with `review-doc.py` and
`read_meta` (T3.8: the three private copies had drifted — see
docs/tomo/scripts/lib/review_state.md, "WHY One Stem Guard"); the argparse
`type=` wrapper here only turns its `False` into exit 2.

## WHY Every Actionable Outcome Exits 0

WHY: SDD Internal API Changes and the repo rule for agent-called scripts (a
red exit makes the model re-run or improvise). `status: stopped` with
`error.kind` `kado-unreachable` / `kado-auth` (F3-AC10: nothing written),
`problems`, `nothing_to_review` and the not-read stop are all exit 0; the
skill acts on the keys. Exit 2 is argparse (missing `--period`, a bad
`--kind`, a period name that does not fit the kind, an unsafe `--stem`);
exit 1 is an unexpected exception. Only `KadoAuthError` and
`KadoConnectionError` are mapped to a stop, as `lib/review_vault.py` does;
any other `KadoError` (a tool error on a configured task note, for example)
is unexpected and reaches the top-level handler, because mapping it to
`kado-unreachable` would tell the user to check a connection that works.
