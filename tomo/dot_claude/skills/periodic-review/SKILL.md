---
name: periodic-review
description: MUST BE USED when the user runs /review, or asks for a weekly or monthly review of their periodic notes (the last finished week or month, a named period such as 2026-W13 or 2026-03, an @-picked weekly or monthly note), to continue, deliver or drop an open review, or to set up or change the review setup (/review setup). NOT for inbox triage (/inbox) and NOT for a single note from a template (/note).
user-invocable: true
allowed-tools: Read, Write, Bash
argument-hint: "a period (2026-W13, W13, 2026-03), month, setup, an @-picked weekly or monthly note, or nothing"
---
# Periodic Review
# version: 0.1.8

Review one finished week or month with the user: Pass 1 writes a review document to the inbox, Pass 2 turns the edited document into an instruction set. Run the steps in order. Run every script from the session's working directory (the instance root), never from the skill's base directory. Write only `tomo-tmp/review/<stem>/proposals.json` and `tomo-tmp/review/confirmed-<kind>.json` yourself; every other change goes through the scripts below.

## Rules

- Every script prints one JSON object. Read its `status` first and branch on it before any other key; a `stopped` or `refused` output is never read for `nothing_to_review`, `open_reviews`, `approved` or a plan.
- `status` `stopped` with `error`: show `error.kind` and `error.detail` verbatim and stop; nothing was written.
- A non-zero exit: show the output and the stderr line verbatim and stop.
- Every question is plain text in the visible reply: first the content, copied from the Read or Bash result, then the question, numbered on one line as `1 First · 2 Second` as the last line. Then end the turn.
- The next user message is the answer: a typed number or option word; when it is unclear, ask again in plain text.
- Show the `error`, `expected`, `example` and `errors` of a script verbatim, and the `hints` of step 2 and the `problems` of step 4; never paraphrase them. Every other `problems` entry, `warnings` entry and `notices` entry is said by the line its step gives it; without one, verbatim.
- Never quote `read.json`, a daily note, a journal answer or a tracker value in your reply; print the scripts' reports and `section_md` only.
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

Then the new request, by `request.kind`:
- `setup` → step 2 for `week`, then for `month`, each starting from `current.<kind>`; then stop.
- `week` or `month` with `setup.<kind>` `missing` → step 2 for that kind, then rerun the `start` call above (skip the open reviews already handled) and continue here.
- Otherwise → step 3.

## 2. Setup

`<kind>` is `week` or `month`. When `current.<kind>` is given, print it first: its values, or that none is saved, or its `invalid` pointers. Run:

```bash
python3 scripts/review-session.py match --kind <kind>
```

- `status` `stopped` → the stopped rule. `error.kind` `unsafe-format` → say the name format must not contain `/`, `\` or `..` and ask for another format; rerun `match` with it as `--format`.
- `template_candidates` is non-empty → say that no template is saved for `<kind>` and that these notes of the templates folder fit it; ask, numbered on one line with `0 none` last: `1 <name> · 2 <name> · 0 none`. End the turn. A number → `<template>` is `"<name>"`, the chosen name in double quotes; run:

```bash
python3 scripts/review-session.py match --kind <kind> --template <template>
```

with the flags of the last `match` call added, and continue with its output. `0` → `<template>` is `none`; continue with this output: no template, a plain note. Without `template_candidates`, `<template>` is `"<proposal.template>"` when `proposal.template` is set, else `none`.
- Every later `match` call of this step carries `--template <template>` and, once `<anchor>` is given, `--anchor "<anchor>"`: the script then lists no candidates and asks for no anchor, so each question is asked once. Never drop either flag from a rerun.
- Print `proposal`, `evidence` (`matched`, `unmatched`, `week_rule`, `folder_listing`, `format_problems`) and every line of `hints`.
- `evidence.folder_listing` is `kado-none` → the `hints` line says so; ask before proposing to create notes there.
- `proposal.template_kind` is `missing` → say that a plain note (title and review section) is proposed. `unreadable` → say the same and that the template may not be readable by the Kado key (no access).
- `daily_path_fix` is set → print `configured` and `found` and say the saved value is corrected to `found` only on Confirm.
- `evidence.week_rule` is `ambiguous` (week only) → ask in plain text, before the confirm question: "Which day does your week start on? Is week 1 the week with 1 January, or the first week with at least four days in the new year?" Map the answer to `--first-day <day>` (the day in lowercase) and `--min-days <n>` (`1` for the week with 1 January, `4` for at least four days), rerun `python3 scripts/review-session.py match --kind <kind> --folder "<folder>" --format "<format>" --first-day <day> --min-days <n> --template <template>` with the proposal's folder and format, and print the new proposal, evidence and hints.
- `needs_anchor` is true → say that no heading could be proposed for the place of the review section (no template, or none with a heading below its title); print `anchor_candidates` as a numbered list and ask: Which heading, by number or typed? End the turn. The answer is `<anchor>` and `proposal.place.anchor`; print the proposal with it in place. Never offer Confirm while `place.anchor` is null.

Ask `1 Confirm · 2 Correct · 3 Abort`.
- Correct: for the folder, the format, the first day, the week-1 rule or the template, rerun `match` with the corrected value as its flag (`--folder`, `--format`, `--first-day` with `--min-days`, `--template` — a corrected template is `<template>` from then on, `none` for no template), the proposal's values for the others, `--template <template>` and `--anchor "<anchor>"` when given, and print the new proposal, evidence and hints; for heading, place, own sections, daily sections or language, print the proposal with the corrected value; a corrected anchor is `<anchor>` from then on. Then ask `1 Confirm · 2 Correct · 3 Abort` again. Write nothing before Confirm.
- Abort: stop; nothing is saved and nothing is written. A kind confirmed and saved earlier in this run stays saved.
- Confirm: write `tomo-tmp/review/confirmed-<kind>.json` with the last `proposal` object as it is, the corrected values in place; add `daily_path_fix` from the `match` output only when the user confirmed it. Then run:

```bash
python3 scripts/review-session.py setup-input --kind <kind> --confirmed tomo-tmp/review/confirmed-<kind>.json
```

`status` `invalid` → show `errors` and `problems` verbatim and ask `1 Correct · 2 Abort`; Correct → the Correct branch above. `status` `ok` → run:

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
- `ok` with `nothing_to_review` true → say that no daily note of the period holds content, that an empty result may also mean the Kado key cannot read the folder, and stop; nothing is written.
- `ok` otherwise → print the `report` as the script prints it: per day the dailies found and their `state`, the `linked` notes with `state` `missing` or `failed`, `day_after`, `task_notes`, `weekly_status` and `weekly_notes` when present, `growth`, `kado_empty` with the access hint, and the pacing line: `calls`, `retried`, `waited_s`, `not_read`. When `advice` holds `raise-kado-limit`, say that Kado turned calls away for its rate limit and suggest raising Kado's rate limit. When `advice` holds `check-key-access`, say that Kado answered with nothing for the `kado_empty` sources and that the Kado key may not reach those folders; the user checks its access. When `not_read` is non-empty, say that these days or notes are missing from the review and that the document will name them at its top; never say that everything was read. Then step 5.

## 5. Propose and write the document

Read `tomo-tmp/review/<stem>/read.json` and `config/vault-config.yaml`; `<language>` is the value of `review.language` in the config file.

Write `tomo-tmp/review/<stem>/proposals.json`:

```json
{"language": "<language>", "groups": {"done": [{"text": "<proposal>", "sources": ["<path or stem from read.json>"]}], "open": [], "themes": [], "growth": [], "weekly_only": [], "not_in_weekly": []}}
```

- Every item is in `<language>`; its `sources` name the notes of `read.json` it rests on, at least one a daily of the period (for `weekly_only` a weekly note of the period). A second line of `text` becomes a continuation line of the item.
- `done`: what happened and got done; `open`: what stayed open; `themes`: a theme found on at least two days; `growth`: what the `growth` lists of `read.json` show; `weekly_only` and `not_in_weekly` (month only, when `read.json` holds `weekly`): what the `only_in_weekly_links` and `dailies_not_in_weekly` lists show. Leave out a group with nothing to propose.
- Habits are computed by the script: never propose them. Never propose text for the user's own sections.

Then run:

```bash
python3 scripts/review-doc.py write --stem <stem> --proposals tomo-tmp/review/<stem>/proposals.json
```

Branch on `status` first:
- `stopped` → the stopped rule; `problems` `kado-write-failed` → say nothing was written and stop.
- `refused` with `proposals-invalid` → show `errors` verbatim, rewrite `proposals.json` once and rerun `write`; a second `proposals-invalid` → show it and stop.
- `refused` with `doc-name-taken` → say `doc_path` is a note that is not Tomo's review document and nothing was overwritten; stop.
- `refused` with `review-exists` → say Tomo's review document for the period already exists at `doc_path` and that replacing it discards the user's edits in it; ask `1 Replace · 2 Keep it`. Replace → run `python3 scripts/review-doc.py replace --stem <stem> --confirm` and branch on its `status` by this list, `replaced` as `written`. Keep it → run `python3 scripts/review-doc.py replace --stem <stem> --abort` and say in one line that the document is kept.
- `refused` with any other problem (`read-missing`, `read-invalid`, `setup-missing`, `setup-invalid`, `inbox-not-configured`) → show `problems` and `errors` verbatim and stop.
- `written` → report `doc_path`, `target` and `target_exists`, `target_found_elsewhere` when set, `counts` per group and every `rejected` item with its `group`, `index` and `reason`. Then say: edit the document in Obsidian, tick `- [x] Approved` and run `/review` again. End the turn.

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
  - `nothing-to-deliver` → say nothing is ticked and ask `1 Start over · 2 Abort` as in step 6.
  - `place-missing`, `place-too-deep` or `user-heading-collision` with `mode` `replace` → say what is wrong with the heading above the Tomo marker in the target note: there is none (`place-missing`); it is one of the user's own sections, or an earlier heading of the same name stands above it (`user-heading-collision`); it is too deep to replace under, the review heading would pass level 5 (`place-too-deep`). Ask `1 Start over · 2 Abort`; Start over → step 4 with the entry's `period` and `kind`, Abort → stop.
  - `user-heading-collision` with `mode` `insert` or `new-note` after a heading pick (the rerun with `--place-anchor`) → say the target note holds a heading that clashes with the review: one named like the review heading, or the picked heading is one of the user's own sections; the user renames or removes the clashing heading in Obsidian. Ask `1 Start over · 2 Abort`; Start over → step 4 with the entry's `period` and `kind`, Abort → stop. Never print `headings` or ask for a number a second time.
  - `place-missing` or `place-too-deep` with `mode` `insert` or `new-note` → name `place.anchor` and `place.placement`, and say that this heading is not in the target note (`place-missing`), or that the review heading would pass level 5 under it (`place-too-deep`); print `headings` as a numbered list and ask: Which number, or 0 Abort? A number → rerun `preview` with that heading as `--place-anchor`, keep it for step 8 and branch on the rerun by this list. 0 → stop.
  - `user-heading-collision` with `mode` `insert` or `new-note` before any heading pick → say a heading of the user's with the same name is never replaced and the review never lands inside one of the user's own sections; print `headings` as a numbered list and ask: Which number, or 0 Abort? (as above).
  - `set-exists` → say an instruction set for this review waits for Hashi and is not applied yet; nothing is delivered. Stop.
  - `set-withdrawn` → say an earlier Drop emptied the instruction set but did not finish (its readable file may still list the actions); nothing is delivered. Ask `1 Drop · 2 Abort`; Drop → step 9 with `<stem>`, Abort → stop.
- `ok` with empty `problems` → print `target`, `mode` (`insert`, `replace` or `new-note`), `place` (`anchor`, `placement`, `level`) and `section_md` in full, in a fenced block, copied from the Bash result. Then one line for `mode` `replace`, per entry of `notices` and per flag set:
  - `mode` `replace` → the note already holds Tomo's review section; it is replaced, not added to.
  - `heading-renamed` → the marker was found under a renamed heading; the section is replaced there.
  - `target_appeared` true → the target note was created since Pass 1; the plan targets it instead of a new note.
  - `variant_missing` or `templater_hint` → the template's Tomo variant is gone, or the template holds Templater code; the readable instructions say to run Templater after the move.
  - `template_unmergeable` → a plain note is built instead.
  - `unlanded-items` → `unlanded` kept items are under a heading the parser does not know and do not land.

  Then ask `1 Deliver · 2 Abort` and end the turn. Say in one line before it that a change is made by editing the document and running `/review` again. Deliver → step 8. Abort → stop; nothing is written, the document stays open.

## 8. Deliver

```bash
python3 scripts/review-instructions.py deliver --stem <stem>
```

Add `--place-anchor "<heading>"` when a heading was chosen in step 7. Branch on `status` first:
- `delivered` or `resumed` → report `target`, `place`, `paths.set_json`, `paths.set_md` and `paths.note` when set, and "Next: review and apply the instruction set in Hashi, or by hand with the readable instructions." Then the step 7 notice lines for `notices` and `target_appeared`.
- `refused` → `name-taken` → say a note at `exists_path` is not Tomo's and nothing was overwritten; stop. `set-exists` or `set-withdrawn` → as in step 7. Any other → the step 7 lines; nothing was written.
- `stopped` → `doc-changed` → say the document was edited, or is open with unsaved edits, since the preview: save it and run `/review` again; the payloads in `paths` already written count as done, and the next `/review` offers Resume or Drop. `kado-write-failed` → say Kado refused or failed at `failed_step`; nothing more was written; the next `/review` offers Resume or Drop. Stop.
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
