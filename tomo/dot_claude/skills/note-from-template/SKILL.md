---
name: note-from-template
description: MUST BE USED when the user runs /note, or asks to create a note from one of their vault templates (meeting note, person note, book note, any template kind) filled from given material or an inbox note, or to set a template's /note process (/note --process <template>). NOT for free-form artifacts (overviews, lists, .base, .canvas) — those are inbox-author.
user-invocable: true
allowed-tools: Read, Write, Bash, AskUserQuestion, Skill
argument-hint: "what the note is about, optionally naming an inbox note; or --process <template>"
---
# Note From Template
# version: 0.2.11

Fill one vault template into a new note with the user, then deliver the note and its instruction set to the inbox. Run the steps in order. Run every script from the session's working directory (the instance root), never from the skill's base directory. Write only `draft.md`, `tomo-tmp/note/note-include.json` and `tomo-tmp/note/process-guidance.md` yourself; every other change goes through the scripts below.

## Rules

# STRICT — A dialog for a draft or a list carries the content in every option's `preview`, copied from the tool result; never a dialog without it.
# Why: the content went into thinking only, so the dialog came without it.

- The preview-dialog questions are the step 2 glob question, the step 6 approval question and the step 8 process offer. The description-dialog questions are the step 3 template choice with at most three candidates and the step 9 destination question. Every other question about a draft or a list, and every free-text question, is plain text only: the step 3 template choice with more than three candidates, the step 5 question rounds, the step 9 required headings, guidance and another-folder name.
- A preview-dialog question calls AskUserQuestion with one option per answer, in the order of its numbered option line, at most four options. Every option carries the same `preview`: the content its step names, copied from the Read or Bash result (a tool result is not visible to the user), in full, never a summary.
- A description-dialog question calls AskUserQuestion with one option per answer and a `description` on each option, at most four options; it needs no `preview`.
- A plain-text question goes in the visible reply text: first the content, copied from the Read or Bash result, then the question, numbered on one line as `1 First · 2 Second` as the last line when it has fixed options. Then end the turn.
- Ask a dialog question in plain text, in that form, when AskUserQuestion is not available, and when the user says they cannot see the content (for example "show me the draft"): print the content as text and call no dialog for that question.
- The next user message is the answer: the dialog choice, or a typed number or option word; dialog "Other" text is read the same way; when it is unclear, ask again in plain text.
- Ask every other question with AskUserQuestion, with at most four options per question.
- The question text of every AskUserQuestion call names what it is about: the draft's title (the template's filename without `.md` when untitled) and created time, the `exists_path`, the reason the action was withdrawn, or the template or source with its one-line error; for the glob question the proposed globs with the `matched` count, for the template choice the source note or the request, for the process offer and the destination question the template stem.
- Ask in the language the user writes in; keep the template's headings.
- Read Templater code (`<%` … `%>`) as a hint only; never run it and leave none in the draft.
- On Abort at any question, run `python3 scripts/note-instructions.py drop --stem <stem>` when a stem exists and confirm in one line that the draft was discarded. Write nothing else. A saved `note_include` stays saved.
- Exit 2 of `new` or `stage` whose error starts with `note-instructions: --title`, `note-instructions: --destination` or `note-instructions: --source` is refused input (a `--source` outside the inbox, a title that is blank, starts with a dot, holds an invisible character or holds `{{` or `<%`, a destination that is not a relative vault folder): name what was refused and ask for another value; rerun the same call with it.
- Any other exit 2 of `new` or `stage` (config, local I/O, stem or `meta.json`): show the error verbatim and stop; do not drop the stem.
- Never run `deliver` before `stage` has recorded a title.
- When `template-outline.py` exits 1, name the template, show its `error` verbatim and say the template may not be readable by the Kado key. Then: "Grant the Kado key read access to the template folder (`templates.base_path`), or do not use `/note`." When `template-outline.py` exits 2, show its `error`. This is the outline failure report; steps 4, 8 and 9 say what follows it.
- Show script error text verbatim.

## 1. Start

Run:

```bash
python3 scripts/note-session.py start --args='<request>'
```

`<request>` is the skill's arguments (`$ARGUMENTS`) verbatim inside single quotes, each `'` written as `'\''`. Keep the request text in the conversation.

For each stem in `stale_stages`: say in one line that a draft whose state could not be read was discarded, then run `python3 scripts/note-instructions.py drop --stem <stem>`.

Handle every entry of `kept_drafts` before the new request. Print each by title, template and created time, then ask per entry: Resume / Drop.
- An entry with an empty `failed_step` is an interrupted delivery: offer Resume / Drop like any other kept draft. Never drop a kept draft without asking.
- Resume: run step 7 for that stem as a resume; skip step 8 for it. Continue with the new request after it ends.
- Drop: when the entry's `steps_done` is non-empty, name each landed file by kind (`note` → the note, `instructions_json` → the instruction set JSON, `instructions_md` → the instruction set MD), say they are in the inbox with names starting `<stem>_` and that the user can delete them in Obsidian. When `steps_done` is empty and the entry's `frozen` is true, say the note may already be in the inbox with a name starting `<stem>_`. When `steps_done` is empty and `frozen` is false, say that nothing landed in the inbox. Never build a vault path yourself. Then run `python3 scripts/note-instructions.py drop --stem <stem>` and confirm in one line.

Then handle every entry of `unfinished_drafts` before the new request. Print each by title (the template's filename without `.md` when `title` is empty), template and created time, then ask per entry: Continue / Discard. Never drop an unfinished draft without asking.
- Continue with `staged` true: run `python3 scripts/note-instructions.py stage --stem <stem>`, then run step 6 for that stem from "When `check.ok` is false": ask the step 6 approval question `1 Deliver · 2 Change something · 3 Abort` with `note.md` and the header as the preview. `<template stem>` is the entry's `template` filename without `.md`. The source in the header is the entry's `source_path`; omit the skipped line, and skip step 8 for it. Continue with the new request after it ends.
- Continue with `staged` false: for that stem, run the step 4 `template-outline.py` and `read` calls with the entry's `template` as `<template path>`; never run `new` again. Handle their exits as step 4 says, read the stage files, then run step 5 for that stem with `source.md` as the material when it exists, and go on from there. Continue with the new request after it ends.
- Discard: run `python3 scripts/note-instructions.py drop --stem <stem>` and say in one line that nothing landed in the inbox.

Then:
- `mode` is `process` → step 9.
- `include_configured` is false → step 2.
- Otherwise → step 3.

## 2. First-run setup

1. Run `python3 scripts/note-session.py match --globs "*"` to see every template name. When `folder_listed` is 0, give the step 3 empty-folder message and stop.
2. Propose filename globs that select the note templates (e.g. a shared prefix). Run `python3 scripts/note-session.py match --globs "<g1>,<g2>"`.
3. Ask `1 Confirm · 2 Correct · 3 Abort` in a dialog whose preview is the proposed globs, `matched`, `unmatched` and `excluded_daily`.
4. On Correct, take the user's globs, rerun `match` and ask again `1 Confirm · 2 Correct · 3 Abort` with the new globs, `matched`, `unmatched` and `excluded_daily` as the preview. Write nothing before Confirm.
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
- When several fit, print them as a numbered list. With at most three candidates ask: Which number, or 0 Abort? in a dialog with one option per candidate, its `description` the reason it fits, and Abort. With more than three candidates ask in plain text only: Which number, or 0 Abort? Any number from the list is valid.
- When none fits, say "No selected template fits." and ask: Adjust patterns / inbox-author / Abort. Adjust patterns → step 2, starting from `note_include`. inbox-author → invoke the `inbox-author` skill with the Skill tool, passing the request and the line "Compose a free-form note with requested type `default`; do not look for another template.", and stop. Abort → stop.

## 4. Stage the draft

When the material is an inbox note, pass its vault path as `--source`; otherwise omit `--source`:

```bash
python3 scripts/note-instructions.py new --template "<template path>" --source "<inbox note path>"
python3 scripts/template-outline.py --template "<template path>" --stage <stem>
python3 scripts/note-process.py read --template <template stem> --outline tomo-tmp/note/<stem>/outline.json
```

`<stem>` is the `stem` from `new`; keep it and `default_destination`. `<template stem>` is the template's filename without `.md`.

- `new` exits 1: say the source could not be read, then ask: Another source / Abort. Another source → rerun `new` with it. Abort → stop.
- `template-outline.py` exits 1: give the outline failure report. Ask: Another template / Abort. Another template → drop the stem, return to step 3 without this template. Abort → drop.
- `template-outline.py` exits 2: show its `error`, drop the stem and stop.
- When `read` reports `error`, say in one line that the process file is ignored and why; continue with the template alone.
- For each name in `missing_required`, say in one line that the template no longer has this required point; continue without it.
- `frontmatter_ok` false: draft the note with a frontmatter block anyway.

Read `tomo-tmp/note/<stem>/template.md`, `tomo-tmp/note/<stem>/outline.json` and, when it exists, `tomo-tmp/note/<stem>/source.md`.

## 5. Ask for open points

The points are every `frontmatter` key, every heading and every token with `prefilled` false in the outline. A point is open when neither the material nor a prefilled value fills it. Required points are the process `required` list minus `missing_required`.

1. Print which points the material covers, then the open points.
2. When no point is open, ask nothing and go to step 6.
3. Ask in plain text, as numbered questions, at most four open points per round, in at most two rounds. Required points first. Order and weight the questions by the process `guidance`. Mark each optional point as skippable; a skip is allowed only for optional points.
4. Round 2 takes the remaining open points plus gaps the answers opened.
5. For each required point still unanswered, ask it again in plain text with no skip option. The user can only answer or abort. Any non-empty answer, "none" included, answers a required point.
6. Optional points still open stay empty under their heading and go into the skipped line of step 6.
7. Abort at any question → drop.

## 6. Draft

Write `tomo-tmp/note/<stem>/draft.md` from `template.md`: fill every point from the material and the answers, keep `{{source_link}}` as written, keep every heading, leave no other `{{…}}` token, add no `tomo:` key. Choose a title from the material. Then run:

```bash
python3 scripts/note-instructions.py stage --stem <stem> --title "<title>"
```

When `check.ok` is false, fix `draft.md` and rerun `stage` before showing anything.

After every `stage`, show `tomo-tmp/note/<stem>/note.md` in full, read fresh from disk, as the approval question below says. Never show `draft.md`. Put this header above the fenced note:

```
Template: <template stem> · Final name: <destination_file> · In the inbox until applied: <inbox_file name>
Skipped, left empty: <points>
Source <source path> is deleted when you apply the instruction set in Hashi.
```

Omit the skipped line when nothing was skipped; omit the source line when there is no source or `keep_source` is true.

Then ask `1 Deliver · 2 Change something · 3 Abort` in a dialog whose preview is the header and the full fenced `note.md`, copied from the Read result. This holds after the first draft, after every Change something, at the Continue of a staged draft and after a restage of a failed delivery. The Rename reprint before `deliver` is visible reply text.
- Change something: apply the change; rewrite `draft.md`, rerun `stage`, then ask `1 Deliver · 2 Change something · 3 Abort` again with the new header and `note.md` as the preview. A new title goes in `--title "<title>"`, a new destination in `--destination "<folder>"`, keeping the source in `--keep-source true` (`--keep-source false` to undo).
- During the resume of a kept draft whose `frozen` is true, title and destination are frozen. When `stage` reports `frozen: true`, say in one line that the requested change can no longer be made: title and destination once a delivery step may have landed, keeping the source once the instruction set may have landed. Keep the staged values.
- Deliver → step 7.
- Abort → drop.

## 7. Deliver

```bash
python3 scripts/note-instructions.py deliver --stem <stem>
```

- Exit 0 (`delivered`): report `note_path`, `instructions_json`, `instructions_md`, whether the source was marked, and "Next: review and apply the instruction set in Hashi." When `source_marked` is false and the draft has a source, say in one line that the source was not marked (it was moved or deleted). Then step 8.
- On exit 3, read `frozen` and `steps_done` from the `deliver` output. Never overwrite.
  - `frozen` false: offer Rename / Abort, naming `exists_path`. Rename: ask for a new title, run `stage --stem <stem> --title "<new title>"`, reprint `note.md` with the header, rerun `deliver`. Abort → drop.
  - `frozen` true: offer Keep / Drop, naming `exists_path`. Keep: leave the draft for a later `/note`. Drop: name the files of `steps_done` (`note` → `note_path`, `instructions_json`, `instructions_md`) so the user can delete them in Obsidian; when `steps_done` is empty, say the note may already be in the inbox as `note_path`. Then run `drop`.
- On exit 1 with `status` `withdrawn`, say nothing was written in this run and why the action was withdrawn, then offer Drop / Abort only (no Rename, no Keep). On either answer: when `steps_done` is non-empty, first name its files by kind (`note` → `note_path`, `instructions_json`, `instructions_md`) so the user can delete them in Obsidian; when `steps_done` is empty and `frozen` is true, say the note may already be in the inbox as `note_path`. Then run `drop`.
- On exit 1 with `status` `failed`, report the failed `step`; the draft stays for the next `/note`. When `step` is empty, the filled-note check or the frontmatter stamp failed instead: fix `draft.md`, rerun `stage` and return to the step 6 question (`1 Deliver · 2 Change something · 3 Abort`, the new header and `note.md` as the preview).
- Exit 2: show the error and stop; the draft stays.

## 8. Process offer

Never ask after a resumed delivery.

Ask once, after the delivery report, only when `read` reported `exists` false and `declined` false and the session showed at least one signal:
- the destination differs from `default_destination`;
- a point named in the `Skipped, left empty:` line was filled through Change something before Deliver;
- the user asked for a question order.

Otherwise, or when `read` reported `exists` or `declined` true, do not ask.

Ask `1 Save · 2 Not now · 3 Never` in a dialog whose preview is what would be saved.
- Save: write the requested order as text to `tomo-tmp/note/process-guidance.md` when one was asked for, then run:

```bash
python3 scripts/template-outline.py --template "<template path>" --out tomo-tmp/note/process-outline.json
```

  When `template-outline.py` exits 1 or 2, give the outline failure report, then run `rm -f tomo-tmp/note/process-outline.json tomo-tmp/note/process-guidance.md`, write nothing and stop. On exit 0, run (one `--required` per point; omit flags without a value):

```bash
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
```

When `template-outline.py` exits 1 or 2, give the outline failure report, then run `rm -f tomo-tmp/note/process-outline.json tomo-tmp/note/process-guidance.md`, write nothing and stop. On exit 0, run:

```bash
python3 scripts/note-process.py read --template <template stem> --outline tomo-tmp/note/process-outline.json
```

1. Print the current values (`destination`, `required`, `guidance`) when `exists` is true, or say there is no process yet. When `error` is set, print it.
2. Ask `1 Keep current · 2 Default · 3 Another folder` in a dialog with a `description` on each option. Offer Keep current only when `exists` is true and `destination` is not empty; without it ask `1 Default · 2 Another folder` the same way. Keep current → `--destination "<destination>"` with the current value. Default → omit `--destination`; notes then go to the atomic-note folder. Another folder → ask in plain text for it and pass it as `--destination "<folder>"`.
3. Print the outline's headings as a numbered list, then ask in plain text which are required; the user names them by number or heading, or none.
4. Ask in plain text for the guidance text; write it to `tomo-tmp/note/process-guidance.md`.
5. Run `python3 scripts/note-process.py write --template <template stem> --outline tomo-tmp/note/process-outline.json` with the step 2 `--destination` (none for Default), one `--required "<point>"` per point and `--guidance-file tomo-tmp/note/process-guidance.md`. Exit 2 on a refused destination: ask in plain text for another folder and rerun.
6. Confirm in one line, then run `rm -f tomo-tmp/note/process-outline.json tomo-tmp/note/process-guidance.md`.

On Abort at any question, run `rm -f tomo-tmp/note/process-outline.json tomo-tmp/note/process-guidance.md` and write nothing.
