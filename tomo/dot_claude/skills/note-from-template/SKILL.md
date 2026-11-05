---
name: note-from-template
description: MUST BE USED when the user runs /note, or asks to create a note from one of their vault templates (meeting note, person note, book note, any template kind) filled from given material or an inbox note, or to set a template's /note process (/note --process <template>). NOT for free-form artifacts (overviews, lists, .base, .canvas) — those are inbox-author.
user-invocable: true
allowed-tools: Read, Write, Bash, AskUserQuestion
argument-hint: "what the note is about, optionally naming an inbox note; or --process <template>"
---
# Note From Template
# version: 0.1.3

Fill one vault template into a new note with the user, then deliver the note and its instruction set to the inbox. Run the steps in order. Run every script from the instance root. Write only `draft.md`, `tomo-tmp/note/note-include.json` and `tomo-tmp/note/process-guidance.md` yourself; every other change goes through the scripts below.

## Rules

- Before every AskUserQuestion call, print as visible text everything the question refers to (lists, previews, covered points, the draft), in the same message. Text in thinking counts as not printed.
- Ask with at most four options per question.
- Ask in the language the user writes in; keep the template's headings.
- Read Templater code (`<%` … `%>`) as a hint only; never run it and leave none in the draft.
- On Abort at any question, run `python3 scripts/note-instructions.py drop --stem <stem>` when a stem exists and confirm in one line that the draft was discarded. Write nothing else. A saved `note_include` stays saved.
- Exit 2 of `new` or `stage` is refused input (a `--source` outside the inbox, a title that is blank, starts with a dot, holds an invisible character or holds `{{` or `<%`, a destination that is not a relative vault folder): name what was refused and ask for another value; rerun the same call with it.
- Never run `deliver` before `stage` has recorded a title.
- Show script error text verbatim.

## 1. Start

Run:

```bash
python3 scripts/note-session.py start --args='<request>'
```

`<request>` is the skill's arguments (`$ARGUMENTS`) verbatim inside single quotes, each `'` written as `'\''`. Keep the request text in the conversation.

For each stem in `stale_stages`: say in one line that an interrupted draft was discarded, then run `python3 scripts/note-instructions.py drop --stem <stem>`.

Handle every entry of `kept_drafts` before the new request. Print each by title, template and created time, then ask per entry: Resume / Drop.
- An entry with an empty `failed_step` is an interrupted delivery: offer Resume / Drop like any other kept draft. Never drop a kept draft without asking.
- Resume: run step 7 for that stem as a resume. Continue with the new request after it ends.
- Drop: run `python3 scripts/note-instructions.py drop --stem <stem>` and confirm in one line.

Then:
- `mode` is `process` → step 9.
- `include_configured` is false → step 2.
- Otherwise → step 3.

## 2. First-run setup

1. Run `python3 scripts/note-session.py match --globs "*"` to see every template name. When `folder_listed` is 0, give the step 3 empty-folder message and stop.
2. Propose filename globs that select the note templates (e.g. a shared prefix). Run `python3 scripts/note-session.py match --globs "<g1>,<g2>"`.
3. Print the proposed globs, `matched`, `unmatched` and `excluded_daily`, then ask: Confirm / Correct / Abort.
4. On Correct, take the user's globs, rerun `match`, reprint and ask again. Write nothing before Confirm.
5. On Abort, stop; nothing is written.
6. On Confirm, write `tomo-tmp/note/note-include.json` as `{"note_include": ["<g1>", "<g2>"]}`, then run:

```bash
python3 scripts/vault-config-writer.py templates-include --input tomo-tmp/note/note-include.json
rm -f tomo-tmp/note/note-include.json
```

On a non-zero exit, show the error and stop. Otherwise rerun the step 1 `start` call (skip kept drafts already handled) and go to step 3.

## 3. Choose the template

When `folder_listed` is 0, say: "The template folder is empty or not readable by the Kado key." Then: "Grant the Kado key read access to the template folder (`templates.base_path`), or do not use `/note`." Show `listing_error` verbatim when it is set. Never say that no template exists. Stop.

Judge which entries of `candidates` fit the request and its material.
- When one candidate fits, name it in one line and continue without asking.
- When several fit, print them as a numbered list, then ask which one (up to four options; the user may type another number), with Abort.
- When none fits, say "No selected template fits." and ask: Adjust patterns / inbox-author / Abort. Adjust patterns → step 2, starting from `note_include`. inbox-author → hand the request to the `inbox-author` skill and stop. Abort → stop.

## 4. Stage the draft

When the material is an inbox note, pass its vault path as `--source`; otherwise omit `--source`:

```bash
python3 scripts/note-instructions.py new --template "<template path>" --source "<inbox note path>"
python3 scripts/template-outline.py --template "<template path>" --stage <stem>
python3 scripts/note-process.py read --template <template stem> --outline tomo-tmp/note/<stem>/outline.json
```

`<stem>` is the `stem` from `new`; keep it and `default_destination`. `<template stem>` is the template's filename without `.md`.

- `new` exits 1: say the source could not be read, then ask: Another source / Abort. Another source → rerun `new` with it. Abort → stop.
- When `template-outline.py` exits 1, name the template, show its `error` verbatim and say the template may not be readable by the Kado key. Then: "Grant the Kado key read access to the template folder (`templates.base_path`), or do not use `/note`." Ask: Another template / Abort. Another template → drop the stem, return to step 3 without this template. Abort → drop.
- `template-outline.py` exits 2: show its `error`, drop the stem and stop.
- When `read` reports `error`, say in one line that the process file is ignored and why; continue with the template alone.
- For each name in `missing_required`, say in one line that the template no longer has this required point; continue without it.
- `frontmatter_ok` false: draft the note with a frontmatter block anyway.

Read `tomo-tmp/note/<stem>/template.md`, `tomo-tmp/note/<stem>/outline.json` and, when it exists, `tomo-tmp/note/<stem>/source.md`.

## 5. Ask for open points

The points are every `frontmatter` key, every heading and every token with `prefilled` false in the outline. A point is open when neither the material nor a prefilled value fills it. Required points are the process `required` list minus `missing_required`.

1. Print which points the material covers, then the open points.
2. When no point is open, ask nothing and go to step 6.
3. Ask at most four open points per round, in at most two rounds. Required points first. Order and weight the questions by the process `guidance`. Offer a skip option for optional points.
4. Round 2 takes the remaining open points plus gaps the answers opened.
5. For each required point still unanswered, ask it again with no skip option. The user can only answer or abort. Any non-empty answer, "none" included, answers a required point.
6. Optional points still open stay empty under their heading and go into the skipped line of step 6.
7. Abort at any question → drop.

## 6. Draft

Write `tomo-tmp/note/<stem>/draft.md` from `template.md`: fill every point from the material and the answers, keep `{{source_link}}` as written, keep every heading, leave no other `{{…}}` token, add no `tomo:` key. Choose a title from the material. Then run:

```bash
python3 scripts/note-instructions.py stage --stem <stem> --title "<title>"
```

When `check.ok` is false, fix `draft.md` and rerun `stage` before showing anything.

After every `stage`, print `tomo-tmp/note/<stem>/note.md` in full, read fresh from disk. Never print `draft.md`. Print this header above the fenced note:

```
Template: <template stem> · Final name: <destination_file> · In the inbox until applied: <inbox_file name>
Skipped, left empty: <points>
Source <source path> is deleted when you apply the instruction set in Hashi.
```

Omit the skipped line when nothing was skipped; omit the source line when there is no source or `keep_source` is true.

Then ask: Deliver / Change something / Abort.
- Change something: apply the change; rewrite `draft.md`, rerun `stage` and reprint `note.md` with the header, then ask again. A new title goes in `--title "<title>"`, a new destination in `--destination "<folder>"`, keeping the source in `--keep-source true` (`--keep-source false` to undo).
- During a resume with a non-empty `steps_done`, title and destination are frozen; once `instructions_json` is in `steps_done`, keeping the source is frozen too. When `stage` reports `frozen: true`, say in one line that the requested change can no longer be made: title and destination once a delivery step landed, keeping the source once the instruction set exists. Keep the staged values.
- Deliver → step 7.
- Abort → drop.

## 7. Deliver

```bash
python3 scripts/note-instructions.py deliver --stem <stem>
```

- Exit 0 (`delivered`): report `note_path`, `instructions_json`, `instructions_md`, whether the source was marked, and "Next: review and apply the instruction set in Hashi." When `source_marked` is false and the draft has a source, say in one line that the source was not marked (it was moved or deleted). Then step 8.
- On exit 3, read `steps_done` in `tomo-tmp/note/<stem>/meta.json`. Never overwrite.
  - `steps_done` empty: offer Rename / Abort, naming `exists_path`. Rename: ask for a new title, run `stage --stem <stem> --title "<new title>"`, reprint `note.md` with the header, rerun `deliver`. Abort → drop.
  - `steps_done` non-empty: offer Keep / Drop, naming `exists_path`. Keep: leave the draft for a later `/note`. Drop: name the files of `steps_done` (`note` → `note_path`, `instructions_json`, `instructions_md`) so the user can delete them in Obsidian, then run `drop`.
- On exit 1 with `status` `withdrawn`, say nothing was written and why the action was withdrawn, then offer Rename / Abort as for exit 3 with `steps_done` empty.
- On exit 1 with `status` `failed`, report the failed `step`; the draft stays for the next `/note`. When `step` is empty, the filled-note check or the frontmatter stamp failed instead: fix `draft.md`, rerun `stage`, reprint and return to the step 6 question (Deliver / Change something / Abort).
- Exit 2: show the error and stop; the draft stays.

## 8. Process offer

Ask once, after the delivery report, only when `read` reported `exists` false and `declined` false and the session showed at least one signal:
- the destination differs from `default_destination`;
- a re-asked skipped point was answered;
- the user asked for a question order.

Otherwise, or when `read` reported `exists` or `declined` true, do not ask.

Print what would be saved, then ask: Save / Not now / Never for this template.
- Save: write the requested order as text to `tomo-tmp/note/process-guidance.md` when one was asked for, then run (one `--required` per point; omit flags without a value):

```bash
python3 scripts/template-outline.py --template "<template path>" --out tomo-tmp/note/process-outline.json
python3 scripts/note-process.py write --template <template stem> --outline tomo-tmp/note/process-outline.json --destination "<folder>" --required "<point>" --guidance-file tomo-tmp/note/process-guidance.md
rm -f tomo-tmp/note/process-outline.json tomo-tmp/note/process-guidance.md
```

  On exit 1, name the points in `rejected_required` in one line and rerun `write` without them.
- Not now: write nothing.
- Never for this template: run `python3 scripts/note-process.py decline --template <template stem>`.

## 9. Process mode

When `process_template_path` is empty, say that the template is unknown and stop; write nothing. Otherwise `<template stem>` is `process_template`:

```bash
python3 scripts/template-outline.py --template "<process_template_path>" --out tomo-tmp/note/process-outline.json
python3 scripts/note-process.py read --template <template stem> --outline tomo-tmp/note/process-outline.json
```

1. Print the current values (`destination`, `required`, `guidance`) when `exists` is true, or say there is no process yet. When `error` is set, print it.
2. Ask for the destination folder (keep current / default / another folder).
3. Print the outline's headings, then ask which are required, four headings per question with multi-select, until every heading was offered.
4. Ask for the guidance text; write it to `tomo-tmp/note/process-guidance.md`.
5. Run `python3 scripts/note-process.py write --template <template stem> --outline tomo-tmp/note/process-outline.json` with `--destination "<folder>"`, one `--required "<point>"` per point and `--guidance-file tomo-tmp/note/process-guidance.md`. Exit 2 on a refused destination: ask for another folder and rerun.
6. Confirm in one line, then run `rm -f tomo-tmp/note/process-outline.json tomo-tmp/note/process-guidance.md`.

On Abort at any question, run `rm -f tomo-tmp/note/process-outline.json tomo-tmp/note/process-guidance.md` and write nothing.
