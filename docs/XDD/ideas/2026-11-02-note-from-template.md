# `/note`: Notes From a Template, With Follow-Up Questions

> Brainstorm spec for #169. Created: 2026-11-02. Status: design approved, next step `/xdd`.
> This file is the handoff contract. Related: `2026-06-28-companion-p1-authoring-skills.md`.

## Goal

The user gives Tomo rough material for a kind of note, for example Meeting Notes, Problem Solving or Travel Reflections. Tomo finds the matching template, checks what the material covers, asks for what is missing, shows a draft, and after approval delivers the note with an instruction set for Hashi.

New kinds of note need no work from us. A normal template is enough, and no Tomo-specific template format is required.

## Decisions

| Topic | Decision |
|---|---|
| Where questions happen | In a separate session, through a new command. `/inbox` does not change. |
| What defines a note kind | The template alone works. A process file is optional. |
| Finding the template | Tomo picks by itself and asks only when unclear. |
| Ending a session | Draft in the console, then the note and an instruction set in the inbox. |
| Who fills the template | The model. Scripts check structure and deliver the result. |
| Discarding a result | By hand, documented. |

## Approaches Considered

- **A, chosen: the model fills, a script delivers.** A new skill and command. Every normal template works, and `/inbox` and the eval gate stay untouched. The note text comes from the model, so scripts check its structure and not its content.
- **B: through Pass 2.** A synthetic item goes through `instruction-render.py`. It renders deterministically, but that renderer fills only known tokens, so every section would need a token. That is the Tomo-specific format we want to avoid.
- **C: extend `inbox-author`.** Least new code, but that skill is defined as covering artifacts without a defined note type. The dialogue and the instruction set would remove that boundary.

## Flow

Command: `/note [what it is]`. The source is text in the call or an inbox note.

1. **Choose the template.** Tomo lists `templates.base_path` and picks from the source and the filenames. It asks when several fit or none does. `templates.note_exclude`, a list of filename globs, excludes system templates. Its default is `["i_*"]`, and the template mapped as `daily` is always excluded.
2. **Derive the checklist.** Headings, frontmatter fields and tokens become points to fill. Templater blocks (`<% %>`) count as hints and are never executed. The model marks each point as filled from the source or open; the script only lists the points.
3. **Ask.** Tomo asks only open points with `AskUserQuestion`, at most four per round. Skipping is allowed, and skipped sections stay empty and are named in the draft. A point the process file marks as required cannot be skipped: Tomo asks again, and the user can only answer or abort.
4. **Draft.** The full note appears in the console. The user changes it through dialogue until they approve.
5. **Deliver.** In this order: write the note to the inbox, write the instruction set, then mark the source.

The note goes to the inbox with `tomo.state: pending-move`. The instruction set holds a `move_note` and, when the source was an inbox note, a paired `delete_source`.

The destination comes from the process file, otherwise from `concepts.atomic_note.path`. The draft names it, and the user can change it there.

## Boundary to `inbox-author`

- `inbox-author` composes artifacts from vault content: overviews, lists, comparisons, `.base` and `.canvas` files. They land in the inbox and are filed later through `/inbox`.
- `/note` turns the user's own material into a note of a template kind, with questions, a draft and an instruction set.
- Today the unknown-type branch of `inbox-author` searches the template folder by name and fills a match without questions. Once `/note` ships, that branch points to `/note` instead, so one request no longer has two paths. The built-in default and the mapped `default` template stay in `inbox-author`.
- Both skills share the write path `kado-write-file.py --no-overwrite` and the `sanitize_stem` rule.

## Optional Process File

Location: `config/note-processes/<template-stem>.md` in the instance, for example `t_meeting.md`. Tomo can read and create these directly, without Hashi.

```markdown
---
destination: Atlas/Meetings/
required:
  - Decisions
---
Ask for the decisions first. For reflections, always ask what I would do differently.
```

- The file adds to the template and never replaces it. Structure always comes from the template.
- A broken file does not stop the session. Tomo says so and continues with the template alone.
- Free text covers order and emphasis. Branching is out of scope.
- `update-tomo.sh` leaves the folder alone, and backup and restore cover all of `config/`. A test keeps both true.
- `add_seed` delivers one reference file. A missing folder is valid.

## Components

| Piece | Job |
|---|---|
| `tomo/dot_claude/commands/note.md` | Thin entry point |
| Skill `note-from-template` | The flow above, imperatives only |
| `scripts/template-outline.py` | Reads a template and returns headings, fields, tokens and Templater positions as JSON |
| `scripts/note-instructions.py` | Stamps the note, builds and validates the instruction set |
| `template-doctor.py --filled-note` | New mode: frontmatter fences and closure, no `<%` left in the note, no hand-written `tomo:` block |
| Skill `inbox-author` | Change: the unknown-type branch of step 2 points the user to `/note` instead of filling a vault template itself. Version bump and WHY entry |

`note-instructions.py` must:

- take the run id from `scripts/run-id.py`
- stamp the note with `build_tomo_block("rendered-note", "pending-move", run_id)`, so the model never writes that block
- call `validate_destinations` and the delete guard itself, because both sit outside `build_actions`
- use a stem with seconds, because `HHMM` collides within a minute with another `/note` or a Pass 2
- write the note and both instruction files through `kado-write-file.py --no-overwrite`, the path `inbox-author` already uses. Exit 3 with `EXISTS:<vault-path>` is the name-taken signal. `upload-rendered.py` is not used, because it has no such protection
- render the Markdown peer with `render_instructions_md` in state `pending-apply`

The source is set to `tomo.state: captured` through the merge path of `mark-captured.py`, after both uploads succeed. Without this, the next `/inbox` proposes a duplicate. `captured` is only a guard until Hashi applies the paired `delete_source`, which ends the source. If the set is never applied, the source stays `captured`.

`templates.note_exclude` is a `vault-config.yaml` key, so it needs writer support and a schema entry, not hand-written YAML. A missing key means the default.

The JSON contract of `template-outline.py`, including which token syntaxes count as points to fill, is an SDD deliverable.

## Failure Cases

| Case | Behaviour |
|---|---|
| No matching template | Tomo says so and offers `inbox-author` |
| Name taken in the inbox or at the destination | Tomo asks, nothing is overwritten |
| Delivery fails at any step | The draft and its stem stay in `tomo-tmp/note/`, and the source is not marked. The next `/note` offers to resume or drop it. Delivery repeats with the same stem: a target with identical content counts as done, different content counts as name taken. |
| Abort during the dialogue | Nothing is written to the vault, and the draft in `tomo-tmp/note/` is removed |
| Result discarded after delivery | The user deletes the note and the instruction set in Obsidian, then runs `/inbox --recover`, which treats captured items as fresh. The documentation describes this. |

## Tests

- Both scripts, with real template shapes such as Templater blocks and callouts.
- Instruction sets validated with `validate-json.py` against `hashi-instructions.schema.json`. `instructions-diff.py` needs a `parsed-suggestions.json` and does not apply here.
- Negative cases: name taken, Kado down, source not marked after a failed upload.
- Triage: after delivery, neither the source nor the note counts as new.
- Backup and restore keep `config/note-processes/`, and `update-tomo.sh` does not touch it.
- `--filled-note` accepts a filled note and rejects `<%` remains.
- A name collision reaches the user through the exit 3 / `EXISTS:` contract of `kado-write-file.py`.
- One paid eval case for the model behaviour. This change edits no eval-gated file. If `settings.json` needs a change, the eval gate applies; its allow rule for `python3 scripts/*.py` should make that unnecessary.

## Project Rules

New runtime files need a mirrored `docs/tomo/<path>.md` and a `# version:` header. The implementation traces to this file, the spec under `docs/XDD/specs/` and #169.

## To Verify in the Spec

- Whether the Kado key allows reads in the template folder. `vault-explorer` deliberately reads only mapped templates. This is a hard prerequisite and comes first in the plan. Check it first with the existing unknown-type branch of `inbox-author` on `tomo-instance`, which already lists and reads that folder, before any new code is written.
- How Hashi handles a `move_note` with the paired `delete_source` for this flow.
- That `update-tomo.sh` delivers the new command and skill.

## Parking Lot

- Tags and MOC links in `/note`
- A vault folder for process files, which would have to go through instructions and Hashi
- Branching in process files
- Questions through the suggestions document
- `/note --discard`
