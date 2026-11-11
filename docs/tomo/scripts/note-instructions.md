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

Once a delivery step is done or its upload is in flight (`failed_step` names
it), the title and destination are part of files that may already have landed;
once `instructions_json` is done or in flight, `keep_source` decides whether the
landed set holds a `delete_source`. A refused change returns `frozen: true`
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
directory before `new` exits 2. Every atomic write here goes through
`lib/note_io.atomic_write_text`, and `vault-config.yaml` is read with
`lib/note_io.load_vault_config`; this script turns any `ConfigError` into
exit 2 (see `docs/tomo/scripts/lib/note_io.md`).

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

## WHY the Deliver Loop Lives in lib/staged_delivery.py (spec 045, ADR-11)

Since spec 045 the per-step loop (`deliver_step`, `mark_in_flight`, `record`,
`fail`) and `stable_block` are `lib/staged_delivery.py`, shared with
`/review`. `deliver` builds one `StagedDelivery` with its own step set
(`lib/note_meta.STEPS`), its own step → path map (`_targets`) and a closure
over `write_meta` as the persist callable, then runs the three inbox steps
through `deliver_step` and the source mark through `record`/`fail`. The rules
below (in flight before the upload, compare instead of skip or overwrite,
check-then-act) describe the loop's behaviour, unchanged by the move; the
reasons for the extraction and for its shape are in
`docs/tomo/scripts/lib/staged_delivery.md`.

## WHY deliver Reports steps_done and frozen

Every `deliver` output carries `steps_done` and `frozen` from `meta.json` as it
stands when the run ends. On exit 3 and on a failed step the skill must know
two things: whether the name can still change (`frozen`, from
`lib/note_meta.is_frozen`) and which files a Drop leaves behind (`steps_done`).
They are separate fields because they disagree: a failed upload of the first
step leaves `steps_done` `[]` but `failed_step` `note`, and that note may be in
the vault, so the draft is frozen with nothing recorded as landed. A skill that
read "empty `steps_done` means Rename is open" would rename it and the resume
would write a second note. Reporting the verdict on stdout gives the skill the
answer from the call it just made instead of a second read of `meta.json` or a
re-derived rule. The tokens are the fixed step names and `frozen` a boolean,
never user text.

## WHY a Step Is Recorded as In Flight Before Its Upload

The upload and the `meta.json` write that records it are two operations, and
nothing makes them atomic. If the record fails (a local I/O error, exit 2) or
the process is killed between them on the first step, the vault holds the note
while `meta.json` still says `steps_done` `[]` and `failed_step` empty: exactly
the shape of an untouched stage. `note-session.py start` would list it as an
unfinished draft (a stale stage before the spec 044 live walk), whose Discard says
nothing landed in the inbox, orphaning a landed note. So `deliver` writes
`meta.json` with `failed_step` set to the step just before uploading it.
Whatever happens after that, the stage is a kept draft; a successful upload is
then recorded as done, which clears `failed_step` as before. A resume finds the
landed target with identical text and counts it as done, so the in-flight mark
costs no rewrite. Only uploads are marked: a probe or comparison that fails is
already recorded by the failure path, and the source mark is never the first
step, so `steps_done` is non-empty by then. The price is one extra local write
per upload, and `failed_step` meaning "failed or possibly landed", which is
what the skill's resume offer needs anyway. The freeze rule follows that
meaning: a delivery step named in `failed_step` freezes title and destination
(and `instructions_json` there freezes `keep_source`) exactly as a done step
does, so a rename cannot point the resume at a second inbox file while the first
one is already in the vault.

## WHY Missing Kado Config Is Its Own Step, kado_config

`KadoClient()` raises only when it cannot resolve a URL or a token (arguments,
`KADO_URL`/`KADO_TOKEN`, `.mcp.json`); it opens no connection. So this stop
means the instance has no Kado configuration, not that Kado is down. The step
is named `kado_config` for that reason: an earlier name, `kado_connect`, sent
the reader looking for a network outage that this branch never sees. A real
outage passes the constructor, reads as an empty listing in the destination
guard (an error is not a collision), and fails at the first step, `note`,
which records it like any other failed step.

When the constructor raises, `deliver` stops before the guards and before any
write. It reports `step` `kado_config` and records it as `failed_step` in
`meta.json`. Recording is what keeps the draft: a first delivery that stopped
there has neither `steps_done` nor `failed_step` otherwise, so
`note-session.py start` would list it as an unfinished draft (a stale stage, dropped
unasked, before the spec 044 live walk) and the user would have to approve the same
draft again. With `failed_step` set it is a kept draft and is offered for resume. Nothing is in
`steps_done`, so the resume reruns the whole delivery from the guards on. A
named step also lets the skill take its generic "report the failed step; the
draft stays" path instead of needing a branch for a missing configuration.

The filled-note check and the frontmatter stamp stop with an empty step and
the script records nothing for them: the fix is in `draft.md` and `stage`
reruns first, so there is no delivery state to keep.

Known leftover: a resume that connects and then stops on exit 3 (name taken)
or `withdrawn` leaves the old `kado_config` in `failed_step`, because only a
step marked done clears its own failed entry. This is harmless: the stage is
still a kept draft, which is what the skill offers on those exits anyway, and
the next failed step or a successful delivery replaces or removes it.

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

## WHY the MD Peer Has No Templater Hint

`render_instructions_md` adds "After moving: run `Templater: Replace Templates
in Active File`" to every `move_note` block, because a Pass 2 rendered note can
still carry Templater syntax. A `/note` note has none left: the filled-note
check refuses any leftover template token before `deliver` writes anything. The
hint would tell the user to run a command that does nothing, and the delivery
report must say exactly what applying the set will do (PRD F3-AC7). So
`deliver` passes `templater_hint: False` in the render config. The default stays
on, which keeps Pass 2 output unchanged.

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

## WHY a Source That Vanished Before the Mark Still Counts as Delivered

The source mark is the last step, and the note and the set are already in the
inbox when it runs. If the user deleted or moved the source in the meantime,
`read_frontmatter` or `write_frontmatter` raises `KadoNotFoundError`. Treating
that as a failure would fail `source_mark` on every resume, because the source
never comes back: the stage would never be removed, and `note-session.py start`
would list a fully delivered draft as a kept draft forever. There is nothing
left to mark, so `deliver` records `source_mark` as done, reports
`source_marked: false`, finishes as `delivered` and removes the stage
directory. `source_marked` reports what happened (a mark written, or found
already written on a resume after the step was recorded), not whether the
draft had a source. Every other Kado error still fails the step, because those
can pass and a resume then marks the source. The set's `delete_source` for
that source will find nothing to delete when it is applied; that is Hashi's
concern, and `deliver` does nothing about it.

## WHY the Mark Needs the Source's modified Time

The mark is a merge guarded by the `modified` time `read_frontmatter` returns
(ADR-3), so an edit the user makes between the read and the write is not
overwritten. When the read returns no `modified`, the merge would run without
the guard. `deliver` fails the `source_mark` step instead; a resume reads again.

## WHY a Resume After a Recorded Mark Reads the Source

A run can be killed after `meta.json` recorded `source_mark` and before the
stage directory was removed. Every file is delivered then, and the mark was
written or the source found gone, so the resume does not write the mark again:
it reads the source's frontmatter and reports `source_marked: true` only when
`tomo:` is a mapping with `state: captured` and this draft's `run_id`. The state is how
triage recognises a captured source (`tomo.state=captured`;
`doc-frontmatter.schema.json` allows `captured` only for `doc_type: source`),
and the run id tells this draft's mark from a `captured` mark another run
wrote. Another run's mark, another state, no `tomo:` key, or a `tomo:` value or
frontmatter that is not a mapping all report `false`; so does a source that is
gone, as on a first run.

A Kado error other than not-found during that read fails the `source_mark`
step with exit 1, although the work is complete. `failed_step` is set and
`source_mark` stays in `steps_done`, so every resume reads again: a persistent
error keeps the draft a kept draft until a read succeeds or the user drops it
at the next `/note` (`drop` removes the stage directory, never the delivered
files). This is accepted because the error leaves the answer unknown and
`deliver` does not guess: `false` could report a mark that is there as missing,
`true` a mark nobody read. Nothing in the vault is at risk while the draft
waits, and the same error fails the step on the first run's write too.

## WHY Some Probes Are Check-Then-Act or Fail Open

Each inbox step asks `path_exists` and then writes. That pair is
check-then-act: a file that appears between the two calls is overwritten,
because Kado's `write_note` and `write_file` create or overwrite and offer no
create-only mode. The window is two calls on files with a fresh stem, so it is
accepted rather than worked around.

The destination probe uses `make_folder_listing`, which fails open: a listing
error counts as an empty folder, the documented behaviour of the destination
guard ("an error is not a collision"), so a failed listing does not block the
delivery.

## WHY a Failed meta.json Write Exits 2

Writing `meta.json` is local I/O: an `OSError` there ends the run with exit 2
and no JSON on stdout, like every other local I/O failure of the script, and
the stage keeps the last `meta.json` that was written.

## WHY the Stage Directory Is Removed Only on Success

The stage directory is the record of what landed (`steps_done`) and of what is
still to do. Removing it after a failure would lose the resume and leave files
in the inbox that no draft accounts for. On success nothing is left to resume,
and a leftover directory would be offered again at the next `/note` (ADR-7).

## WHY NOTE_FILE Comes From lib/note_meta.py

`stage` writes `note.md`, and `lib/note_meta.list_stages` reads its presence as
the `staged` signal of an unfinished draft. The name is defined once in the
library and imported here, so the writer and the listing cannot name different
files.

## WHY stage Writes tomo-tmp/note/view.md

The user must see the whole staged draft before approving it. Printing it was
the model's job, and live it failed in two ways: the model wrote the text into
its thinking and called `AskUserQuestion` with nothing visible (sessions
2e8fb1d3, 23125562), and the dialog preview that 0.2.11 fills is cut off by the
terminal for a long draft. `view.md` is the deterministic copy the
`tomo-note-view` mod draws in a side pane (spec 044 ADR-9, F4-AC5; see
[tomo-note-view](../dot_claude/skills/tomo-note-view.md)).

- One file, `tomo-tmp/note/view.md`, not one per stem: only one draft is at the
  approval question at a time, and the mod then needs no stem to find it. It
  sits beside the stem directories and `list_stages` only reads directories
  whose name is a stem, so it is never taken for a draft.
- The header is the SKILL step 6 header in its wording, built from `meta.json`:
  `Template: <template stem> · Final name: <destination_file> · In the inbox
  until applied: <inbox_file name>`, then `Source <source path> is deleted when
  you apply the instruction set in Hashi.` only when there is a source and
  `keep_source` is false, exactly when step 6 shows that line. The skipped line
  is left out: which points were skipped is known only in the conversation, so
  the script cannot write it and must not guess it. Each header line is its
  own Markdown paragraph so the pane draws them as separate lines.
- `note.md` follows in a fence one backtick longer than the longest backtick
  run in it (at least four), so a code block inside the note cannot end the
  fence early.
- `stage` removes `view.md` before it does anything else and writes it again
  only when the stage has a title and the filled-note check passes. A refused
  stage (exit 2), an untitled stage or a failing check therefore leaves no
  `view.md`: the pane never shows another stem's draft, and never a draft the
  skill is about to fix before asking.
- `new`, `deliver` (at its start, whatever the outcome) and `drop` remove it:
  after each of them no approval question is due for the staged text. A
  restage after a failed delivery or a Rename writes it again.
- It is local instance state like `note.md`; nothing on stdout or stderr
  changes (CON-3), and the exit codes are unchanged.
