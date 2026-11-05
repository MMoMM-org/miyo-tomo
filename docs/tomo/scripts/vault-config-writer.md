# WHY: scripts/vault-config-writer.py

The WHY layer for `tomo/scripts/vault-config-writer.py`. Created 2026-09-13,
when a section write was found destroying user configuration.

## Why a section write must preserve curated keys

`replace_top_level_section` does exactly what its name says: the whole
`trackers:` block is replaced by whatever the caller supplied. Everything
*outside* the block survives byte-for-byte — that is the design, and it is
still right. What was missing is that the same guarantee has to hold *inside*
the block for values the caller cannot know.

`/explore-vault` rediscovers tracker fields by scanning daily notes. It can
determine a name, a type, a syntax and a placeholder description. It cannot
determine `positive_keywords`, `negative_keywords`, `keywords` or `active` —
those come from a person, through `tomo-trackers-wizard`. So every rediscovery
pass emitted a JSON without them, the writer replaced the block, and the
keyword lists were gone.

The failure is silent at every layer. The schema does not require keywords, so
the config still validates. The analyst reads `positive_keywords` and falls
back to splitting the `description` into words when it finds none — with no
complaint. The only symptom is that trackers stop matching, which reads as
"nothing matched today" rather than "the configuration was deleted". In a
German vault the fallback cannot fire either, because the descriptions are
English, so the degradation is total rather than partial.

`preserve_curated_tracker_keys` closes it: for every field the input carries,
any key in `TRACKER_CURATED_KEYS` that the input does not supply is taken from
the config on disk.

**Why in the writer and not in `/explore-vault`.** The agent is one caller.
Putting the merge there protects that path and leaves the next caller — a
future wizard, a migration script, a hand-run command — free to repeat the
same loss. The writer sees both versions by construction and is the only place
that can make the guarantee hold for everyone.

**Absent versus empty is the whole distinction.** A missing key means "not
supplied" and is restored. An explicit `[]` means "cleared on purpose" and is
respected. Without that split there would be no way to ever remove a keyword.

**Matching is by (list, field name).** A renamed or deleted field keeps
nothing. That is a real change the caller is making, not an omission to repair,
and guessing across a rename would be worse than losing the keywords.

**It runs before the `--stdout` branch** so a preview shows what would actually
be written. A dry-run that omits the preservation would advertise a data loss
that is not going to happen.

**It reports on stderr.** A rescue nobody is told about is only half a fix —
and the line is what tells a user their wizard work survived a rediscovery.

## Why `active` and `enabled` are preserved alongside the keywords

Both are switches a person set, and neither is discoverable by scanning a
vault. Losing `active: false` silently re-enables a tracker the user turned
off; losing `enabled: false` re-enables the whole feature. They belong in the
same set as the keyword lists for the same reason.

Neither is written when true: absent means on, so a config that predates the
switches gains no new lines and behaves exactly as before.

## Guard

`tests/test_tracker_config_durability.py::TestWriterPreservesCuratedValues`,
including an end-to-end case that drives `cmd_trackers` over a real YAML file.
The unit tests cover the merge function; the end-to-end test is what catches a
regression at the *call site*, which is where the bug would come back — the
function can be perfectly correct and simply not be called.

## Why `templates-include` edits one key inside the block (ADR-5)

`/note` (spec 044) needs to save one user choice: which template filenames
under `templates.base_path` are note templates (`templates.note_include`, a
list of globs). Every other subcommand renders a whole top-level block and
hands it to `replace_top_level_section`. That is the wrong tool here: the
`templates:` block is hand-curated — `base_path`, the `mapping` with its
explanatory comments, the commented `default:` hint, the `custom_tokens`
example — and no caller of `templates-include` knows any of it. Rendering the
block from the input would drop all of it, the same class of loss the tracker
preservation above had to repair after the fact.

So `templates-include` changes only the `note_include` lines:

- **Key present** — the key line and its list continuation lines (deeper
  indented, or `- ` items at the key's own indent) are replaced. A flow list
  on the key line (`note_include: ["t_*.md"]`) is one line and is replaced the
  same way. A quoted key (`"note_include":` or `'note_include':`) is the same
  key to YAML, so it is replaced too; inserting a second, unquoted key next to
  it would leave two keys of which YAML silently keeps one.
- **Comments around the list** — a comment line after the last list item is
  the user's and is kept, even when it is indented deeper than the key. A
  comment *between* two list items is part of the list being replaced and goes
  with it: the old list is gone, so a comment about one of its entries has
  nothing left to describe, and keeping it would need a guess about which new
  entry it belongs to.
- **Key absent** — the key is inserted after the last non-blank line of the
  `templates:` block, at the indent the block's own children use, so trailing
  blank lines and the next section's banner stay where they were.
- **No `templates:` block** — a minimal `templates:` block holding only the
  key is appended, through the same append path the section writers use.

Every byte outside those lines stays identical. The byte-identity tests in
`tests/test-vault-config-writer.py` are the guard: they compare the file
before and after with the `note_include` lines removed.

**Why a hand-written validator.** As for the other subcommands, `jsonschema`
is not guaranteed in the container. The rule is small — exactly one key,
`note_include`, a non-empty list of non-empty strings — and
`tomo/schemas/vault-config-templates.schema.json` documents the same contract.
An empty list is rejected rather than read as "clear": "no note templates" is
expressed by the key being absent, which is the state `/note`'s first-run
setup detects, and an empty list would be a third state nobody reads.

**Why `yaml.safe_load` and a read-back before writing.** Textual insertion can
produce YAML that parses but means something else — a `templates:` written as
an inline `{}`, a duplicate key further down that overrides ours. The writer
parses the result and requires `templates.note_include` to equal the input
list. Anything else exits 1 and the file is not touched.

**Why a duplicate the edit introduces refuses the write.** `yaml.safe_load`
does not reject duplicate keys — it keeps the last one. A read-back with plain
`safe_load` therefore passes on exactly the result it exists to catch: a
second `templates:` block appended below the user's (their `base_path` and
`mapping` shadowed), or a second `note_include` next to one the matcher missed.
So the writer lists every repeated mapping key, with its path, in the file
before the edit and in the result. A path repeated more often in the result
than in the original is one the edit made: exit 1, nothing written.

**Why a duplicate already in the file is not blamed on the edit — outside
`templates:`.** An earlier version refused any duplicate in the result, so a
repeated key in some unrelated section (`trackers:`, `tags:`) blocked saving
`note_include` and the error blamed "resulting YAML" — the edit, which had not
caused it. The edit never touches that section and every reader of it is as
confused before the save as after it, so refusing helps nobody. Such a
duplicate is left alone and the write proceeds; the result still has to parse
and read back `templates.note_include` equal to the input under plain
`safe_load`.

**Why a duplicate inside `templates:` is still refused, even when it was
already there.** Two `templates:` blocks, or two `note_include` keys in one
block, mean the edit can land in the copy YAML throws away: the writer edits
the first block or the first key, `safe_load` keeps the last. The save would
report success and `/note` would read the other copy. The writer therefore
refuses any duplicate whose path starts at `templates` (the top-level
`templates` key itself included), and the error names it as already in the
file, so the user fixes the file instead of retrying the save.

**Why the errors carry no config text.** Stderr from this subcommand ends up
in the model's context and in session transcripts; the config can hold vault
paths, folder names and tokens. A YAML parse error is reported as its
exception class and line number only — the raw PyYAML message quotes the
offending line. A duplicate is reported as introduced or pre-existing with its
line number, never its key. An invalid glob is reported by its index in
`note_include`, never by its value.

**Why a glob with leading or trailing whitespace is rejected.** `" t_*.md "`
is a non-empty string, so it used to pass, and then it never matched a
filename — the save looked fine and `/note` found no templates. The input is
written by the model, so the writer exits 1 and names the index; it does not
strip silently, which would save something other than what the model meant
and keep the model from learning its input was wrong. The schema's `pattern`
says the same: no whitespace at either end.

**Why line endings are preserved (CRLF).** A config saved on Windows, or by an
editor set to CRLF, ends every line with `\r\n`. The file is read and written
without newline translation, so its endings survive; the key-line matchers
accept a trailing `\r`, so the `templates:` header is still found in a CRLF
file (otherwise a second block would be appended); and the inserted lines use
the file's own ending — the one its first line uses — so one file never mixes
the two. Reading with Python's default text mode would instead turn every
`\r\n` in the file into `\n`, changing every line of a file that promises to
change one key. The CRLF-tolerant header check (`_is_top_level_key_line`) is
shared with the older section subcommands; they read in default text mode, so
their input never holds a `\r` and their behaviour is unchanged.

**Why an atomic write.** The new text goes to a temporary file in the
config's own directory, takes the config's permission bits, and replaces the
config with `os.replace`. An interrupted write then leaves the old config or
the new one, never half of one. The older section subcommands still write in
place; they were not changed with this one.

**Why `--stdout` prints only the key lines.** It previews the `note_include`
lines the edit would write, not the whole `templates:` block: the rest of the
block is the user's and the edit does not change it. It matches the sibling
subcommands, which print the block they would write, and it never reads or
writes the config — so it cannot report the duplicate or read-back refusals a
real save would hit.
