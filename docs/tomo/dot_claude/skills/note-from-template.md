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
a killed process (`steps_done` set, `failed_step` empty), treated like a failed delivery. During a resume with a
non-empty `steps_done`, title and destination are frozen because the landed files carry them. A name collision during a resume is branched on `steps_done`
(see the next section).

## Why Exit 3 Branches on steps_done, Not on "Is This a Resume"

WHY: A kept draft can be resumed with nothing landed: the first step failed, so `failed_step` is set and
`steps_done` is empty. `is_frozen` (`lib/note_meta.py`) freezes title and destination only once a step is done, so
such a draft can still be renamed with `stage --title`; offering only Keep/Drop would force a needless discard.
Keep/Drop is right only when files are already in the vault: the name cannot change, and Drop must name the landed
files so the user can delete them in Obsidian. The skill reads `steps_done` from `meta.json` because `start`'s
`kept_drafts` entries do not carry it.

## Why One Frozen Message Names Both Refusals

WHY: `stage` reports `frozen: true` for two different refusals, both decided by `apply_stage_update`
(`lib/note_meta.py`). `is_frozen` refuses a title or destination change once `steps_done` is non-empty, because the
landed files carry those names. `is_keep_source_frozen` refuses a `--keep-source` change once `instructions_json` is in
`steps_done`: the landed instruction set already encodes the source delete (or its absence), so flipping keep-source
afterwards would make the note and the instruction set disagree. The output does not say which rule fired, so the skill
gives one message naming both conditions. A message naming only title and destination would misreport the keep-source
refusal and leave the user asking why a change they did not make was refused. The staged values stay as they were,
because a refused update changes nothing in `meta.json`.

## Why Exit 1 Branches on status, Then on step

WHY: `deliver` exits 1 for three different stops, and only the `status` field tells them apart. A guard that withdrew
an action reports exit 1, `status` `withdrawn` and an empty step: the same exit code and step as a failed filled-note
check. Without the `status` branch the model would read the empty step as "fix the draft" and loop on a refusal no
draft edit can cure. Withdrawn writes nothing, so it offers Rename / Abort exactly as exit 3 does with `steps_done`
empty: nothing landed and the name is still free to change.

With `status` `failed`, the step decides. A named step is a Kado or system error: report it, the draft stays, and the
next `/note` offers resume. That includes `kado_connect`, the step `deliver` reports when Kado is unreachable before
any write, so it needs no branch of its own. An empty step means the draft itself was refused before Kado was asked:
either the filled-note check failed or the frontmatter stamp failed (malformed draft frontmatter). The skill names
both because `stage` reports `check.ok` true for a draft whose frontmatter cannot take the stamp; naming only the check
would leave the model looking at a check that passed and no reason to look at the frontmatter. Either way the fix is in
`draft.md`, then `stage` reruns and the step 6 question is asked again.

## Why Delivery Is One Script (ADR-2)

WHY: `note-instructions.py deliver` writes the note, the instruction set JSON and MD, and marks the source in
one process, with the `kado-write-file.py` exit contract (exit 3 and an `EXISTS:` line on a name collision,
never an overwrite). Order, collision handling and the resume comparison (identical content counts as done)
become testable instead of left to the model. Marking the source is a direct frontmatter merge, not a call to
`mark-captured.py` (ADR-3). The skill never runs the delivery steps itself.

When the guard withdrew the action (exit 1, `status` `withdrawn`), the skill reports that nothing is written and why,
then offers rename or abort: a withdrawn action has no content to deliver, so keeping the draft would only repeat the
refusal.

## Why a Source That Moves or Changes Does Not Fail the Delivery

WHY: The source mark is the last step and the least important one: the note and the instruction set already landed.
If the source was deleted or moved before the mark, there is nothing left to mark, so the step counts as done,
`deliver` reports `delivered` with `source_marked: false`, and the report says in one line the source was not marked. Failing there would strand a complete delivery behind a resume that can never succeed. If the source changed
between the read and the mark, a merge would overwrite the newer content, so it is reported as a failed `source_mark`
(exit 1) and resume retries it against the current file. The draft stays until the mark succeeds.

## Why Exit 2 Means "Ask for Another Value" (User-Fixable Input)

WHY: Exit 2 of `new` and `stage` is refused input: a `--source` outside `concepts.inbox`, a blank or dotted title,
an invisible character or `{{`/`<%` in it, a destination that is not a relative vault folder. These are the
user's to fix. The skill names what was refused and asks for another value; nothing is staged. Exit 3 (name
taken) is different: never overwrite; the skill branches on `steps_done` (see
[Why Exit 3 Branches on steps_done](#why-exit-3-branches-on-steps_done-not-on-is-this-a-resume)). Exit 1 of
`deliver` is branched on `status` first and then on `step` (see
[Why Exit 1 Branches on status](#why-exit-1-branches-on-status-then-on-step)).

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

## Why One Shared Parser (ADR-4)

WHY: `lib/template_syntax.py` holds frontmatter blocks, tokens, Templater spans, headings and the filled-note
checks. Hyphenated scripts cannot import each other, so a shared module is the only way the outline points and
the filled-note check can agree. `lib/note_process.py` keeps its own leading-fence split for process files
(CR-only line breaks; see the ADR-4 exception).

## Why note_include Is Written by a Writer Subcommand (ADR-5)

WHY: Which templates `/note` may offer is a vault-config setting. `vault-config-writer.py templates-include`
edits only the `note_include` lines inside `templates:`; the existing helper replaces whole top-level blocks and
would drop the `mapping` comments. The skill never composes YAML by hand. The glob preview in `note-session.py`
lets the user confirm before anything is written.

## Why the Question Budget Is Two Rounds of Four

WHY: `AskUserQuestion` caps at four options, and long interviews lose the user. Round 1 asks up to four open
points (required first, process guidance deciding order); round 2 up to four more plus gaps opened by
answers. A required point still unanswered is asked again without a skip option: answer or abort. Optional points
left open are named in the "Skipped, left empty:" line above the draft, so skipping is visible.

## Why --process Is a Separate Mode

WHY: `/note --process <template>` stores per-template guidance (destination, required points, guidance text) in
`config/note-processes/<template-stem>.md` through `note-process.py read` and `write`. After a delivery the
skill offers Save / Not now / Never once, only when the template has no process file and no decline marker and the
session showed a signal worth saving (a changed destination, an answered re-asked point, a requested question order); "Never" writes a decline marker that `write` later replaces. An unknown
template writes nothing (F7-AC11). The temporary outline file is removed afterwards.

## Why Template and Config Problems Continue Instead of Stopping

WHY: A broken process file (`error` set) is ignored with one line and the template alone is used. A required point
missing from the template is named in one line and skipped. A template without frontmatter is drafted with a
frontmatter block anyway; `stage` reports the filled-note result. The note matters more than an optional
refinement being intact. A filled-note check that fails at `stage` is different: the skill fixes the draft and
reruns `stage` before showing the draft, so the skill never calls `deliver` on a known failing check. `deliver`
checks again and also stamps the frontmatter; either failing there (exit 1, `status` `failed`, empty `step`) sends
the skill back to fixing the draft and rerunning `stage`.

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
`$` or backticks in the user's text. The first-run setup previews `match --globs "*"` first because the model
cannot propose globs for template names it has not seen. The skill writes only three local files itself
(`draft.md`, `tomo-tmp/note/note-include.json` as the writer's `--input`, `tomo-tmp/note/process-guidance.md` as
`--guidance-file`); the two helper files are removed right after the script call. The skill pins no `model`:
the note text is the model's work (ADR-1), so it runs on the session's model. The description carries
`MUST BE USED` per the authoring rules, and the `NOT for` clause keeps free-form artifacts with `inbox-author`.

Templater code (`<%` ... `%>`) is a hint to the model only: it is never executed, none is left in the draft, and a
`<%` surviving in the draft fails the filled-note check (F3-AC7). Questions follow the language of the call while the
note keeps the template's headings, so the output still matches the template (F3-AC8). The first-run `note_include`
setup previews the glob matches (`match`) before asking, so the user confirms against real template names.
The request text stays in the conversation because `start` does not echo it back, and the later steps (template choice, source, draft) work from it.
