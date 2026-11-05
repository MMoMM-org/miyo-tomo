# WHY: note-from-template (skill)

> Rationale for `tomo/dot_claude/skills/note-from-template/SKILL.md`.
> Spec 044 (issue #169, `docs/XDD/specs/044-note-from-template/`). ADR numbers refer to its `solution.md`.
> Entry point: [note](../commands/note.md). Related: [inbox-author](inbox-author.md).

## Why the Model Fills the Template and Scripts Check and Deliver (ADR-1)

WHY: Any ordinary vault template must work. A Pass 2 route would need a Tomo token for every section of every
template. So the model reads the outline and writes `draft.md`; scripts only check structure
(`template-outline.py`, the filled-note check in `note-instructions.py stage`) and deliver. Note quality is the
model's; the scripts never judge content. This is also why the skill writes `draft.md` and nothing else:
every other state change goes through `note-instructions.py`.

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
a killed process (`steps_done` set, `failed_step` empty), treated like a failed delivery. During a resume, title
and destination are frozen because the landed files carry them. A name collision then offers keep or drop only,
and on drop names the landed files so the user can delete them in Obsidian.

## Why Delivery Is One Script (ADR-2)

WHY: `note-instructions.py deliver` writes the note, the instruction set JSON and MD, and marks the source in
one process, with the `kado-write-file.py` exit contract (exit 3 and an `EXISTS:` line on a name collision,
never an overwrite). Order, collision handling and the resume comparison (identical content counts as done)
become testable instead of left to the model. Marking the source is a direct frontmatter merge, not a call to
`mark-captured.py` (ADR-3). The skill never runs the delivery steps itself.

## Why Exit 2 Means "Ask for Another Value" (User-Fixable Input)

WHY: Exit 2 of `new` and `stage` is refused input: a `--source` outside `concepts.inbox`, a blank or dotted title,
an invisible character or `{{`/`<%` in it, a destination that is not a relative vault folder. These are the
user's to fix. The skill names what was refused and asks for another value; nothing is staged. Exit 3 (name
taken) is different: rename or abort, never overwrite. Exit 1 is a Kado or system error: report the failed step,
keep the draft, and the next `/note` offers resume.

## Why Template Unreadable Is Not "No Template Exists"

WHY: A Kado key without read access to `templates.base_path` returns an empty listing, indistinguishable from an
empty folder. When `folder_listed` is 0 the skill says the folder is empty or not readable by the key, offers the
remedy (grant read access or do not use `/note`) and stops. It never says that no template exists. The same wording
applies when `template-outline.py` exits 1. A `listing_error` is shown verbatim.

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
`config/note-processes/<template-stem>.md` through `note-process.py read` and `write`. After a first note the
skill offers Save / Not now / Never; "Never" writes a decline marker that `write` later replaces. An unknown
template writes nothing (F7-AC11). The temporary outline file is removed afterwards.

## Why Template and Config Problems Continue Instead of Stopping

WHY: A broken process file (`error` set) is ignored with one line and the template alone is used. A required point
missing from the template is named in one line and skipped. A template without frontmatter is drafted with a
frontmatter block anyway; `stage` reports the filled-note result. The note matters more than an optional
refinement being intact. A filled-note check that fails at `stage` is different: the skill fixes the draft and
reruns `stage`; `deliver` never runs on a failing check.

## Why STRICT Is Rare

WHY: Per the repo rule, a `STRICT` block with a one-line `Why:` is only for a deviation actually observed in a run.
The runtime text holds imperatives only; every rationale lives in this file. Add a STRICT when an eval or live run
shows the model skipping a step, and state the failure mode in one line.

## Why Only One Eval Case, Outside the CLAUDE.md Gate (ADR-8)

WHY: One recorded paid run proves the model prints the draft before asking and delivers only after approval.
`/note` is not in the CLAUDE.md eval gate because gating every later edit would cost a paid run each time. The
trade-off: later edits to the skill have no automatic model check, so review them by hand.
