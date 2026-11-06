# Spec 044 live-walk checklist (/note, #169)

Purpose: T4.2. The owner walks `/note` on `tomo-instance` against the test vault; Claude reads the transcripts and fills Outcome and Evidence (session id) per line. Failures become fixes before merge or are recorded with the owner's decision.

Prerequisites:

1. `./scripts/update-tomo.sh --instance tomo-instance --yolo` from the branch or `main` as the owner decides. NEVER `tomo-privat`. Grep the instance for `# version: 0.2.3` in `note-from-template/SKILL.md` afterwards.
2. Restart the Tomo session after the sync.
3. Test vault (host filesystem, for inspection only): `/Volumes/Moon/Coding/MiYo/temp/Privat-Test/`, inbox `100 Inbox/`. Kado must be running; the vault needs several templates, at least one with required-looking points, and an inbox note with partial material.
4. Lines are ordered for one session: setup first, destructive cases last (group 7). Group 7 ends with a restore step; do not skip it.

Outcome: pass / fail / n.a. Evidence: session id of the transcript.

## 1. Setup and choice

| # | Criteria | Do | Expect | Outcome | Evidence |
|---|----------|----|--------|---------|----------|
| 1.1 | F1-AC1, F1-AC6 | With no `templates.note_include` set, run `/note <request>`. | Proposed globs printed with matched, unmatched and excluded daily lists before the Confirm / Correct / Abort question. The daily template is excluded. | | |
| 1.2 | F1-AC2 | Choose Correct and give other globs. | `match` is rerun and the lists reprinted before asking again; `vault-config.yaml` unchanged so far. | | |
| 1.3 | F1-AC3 | Choose Confirm. | `note_include` written via `templates-include`; the run continues to template choice. Only that key changed in `vault-config.yaml`. | | |
| 1.4 | F2-AC1 | Request that fits exactly one template. | The template is named in one line, no question. | | |
| 1.5 | F2-AC2 | Request that fits several templates. | Numbered list printed first; question offers at most three candidates plus Abort. | | |
| 1.6 | F2-AC2 | Type another listed number (not one of the options). | That template is used. | | |
| 1.7 | F2-AC3 | Request that fits no template. Choose inbox-author. | "No selected template fits." then Adjust patterns / inbox-author / Abort. `inbox-author` is invoked with requested type `default`, composes a free-form note and looks for no other template. | | |
| 1.8 | F2-AC3 | Same request, choose Adjust patterns. | Returns to the glob setup starting from `note_include`. | | |

## 2. Dialogue

| # | Criteria | Do | Expect | Outcome | Evidence |
|---|----------|----|--------|---------|----------|
| 2.1 | F3-AC1, F3-AC2 | Request naming an inbox note as source, template with open and required points. | Covered points printed, then open points; at most four per round, at most two rounds, required first. | | |
| 2.2 | F3-AC5, F3-AC6 | Leave a required point unanswered once, then answer it with "none". | Asked again with no skip option; "none" accepted. | | |
| 2.3 | F3-AC4, F4-AC1 | Skip an optional point. | Heading stays empty; draft printed from `note.md` with the header (template, final name, inbox file, source deletion) and "Skipped, left empty: <points>". | | |
| 2.4 | F4-AC2, F4-AC3 | Choose Change something: edit content, then title, destination and keep-source. | Full note reprinted with the header after each change; header shows the new title, destination, keep-source. | | |
| 2.5 | F4-AC4, F6-AC5 | Start a second `/note`, reach the draft, choose Abort. | One-line discard confirmation; no stage directory in `tomo-tmp/note/`; nothing in the inbox; source untouched; confirmed `note_include` stays. | | |

## 3. Delivery

| # | Criteria | Do | Expect | Outcome | Evidence |
|---|----------|----|--------|---------|----------|
| 3.1 | F4-AC4, F5-AC1, F5-AC2, F5-AC3, F5-AC7, F6-AC6 | Run a note with an inbox-note source, approve with Deliver. | Report names note path, both set paths, source marked, "Next: review and apply the instruction set in Hashi." Inbox holds `<stem>_...` note, `_instructions.json`, `_instructions.md`, flat. Stage directory gone. Set has `delete_source` for the source. | | |
| 3.2 | F5-AC5 | In Hashi apply the set (note moves, then the source goes to trash). | Both effects happen. | | |
| 3.3 | F5-AC5 | Run `/inbox`. | Neither the note, nor the peer instruction files, nor the marked source is proposed as new. | | |
| 3.4 | F5-AC6 | Fresh draft whose final name already exists in the destination (or inbox). Deliver. | `EXISTS:` clash, exit 3, `frozen` false; Rename / Abort offered naming the path; nothing overwritten. Rename: new title, reprint, redeliver succeeds. | | |
| 3.5 | F5-AC5, F5-AC7 | Reach the draft with a source, then in Obsidian move or delete the source before Deliver. | Note and set delivered; report says the source was not marked (moved or deleted). | | |

## 4. Process files

| # | Criteria | Do | Expect | Outcome | Evidence |
|---|----------|----|--------|---------|----------|
| 4.1 | F7-AC6 | Deliver with a destination different from the default, template without a process file. | After the delivery report: Save / Not now / Never for this template. | | |
| 4.2 | F7-AC6 | Deliver a run where a point from "Skipped, left empty:" was filled through Change something before Deliver (default destination). | Process offer appears (signal 2). | | |
| 4.3 | F7-AC9 | Answer "Never for this template". | Decline marker written. | | |
| 4.4 | F7-AC7, F7-AC9 | Second run with the same template and a signal. | No process offer. | | |
| 4.5 | F7-AC7 | Resume a kept draft to delivery (after group 7) with a signal present. | No process offer after a resumed delivery. Run this line after 7.6. | | |
| 4.6 | F7-AC10 | `/note --process <template>` with an existing process. Choose Keep current. | Current values printed, destination kept, required points asked from the outline (four headings per question), guidance asked, written. | | |
| 4.7 | F7-AC10 | `/note --process <template>`, choose Another folder. | Given folder saved as `destination`; replaces a decline marker if present. | | |
| 4.8 | F7-AC1, F7-AC10 | `/note --process <template>`, choose Default. | No `destination` saved; a later `/note` for it delivers to the atomic-note folder. | | |
| 4.9 | F7-AC1 | Hand-edit a process file in `config/note-processes/` to an empty `destination:` or `offer:` key, run `/note` with it. | File still used; no error. | | |
| 4.10 | F7-AC11 | `/note --process nosuchtemplate`. | "Template is unknown"; nothing written. | | |

## 5. Refusals (exit 2 of `new` / `stage`)

| # | Criteria | Do | Expect | Outcome | Evidence |
|---|----------|----|--------|---------|----------|
| 5.1 | no AC id (skill rule) | At the draft, change title to one starting with a dot. | Refusal named, another title asked, same call rerun; nothing dropped. | | |
| 5.2 | no AC id (skill rule) | Change destination to one outside the vault tree (absolute or `..`). | Refusal named, another value asked. | | |
| 5.3 | no AC id (skill rule) | Name a `--source` outside the inbox. | Refusal named, another source asked. | | |
| 5.4 | no AC id (skill rule) | Produce a non-refusal exit 2 safely: make `tomo-tmp/note/<stem>/meta.json` unreadable (`chmod 000`) on a throwaway draft, then Change something. Restore with `chmod 644`. | Error shown verbatim, run stops, stem NOT dropped (directory still present). | | |

## 6. inbox-author

| # | Criteria | Do | Expect | Outcome | Evidence |
|---|----------|----|--------|---------|----------|
| 6.1 | no AC id (PRD scope) | Ask `inbox-author` for an overview. | Behaves as before (unchanged). | | |
| 6.2 | no AC id (PRD scope) | Ask `inbox-author` for a template kind note (e.g. meeting note). | Points the user to `/note`. | | |

## 7. Failed delivery and resume (destructive, last)

Safe failure recipes on `tomo-instance`: interrupt the session (Esc / Ctrl-C) during Deliver to kill a delivery mid-run; stop Kado by disabling the Kado plugin in the test vault; remove `KADO_URL` / `KADO_TOKEN` by editing a copy-protected backup first (`cp` the instance env file and any `.mcp.json` to `$TMPDIR`) and restoring it at the end.

| # | Criteria | Do | Expect | Outcome | Evidence |
|---|----------|----|--------|---------|----------|
| 7.1 | F6-AC1, F5-AC4, F6-AC2 | Start Deliver and interrupt the session after the first upload began. Start a new session, `/note`. | Kept draft listed by title, template and time with Resume / Drop (never an unfinished draft or a stale stage, never dropped unasked), `frozen` true. | | |
| 7.2 | F6-AC3 | Choose Resume. | Identical existing target treated as done, remaining steps run, delivery report, stage directory gone. | | |
| 7.3 | F6-AC4, F6-AC2 | Repeat 7.1, choose Drop at start. | Landed files named by kind with names starting `<stem>_`; "may already be in the inbox" only when `steps_done` is empty and `frozen` true, otherwise "nothing landed". Stage directory removed. | | |
| 7.4 | F5-AC6, F6-AC3 | Repeat 7.1, then in Obsidian edit the landed note so it differs; Resume. | Exit 3 with `frozen` true: Keep / Drop (no Rename), `exists_path` named; Drop names `steps_done` files, or "may already be in the inbox as `note_path`" when empty. | | |
| 7.5 | F4-AC3, F6-AC1 | In a resumed frozen draft choose Change something: keep-source false, title, destination. | One line says the change can no longer be made; staged values kept. `--keep-source` refused as frozen once `instructions_json` landed or was in flight. | | |
| 7.6 | F6-AC7 | Interrupt `/note` during the questions (after `new`, before the first `stage`), then start a new session, `/note`. | Unfinished draft listed by title (template name when untitled), template and time with Continue / Discard, never dropped unasked. Continue reruns the outline for the same stem (no new stem) and asks the questions again. | | |
| 7.6a | F6-AC7 | Run `/note` to the printed draft and its approval question, do not answer, run `/note` again (session c573b7b7). | The printed draft is offered Continue / Discard. Continue reprints the header and `note.md` and asks Deliver / Change something / Abort; Discard says nothing landed in the inbox and removes the stage. A stage with an unreadable `meta.json` alone is dropped with a one-line notice. | | |
| 7.7 | F6-AC1, F5-AC4 | Disable the Kado plugin in the test vault; run `/note` to Deliver. | `failed` at step `note`; later steps not run; source unmarked; kept draft with `frozen` true. Re-enable Kado, `/note`, Resume completes. | | |
| 7.8 | F6-AC1, F5-AC4 | Remove `KADO_URL` / `KADO_TOKEN` (and any `.mcp.json` fallback); run `/note` to Deliver. | `failed` at step `kado_config`; nothing written; draft kept with `frozen` false. | | |
| 7.9 | restore | Restore `KADO_URL` / `KADO_TOKEN` and `.mcp.json` from the backup, re-enable Kado, restart the session, Resume or Drop the kept draft, clean test notes from the inbox. | `/note` runs normally again. | | |
| 7.10 | F5-AC4 | `withdrawn` (exit 1, `step` empty): not live-reachable. | Covered by tests: `tests/test_note_instructions.py::test_deliver_refuses_a_set_the_guards_cut` (status `withdrawn`, no write events, stage kept) and `tests/test_note_skill_prose.py::test_a_withdrawn_action_offers_only_drop_or_abort_and_names_landed_files` (Drop / Abort only, landed files named). | n.a. | tests |
