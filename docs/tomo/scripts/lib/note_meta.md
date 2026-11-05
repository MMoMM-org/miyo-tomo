# WHY: lib/note_meta.py

> Rationale for decisions in `tomo/scripts/lib/note_meta.py`.
> The module owns `tomo-tmp/note/<stem>/meta.json`, the draft state of one `/note`
> draft (spec 044, ADR-7), and the listing of stage directories.

## WHY One Library Owns meta.json

Two scripts touch draft state: `note-instructions.py` (`new`, `stage`, `deliver`,
`drop`) writes it, and `note-session.py start` lists it to offer resume. Hyphenated
scripts cannot import each other, so the field set, the frozen rule and the
kept/stale split live here once. A second reader that re-derived "a kept draft is
one with `failed_step` set or `steps_done` non-empty" would drift from the writer the first time either
changed.

## WHY Title and Destination Freeze Once a Step Is Done

`steps_done` non-empty means at least the note already landed in the inbox under
`inbox_file`, and the instruction set may already point at `destination_file()`.
Renaming after that would leave a landed file under the old name and a resumed
delivery writing a second file under the new one. `apply_stage_update` refuses the
whole update (title, destination and keep_source) when any frozen field would change,
so a refused call leaves meta.json exactly as it was. Restating the current value
is not a change: the skill may pass every field on each `stage` call.

## WHY keep_source Freezes Once instructions_json Is Done

The instruction set carries a `delete_source` action exactly when `keep_source`
is false. Once `instructions_json` is in `steps_done`, that set has landed in the
inbox; flipping `keep_source` afterwards would make a resumed delivery rebuild a
different set (`delete_source` added or removed) than the one already written,
and the user would approve one set while another one is on disk.

It does not freeze earlier, at `note`: until the set is written, keeping or
deleting the source is still the user's free choice in the dialogue (PRD
F4-AC3), and nothing on disk depends on it yet. The same all-or-nothing rule
applies: a refused `keep_source` change leaves title and destination untouched,
and a refused title or destination change leaves `keep_source` untouched.
Restating the current `keep_source` is not a change.

## WHY a Started Delivery Is Kept and Only an Untouched Stage Is Stale

A kept draft is a delivery that started and did not finish: `failed_step` is set
(a step failed, F6-AC1, or the Kado configuration was missing: `kado_config`) or `steps_done` is non-empty (SDD "Interrupted
delivery"). The second case has `failed_step` empty because the process was
killed between steps, before any step could record a failure. Part of that
delivery is already in the vault (at least the note in the inbox), so dropping
it silently would orphan a landed file; it is offered for resume or drop like a
failed one. A kill between an upload and its record cannot fall through to
stale: `note-instructions.py deliver` sets `failed_step` to the step before
uploading it, so the in-flight step already keeps the draft.

A stale stage has neither `failed_step` nor `steps_done`: a dialogue that was
interrupted before approval. It holds user material but nothing landed, so
`start` reports it as stale and the skill drops it. A directory whose meta.json
is missing or unreadable is stale for the same reason: `new` writes meta.json
right after creating the directory, so its absence means the run died in
between.

## WHY FAILED_STEPS Is Separate From STEPS

`kado_config` is where a delivery stops when no Kado URL or token can be
resolved (the client constructor opens no connection, so an outage fails at
`note` instead): a stop point, not a vault target. It may be recorded as `failed_step` (so the draft is
kept rather than listed as stale) but is never in `steps_done`, because nothing
was written. `FAILED_STEPS` (`KADO_CONFIG` plus `STEPS`) is what
`mark_step_failed` and `read_meta` accept for `failed_step`; `STEPS` stays the
list of vault targets that `mark_step_done` and the `steps_done` check accept.
Adding `kado_config` to `STEPS` instead would shift the `INBOX_STEPS` and
`SOURCE_MARK` slices in `note-instructions.py` (`STEPS[:3]`, `STEPS[3]`), let a
corrupt `steps_done` holding `kado_config` pass validation and freeze title and
destination with nothing landed. The separate tuple keeps the slicing, the
freeze rules and the `steps_done` validation unchanged.

## WHY read_meta Checks Every Field's Type

meta.json sits on disk where a crash, a hand edit or a future writer bug can
leave a valid JSON object with wrong types. The freeze checks test membership
(`"instructions_json" in meta.steps_done`); on a string `steps_done` that is a
substring match, so a corrupt file could freeze or unfreeze `keep_source` by
accident. `read_meta` therefore accepts only: every string field a `str`
(`source_path` a `str` or null), `keep_source` a `bool`, `steps_done` a list of
known steps (`STEPS`) without duplicates, `failed_step` empty or one of
`FAILED_STEPS`, and `stem`
equal to the directory name (a copied meta.json must not deliver under another
draft's names). Anything else raises MetaError, and the listing counts the
directory as stale, the same as unreadable JSON.

`source_path`, `profile`, `keep_source` and `steps_done` are checked outside the plain
string-field list because each has its own shape (string or null, string or
null, boolean, list of steps).

## WHY the Profile Is Part of the Draft State

The instruction set carries the vault-config `profile`. `new` reads it once and
stores it in `profile`; every `deliver` builds the set from meta.json alone. If
`deliver` re-read the config, a profile edited between a failed delivery and its
resume would rebuild a different `<stem>_instructions.json`, and the resume
would see a name collision instead of an identical file (F6-AC3). The field is
defaulted to null so a meta.json written before it existed still reads; such a
draft delivers with `profile: null`, which the Hashi schema allows.

## WHY a Missing Defaulted Field Reads as Its Default

`keep_source`, `steps_done`, `failed_step` and `profile` have dataclass defaults
(`false`, `[]`, `""`, null). `read_meta` validates each of them only when its key is present; an
absent key takes the default. An older or partial meta.json must not be dropped
as stale: a file without `failed_step` whose `steps_done` is `["note"]` is a
started delivery with a note already in the inbox, and rejecting it for the
missing key would silently drop that draft, the data loss the kept/stale split
exists to prevent. A key that is present with the wrong type is still rejected.

## WHY Error Messages Never Carry the Offending Value

Script output reaches the model. A stem, template stem or step name supplied by
a caller, or text read from meta.json, may carry vault folder names or note
titles the user considers private, and an attacker-shaped argument should not be
echoed back into the model's context. ValueError and MetaError therefore use
fixed text naming the problem class (malformed stem, unknown step, field of the
wrong type), never the value.

## WHY new_meta Takes stem as a Keyword-Only Parameter

`stem` is needed before the dataclass is built (it names the inbox file). Taking
it from `**fields` turned a forgotten stem into a bare `KeyError: 'stem'`; an
explicit keyword-only parameter fails with a TypeError that names the missing
argument.

## WHY the Stem Is Validated Before Any Path Is Built

`drop` deletes a directory named from a CLI argument. Accepting only
`YYYY-MM-DD_HHMMSS` means a stem can never climb out of `tomo-tmp/note/`, and the
listing can skip foreign entries such as `process-outline.json` without guessing.
The stem carries seconds because Pass 2 sets use `YYYY-MM-DD_HHMM`; both end in
`_instructions.json`, and seconds keep two `/note` drafts in one minute apart.

## WHY the Destination Is Normalised to a Trailing Slash

`destination_file()` is `destination + sanitize_stem(title) + ".md"`. A process
file or a user answer may name the folder without the slash; normalising on every
write keeps the concatenation correct without each caller remembering it.

## WHY sanitize_stem From lib/obsidian_filename

Kado rejects Obsidian-forbidden characters on create. The inbox file and the
destination file must use the same sanitised title, and the transcription
pipeline already relies on `sanitize_stem` as the single conversion.

## WHY write_meta Replaces the File Atomically

A resume reads meta.json to decide what is done. A crash mid-write would leave a
truncated file that lists as stale and loses a failed delivery. Writing a sibling
temp file and `os.replace` keeps either the old or the new state on disk. The
write is `lib/note_io.atomic_write_text`, the one atomic write of the /note
scripts (see `docs/tomo/scripts/lib/note_io.md`).
