# WHY: lib/note_actions.py

> Rationale for decisions in `tomo/scripts/lib/note_actions.py`.
> The module builds the instruction set a `/note` draft delivers (spec 044,
> SDD "NoteInstructionSet", ADR-2, ADR-7): one `move_note`, and a
> `delete_source` when the draft came from an inbox note the user does not keep.

## WHY a Library, Not Code Inside note-instructions.py

The set is built twice per draft lifetime: `deliver` builds it to write
`<stem>_instructions.json`, and a resumed `deliver` builds it again to compare
against the file already in the inbox. The tests also build it to validate it
against `hashi-instructions.schema.json` with `jsonschema`. A hyphenated script
cannot be imported by name, so the builder lives in `lib/` where the script, its
resume path and the tests share one implementation.

## WHY the Set Is Built Only From the Draft State

Every input is in `NoteDraftMeta` (stem, `generated`, title, destination,
`inbox_file`, `source_path`, `keep_source`, `profile`) plus the wire version. Nothing reads the clock or Kado. A resume therefore rebuilds a
byte-identical JSON file, which is what lets "identical target counts as done"
(F6-AC3) work: a builder that stamped `now()` would turn every resume into a
name collision.

## WHY move_note Carries Exactly Seven Keys

`move_note` in the Hashi schema has `additionalProperties: false`. The builder
writes the seven keys the SDD names (`id`, `action`, `source`, `destination`,
`title`, `rendered_file`, `source_inbox_item`) and no Pass 2 field
(`audio_peer`, `parent_mocs`, `tags`, `applied`). Copying a Pass 2 action as a
starting point would carry such a field over and Hashi would reject the whole
set at apply time, one layer below where Tomo can report it.

`source_inbox_item` is `null` for a text-in-call draft: the schema types it as
string-or-null, and null says "no inbox origin" explicitly instead of leaving
the reader to infer it from an absent key.

## WHY delete_source Depends on I01 Only

The source note's content is carried into the new note by the `move_note`;
nothing else captures it. `depends_on: ["I01"]` makes Hashi withhold the delete
until that move applied, so a failed move never costs the source. The key is
always written: the schema requires it, and an empty list would mean "a
user-requested deletion with no partner", which this is not (spec 036 F5-AC2).

The delete is emitted only when there is a source and `keep_source` is false
(F5-AC2). A text-in-call draft has nothing to delete.

## WHY schema_version Comes From the Schema File

`wire_schema_version("instructions.schema.json")` is the same call every other
instruction-set producer makes (spec 035 ADR-5). A literal here would let a
schema bump and this producer drift apart without a failing test.

## WHY the Profile Comes From the Draft State

`build_note_instruction_set` takes the profile from `meta.profile`, which
`note-instructions.py new` stored from `vault-config.yaml`. The builder takes no
separate profile argument: with one, a caller could pass a freshly read config
value on resume and rebuild a set that differs from the one already in the
inbox. Reading it from the draft state keeps every input of the set in one
place and keeps the builder free of filesystem reads.
