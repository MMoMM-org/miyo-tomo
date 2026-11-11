# WHY: lib/vault_config_edit.py

> Rationale for decisions in `tomo/scripts/lib/vault_config_edit.py`.
> The module owns text-preserving edits of one nested key in
> `vault-config.yaml`: insert, replace or remove a scalar, a list or a
> mapping at any depth, creating the missing parents on the way, while every
> other byte of the file stays as it was (spec 045, T2.1, ADR-5).

## WHY a Nested Editor Instead of the Section Writers

`vault-config-writer.py` renders whole top-level blocks
(`replace_top_level_section`) or one key inside `templates:`
(`set_templates_note_include`). The review setup touches four sections, some
of them hand-curated (`concepts`, `templates`), and inserts keys that do not
exist yet four levels deep (`concepts.calendar.granularities.weekly`). Rendering
`concepts:` from the input would destroy every other concept path the user
configured; the `templates-include` walker knows one key at one depth. The
generic walker here is the `templates-include` logic made recursive: find the
key line at the expected indent, descend into its block, insert at the end of
the block when a key is absent, replace the key's extent when it is present.

It lives in `lib/` rather than the writer because the writer is already the
largest script in `tomo/scripts` (SDD Implementation Gotchas: add only the
subcommand there) and because the line-walking helpers are shared with
`templates-include`; the writer imports them from here so the two edit paths
cannot drift.

## WHY Edits Apply One Leaf at a Time, in Order

A mapping value is decomposed into leaf paths and applied sequentially on the
text. The first leaf that finds `review:` missing appends the section; the
next leaf finds it and inserts inside it. One pass that tried to build the
whole tree at once would need to know the file's indentation before any of
the new lines exist; sequential leaves read the indentation the previous
insert produced. Order is the order of the caller's edit list, which is the
order the keys appear in the SDD's config example, so a created section reads
like the documented one.

## WHY a Key Is Found by Indent, Not by Name Alone

`weekly:` appears under `granularities` and under `review`. The walker searches
only the body of the parent it descended into and only at the indent the
parent's children use, so a same-named key under another parent is never
touched. A quoted spelling (`"weekly":`) is the same key to YAML and is found
too; inserting a second, unquoted copy next to it would leave two keys of
which YAML silently keeps one.

## WHY an Absent Key Is Inserted at the End of Its Parent's Block

The end of the block is the one position that cannot split an existing
key from its continuation lines or from the comment above it. Trailing
comment lines that are indented deeper than the parent are part of its block
and stay above the inserted line; a comment at the parent's own indent ends
the block and stays below. A missing top-level section is appended at the end
of the file after one blank line, the same path the section writers use.

## WHY a Flow Mapping on the Key Line Is Rewritten as a Block

The profile spells granularities as `weekly: { enabled: true, path: "…" }`.
A config copied from it holds the same line, and no byte-level edit inside a
flow mapping is safe without a YAML parser for that one line. So the line is
parsed with `yaml.safe_load`, the leaf merged in, and the mapping written
back as a block at the same indent. Only that line changes; a scalar where a
mapping is expected is refused (`EditRefused`) rather than overwritten.

## WHY `null` Removes the Key

The review setup's reader treats an absent key and `null` alike. Writing
`template: null` would keep a line that says nothing; removing the key line
(and a list's continuation lines) is the edit that matches what the user
confirmed. A `null` for a key that does not exist is a no-op.

## WHY an Inline Comment on a Replaced Line Is Not Kept

`path: "Calendar/301 Daily/ "  # trailing space on purpose` becomes
`path: "Calendar/301 Daily/"` when the user confirms the correction. Keeping
the comment needs a scanner that knows where the value ends inside quotes;
`templates-include` makes the same trade for comments between list items. A
replaced line is a value the user just confirmed, so the comment it carried
described the old value.

## WHY the Rendering Is Double-Quoted Strings and Flow Lists

Same convention as the section writers and `vault-example.yaml`: strings via
JSON escaping (safe for `#`, `:`, quotes and non-ASCII), lists on one line
(`["Habit", "Daily Log"]`), booleans lowercase. A list the file held as block
items is replaced by the flow form; the read-back in the writer guarantees
both parse to the same value.

## WHY Line Endings Follow the File

A CRLF config gets CRLF insertions, determined from the file's first line,
so one file never mixes endings (the `templates-include` precedent).
