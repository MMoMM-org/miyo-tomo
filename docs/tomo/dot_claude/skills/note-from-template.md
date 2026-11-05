# WHY: note-from-template (skill)

> Rationale for `tomo/dot_claude/skills/note-from-template/SKILL.md`.
> Spec 044 (issue #169, `docs/XDD/specs/044-note-from-template/`). ADR numbers refer to its `solution.md`.
> Entry point: [note](../commands/note.md). Related: [inbox-author](inbox-author.md).

## Why the Model Fills the Template and Scripts Check and Deliver (ADR-1)

WHY: Any ordinary vault template must work. A Pass 2 route would need a Tomo token for every section of every
template. So the model reads the outline and writes `draft.md`; scripts only check structure
(`template-outline.py`, the filled-note check in `note-instructions.py stage`) and deliver. Note quality is the
model's; the scripts never judge content. This is also why the skill writes only `draft.md` and two helper
input files (see "Why the Runtime Details Look the Way They Do"): every other state change goes through the scripts.

## Why /note Runs in the Main Session, Not as a Subagent

WHY: The skill calls `AskUserQuestion` at several points. Subagents cannot ask the user and cannot use the
Agent tool (Anthropic platform constraint), so the skill is loaded by the command shim in the main session and
no step dispatches a subagent. Revisit if the platform changes.

## Why the Draft Is Printed Before Every Question

WHY: `AskUserQuestion` shows only a short prompt. The user cannot approve text they have not seen, so the
skill prints the draft (header line, then the fenced note) as ordinary output before the approval
question, and again before each re-ask after a change. What is printed is `note.md` (the staged result with
`{{source_link}}` resolved), never `draft.md` (F4-AC2): the user approves what will land in the vault. The
same rule covers the question rounds: any text the user needs to decide on is printed first.

## Why the Source Delete Is Named Before the User Approves

WHY: When the draft came from an inbox note that is not kept, the instruction set carries a `delete_source` action
(I02, `lib/note_actions.py`). Applying the set in Hashi deletes the source, so the user must know that before they
approve: the header line "Source ... is deleted when you apply the instruction set in Hashi." is printed above every
draft, ahead of the Deliver question. The line is omitted exactly when `build_delete_source` returns no action: with no
source there is nothing to delete, and with `keep_source` true nothing is deleted. Printing it then would announce a
delete that never happens. Deleting is the default because the new note replaces the inbox note (the action's reason is
"Replaced by a /note note"); `--keep-source true` exists for the case where the user wants the original kept, e.g.
raw material they still need. Keeping also changes the note: `stage` resolves `{{source_link}}` to `[[<source stem>]]`
instead of empty text, so the note links to the kept original. `--keep-source false` undoes it. The option is refused
once the instruction set is done or in flight (`is_keep_source_frozen`), see the frozen message below.

## Why the Draft Keeps {{source_link}} as Written

WHY: The `{{source_link}}` value depends on `keep_source`, which the user can still change at the step 6 question.
`stage` resolves the token into `note.md` and never changes `draft.md`, so a keep-source change needs only a rerun of
`stage`, not a rewrite of the draft by the model. Every other `{{…}}` token must be filled: a token left in the note
fails the filled-note check.

## Why the Draft Adds No tomo: Key

WHY: `deliver` stamps the note itself: `_checked_note` (`note-instructions.py`) merges a `tomo:` block
(`rendered-note` / `pending-move`, with the draft's run id) into the frontmatter, and triage uses that stamp to skip the
note in the inbox. A draft-supplied `tomo:` key would clash with the stamp: `merge_tomo_block_into_markdown` refuses a
frontmatter that already has a top-level `tomo:` key (`FrontmatterMergeError`) rather than write a duplicate key, and
the filled-note check reports it as `no_user_tomo_key` FAIL. Either way the delivery stops until the draft is fixed.

## Why the Header Names Both File Names

WHY: The note lands in the inbox first, as `inbox_file` (`<stem>_<title>.md`), and moves to `destination_file` only when
the user applies the instruction set in Hashi. The MVP boundary lets Tomo write only to the inbox. The header names both
so the user knows where to find the note now and where it ends up; the delivery report ends with "Next: review and
apply the instruction set in Hashi." because nothing reaches its destination until that happens.

## Why Session Start Is a Script (ADR-6)

WHY: `note-session.py start` parses `$ARGUMENTS`, lists kept drafts, checks `note_include`, lists candidate
templates (daily template excluded) and previews proposed globs. The `/inbox` pattern (argparse in a script)
is deterministic; a prose "if the first token is --process" depends on the model reading it right. A kept
draft is always handled before the new request.

## Why Draft State Lives per Stem in tomo-tmp/note/ (ADR-7)

WHY: Resume needs the stem, title, destination, source and the steps already done. One directory per stem
(`template.md`, `outline.json`, `source.md`, `draft.md`, `note.md`, `meta.json`) keeps parallel drafts apart.
`reset-tomo-tmp.sh` never touches it, so `/inbox` resets cannot destroy a draft; the price is that only `drop`
and a successful `deliver` clean it up, which is why the skill must call `drop` on every abort.

## Why Abort Drops the Draft

WHY: A draft holds user material and nothing deliverable until approved. On abort at any question the skill runs
`note-instructions.py drop` when a stem exists and confirms in one line, so no orphan stage remains. A confirmed
`note_include` stays saved: it is a configuration decision, not part of the draft. Interrupted dialogues found at
start (`stale_stages`) get one line and a `drop` each for the same reason.

## Why Resume-or-Drop Is Never a Silent Drop

WHY: A kept draft with `steps_done` non-empty already has files in the vault (the note, the JSON, the MD). A
silent drop would leave them there with no record. The next `/note` therefore offers resume or drop; this also covers
a killed process (`steps_done` set, `failed_step` empty), treated like a failed delivery. A resumed draft whose `frozen` is
true keeps its title and destination frozen (see
[Why One Frozen Message Names Both Refusals](#why-one-frozen-message-names-both-refusals)), and a name collision is
branched on the `frozen` verdict `deliver` reports (see the next section).

## Why Exit 3 Branches on the Script's frozen Verdict, Not on steps_done

WHY: A taken name can be cured by a rename only while title and destination may still change. That is exactly
`is_frozen` (`lib/note_meta.py`): true once `steps_done` is non-empty or `failed_step` names a delivery step (in
`STEPS`), because `deliver` writes a step as `failed_step` before uploading it and an upload in flight may have landed
under the old name even though `steps_done` is still empty. `kado_config` is not a delivery step and freezes nothing.
A kept draft whose first step failed before any upload (only `kado_config`) can still be renamed with `stage --title`;
offering only Keep/Drop there would force a needless discard. Keep/Drop is right when `frozen` is true: the name cannot
change, and Drop names the landed files of `steps_done` so the user can delete them in Obsidian, or, with `steps_done`
empty (the first upload was in flight), says the note may already be in the inbox.

The script owns the rule; the skill reads the boolean `frozen` that `deliver` prints on stdout, which is `is_frozen` on
`meta.json` when the run ended. Recomputing the rule in prose drifted once already: the skill keyed Rename on
`steps_done` empty, which offered a rename that `stage` then refused for an in-flight stage. Reading `meta.json` itself
would add a file read the model can get wrong (a stale or misread file) for a value the script already prints.
`steps_done` stays in the output because it names the files a Drop leaves behind. A withdrawn stop (exit 1) branches
the same way: the guards run before the uploads on every `deliver`, a resume included, so a withdrawn resume can come
on a stage that is already frozen.

## Why a Kept Draft Drop Names Landed Files by Kind

WHY: A kept draft dropped at session start may have files in the inbox. `start`'s `kept_drafts` entries carry
`steps_done` but no path: only `stem`, `title`, `template`, `created`, `failed_step`. The skill therefore names each
landed file by kind (the note, the instruction set JSON, the instruction set MD) and says it is in the inbox with a
name starting `<stem>_`, which is true of all three (`<stem>_<title>.md`, `<stem>_instructions.json`,
`<stem>_instructions.md`). It must not build a vault path itself: the inbox file name goes through `sanitize_stem` and
the inbox folder comes from the config, so a model-built path can be wrong and send the user looking for a file that
is not there. `deliver` writes a step as `failed_step` before uploading it (the step is in flight), so an entry with
`failed_step` set and `steps_done` empty may already have the note in the inbox: the upload can land and the run end
before the step is recorded as done. Saying "nothing landed" there would be a false promise, so the skill says the
note may already be in the inbox.

## Why One Frozen Message Names Both Refusals

WHY: `stage` reports `frozen: true` for two different refusals, both decided by `apply_stage_update`
(`lib/note_meta.py`). `is_frozen` refuses a title or destination change once `steps_done` is non-empty or `failed_step`
names a delivery step (an upload in flight may have landed; `kado_config` does not count), because the landed files
carry those names. `is_keep_source_frozen` refuses a `--keep-source` change once `instructions_json` is in `steps_done`
or is `failed_step`: the landed instruction set already encodes the source delete (or its absence), so flipping
keep-source afterwards would make the note and the instruction set disagree. Hence the message says "may have
landed", not "landed": the refusal can come with `steps_done` empty. The skill never predicts either rule; it states
the frozen title for a kept draft whose `frozen` is true and otherwise reacts to `stage`'s refusal. The output does not say which rule fired, so the skill
gives one message naming both conditions. A message naming only title and destination would misreport the keep-source
refusal and leave the user asking why a change they did not make was refused. The staged values stay as they were,
because a refused update changes nothing in `meta.json`.

## Why Exit 1 Branches on status, Then on step

WHY: `deliver` exits 1 for three different stops, and only the `status` field tells them apart. A guard that withdrew
an action reports exit 1, `status` `withdrawn` and an empty step: the same exit code and step as a failed filled-note
check. Without the `status` branch the model would read the empty step as "fix the draft" and loop on a refusal no
draft edit can cure. Withdrawn writes nothing in this run, so the skill says so and why the action was withdrawn,
then branches on `frozen` as exit 3 does (rename while it is false, Keep/Drop naming the files of
`steps_done` once it is true): the guards run before the uploads on every `deliver`, a resume included, so
earlier runs may already have landed files and frozen the name. It offers no resume because a withdrawn action has no content to deliver, so keeping the draft would only
repeat the refusal.

With `status` `failed`, the step decides. A named step is a Kado or system error: report it, the draft stays, and the
next `/note` offers resume. That includes `kado_config`, the step `deliver` reports when no Kado URL or token is
configured, before any write, so it needs no branch of its own. An empty step means the draft itself was refused before Kado was asked:
either the filled-note check failed or the frontmatter stamp failed (malformed draft frontmatter). The skill names
both because `stage` reports `check.ok` true for a draft whose frontmatter cannot take the stamp; naming only the check
would leave the model looking at a check that passed and no reason to look at the frontmatter. Either way the fix is in
`draft.md`, then `stage` reruns and the step 6 question is asked again.

## Why Delivery Is One Script (ADR-2)

WHY: `note-instructions.py deliver` writes the note, the instruction set JSON and MD, and marks the source in
one process, with the `kado-write-file.py` exit contract (exit 3 and an `EXISTS:` line on a name collision,
never an overwrite). Order, collision handling and the resume comparison (identical content counts as done)
become testable instead of left to the model. Marking the source is a direct frontmatter merge, not a call to
`mark-captured.py` (ADR-3). The skill never runs the delivery steps itself. A withdrawn action (exit 1, `status`
`withdrawn`) means nothing is written; the skill's handling is explained in
[Why Exit 1 Branches on status](#why-exit-1-branches-on-status-then-on-step).

## Why a Source That Moves or Changes Does Not Fail the Delivery

WHY: The source mark is the last step and the least important one: the note and the instruction set already landed.
If the source was deleted or moved before the mark, there is nothing left to mark, so the step counts as done,
`deliver` reports `delivered` with `source_marked: false`, and the report says in one line the source was not marked.
Failing there would strand a complete delivery behind a resume that can never succeed. If the source changed
between the read and the mark, a merge would overwrite the newer content, so it is reported as a failed `source_mark`
(exit 1) and resume retries it against the current file. The draft stays until the mark succeeds.

## Why Exit 2 Means "Ask for Another Value" Only When the Error Names an Option

WHY: Exit 2 of `new` and `stage` covers two kinds of stop. Refused input: a `--source` outside `concepts.inbox`, a
blank or dotted title, an invisible character or `{{`/`<%` in it, a destination that is not a relative vault folder.
These are the user's to fix. The skill names what was refused and asks for another value; nothing is staged. But
the same exit code also covers an unusable `vault-config.yaml` (`read_note_config`), local I/O failures, an unknown stem or a
malformed one and an unusable `meta.json`. No other value the user could type cures those, so asking for one would
loop. The exit code cannot tell them apart; the error text can: every refused-input `UsageError` in
`note-instructions.py` starts with the option it refuses (`note-instructions: --title ...`,
`note-instructions: --destination ...`, `note-instructions: --source ...`), and none of the others does. The skill
branches on that prefix: an option error asks again; any other exit 2 is shown verbatim and the skill stops, keeping
the stem (dropping it would discard the user's material; `new` creates no stage before it fails). Exit 3 (name
taken) is different: never overwrite; the skill branches on `deliver`'s `frozen` (see
[Why Exit 3 Branches on the Script's frozen Verdict](#why-exit-3-branches-on-the-scripts-frozen-verdict-not-on-steps_done)). Exit 1 of
`deliver` is branched on `status` first and then on `step` (see
[Why Exit 1 Branches on status](#why-exit-1-branches-on-status-then-on-step)).

## Why deliver Exit 2 Stops and Keeps the Draft

WHY: Exit 2 of `deliver` is not refused user input. `note-instructions.py` maps every `UsageError` and local `OSError`
to exit 2, and on the `deliver` path those are: a malformed or unknown stem (`_existing_stage`), a `meta.json` that
cannot be read (`_stage_meta`) or written, and "no title staged". (The `vault-config.yaml` errors of
`read_note_config` are exit 2 too, but only `new` reads the config.) Each is a bad invocation or a broken local stage;
no other value the user could give cures it, so there is nothing to ask for. The skill shows the error and stops;
the draft stays, because dropping it would discard the user's material in `tomo-tmp/note/<stem>/` and, once
`meta.json` records a step or a failure, the chance to resume.

Whether anything reached the vault depends on the cause. A malformed or unknown stem, an unreadable `meta.json` and
"no title staged" stop `deliver` before it asks Kado, so nothing reached the vault. A failed `meta.json` write can come
after a step landed: `_record` writes it after each delivery step and `_fail` after a failed one, so the inbox may
already hold the note or the `<stem>_instructions` files, and a failed `_record` write leaves that step out of
`steps_done`. On the next `/note`, a stage whose `meta.json` already holds a `steps_done` entry or a `failed_step` is a
kept draft, and resume counts the landed file as done, not as a name clash, because `deliver` rebuilds identical text.
That holds for the first step (`note`) too: `deliver` writes the step as `failed_step` to `meta.json` before uploading
it, so a stage whose upload landed but was never recorded is a kept draft, never one of the `stale_stages` the skill
discards. A failure of that in-flight write itself exits 2 before its upload is sent, so that step adds no file.

The rule "never run `deliver` before `stage` has recorded a title" exists because the title names the files: `new`
records an empty title, and `inbox_file` (`<stem>_<sanitize_stem(title)>.md`) and `destination_file`
(`<destination><sanitize_stem(title)>.md`) are derived from it. Without a title there is no file name to write, no
`note.md` the user has seen, and no filled-note check result, so `deliver` refuses with "no title staged" rather than
guessing a name.

## Why new Exit 1 and template-outline.py Exit 2 Stop

WHY: `new` exits 1 on a `SourceError`: Kado could not read the source note. `new` reads the source before the stage
directory is created, so nothing is staged yet: no stem exists and there is nothing to drop. The source may have moved
or be outside the key's read access, so the skill says it could not be read and offers Another source / Abort. Abort
simply stops.

`template-outline.py` exits 2 for a bad invocation, an unusable stage `meta.json` or a local write failure. These come
from the script call or the local stage, not from anything the user typed, so no retry with another value cures them:
the skill shows the `error`, must drop the stem (it already exists from `new`) and stops. Exit 1 of the same script
is different: the template is unreadable, which another template can avoid.

## Why Another Template Drops the Stem

WHY: `new` fixes the template in `meta.json` (`template`, `template_stem`) and `template-outline.py --stage` writes that
template's `template.md` and `outline.json` into the stage. A stage cannot switch templates, so trying another template
means dropping this stem and running `new` again from step 3, which draws a new stem.

## Why Template Unreadable Is Not "No Template Exists"

WHY: A Kado key without read access to `templates.base_path` returns an empty listing, indistinguishable from an
empty folder. When `folder_listed` is 0 the skill says the folder is empty or not readable by the key, offers the
remedy (grant read access or do not use `/note`) and stops. It never says that no template exists. The same wording
applies when `template-outline.py` exits 1. A `listing_error` is shown verbatim.

## Why No Candidate Fitting Is Not an Error (F2-AC3)

WHY: With `folder_listed` above 0 the folder was readable and the model judged that no selected template fits. That is
a normal outcome, so the skill says "No selected template fits." and offers three exits: adjust patterns (back to the
`note_include` setup), `inbox-author` (a free-form artifact needs no template) or abort. `folder_listed` equal to 0 is
the unreadable case above and never reaches this offer.

The `inbox-author` hand-off passes the line "Compose a free-form note with requested type `default`; do not look for
another template." Without it the hand-off can loop: `inbox-author` resolves an unknown requested type by a `kado-search`
byName in the template folder, and when a template outside `note_include` matches by name it tells the user to run
`/note` and stops, which sends the user straight back here. `default` is a known key in `inbox-author`'s schema list,
so it resolves through `templates.mapping.default` (or its built-in default) and never runs the byName search. The fix
lives here because `inbox-author`'s sections are byte-locked by tests and the loop is this skill's hand-off to solve.
The hand-off is a Skill tool call, so `Skill` is in `allowed-tools`.

## Why Template Choice Asks Only When Several Fit

WHY: When one candidate fits the request and its material, a question would only confirm the obvious, so the skill
names it in one line and continues without asking; the user still sees the template in the draft header and can abort
at the Deliver question. When several fit, the user decides: the skill prints them as a numbered list first (the
print-before-ask rule) and asks with at most three candidates plus Abort, which keeps the question within the
four-option cap of every `AskUserQuestion` in the skill; "up to four candidates with Abort" could have made five. With
more than three fits, the list is printed in full and the user may type another number from it.

## Why One Shared Parser (ADR-4)

WHY: `lib/template_syntax.py` holds frontmatter blocks, tokens, Templater spans, headings and the filled-note
checks. Hyphenated scripts cannot import each other, so a shared module is the only way the outline points and
the filled-note check can agree. `lib/note_process.py` keeps its own leading-fence split for process files
(CR-only line breaks; see the ADR-4 exception).

## Why note_include Is Written by a Writer Subcommand (ADR-5)

WHY: Which templates `/note` may offer is a vault-config setting. `vault-config-writer.py templates-include`
edits only the `note_include` lines inside `templates:`; the existing helper replaces whole top-level blocks and
would drop the `mapping` comments. The skill never composes YAML by hand, and nothing is written before the user
confirms the glob preview (see
[Why the Runtime Details Look the Way They Do](#why-the-runtime-details-look-the-way-they-do)).

## Why Setup Reruns start and Kept Drafts Come First

WHY: `start` computes `candidates` from the saved `note_include`; before the first-run setup there was none, so the
skill reruns `start` after the writer call to get the candidates for step 3, skipping the kept drafts it already
handled. Kept drafts are handled before any new request because each kept draft is a delivery the user started and
may already have files in the vault; starting a new draft first would bury it.

## Why the Question Budget Is Two Rounds of Four

WHY: `AskUserQuestion` caps at four options, and long interviews lose the user. Round 1 asks up to four open
points (required first, process guidance deciding order); round 2 up to four more plus gaps opened by
answers. A required point still unanswered is asked again without a skip option: answer or abort. Optional points
left open are named in the "Skipped, left empty:" line above the draft, so skipping is visible.
Any non-empty answer, "none" included, answers a required point: required means the user must address the point, and
"none" is a deliberate answer, not a skip, so re-asking would loop. Tokens with `prefilled` true are not points:
`template-outline.py` already filled them from the clock, the config or the source path.

## Why --process Is a Separate Mode

WHY: `/note --process <template>` stores per-template guidance (destination, required points, guidance text) in
`config/note-processes/<template-stem>.md` through `note-process.py read` and `write`. After a delivery the
skill offers Save / Not now / Never once, only when the template has no process file and no decline marker and the
session showed a signal worth saving (a changed destination, a point from the `Skipped, left empty:` line filled
through Change something before Deliver, a requested question order); "Never" writes a decline marker that `write`
later replaces. An unknown template writes nothing (F7-AC11). The temporary outline file is removed afterwards.

The second signal was "a re-asked skipped point was answered". Points are re-asked only when they are required, and
required points come only from a process file, which the offer excludes, so that signal could never fire (owner
decision, spec 044 Decisions Log). The new signal is dialogue the model saw itself: the user skipped a point in the
question rounds, the draft header named it in the skipped line, and a Change something request then filled it. That
shows the point matters to the user, which a saved required point would capture.

## Why the Default Destination Omits --destination

WHY: `note-process.py write` replaces the whole process file and stores a destination only when `--destination` is
given. With no stored destination, `note-instructions.py new` falls back to the atomic-note folder
(`concepts.atomic_note`). So "Default" in process mode means omit `--destination`; passing the atomic-note folder
would pin today's config value into the file and stop following a later config change. "Keep current" must pass the
current value again, because the write replaces the file; it is offered only when `read` reported `exists` true with a
non-empty `destination`, since there is nothing to keep otherwise (a missing file, a decline marker, or a file that
stores no destination, which already means Default).

## Why Both Process Paths Branch on template-outline.py Exits

WHY: The Save path of the process offer and `/note --process` both outline the template before `note-process.py` runs.
An unreadable template is exit 1 there too, so both give the F2-AC4 remedy (grant the Kado key read access to
`templates.base_path`, or do not use `/note`) in the same words as step 4. Exit 2 is a bad invocation or local write
failure that no other value cures, so the skill shows the error. Either way `note-process.py` would have no outline to
check required points against, so the skill runs `rm -f` on the helper files and stops: it must write nothing.

## Why a Resume Gets No Process Offer

WHY: The offer's conditions come from `note-process.py read` in step 4 (`exists`, `declined`) and from the dialogue of
this session (`default_destination`, skipped points, a requested order). A kept draft resumed at session start goes
straight to delivery: `read` never ran this session and the dialogue that produced the draft happened in an earlier
one. The model would have to guess every condition, so the skill skips the offer after a resume.

## Why the Process Offer Re-Outlines the Template

WHY: The offer comes after a successful delivery, and `deliver` removes the stage directory on success, so the stage's
`outline.json` is gone. `note-process.py write` checks the required points against an outline, so the skill writes a
fresh one with `template-outline.py --out tomo-tmp/note/process-outline.json`. `write` exits 1 and writes nothing when
a required point is not in the outline; the skill names `rejected_required` and reruns without them, so the valid rest
of the process is still saved.

## Why Template and Config Problems Continue Instead of Stopping

WHY: A broken process file (`error` set) is ignored with one line and the template alone is used. A required point
missing from the template is named in one line and skipped. A template without frontmatter is drafted with a
frontmatter block anyway; `stage` reports the filled-note result. The note matters more than an optional
refinement being intact. A filled-note check that fails at `stage` is different: the skill fixes the draft and
reruns `stage` before showing the draft, so the skill never calls `deliver` on a known failing check. The check or the
frontmatter stamp failing inside `deliver` is covered in
[Why Exit 1 Branches on status](#why-exit-1-branches-on-status-then-on-step).

## Why Script Errors Are Shown Verbatim

WHY: The `/note` scripts write their errors to name only the problem class (never a title, a path or note text, per
the script docstrings), and the wording is written for the user: "no title staged: run stage --title first", "--source
must be a note inside concepts.inbox". The text is already safe and specific. A paraphrase would hide the cause, e.g.
turn "unknown stem: no stage directory" into a vague "something went wrong", and the user could no longer tell which
check failed.

## Why STRICT Is Rare

WHY: Per the repo rule, a `STRICT` block with a one-line `Why:` is only for a deviation actually observed in a run.
The runtime text holds imperatives only; every rationale lives in this file. Add a STRICT when an eval or live run
shows the model skipping a step, and state the failure mode in one line.

## Why Only One Eval Case, Outside the CLAUDE.md Gate (ADR-8)

WHY: One recorded paid run proves the model prints the draft before asking and delivers only after approval.
`/note` is not in the CLAUDE.md eval gate because gating every later edit would cost a paid run each time. The
trade-off: later edits to the skill have no automatic model check, so review them by hand.

## Why the Runtime Details Look the Way They Do

WHY: `start` is called as `--args='<request>'` (single quotes, each `'` written as `'\''`): the `=` form keeps a
request beginning with `--process` from being read as an option, and single quotes keep the shell from expanding
`$` or backticks in the user's text. The request text stays in the conversation because `start` does not echo it
back, and the later steps (template choice, source, draft) work from it. The first-run `note_include` setup previews
`match --globs "*"` first because the model cannot propose globs for template names it has not seen, then previews
the proposed globs' matches before asking, so the user confirms against real template names. The skill writes
only three local files itself (`draft.md`, `tomo-tmp/note/note-include.json` as the writer's `--input`, `tomo-tmp/note/process-guidance.md` as
`--guidance-file`); the two helper files are removed right after the script call. The skill pins no `model`:
the note text is the model's work (ADR-1), so it runs on the session's model. The description carries
`MUST BE USED` per the authoring rules, and the `NOT for` clause keeps free-form artifacts with `inbox-author`.
`allowed-tools` lists `Skill` for the `inbox-author` hand-off in step 3.

Templater code (`<%` ... `%>`) is a hint to the model only: it is never executed, none is left in the draft, and a
`<%` surviving in the draft fails the filled-note check (F3-AC7). Questions follow the language of the call while the
note keeps the template's headings, so the output still matches the template (F3-AC8).
