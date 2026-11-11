# WHY: review-session.py

> Rationale for decisions in `tomo/scripts/review-session.py`.
> The script is the deterministic session start of `/review` (spec 045,
> ADR-1, ADR-5, ADR-7, ADR-8): `match` previews the setup of one period kind
> against the notes that exist (F1), `setup-input` turns a confirmed proposal
> into the writer input (T2.2); `start` (T2.3) parses the request and lists
> the open reviews.

## WHY the Setup Preview Is a Script

WHY: ADR-1 and ADR-5, the same shape as `/note`'s `note-session.py match`.
Listing a folder, matching names against a Moment-style format, reading
dates out of eight notes and deriving a week rule are rules, not judgement.
Done by the model they drift between runs (a format that matches on one run
and not the next, a week rule read off the Obsidian plugin settings). One
script makes the preview the same every time and testable on a fake vault
without a model in the loop (Constitution L1). Nothing is saved by `match`;
the writer (`vault-config-writer.py review`) runs only after the user
confirms, and `setup-input` is the only step between the two.

## WHY Every Actionable Outcome Exits 0

WHY: SDD Internal API Changes and the repo rule for agent-called scripts. The
skill acts on `status`, `error` and `errors`; a non-zero exit makes the model
re-run the script or improvise. Exit 2 is reserved for a bad invocation
(argparse: unknown subcommand, bad `--kind`, missing `--confirmed` file), exit
1 for an unexpected exception, where stderr carries the exception class name
and nothing else (ADR-9: stderr never carries note text, titles or paths).

## WHY the Kado Access and the Inference Live in `lib/`

WHY: T2.2 code review. With `match` and `setup-input` alone the script passed
600 lines, and T2.3 adds `start`, which needs the same Kado wrapper and the
same date helpers. The wrapper, the `Stopped` exception and the helpers that
read a weekly note's evidence are `lib/review_vault.py` (WHY:
`docs/tomo/scripts/lib/review_vault.md` — the error mapping, `kado-none`,
`journal-end-date` − 6, day headings as a full week); the week-rule
inference is `lib/week_rule_inference.py` (WHY:
`docs/tomo/scripts/lib/week_rule_inference.md` — never `.obsidian`, the
eight-note budget, the rule intersection, duplicated stems). The script
keeps what is specific to the subcommands: the precedence of flags, config,
inference and defaults, the name matching, the proposal, the writer input
and the argparse wiring.

## WHY the Config Beats the Inference

WHY: the documented order is flags > config > inference > defaults, and the
first draft had the inference ahead of the config. A `review.week` rule in
the config is a setup the user confirmed; the inference reads what the notes
look like today. If the notes were later renamed or an old year counted
differently sits in the folder, the inference changing silently would show a
proposal the user never confirmed, and `/review setup` would display a
guess instead of the current setup (the same reason every other configured
value wins over its proposal). `evidence.week_rule` still reports what the
notes showed, and a configured rule the notes contradict puts those notes
under `unmatched`, so the skill can say so.

## WHY Two Notes With the Same Stem Are Both Listed

WHY: the first draft keyed the listing by stem, so a note in the folder and
its namesake in a year subfolder collapsed into one: `notes_checked`
undercounted, the hidden copy's dates never reached the inference, and
`matched`/`unmatched` showed one note where two exist. Every path is now
matched on its own dates, and a duplicated stem appears once per note in
the listing — the preview shows what the folder holds, and T2.3's `start`
meets the duplicate as a known case rather than a surprise.

## WHY `week_rule` Reports the Notes, and Flags Set the Proposal

WHY: F1-AC5 and F1-AC8. When the skill re-runs `match` with `--first-day`
and `--min-days` from the user's answer or correction, the proposal follows
the flags and the matches are recomputed under them; `evidence.week_rule`
still says what the notes showed (`inferred`, `ambiguous`, `default`), so the
skill can show the notes the new rule no longer matches without pretending
the notes agreed. `--format` works the same way. The two week flags are
accepted only together; one alone is a usage error (exit 2). A week rule is
one answer — the user names the first day and how week 1 is counted in the
same breath, and the skill always passes both after that answer. Filling the
missing half from the inferred or configured rule would silently pair the
user's first day with a `min_days` the notes may never have supported, and
the proposal would then show a rule nobody stated. A dated note is `matched` only
when its name parses under the proposal's format and rule AND the resulting
week starts on the note's date; a name that parses with contradicting dates
is listed under `unmatched` (SDD walkthrough row 2026-03-01 under Sunday).
Notes beyond the eight checked are matched by name alone.

## WHY the Default Format Follows the Rule

WHY: `period.check_format` refuses upper-case week tokens under a non-ISO rule
(`iso-tokens-need-iso-rule`). The proposal therefore defaults to
`GGGG-[W]WW` for the ISO rule and `gggg-[W]ww` otherwise; months default to
`YYYY-MM`. A configured `naming.calendar_patterns.<kind>` or `--format` wins
over the default, and any problem `check_format` finds with the format in
use is listed in `evidence.format_problems` so the skill can say at preview
time what `setup-input` would refuse later. An unsafe format (`/`, `\`, `..`)
stops the preview before any Kado call with `error.kind = unsafe-format`: a
name that leaves its folder must not even be matched.

## WHY `kado-none` Is Never "No Notes"

WHY: PRD Rule 6, F3-AC9 and the memory rule that an empty Kado search hides a
denial. A listing that returns nothing or `Path not found` is reported as
`folder_listing: kado-none` with the access hint in `hints`; the skill asks
before proposing to create notes there. `found` with no name that parses
under the proposal's format (an empty `matched` while the week rule is
`default`, or a month folder with only non-periodic names) means the folder
answered, but with nothing to compare the format against — only then does
the script add the "no notes to compare" hint (F1-AC4), so the two wordings
can never appear for the same listing. The script puts the sentence in
`hints` rather than leaving it to the skill because the skill was observed
saying "no notes" for a `kado-none` listing; a hint the script chose is the
same on every run. Names that parse but fail their dates under a flagged rule
are notes to compare — they are listed under `unmatched` without the hint.

The folders come from `review_config.folder_for`, the same resolver `start`
and the reader use (config over profile, a disabled or blank entry is None),
so the preview and the session can never list two different folders.

## WHY the Template Is Classified by Reading It

WHY: ADR-8 and F1-AC7. Whether a template is Templater (`<%`) decides the
delivery path (variant or raw template with a Templater hint), so the
proposal names the kind. `missing` is a configured name Kado reports as not
found, or no mapping at all; `unreadable` is any other Kado failure on the
read (a tool error, a refused key) and the hint says the key may have no
access — Kado answers the same way for both. A broken connection is not
`unreadable`: it stops the whole preview as `kado-unreachable`, because the
listing that succeeded a moment ago would be stale evidence. No template
search is attempted when the mapping is absent: a guessed file would have to
be confirmed by the user anyway, and a plain note (title and review section)
is the documented fallback.

## WHY the Place and the Daily Sections Come From the Templates

WHY: F1-AC1 asks for a proposal of the review heading, its place and the
daily sections, so that the user confirms rather than types. The template's
headings (level 2 and deeper, without Templater code) are the only source
that exists before any note is read; the proposed anchor is the last of the
shallowest headings with placement `before`, which keeps the review above the
user's closing section without guessing its name. The daily sections are the
daily template's headings (`templates.mapping.daily`) minus headings that
carry Templater code or links, because their text changes per day (the
Dayplanner embed). A configured value always wins: `/review setup` shows the
current setup, not a fresh guess. `evidence.template_headings` lists the
anchor candidates (the same headings the proposal chose from, with their
levels) so the skill can offer alternatives when the user corrects; the
title and Templater headings are left out because neither can be a place.

## WHY the Language Falls Back to the Notes' `locale`

WHY: SDD Data Storage Changes: the review language defaults to the
frontmatter `locale` of the dailies, else `en`. The weekly notes checked for
the rule carry the same key in the owner's vault, so no extra read is spent;
a month preview reads no note and falls back to the configured language or
`en` — the week setup normally runs first and has saved it by then.

## WHY the Daily-Path Fix Is Proposed Only When the Other Spelling Exists

WHY: F1-AC9. The instance config carries `Calendar/301 Daily/ ` with a
trailing space; proposing the trimmed spelling blindly would "fix" a path
that may not exist. The script probes the trimmed spelling through
`lib/vault_folder_lookup` (one `list_dir`) and proposes the fix only when
that folder is `listed`; `absent` and `unanswered` propose nothing. The
probe runs only when the configured path differs from its trimmed form, so a
clean config costs no call. Saving the fix is still the user's confirmation:
`setup-input` carries `daily_path_fix` only when the confirmed proposal does.

## WHY `setup-input` Validates Before the Writer Does

WHY: SDD Error Handling row for `setup-input`: an invalid confirmed input is
`status: invalid` with pointers and nothing saved. The writer validates
again, but the skill needs the pointers before it spends a writer call, and
the confirmed proposal is not the writer's shape: `template_kind` is dropped,
a month proposal's null `first_day`/`min_days` are dropped (the schema forbids
them for a month), and `daily_path_fix` is reduced to the found spelling.
Validation is `review_config.input_problems`, the writer's own check, so the
two cannot disagree. The input is written atomically to
`tomo-tmp/review/setup-<kind>.json` (`--output` overrides) and `input_path`
names it; the skill passes it to the writer and removes it, as `/note` does
with `note-include.json`.

## WHY the JSON Is Written ASCII-Escaped

WHY: as in `note-session.py`: `ensure_ascii=True` cannot fail on a non-UTF-8
stdout or a lone surrogate, and every reader decodes the escapes.
