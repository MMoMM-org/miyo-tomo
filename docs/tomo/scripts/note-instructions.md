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

An empty title would name the note `.md`; a destination with `..` or a leading
`/` would point outside the vault folders Hashi expects; a malformed stem would
build a path outside `tomo-tmp/note/`. All three exit 2 with a message that
names the problem class only.

## WHY Every Destination Goes Through One Validator

The destination becomes the `move_note` target of the Hashi instruction set,
so an absolute or traversing folder must never reach `meta.json`, whatever its
origin. There are three origins: `--destination` on `stage`, the process file's
`destination`, and `concepts.atomic_note` in `vault-config.yaml`. All three go
through `vault_folder()`, the only place the rule lives. It strips the value
once and rejects a value that starts with `/`, contains `\`, contains a control
character (Unicode category Cc, newline and tab included), or has a segment
that is empty, `.` or `..` after stripping (one trailing `/` is allowed). The
accepted value is returned with exactly one trailing `/`. Checking the stripped
value is the point: an earlier check on the raw value let `" /etc"` become
`/etc`, and an unstripped segment let `a/ ../b` through.

A failure is handled by origin. `--destination` exits 2, nothing written. A
process-file destination that fails falls back to the atomic-note path with one
stderr line naming the problem class, the same as a broken process file (F7-AC4):
a bad process file must not stop `/note`. An invalid `concepts.atomic_note` exits
2 with a fixed message, because there is no further fallback and the config is
the user's to fix.

## WHY new Removes the Stage When a Write Fails

`source.md` and `meta.json` are written after the stage directory exists. A
failure between the two would leave a directory without `meta.json`, which the
next session reports as a stale stage. So both files are written atomically
(temp file, then replace) and any `OSError` while writing them removes the stage
directory before `new` exits 2.

## WHY the Title Is Trimmed and Loses Its Trailing Dots

The title becomes a file name in the inbox and in the destination. Surrounding
whitespace is trimmed. A control character (newline included) is rejected, not
replaced: it is a sign the caller passed the wrong text, and a newline in a file
name breaks wikilinks. Trailing dots and spaces are stripped, because Windows does not
allow a file name ending in either, so a vault opened on Windows breaks on them,
and `foo.` would otherwise become `<stem>_foo..md`. A title empty after trimming (`...` included) is rejected.
Other characters Obsidian forbids are left to `sanitize_stem`, which replaces
them in the file name while the title keeps them.

## WHY No User Text Reaches stdout or stderr

The source body and the draft are user content (CON-3). Only the fields the SDD
names as output (`title`, `inbox_file`, `destination_file`) carry user-chosen
text, because the skill prints them in the draft header. Error messages name the
problem class, never the value, and the source body goes only to `source.md`.
