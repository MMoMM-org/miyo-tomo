# WHY: tomo-note-view (mod)

> Rationale for `tomo/dot_claude/skills/tomo-note-view/`, a Claude Code mod
> (function-hooks plugin), not a skill: it has no `SKILL.md`.
> Spec 044 (issue #169) ADR-9, PRD/SDD F4-AC5, SDD "Draft view pane"; answers
> issue #182 ("Look if Claude Mods could be useful").
> Producer of the file it draws: [note-instructions.py](../../scripts/note-instructions.md).
> Version: 0.1.1 (`dot_claude-plugin/plugin.json` `version` and the
> `// version:` line of `hooks/register.tsx` move together).

## Why a Mod

WHY: `/note` must show the full staged draft before the approval question
(Deliver / Change something / Abort). Every way of showing it through the
model failed or fell short live:

- Printed text before the dialog: the model wrote it into thinking and called
  `AskUserQuestion` with no visible text (sessions 2e8fb1d3, 23125562), even
  under STRICT.
- The dialog's `preview` (note-from-template 0.2.11): the model fills it fully
  (session 8a8f3e67), but the terminal box cuts a long draft ("preview cannot be
  shown in full").

A mod is code the engine runs, not text the model may skip. It reads the file
`note-instructions.py stage` writes (`tomo-tmp/note/view.md`) and opens a side
pane with it when `AskUserQuestion` is called, so what the user sees no longer
depends on the model. The 0.2.11 preview and "show me the draft" stay as the
fallback, so the skill is unchanged.

## Rejected Options

- Longer or split preview: the preview box is the terminal's; its size is not
  ours to set.
- Drawing at the `AskUserQuestion` render site: a mod may draw there, but the
  terminal allows only 12 rows around the question dialog and refuses a
  `Markdown` element there; a draft does not fit.
- A hook `systemMessage`: capped at about 10,000 characters and how a host
  shows it is not documented; no scrolling.
- The IDE bridge (Hashi Tomo Context): it offers the model no `openFile`, and
  the draft is in `tomo-tmp/`, not in the vault, so Obsidian cannot open it.
- Ctrl+O on the transcript or `! cat tomo-tmp/note/<stem>/note.md`: both need
  the user to know and act; the point is that the draft is just there.

## Why view.md and Not note.md

The pane needs the header (template, final name, inbox name, source deleted)
as well as the note, and needs one fixed path. `stage` writes both into one
file and removes it whenever no approval is due (see the script's WHY doc), so
the mod only checks one path and never decides which draft is current.

## Why These Hooks

- `tool.call` on `AskUserQuestion`: the approval question is an
  `AskUserQuestion` call; opening the pane before `next(e)` puts it up while
  the dialog waits. It opens only when an option label of the call contains
  `Deliver` (the step 6 approval options, `1 Deliver` or `Deliver`): a
  `view.md` left by an abandoned `/note` session would otherwise open the pane
  at any later, unrelated question (`/inbox`, the glob setup, the process
  offer). When `view.md` is absent an open pane is closed at any question.
  The match is on the English option word the skill names; a dialog the model
  words in another language opens no pane by itself, and `/note-draft` still
  does.
- `tool.call` on `Bash`, after the call: `stage`, `deliver` and `drop` run
  through Bash; re-reading `view.md` then keeps an open pane current and closes
  it once the file is gone (delivered or dropped).
- `/note-draft`: the user can open the pane at any time; it is also the one
  way to get it placed on a narrow terminal (below).
- `$.state` holds the text, not a module variable: a hot reload drops module
  variables, and a state write redraws the pane.
- Control characters other than tab and newline are removed before drawing:
  the `Markdown` element refuses them, and a refused tree draws nothing.
- When `$.ui.open` answers `isPlaced: false`, `$.ui.log` names the reason and
  `/note-draft`, so a missing pane is explained on screen.

## Why the Width Rule Matters

An open the mod makes on its own (the `AskUserQuestion` call is the model's, so
it is not the person's input) is placed only from 144 terminal columns, or
from 110 once the person opened the pane with `/note-draft` in this or an
earlier session and has not closed it by hand; below that it waits undrawn.
An open that answers the person's command is placed at any width: docked
beside the transcript in fullscreen from 110 columns, else inline above the
prompt (a third of the rows by default); arrows scroll it when it has focus.
So on a normal-width terminal the user runs `/note-draft` once, and from then
on the pane appears by itself.

## Why It Ships as a Skills-Folder Plugin

Claude Code auto-loads a plugin folder from the project's
`.claude/skills/<name>` (plugin-authoring reference), and the instance root is
the project in the container, so no `--plugin-dir`, settings entry or
marketplace is needed. The source tree stores the manifest folder as
`dot_claude-plugin/` (hidden source paths trigger sandbox prompts and break git
operations, as for `dot_claude/`); `install-tomo.sh` renames it to
`.claude-plugin/` after its recursive skill copy, and `update-tomo.sh` maps the
leading `dot_claude-plugin/` when it syncs skill support files bytewise (a JSON
or TSX file cannot carry a `# version:` header, so the version gate does not
apply). `.claude-plugin/types/`, which the engine writes beside a loaded mod,
is gitignored, never copied and never compared.

## Limits

- Mods do not run under `claude -p` or in `claude plugin eval`; the eval case
  never sees the pane, and the model-side fallback is what it grades.
- The mod API is early access and moves between releases; `claude plugin
  validate` and `claude plugin test` on an installed-layout copy are the check.
- Hashi's session view draws whatever its host supports; without pane support
  the fallback stands.

## Revisit When

- The terminal preview stops truncating, or the dialog render site takes
  Markdown and more rows: the pane may then be redundant.
- The width floor for unasked panes changes, or a hook-opened pane counts as
  asked.
- Hashi's session view draws mod panes, or the IDE bridge gains an `openFile`
  the model can call.
