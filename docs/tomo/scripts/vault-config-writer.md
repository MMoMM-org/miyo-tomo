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
