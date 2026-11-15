# WHY: review-read.py

> Rationale for decisions in `tomo/scripts/review-read.py`.
> The script is the deterministic reading step of `/review` (spec 045, T3.4;
> PRD F3-AC8–F3-AC13; SDD Internal API Changes, Runtime View step 4, Error
> Handling rows for `review-read`): it reads one finished period through
> `lib/review_period.py` under `lib/review_pacer.py`, writes `read.json` for
> the model and prints the per-day report with the pacing summary.

## WHY a Script Reads the Period, Not the Model

WHY: ADR-1 and ADR-12. Which dailies exist, which linked notes could be read,
how many calls were retried and what is still missing are facts the model
must not have to establish by reading the vault itself — done that way they
differ between runs and the report cannot be tested. The script does every
Kado read, writes what it read to `read.json`, and prints only counts, paths,
dates and states. The model's one creative step comes after: it reads
`read.json` and writes `proposals.json` (`review-doc.py write` takes it from
there). The reading itself lives in `lib/review_period.py` (WHY:
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
`read.json`: a review without its dailies is never built. A weekly folder
that stays in `not_read` does not stop the run — the month is still built
from the dailies and `weekly_status: not-read` says what is missing (F3-AC6,
F3-AC13).

## WHY "Nothing to Review" Writes Nothing and Says the Access Hint on the Advice Only

WHY: F3-AC9 and PRD Rule 6. `nothing_to_review` is true when no day of the
period has content beyond the template skeleton (`has_content` from
`review_day`): no `read.json` is written, so on a fresh stem the document
step finds nothing to build (`review-doc.py write` → `read-missing`). Only a run that writes
read files clears the stage's earlier `read*.json` first
(`lib/review_read_parts.write`); this run writes none, so a file an earlier
run left under a reused `--stem` stays — the skill stops on
`nothing_to_review` and never calls `review-doc.py`, so it is not read. The status stays `ok`:
Kado was reached and answered; it is the period that holds nothing.

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

## WHY the Section Definitions Ride in `read.json`, and Only With a Mapping

WHY: spec 046 ADR-1, PRD F1-AC1. With a confirmed mapping the model must know,
for each mapped section of the period kind's template, what to look for in
the notes it reads. Those definitions go into the file it already reads —
key `sections` of `read.json` for a week or a month, of `read-index.json`
for a quarter (see "WHY a Quarter Writes `read-index.json` and One Part per
Month") — so no file is read for the definitions alone and no extra path has
to be named in the skill. Each entry is the SDD's
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
still writes their items under their `key`; only the landing differs, and
that is decided later from the config row.

Without a mapping (no template configured, or no rows stored for it) there
is no `sections` key at all, not an empty list: CON-2 keeps the unmapped
`read.json` as spec 045 wrote it, and the skill branches on the key being
present.

## WHY `read.json` Is Written Compact

WHY: spec 046 ADR-7 and CON-2. The measured March `read.json` was 274.7 KB,
over what the model's Read tool takes in one call; `indent=2` spent a large
share of that on indentation and newlines that carry nothing. Every
`read*.json` is therefore written with `separators=(",", ":")`, ASCII-escaped
as before (the encoder is `lib/review_read_parts.encode`, shared by the
write and `--measure`). This is one of the five intended differences CON-2 lets reach the
unmapped path: without a mapping the parsed content is unchanged — the
script test pins that the parsed file equals the T3.1 golden recording of
`read_period` (plus the pacing counters this script always merged into the
report) and that the bytes are the compact dump of it. The consumers parse
the file with `json.loads`/`json.load` (`review-doc.py`), so the encoding is
invisible to them.

## WHY a Quarter Writes `read-index.json` and One Part per Month

WHY: spec 046 ADR-7, T3.4. 2026-Q1 measured 710,106 bytes as one compact
`read.json`, almost three times what the model's Read tool takes. A quarter
run therefore writes `read-index.json` (period, report, sections, the part
list and the small lists) and `read-<YYYY-MM>.json` per month (that month's
days, weekly notes and monthly note); a week and a month still write one
`read.json`. Which entry goes to which file, the write order and the loader
that joins the parts back are `lib/review_read_parts.py`'s (WHY:
`docs/tomo/scripts/lib/review_read_parts.md`), so `review-doc.py` (T4.5)
loads through the same module that wrote. stdout says where they are:
`read_path` is the index for a quarter (the file the model reads first) and
`read_parts` lists the month parts in order, so the skill never composes a
path; a week or a month has no `read_parts` key, so its stdout is unchanged.
The week rule is handed to the split because a weekly note's month is
computed from its week's days under that rule.

## WHY `--measure` Writes No File and Prints Only Counts

WHY: spec 046 ADR-7. Before the quarter's read was split per month (T3.4),
the owner measured 2026-Q1 on the test vault without a model run: how many
Kado calls, how long the pacer waited, how many bytes the file would hold.
`--measure` runs the same read through the same client and pacer and the
same stop rules, then prints `measure` — `calls`, `retried`, `waited_s`,
`not_read` (a count), `bytes` per file the run would write (`read.json`, or
`read-index.json` and each `read-<YYYY-MM>.json` for a quarter — the text
`lib/review_read_parts.files_of` builds for the write, so the measured bytes
are the written bytes) and `day_bytes` per month (the compact bytes of the
month's `days` entries; kept after the split because it shows how much of a
part is days and how much is the month's other entries) — next to
`status`, `stem`, `period` and `nothing_to_review`. It writes no file, so a
measurement never leaves content in `tomo-tmp` for a later session to pick
up, and the per-day report is left out because the measurement is about
size and pacing, not about which notes exist. CON-3: a byte count is the
only trace of the content; no note text reaches stdout or stderr (the
privacy assertion of the script tests runs over the measured output too).

## WHY Reads After a Recovered Listing Run at 2 s

WHY: T3.4 decision on `ReviewPacer.finish()` (WHY:
`docs/tomo/scripts/lib/review_pacer.md`). When the end pass recovers the
daily folder listing, the whole period is read *after* the end pass, on a
Kado that refused that listing for the entire run. Those reads must be sent
at the widest spacing, which is why `finish()` no longer restores the saved
interval; the script leaves the `with ReviewPacer(...)` block only after
`read_period` returned, so the restore happens once the last read is done.

## WHY `read.json` Lives Under `tomo-tmp/review/<stem>/` and stdout Holds No Text

WHY: ADR-9. `read.json` holds daily text, tracker values, task lines and
linked-note text — content. It rests where the SDD puts the stage files of a
review (`tomo-tmp/review/<stem>/`, `<stem>` = `<period-name>_review`, the
same stem `review_state` derives and `review-doc.py --stem` takes), is
written atomically, and is deleted by `review-doc.py write` once the document
exists. stdout prints the report: paths, dates, states, counts, the advice —
and `read_path`, so the skill never composes the path. stderr carries the
exception class name on an unexpected error and nothing else; the privacy
test over the script asserts that a marker from a daily's text reaches neither
stream. `--stem` is accepted (the SDD's `[--stem S]`) and refused when it
contains `/`, `\` or `..`, as `review-doc.py` refuses it. It is also refused
when it is empty, whitespace or exactly `.`: those pass the
marker check but do not name a folder *under* `--tmp` — `Path(tmp) / "."` is
`tomo-tmp/review` itself, so `read.json` would land beside every other
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
