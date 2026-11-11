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

## WHY "Nothing to Review" Writes Nothing and Carries the Access Hint

WHY: F3-AC9 and PRD Rule 6. `nothing_to_review` is true when no day of the
period has content beyond the template skeleton (`has_content` from
`review_day`), which is also what the run looks like when the Kado key
cannot read the daily folder — Kado answers an empty listing for a denied
folder. The script cannot tell the two apart, so it says both: the report
carries `check-key-access` whenever nothing is to review, not only when the
listing was empty (`kado_empty`), and no `read.json` is written, so the
document step finds nothing to build (`review-doc.py write` → `read-missing`).
The status stays `ok`: Kado was reached and answered; it is the period that
holds nothing.

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
contains `/`, `\` or `..`, as `review-doc.py` refuses it.

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
