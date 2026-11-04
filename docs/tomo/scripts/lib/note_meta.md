# WHY: lib/note_meta.py

> Rationale for decisions in `tomo/scripts/lib/note_meta.py`.
> The module owns `tomo-tmp/note/<stem>/meta.json`, the draft state of one `/note`
> draft (spec 044, ADR-7), and the listing of stage directories.

## WHY One Library Owns meta.json

Two scripts touch draft state: `note-instructions.py` (`new`, `stage`, `deliver`,
`drop`) writes it, and `note-session.py start` lists it to offer resume. Hyphenated
scripts cannot import each other, so the field set, the frozen rule and the
kept/stale split live here once. A second reader that re-derived "a kept draft is
one with `failed_step` set" would drift from the writer the first time either
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

## WHY a Stage Without failed_step Is Stale, Not Kept

`failed_step` is set only by a delivery that failed (F6-AC1); that draft has
nothing left to ask and can resume. A stage directory without it is a dialogue
that was interrupted before approval: it holds user material but no approved
note, so `start` reports it as stale and the skill drops it. A directory whose
meta.json is missing or unreadable is stale for the same reason: `new` writes
meta.json right after creating the directory, so its absence means the run died
in between.

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
temp file and `os.replace` keeps either the old or the new state on disk.
