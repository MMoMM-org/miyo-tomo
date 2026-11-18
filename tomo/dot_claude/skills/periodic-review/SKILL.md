---
name: periodic-review
description: MUST BE USED when the user runs /review, or asks for a weekly, monthly or quarterly review of their periodic notes (the last finished week, month or quarter, a named period such as 2026-W13, 2026-03 or 2026-Q1, an @-picked periodic note), to continue, deliver or drop an open review, or to set up or change the review setup (/review setup). NOT for inbox triage (/inbox) and NOT for a single note from a template (/note).
user-invocable: true
allowed-tools: Read, Write, Bash
argument-hint: "a period (2026-W13, W13, 2026-03, 2026-Q1), month, quarter, setup, an @-picked periodic note, or nothing"
---
# Periodic Review
# version: 0.2.11

Review one finished week, month or quarter with the user: Pass 1 writes a review document to the inbox, Pass 2 turns the edited document into an instruction set. Run the steps in order. Run every script from the session's working directory (the instance root), never from the skill's base directory. Write only `tomo-tmp/review/<stem>/proposals.json` and `tomo-tmp/review/confirmed-<kind>.json` yourself; every other change goes through the scripts below.

## Rules

- Every script prints one JSON object. Read its `status` first and branch on it before any other key; a `stopped` or `refused` output is never read for `nothing_to_review`, `open_reviews`, `approved` or a plan.
- `status` `stopped` with `error`: show `error.kind` and `error.detail` verbatim and stop; nothing was written.
- A non-zero exit: show the output and the stderr line verbatim and stop.
- Every question is plain text in the visible reply: first the content, copied from the Read or Bash result, then the question, numbered on one line as `1 First · 2 Second` as the last line. Then end the turn.
- The next user message is the answer: a typed number or option word; when it is unclear, ask again in plain text.
- Show the `error`, `expected`, `example` and `errors` of a script verbatim, and the `hints` of step 2 and the `problems` of step 4; never paraphrase them. Every other `problems` entry, `warnings` entry and `notices` entry is said by the line its step gives it; without one, verbatim.
- Never quote `read*.json`, a daily note, a journal answer or a tracker value in your reply; print the scripts' reports and `section_md` only.
- Never say a folder is empty or a note does not exist: `kado-none`, `kado_empty` and an empty result may mean the Kado key cannot read the folder; say so.
- On Abort at any question, run no further script and write nothing; say in one line what stays as it is.
- Ask in the language the user writes in.

## 1. Start

Run:

```bash
python3 scripts/review-session.py start --args='<request>'
```

`<request>` is the skill's arguments (`$ARGUMENTS`) verbatim inside single quotes, each `'` written as `'\''`. Keep the request text in the conversation.

- `status` `stopped` → the stopped rule.
- `problems` holds `inbox-not-configured` → say the inbox folder is not configured and stop.
- `error` set → show `error.kind`, `expected` and `example` verbatim (`invalid-period`, `not-periodic-note`, `unknown-argument`); for `unfinished-period` say that only finished periods can be reviewed and name `last_finished`. Stop; nothing is written.

Say one line per entry of `skipped_review_docs` with its `doc_path` and `reason` (`frontmatter-unreadable`, `period-missing`, `stem-unsafe`); never drop one silently.

Handle every entry of `open_reviews` before the new request, in the order listed. Print each by `period`, `kind` and `state`, then branch on `state`:
- `failed-delivery` → ask `1 Resume · 2 Drop`. Resume → step 8 with the entry's `stem`. Drop → step 9 with the entry's `stem`.
- `open` → ask `1 Continue · 2 Start over · 3 Abort`. Continue → step 6 with the entry's `stem`. Start over → step 4 with the entry's `period` and `kind` (the `write` there refuses with `review-exists` and step 5 asks before replacing). Abort → say in one line that the document stays as it is and end the run: no further entry, not the new request.
- `delivered` → say in one line that its instruction set waits for Hashi, or for the user to apply it by hand; no second set is delivered.
- `move-refused` → say in one line that the target note existed when Hashi applied the move, so the inbox copy is still there; the user decides in Obsidian.
- `target-missing` → say in one line that the target note is gone since delivery; the user decides in Obsidian.
- `applied` → say in one line that the review was applied. When `notices` holds `applied-not-recorded`, add that the line will show once more next time.

Continue with the next entry, then with the new request, after each one ends without an Abort; an Abort at any question of an entry ends the whole run: no further entry, not the new request. When the request names the same `period` as an open review, that open review is the request: stop after it.

`request` is null (`request_withheld` `open-reviews`) → there is no new request: say in one line that a bare `/review` starts no new period while a review is listed, and that `/review <period>` (`2026-W13`, `2026-03`) or `/review month` names one; end the run after the last entry.

Then the new request, by `request.kind`:
- `setup` → step 2 for `week`, then for `month`, then for `quarter`, each starting from `current.<kind>`; then stop.
- `week`, `month` or `quarter` with `setup.<kind>` `missing` → step 2 for that kind, then rerun the `start` call above (skip the open reviews already handled) and continue here.
- Otherwise → step 3.

## 2. Setup

`<kind>` is `week`, `month` or `quarter`. When `current.<kind>` is given, print it first: its values, or that none is saved, or its `invalid` pointers. Run:

```bash
python3 scripts/review-session.py match --kind <kind>
```

- `status` `stopped` → the stopped rule. `error.kind` `unsafe-format` → say the name format must not contain `/`, `\` or `..` and ask for another format; rerun `match` with it as `--format`.
- `template_not_found` is set → say that the template `template_not_found.name` was not found (`source` `typed`: the name typed, `configured`: the saved one); the `template_candidates` line asks for another. `template_candidates` is empty → in the same reply ask: Which template, typed, or `0` for none? End the turn. A typed name → `<template>` is that name in double quotes; run `python3 scripts/review-session.py match --kind <kind> --template <template>` with the flags of the last `match` call added, except `--template` and `--anchor`, and continue with its output. `0` → `<template>` is `none`; continue with this output: no template, a plain note.
- `template_candidates` is non-empty → without `template_not_found`, say that no template is saved for `<kind>`; say that these notes of the templates folder fit it; ask, numbered on one line with `0 none` last: `1 <name> · 2 <name> · 0 none`. End the turn. A number → `<template>` is `"<name>"`, the chosen name in double quotes; a typed name → `<template>` is that name in double quotes; run:

```bash
python3 scripts/review-session.py match --kind <kind> --template <template>
```

with the flags of the last `match` call added, except `--template` and `--anchor`, and continue with its output. `0` → `<template>` is `none`; continue with this output: no template, a plain note. Without `template_candidates`, `<template>` is `"<proposal.template>"` when `proposal.template` is set, else `none`.
- Every later `match` call of this step carries `--template <template>`, once `<anchor>` is given `--anchor "<anchor>"`, once the week question is answered `--first-day <day> --min-days <n>`, and once the frontmatter question is answered with `1` `--template-frontmatter-ok <ok-template>`: the script then lists no candidates, asks for no anchor, reports `week_rule` `given` and sets no `needs_template_ok`, so each question is asked once. Never drop one of these flags from a rerun, except `--anchor` by the next line.
- When `<template>` changes, the next `match` call carries no `--anchor` and `<anchor>` is unset: the new output proposes the place, and `needs_anchor` asks again.
- Print `proposal`, `evidence` (`matched`, `unmatched`, `week_rule`, `folder_listing`, `format_problems`) and every line of `hints`.
- `evidence.folder_listing` is `kado-none` → the `hints` line says so; ask before proposing to create notes there.
- `proposal.template_kind` is `missing` → say that a plain note (title and review section) is proposed. `unreadable` → say the same and that the template may not be readable by the Kado key (no access).
- `needs_template_ok` is true → say that the template `<template>` has no frontmatter block at its first line and ask: `1 Use it as it is · 2 I'll create a Tomo variant`. End the turn. `1` → `<ok-template>` is `<template>` as it is now; continue with the proposal already shown: rerun no `match` and name no flag or field. `2` → the Abort branch below; say in its line: create a Tomo variant of the template, `<template>` with `_tomo` before `.md`, next to it, whose first line is `---` and whose frontmatter is closed by `---`; then run `/review setup` again and choose the variant.
- `daily_path_fix` is set → print `configured` and `found` and say the saved value is corrected to `found` only on Confirm.
- `evidence.week_rule` is `ambiguous` (week only) → ask in plain text, before the confirm question: "Which day does your week start on? Is week 1 the week with 1 January, or the first week with at least four days in the new year?" Map the answer to `--first-day <day>` (the day in lowercase) and `--min-days <n>` (`1` for the week with 1 January, `4` for at least four days), rerun `python3 scripts/review-session.py match --kind <kind> --folder "<folder>" --format "<format>" --first-day <day> --min-days <n> --template <template>` with the proposal's folder and format, and print the new proposal, evidence and hints. Its `evidence.week_rule` is `given`: the question is answered and not asked again; only `ambiguous` asks it.
- `needs_anchor` is true → say that no heading could be proposed for the place of the review section (no template, or none with a heading below its title); print `anchor_candidates` as a numbered list and ask: Which heading, by number or typed? End the turn. The answer is `<anchor>` and `proposal.place.anchor`; print the proposal with it in place. Never offer Confirm while `place.anchor` is null.
- `sections.dropped` is non-empty → say in one line per entry that `heading` (level `level`, under `parent`) of the earlier mapping is not in `<template>`: with `sections.mappable` true it is not kept; with `sections.mappable` false the save leaves the saved rows as they are.
- `sections.mappable` is false → say in one line that no section of the template can be mapped, so the review goes into its own section only; print no table.
- `sections.mappable` is true → print the mapping table in the same reply, before the confirm question, from `sections.candidates` in their order:
  - Each candidate with `state` `offered` or with `saved` set is one row, numbered `s1`, `s2`, … in order: `heading_key` as heading (level, under parent), its `flags` in brackets, description, keywords, groups, placement and cap. With `saved` set, take them from `saved`; else placement and cap from `defaults`, and write the description: what to look for in the period's notes for that section, in `proposal.language`; add keywords (at most 12) and groups only where they fit.
  - Groups a row may name: `done`, `open`, `themes`, `growth`; for `month` also `weekly_only`, `not_in_weekly`; for `quarter` also `monthly_only`, `not_in_monthly`. Never `habits`.
  - A heading that looks ahead (what comes next, goals, wishes, what to start, stop or continue, what will be challenging) gets a description asking for suggestions drawn from what the period shows.
  - Each other candidate is one line `—` with heading, level, parent and the `reason` in words: `templater` Templater code in the heading, `link` a link in the heading, `per-period-parent` repeats under headings that change per period, `off-limits` marked off-limits, `automatic` only automatic content, can get an analysis row.
  - Last the line `Off-limits:` with each `sections.off_limits` row (heading, level, parent, `with sub-sections` when `with_subsections` is true), or `none`.

Ask `1 Confirm · 2 Correct · 3 Abort`.
- Correct: for the folder, the format, the first day, the week-1 rule or the template, rerun `match` with the corrected value as its flag (`--folder`, `--format`, `--first-day` with `--min-days`, `--template` — a corrected template is `<template>` from then on, `none` for no template), the proposal's values for the others, `--template <template>`, `--anchor "<anchor>"` when given, `--first-day <day> --min-days <n>` once the week question was answered and `--template-frontmatter-ok <ok-template>` once the frontmatter question was answered with `1`, and print the new proposal, evidence and hints; its `needs_template_ok` line above applies; for heading, place, own sections, daily sections or language, print the proposal with the corrected value; a corrected anchor is `<anchor>` from then on. Then ask `1 Confirm · 2 Correct · 3 Abort` again. Write nothing before Confirm.
- Correct of the table: the user names a row (`s<n>` or its heading) and the change in plain text. Change its description, keywords, groups, placement (`before`, `under`, `end`) or cap (1 to 30), or remove it. Add a heading: an `offered` candidate → a row with its `defaults`; an `automatic` one with a description → an analysis row with placement `review`; any other `left-out` one → say its `reason` and add nothing; a heading not among the candidates → say it is not in `<template>`. Mark a candidate off-limits, heading only or with sub-sections → it joins the `Off-limits:` line and its row leaves the table (with sub-sections, the rows under it too); unmark → it leaves the line. Print the table again with the change, run no `match` and ask `1 Confirm · 2 Correct · 3 Abort` again.
- A `match` rerun with the same `<template>` keeps the table changes; with a changed `<template>` the table is built anew from the new `sections`.
- Abort: stop; nothing is saved and nothing is written. A kind confirmed and saved earlier in this run stays saved.
- Confirm: write `tomo-tmp/review/confirmed-<kind>.json` with the last `proposal` object as it is, the corrected values in place; add `daily_path_fix` from the `match` output only when the user confirmed it. With `sections.mappable` true, add `sections`, the table rows in order, each with `heading`, `level`, `parent` and `occurrence` of its `heading_key`, `description`, `placement`, `cap`, and `keywords` and `groups` when set; and `off_limits`, each entry of the `Off-limits:` line with its `heading_key` fields and `with_subsections`; `[]` when there is none. Then run:

```bash
python3 scripts/review-session.py setup-input --kind <kind> --confirmed tomo-tmp/review/confirmed-<kind>.json
```

`status` `invalid` → show `errors` and `problems` verbatim and ask `1 Correct · 2 Abort`; Correct → the Correct branch above. A pointer that starts with `/sections/<i>` is the row at index `<i>` of `sections`, counted from 0: name its heading. `/place` is the place of the review section, `/template` the template: name them in words. `status` `ok` → run:

```bash
python3 scripts/vault-config-writer.py review --input <input_path>
rm -f tomo-tmp/review/confirmed-<kind>.json <input_path>
```

On a non-zero exit of the writer, show its output verbatim and stop; nothing is saved. Otherwise confirm in one line that the setup of `<kind>` is saved.

## 3. The request

`<period>` is `request.period`, `<kind>` is `request.kind` and `<stem>` is `<period>_review`. When `request.year_inferred` is true, say in one line which year was chosen (the year of `request.period`) before reading. Then step 4.

## 4. Read the period

```bash
python3 scripts/review-read.py --period <period> --kind <kind> --stem <stem>
```

Branch on `status` first:
- `stopped` with `error` → the stopped rule. `stopped` with `problems` → show them verbatim (`setup-missing`, `setup-invalid` with `errors`, `daily-not-configured`, `dailies-not-read`) and the `report` when present, and stop; nothing is written. Never read `nothing_to_review` from a `stopped` output.
- `ok` with `nothing_to_review` true → say that no daily note of the period holds content and name the days of `report.days`; when `advice` holds `check-key-access`, add that Kado answered with nothing for the `kado_empty` sources and that the Kado key may not reach those folders. Stop; nothing is written.
- `ok` otherwise → print the `report` as the script prints it: per day the dailies found and their `state`, the `linked` notes with `state` `missing` or `failed`, `day_after`, `task_notes`, `weekly_status` and `weekly_notes`, `monthly_status` and `monthly_notes` when present, `growth`, `kado_empty` with the access hint, and the pacing line: `calls`, `retried`, `waited_s`, `not_read`. When `advice` holds `raise-kado-limit`, say that Kado turned calls away for its rate limit and suggest raising Kado's rate limit. When `advice` holds `check-key-access`, say that Kado answered with nothing for the `kado_empty` sources and that the Kado key may not reach those folders; the user checks its access. When `not_read` is non-empty, say that these days or notes are missing from the review and that the document will name them at its top; never say that everything was read. Then step 5.

## 5. Propose and write the document

Read `read_path` of step 4 and `config/vault-config.yaml`; `<language>` is the value of `review.language` in the config file. A quarter: then read each file of `read_parts` in the listed order, one Read call after the other; in this step `read.json` means all these files together. Write `proposals.json` only after the last part.

Write `tomo-tmp/review/<stem>/proposals.json`:

```json
{"language": "<language>", "groups": {"done": [{"text": "<proposal>", "sources": ["<path or stem from read.json>"]}], "open": [], "themes": [], "growth": [], "weekly_only": [], "not_in_weekly": []}}
```

- Every item is in `<language>`; its `sources` name the notes of `read.json` it rests on, at least one a daily of the period (for `weekly_only` a weekly note of the period). A second line of `text` becomes a continuation line of the item.
- `done`: what happened and got done; `open`: what stayed open; `themes`: a theme found on at least two days; `growth`: what the `growth` lists of `read.json` show; `weekly_only` and `not_in_weekly` (month only, when `read.json` holds `weekly`): what the `only_in_weekly_links` and `dailies_not_in_weekly` lists show. Leave out a group with nothing to propose.
- Quarter (when `read.json` holds `monthly`, `report.monthly_status` `found`): `monthly_only` and `not_in_monthly` are what `only_in_monthly_links`, `dailies_not_in_monthly` and the `month_text` of the `monthly` entries show; a `monthly_only` item's sources name a `monthly` note; a section item carries `"mark": "monthly_only"` or `"mark": "not_in_monthly"` as a month's carries its marks.
- Habits are computed by the script: never propose them. Never propose text for the user's own sections other than the `sections` of `read.json`.
- `read.json` holds `sections` → add `"sections": [{"key": "<key>", "items": [{"text": "<reminder>", "sources": ["<path or stem from read.json>"]}]}]` beside `groups`: one entry per `sections` entry with something to propose, its `key` copied; no other key.
- A section's items are what its `description` and `keywords` ask for in the period's notes, whatever group they would fit. Each is a reminder of what happened or will need to happen, with its sources; never finished review text, never a judgement. At most `cap` items: merge findings that say the same, keeping the sources of each.
- Each finding goes in one place: the section it fits best, else its group; never in a second section or a group as well.
- A `sections` entry with `analysis` true → items that sum up what the period's values for it show, each an overview, never one item per day.
- Month: a section item that only the weekly notes hold, or that they left out, carries `"mark": "weekly_only"` or `"mark": "not_in_weekly"`; its sources as for that group.
- `<section heading>` of a key is the `heading` of the row with that `id` under `review.<weekly|monthly|quarterly>.sections` (the kind's) in `config/vault-config.yaml`.

Then run:

```bash
python3 scripts/review-doc.py write --stem <stem> --proposals tomo-tmp/review/<stem>/proposals.json
```

Branch on `status` first:
- `stopped` → the stopped rule; `problems` `kado-write-failed` → say nothing was written and stop.
- `refused` with `proposals-invalid` → show `errors` verbatim, rewrite `proposals.json` once and rerun `write`; a second `proposals-invalid` → show it and stop.
  In the rewrite, fix each `errors` entry in the item or entry its pointer names: `unknown-section` or `duplicate-section` → each `read.json` key once, no other; `over-cap (<key>)` → merge that section's items down to its `cap`; `double-placement` → remove that item; `mark-not-allowed` → drop its `mark`.
- `refused` with `doc-name-taken` → say `doc_path` is a note that is not Tomo's review document and nothing was overwritten; stop.
- `refused` with `review-exists` → say Tomo's review document for the period already exists at `doc_path` and that replacing it discards the user's edits in it; ask `1 Replace · 2 Keep it`. Replace → run `python3 scripts/review-doc.py replace --stem <stem> --confirm` and branch on its `status` by this list, `replaced` as `written`. Keep it → run `python3 scripts/review-doc.py replace --stem <stem> --abort` and say in one line that the document is kept.
- `refused` with `sections-changed` → say the section setup changed since the read; run step 4 again, once, and continue there; a second `sections-changed` → show it and stop.
- `refused` with any other problem (`read-missing`, `read-invalid`, `setup-missing`, `setup-invalid`, `inbox-not-configured`) → show `problems` and `errors` verbatim and stop.
- `written` → report `doc_path`, `target` and `target_exists`, `target_found_elsewhere` when set, `counts` per group and per section (by `<section heading>`), and every `rejected` item with its `group` or `section`, `index` and `reason`. Then say: edit the document in Obsidian, tick `- [x] Approved` and run `/review` again. End the turn.

## 6. Continue an open review

```bash
python3 scripts/review-doc.py parse --stem <stem>
```

Branch on `status` first:
- `stopped` → the stopped rule.
- `not-found` → say the review document was not found at `doc_path` and ask `1 Start over · 2 Abort`. Start over → step 4 with the entry's `period` and `kind`. Abort → stop.
- `ok` → report `counts` (`kept`, `unticked`, `deleted`, `added`), then one plain line per entry of `warnings`:
  - `approved-line-missing` → the Approved line is missing; restore `- [ ] Approved` at column 0 and tick it.
  - `unknown-group` → a heading the parser does not know; its items do not land.
  - `duplicate-group` → the second heading of that name is ignored.
  - `frontmatter-broken` → the document's frontmatter could not be read; the period is taken from the stage.
  - `item-outside-group` → an item above the first heading; it is filed under an unknown group and does not land.
  - `section-checkbox-missing` → per entry of `section_problems`: the checkbox line of the section `<section heading>` (step 5) of its `key` is missing or broken; restore the line `restore`, verbatim, under that heading and run `/review` again. Stop after the warnings; nothing is delivered.

  Then: `approved` false → say the document is not approved yet and name the box `- [ ] Approved`; stop, nothing is delivered. `nothing_to_deliver` true → say nothing is ticked and ask `1 Start over · 2 Abort`; Start over → step 4 with the entry's `period` and `kind`, Abort → stop. Otherwise → step 7.

## 7. Preview

```bash
python3 scripts/review-instructions.py preview --stem <stem>
```

With a chosen heading add `--place-anchor "<heading>"`. Branch on `status` first:
- `stopped` → the stopped rule. `not-found` → as in step 6. `refused` → show `problems` and `errors` verbatim and stop.
- `ok` with a non-empty `problems` → one line per problem:
  - `not-approved` → name the box `- [ ] Approved`; stop.
  - `approved-line-missing` → say the Approved line is missing; restore `- [ ] Approved` at the line start and tick it; stop.
  - `section-checkbox-missing` → run `python3 scripts/review-doc.py parse --stem <stem>` and say its `section-checkbox-missing` line of step 6; stop.
  - `nothing-to-deliver` → say nothing is ticked and ask `1 Start over · 2 Abort` as in step 6.
  - `place-missing`, `place-too-deep` or `user-heading-collision` with `mode` `replace` → say what is wrong with the heading above the Tomo marker in the target note: there is none (`place-missing`); it is one of the user's own sections, or an earlier heading of the same name stands above it (`user-heading-collision`); it is too deep to replace under, the review heading would pass level 5 (`place-too-deep`). Ask `1 Start over · 2 Abort`; Start over → step 4 with the entry's `period` and `kind`, Abort → stop.
  - `user-heading-collision` with `mode` `insert` or `new-note` after a heading pick (the rerun with `--place-anchor`) → say the target note holds a heading that clashes with the review: one named like the review heading, or the picked heading is one of the user's own sections; the user renames or removes the clashing heading in Obsidian. Ask `1 Start over · 2 Abort`; Start over → step 4 with the entry's `period` and `kind`, Abort → stop. Never print `headings` or ask for a number a second time.
  - `place-missing` or `place-too-deep` with `mode` `insert` or `new-note` → name `place.anchor` and `place.placement`, and say that this heading is not in the target note (`place-missing`), or that the review heading would pass level 5 under it (`place-too-deep`); print `headings` as a numbered list and ask: Which number, or 0 Abort? A number → rerun `preview` with that heading as `--place-anchor`, keep it for step 8 and branch on the rerun by this list. 0 → stop.
  - `user-heading-collision` with `mode` `insert` or `new-note` before any heading pick → say a heading of the user's with the same name is never replaced and the review never lands inside one of the user's own sections; print `headings` as a numbered list and ask: Which number, or 0 Abort? (as above).
  - `set-exists` → say an instruction set for this review waits for Hashi and is not applied yet; nothing is delivered. Stop.
  - `set-withdrawn` → say an earlier Drop emptied the instruction set but did not finish (its readable file may still list the actions); nothing is delivered. Ask `1 Drop · 2 Abort`; Drop → step 9 with `<stem>`, Abort → stop.
  - `landing-off-limits` with no entry of `sections` carrying a `stop` → say that the "Tomo Review" section, placed at `place.anchor`, would land in an off-limits section, that the place is changed with `/review setup`, and that nothing is delivered; stop.
  - `section-missing`, `section-ambiguous`, `section-broken`, `section-moved`, `block-in-review-section` or `landing-off-limits` with no other problem in `problems` → print the plan as `ok` with empty `problems` below does, without its question; then per entry of `sections` with a `stop` one line in `<language>` (`review.language` of `config/vault-config.yaml`, Read it): the section `<section heading>` (step 5) of its `key`, its `placement`, why it stops (its heading is not in the target note, is there more than once, Tomo's earlier block in it is broken, the block was moved under `block_at.heading`, the block sits inside the "Tomo Review" section, or it would land in an off-limits section) and its `choices`: `skip` leaves the section out, `review` puts its items into the "Tomo Review" section, `confirm-moved` replaces the block where it sits now. Beside another problem only that problem's line applies.
    - An entry with empty `choices` → say that it can only be aborted; nothing is delivered; stop.
    - Otherwise ask per listed section for one of its `choices`, or 0 Abort, and end the turn. The answer → rerun `preview` with `--section-choice <key>=skip`, `--section-choice <key>=review` or `--confirm-moved <key>` per listed section, keep these flags for step 8 and branch on the rerun by this list; `ok` with empty `problems` → its bullet below, its question included. 0 → stop.
  - `choice-invalid` → say the note changed since the preview: the choice for each key in `choices_invalid` answers no stop of that section now; rerun `preview` without the section choice flags and branch on the rerun by this list.
- `ok` with empty `problems` → print `target`, `mode` (`insert`, `replace` or `new-note`), `place` (`anchor`, `placement`, `level`) and `section_md` in full, in a fenced block, copied from the Bash result, then per entry of `sections` the section `<section heading>` (step 5) of its `key`, its `placement`, its `mode` and its `lines` in a fenced block. Then one line for `mode` `replace`, per entry of `notices` and per flag set:
  - `mode` `replace` → the note already holds Tomo's review section; it is replaced, not added to.
  - `heading-renamed` → the marker was found under a renamed heading; the section is replaced there.
  - `target_appeared` true → the target note was created since Pass 1; the plan targets it instead of a new note.
  - `variant_missing` or `templater_hint` → the template's Tomo variant is gone, or the template holds Templater code; the readable instructions say to run Templater after the move.
  - `template_unmergeable` → a plain note is built instead.
  - `unlanded-items` → `unlanded` kept items are under a heading the parser does not know and do not land.
  - `block-replaced` → per entry of `sections` with this notice: Tomo's earlier block in that section is replaced; edits inside the block are replaced, text outside it is kept.
  - `block-moved-confirmed` → that block is replaced where it sits now.
  - `review-section-kept` → the earlier "Tomo Review" section gets nothing new and stays as it is.
  - `section-dropped` → per entry of `dropped`: the section `<section heading>` of its `key` is left out, and the user's own `added` items in it are dropped with it.
  - `section-empty` → per key in `empty`: the section `<section heading>` is empty and receives nothing.

  Then ask `1 Deliver · 2 Abort` and end the turn. Say in one line before it that a change is made by editing the document and running `/review` again. Deliver → step 8. Abort → stop; nothing is written, the document stays open.

## 8. Deliver

```bash
python3 scripts/review-instructions.py deliver --stem <stem>
```

# STRICT — never write the review document, the instruction set, the new note or a file under `tomo-tmp/` other than the two named at the top yourself, not through Kado and not with Write; only the review scripts write them. Why: a hand-written document mark and a hand-edited `meta.json` make the next deliver or drop act on a delivery that never happened.

Add `--place-anchor "<heading>"` when a heading was chosen in step 7, and the section choice flags of the last `preview` of step 7, unchanged. Branch on `status` first:
- `delivered` or `resumed` → report `target`, `place`, `paths.set_json`, `paths.set_md` and `paths.note` when set, and "Next: review and apply the instruction set in Hashi, or by hand with the readable instructions." Then the step 7 notice lines for `notices` and `target_appeared`.
- `refused` → `name-taken` with `step` `note` → say a note at `exists_path` is not Tomo's and nothing was overwritten; stop. `name-taken` with `step` `set_json` or `set_md` → say an earlier instruction set of this review waits at `exists_path` and nothing was overwritten; for a fresh delivery the user applies that set in Hashi, or deletes it in Obsidian (with `step` `set_json` also the readable instructions beside it), then runs `/review` and chooses Resume; stop. `set-exists` or `set-withdrawn` → as in step 7. `replan-differs`, `anchor-needed` or `choices-needed` → the lines below. Any other → the step 7 lines; nothing was written.
  - `replan-differs` → say the vault changed since the stopped delivery: the target note or its place is not what the first attempt wrote for; nothing more was written, and Resume would refuse again. Ask `1 Drop · 2 Abort`; Drop → step 9 with `<stem>`, Abort → stop.
  - `anchor-needed` → say the stopped delivery used a chosen heading that is asked again: print `headings` as a numbered list and ask: Which number, or 0 Abort? A number → rerun `preview` of step 7 with that heading as `--place-anchor`, keep it for this step and branch on the rerun by the step 7 list. 0 → stop.
  - `choices-needed` → say the stopped delivery was begun with section choices that are asked again: rerun `preview` of step 7 and branch by its list.
- `stopped` → `doc-changed` → `reason` `open-unsaved` → say the document is open in Obsidian with unsaved changes (a plugin that stamps the note on edit can cause that): the user saves it (Cmd+S) or closes it first; the payloads in `paths` already written count as done. `reason` `changed-since-read` or `unknown` → say the document was edited, or is open with unsaved edits, since the preview: the user saves it first; the payloads in `paths` already written count as done. `kado-write-failed` → say Kado refused or failed at `failed_step`; nothing more was written. Then ask `1 Retry · 2 Drop · 3 Abort`. Retry → rerun `deliver --stem <stem>` and branch on it by this list. Drop → step 9 with `<stem>`. Abort → stop; the next `/review` offers Resume or Drop.
- `not-found` → as in step 6.

## 9. Drop a failed delivery

```bash
python3 scripts/review-instructions.py drop --stem <stem>
```

Branch on `status` first:
- `withdrawn` → say the set was withdrawn (nothing for Hashi to apply) and name every file in `paths` so the user can delete them in Obsidian.
- `dropped` → say only the stage was removed (`removed`); nothing was in the inbox.
- `refused` → one line per problem:
  - `already-applied` → say Hashi already applied an action of this review, so nothing is withdrawn and nothing more is delivered; stop.
  - `setup-missing`, `setup-invalid` or `inbox-not-configured` → as the `refused` line of step 7: show `problems` and `errors` verbatim and stop.
- `stopped` → one line per problem:
  - `set-changed` → say the set changed between read and write; run `drop` once more.
  - `kado-write-failed` → say the withdrawal may be partly written (the set may already hold nothing for Hashi while the readable file still lists the actions) and nothing else changed; run `drop` once more. A second `kado-write-failed` → show it, say the next `/review` lists this review again and offers Drop, and stop.
- `not-found` → as in step 6.
