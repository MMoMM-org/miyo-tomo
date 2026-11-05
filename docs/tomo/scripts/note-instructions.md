# WHY: note-instructions.py

> Rationale for decisions in `tomo/scripts/note-instructions.py`.
> The script owns the lifecycle of one `/note` draft in
> `tomo-tmp/note/<stem>/` (spec 044, ADR-2, ADR-7): `new`, `stage`, `drop`,
> and `deliver` (T2.6).

## WHY One Script With Subcommands

The draft directory has one owner. `new` creates it, `stage` updates its
`meta.json`, `deliver` empties it on success and `drop` removes it on abort.
Keeping all four in one script means the stem validation, the config reading
and the exit-code contract exist once, and the skill calls one script for every
state change of the draft rather than composing files itself.

## WHY new Draws the Stem, the Run Id and generated

The stem (`YYYY-MM-DD_HHMMSS`, with seconds) names the inbox files and the stage
directory; the run id stamps the note and the source mark; `generated` goes into
the instruction set. All three come from the script's clock, never from the
model, so they are well-formed and two drafts in the same minute do not share a
name. `generated` is fixed at `new` and reused by every `deliver`, so a resume
rebuilds identical files.

## WHY new Reads the Source Before Creating the Stage Directory

A Kado error reading the source exits 1 with nothing on disk. Creating the
directory first would leave a stage with no `meta.json`, which `note-session.py
start` would then report as a stale stage for the skill to drop: a failed start
must not leave work for the next session.

## WHY the Default Destination Comes From the Process File First

A process file for the template (`config/note-processes/<stem>.md`) names where
notes of that kind belong (F7-AC1); `concepts.atomic_note` is the general
fallback. When `atomic_note` is a mapping with a `paths` list, the first entry is
taken, the same reading the rest of Tomo applies to that key; an empty `paths`
list counts as no path. A broken process file does not stop `new`:
`read_process` reports the error and the atomic-note path is used, which is
what the skill says in one line (F7-AC4).

## WHY the Title Starts Empty

`new` runs before the model has drafted anything, so there is no title yet.
The title is recorded by the first `stage`. Until then `stage` reports
`inbox_file` and `destination_file` as empty strings rather than a name built
from an empty title.

## WHY new Stores the Profile in meta.json

`new` reads `profile` from `vault-config.yaml` together with the inbox and the
atomic-note path and stores it in `meta.profile`. `deliver` never re-reads the
config, so a resume rebuilds the instruction set with the profile of the first
run (the same reason `generated` is fixed at `new`).

## WHY stage Resolves source_link Into note.md, Not Into draft.md

`{{source_link}}` depends on `keep_source`: `[[<source stem>]]` when the source
is kept, empty text when it will be deleted (a link to a deleted note would
dangle) or when there is no source. `keep_source` can change on any later
`stage` until `instructions_json` is done. Replacing the token inside `draft.md`
would destroy it: after a resolution to empty text there is nothing left to
re-resolve when the user then keeps the source, and a resolved `[[stem]]` cannot
be told apart from a link the model wrote. So `draft.md` stays exactly as the
model wrote it, token included, and every `stage` writes `note.md` beside it:
`draft.md` with every real `{{source_link}}` replaced (the positions come from
`lib/template_syntax`, so a fenced or escaped token is left alone, the same
tokens the filled-note check sees) and nothing else changed. The filled-note
check runs on `note.md`, the skill prints `note.md`, and `deliver` resolves
`draft.md` again with the same function before it checks and uploads, so a
`draft.md` rewritten after the last `stage` never ships with a stale link.
`note.md` is written atomically (temp file, then replace); a missing `draft.md`
removes any old `note.md` so a stale preview is never printed.

The value and the replacement come from `lib/template_syntax`:
`source_link_value(source_path, keep_source)` and `resolve_tokens(text,
{"source_link": value})`, the same rule and the same token positions that
`tokens()` and the filled-note check use. `resolve_tokens` replaces only the
names it is given, so a leftover `{{uuid}}` still reaches the check.

## WHY stage Refuses Rather Than Silently Ignores a Frozen Change

Once a delivery step is done, the title and destination are part of files that
already landed; once `instructions_json` is done, `keep_source` decides whether
the landed set holds a `delete_source`. A refused change returns `frozen: true`
and leaves `meta.json` unchanged, so the skill can tell the user why the rename
did not happen. The rule itself lives in `lib/note_meta.py`.

## WHY stage Runs the Filled-Note Check

The skill prints `note.md` after every `stage`. The check (closed fence, no
user-authored `tomo:` key, no `<%`, no `{{token}}` left) is reported with it so
problems surface during revision, not at `deliver`. Findings are output, not an
exit code: `stage` exits 0 so the agent reads the result instead of retrying.

## WHY Input Is Validated at the Boundary

Every path the script builds ends up in the Hashi instruction set or in a Kado
write in the vault. An empty title would name the note `.md`; a folder or note
path that is absolute, traverses or is hidden would point outside the vault
folders Hashi and Kado expect; a source outside the inbox would make Tomo write
and delete outside it; a malformed stem would build a path outside
`tomo-tmp/note/`. Each exits 2 with a message that names the problem class
only, never the value.

## WHY Every Folder Goes Through One Validator

The destination is the folder of the `move_note` target. The inbox is the
folder of `inbox_file`, which `deliver` writes through Kado and which is the
`move_note` source. So an absolute, traversing or hidden folder must never reach
`meta.json`, whatever its origin. There are four origins: `--destination` on
`stage`, the process file's `destination`, and `concepts.atomic_note` and
`concepts.inbox` in `vault-config.yaml`. All four go through `vault_folder()`
from `lib/note_paths.py`, the only place the rule lives; the rules and their
reasons are in `docs/tomo/scripts/lib/note_paths.md`. `note-process.py write`
applies the same function before it saves a process file, and
`lib/note_process.py` applies it again on read, so a destination the user saves
is one `new` accepts, byte for byte.

For the process file, `new` relies on that check on read and does not repeat
it. `read_process` returns the destination in `vault_folder` form, or an empty
string, and reports a destination `vault_folder` refuses as its `error`.
`vault_folder` returns its own output unchanged, so a second check in `new`
could never fail. Up to 0.1.5 `new` checked again, with a stderr line of its
own. That check was needed while `lib/note_process.py` accepted any non-empty
destination on read; since its 0.1.2 refuses what `vault_folder` refuses, the
line could no longer be reached, and 0.1.6 removed it.

A failure is handled by origin. `--destination` exits 2, nothing written. A
process-file destination that fails falls back to the atomic-note path with one
stderr line naming the problem class. It is the `error` from `read_process`,
the same line a broken process file gets (F7-AC4): a bad process file must not
stop `/note`. An invalid `concepts.atomic_note` or
`concepts.inbox` exits 2 with a fixed message that names the key, because there
is no further fallback and the config is the user's to fix. Until 0.1.4 the
inbox was only refused when blank, so `../x`, `/abs` and `" In/../.."` reached
`inbox_file` unchanged.

## WHY --template and --source Pass the Same Rules

`--source` is the path with the most consequences. It becomes
`move_note.source_inbox_item` and `delete_source.source_path` in the instruction
set, `deliver` writes the source mark to it through Kado, and its stem becomes
the `[[link]]` in `note.md`. `--template` is stored in `meta.json`, shown when a
kept draft is offered for resume, and its stem names the process file. Until
0.1.4 both were only required to end in `.md`. `vault_note()` applies the folder
rules to the whole path, file name included, so `In/.hidden.md` and `In/.md`
are refused, and requires `.md`. Like a folder, the path is stripped once and
stored stripped. Both flags are checked before Kado is asked, so an unsafe
source is never read.

## WHY --source Must Lie Inside the Inbox

The source mark is a Kado write, and `delete_source` removes the file when the
set is applied. Tomo writes to the vault only inside the inbox (CON-2), and a
`/note` source is an inbox note (F5-AC2; the SDD names `--source` an inbox note
path). A source outside `concepts.inbox` would make `deliver` write outside the
inbox and the set delete a filed note. A clean path such as
`Atlas/202 Notes/Filed.md` passes every shape rule, so this check is separate
and runs once the config is read. It uses `note_paths.is_inside()`, which
compares `path_key` values (NFC, then casefold), because the vault may be case-insensitive and macOS hands back
decomposed names. The inbox's trailing `/` puts the comparison on a segment
boundary, so `100 Inbox Archive/x.md` is not inside `100 Inbox/`. Subfolders of
the inbox are inside, as in recursive inbox discovery (spec 034).

## WHY Unsafe Characters and Unicode Forms Follow lib/note_paths

Folders, note paths and titles share `has_unsafe_char()` from
`lib/note_paths.py`. Which characters are unsafe, and why Unicode is never
normalised, is explained in `docs/tomo/scripts/lib/note_paths.md`.

## WHY new Removes the Stage When a Write Fails

`source.md` and `meta.json` are written after the stage directory exists. A
failure between the two would leave a directory without `meta.json`, which the
next session reports as a stale stage. So both files are written atomically
(temp file, then replace) and any `OSError` while writing them removes the stage
directory before `new` exits 2.

## WHY the Title Is Trimmed and Loses Its Trailing Dots

The title becomes a file name in the inbox and in the destination. Surrounding
whitespace is trimmed. An unsafe character (Cc, Cf, Zl, Zp; newline included) is
rejected, not replaced, anywhere in the title, ends included: it is a sign the
caller passed the wrong text, and a newline in a file name breaks wikilinks.
Trailing dots and spaces are stripped, because Windows does not allow a file
name ending in either, so a vault opened on Windows breaks on them, and `foo.`
would otherwise become `<stem>_foo..md`. A title empty after trimming (`...`
included) is rejected. A title that starts with a dot is rejected, not
stripped: `destination_file` would be a hidden file (see the folder rules), and
stripping would change the title's meaning (`.NET` is not `NET`). Template
syntax (`{{`, `<%`) is rejected: a title such as `{{title}}` is an unfilled
token, and `{{` would reach both file names. Other characters Obsidian forbids
are left to `sanitize_stem`, which replaces them in the file name while the
title keeps them.

## WHY No User Text Reaches stdout or stderr

The source body and the draft are user content (CON-3). Only the fields the SDD
names as output (`title`, `inbox_file`, `destination_file`) carry user-chosen
text, because the skill prints them in the draft header. Error messages name the
problem class, never the value, and the source body goes only to `source.md`.

## WHY deliver Is One Process With a Fixed Order

`deliver` writes the note, then `<stem>_instructions.json`, then
`<stem>_instructions.md`, then merges the source mark (ADR-2). Three separate
script calls would leave the order, the collision handling and the resume
comparison to the model. The order is the order of consequence: the note is
inert on its own (triage skips it by its `rendered-note`/`pending-move` stamp),
the JSON is what Hashi acts on, the MD is its human-readable peer and the one
file triage counts as downstream of the marked source, and the mark is last
because a marked source with no set beside it would read as an orphan. When a
step fails, no later step runs: the source stays unmarked, the stage directory
stays with `failed_step` set, and the next `/note` offers resume. `meta.json` is
written after every step, so a process killed between steps leaves
`steps_done` accurate with `failed_step` empty, and `note-session.py start`
lists it as a kept draft (part of it is already in the vault), never as a stale
stage to drop.

## WHY deliver Checks the Draft Again

`deliver` resolves `{{source_link}}` in `draft.md` with the same function as
`stage` and runs the filled-note check on the result. The skill may have
rewritten `draft.md` after the last `stage`, and the check is the script's
gate, not a step the model is trusted to have run. A failing check, a missing
`draft.md` or a draft with no title refuses delivery before Kado is asked.

## WHY Every Generated File Is Byte-Stable

A resume rebuilds every payload and compares it with what is already in the
vault, so two runs over the same `meta.json` must produce the same bytes. The
set takes `generated` and `profile` from `meta.json` (fixed at `new`). The
`tomo:` blocks of the note and of the MD peer carry `updated_at`, which
`build_tomo_block` sets from the clock; `deliver` sets it to `meta.generated`
instead. For the same reason the MD peer is rendered without a run id and its
`tomo:` block (`instructions`/`pending-apply`, with the draft's run id) is then
inserted by `merge_tomo_block_into_markdown`, rather than letting
`render_instructions_md` stamp it with the current time. The block is what
makes triage count the peer as an instruction set; without it triage would warn
that the marked source is orphaned. The source mark is not compared, so it is
`build_tomo_block("source", "captured", run_id)` as `mark-captured.py` writes
it (ADR-3).

## WHY a Resume Compares Instead of Skipping or Overwriting

Before each write `deliver` asks whether the target exists. Absent: write it.
Present with the same text as the payload: a previous run wrote it, the step
counts as done. Present with other text: the user edited it in Obsidian, or
another file has the name; `deliver` exits 3 with `EXISTS:<path>` on the first
line and writes nothing more, because overwriting would destroy the user's
edit. Kado's reads return the stored text, so the comparison normalises only a
trailing newline. The comparison runs for steps already in `steps_done` too, so
a note the user edited in Obsidian between two runs is reported as taken, not
silently shipped. A step in `steps_done` whose target is now absent is never
written again: the file may already have been applied by Hashi (the note moved
to its destination), and a second copy would be a duplicate. The probe is `KadoClient.path_exists`, the same one
`kado-write-file.py --no-overwrite` uses, with the same exit code and stdout
line, so the skill reads one contract.

## WHY the Destination Is Checked Before Any Write

The note's final place is outside the inbox, where Tomo does not write; Hashi
moves it there later. A note already at `destination_file` would make the move
fail or overwrite it, so `deliver` runs `validate_destinations` over the set
with a listing of the destination folder before it writes anything, and a
clash exits 3 with `EXISTS:<destination>`. Nothing is in the vault yet, so the
skill can offer a rename.

## WHY a Set the Guards Cut Is Refused

`validate_destinations` and `withdraw_unjustified_deletes` drop actions
without raising. In Pass 2 that is right: the dropped item is reported in the
MD and the rest ships. A `/note` set has one move and at most one delete; a
cut set is either empty or a delete without its move, which would remove the
source while refusing to file the note. So `deliver` compares the guards'
output with its input and refuses any difference with status `withdrawn`
(exit 1), writing nothing.

## WHY the Stage Directory Is Removed Only on Success

The stage directory is the record of what landed (`steps_done`) and of what is
still to do. Removing it after a failure would lose the resume and leave files
in the inbox that no draft accounts for. On success nothing is left to resume,
and a leftover directory would be offered again at the next `/note` (ADR-7).
