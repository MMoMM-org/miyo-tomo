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
flow mapping is safe without knowing where its members begin and end. So the
mapping is split into its members as text (`_scan_flow_mapping`: quotes,
nested `[]`/`{}` and `#` comments honoured), the one member the path names is
replaced, removed or appended, and the result is written as a block at the
same indent. Only that line (or those lines, for a mapping spanning several)
changes; a scalar where a mapping is expected is refused (`EditRefused`)
rather than overwritten.

### WHY the Other Members Are Copied as Text, Not Re-rendered

The first version parsed the mapping with `yaml.safe_load` and rendered every
member back through the module's renderer. That rewrote bytes the user never
confirmed: a plain `path: Calendar/` came back double-quoted, a `template: ~`
member vanished (the renderer skipped nulls), a trailing `# from the profile`
on the key line was lost, and a float or date sibling (`ratio: 0.5`,
`since: 2026-01-05`) made the edit fail with "value must be a string, number,
boolean, list or mapping" — a message about the *caller's* value, for a
sibling the caller never touched. Copying each untouched member's raw text
onto its own block line (`key: <text as written>`) keeps all of that: the
spelling, the null as `~` or `null` as written, a nested flow mapping as a
flow mapping, and whatever scalar type YAML gives it. A bare member
(`{ a, b: 1 }`) becomes `a:` — the block spelling of the same null. The text
after the closing brace — the key line's comment — is appended to the new
key line unchanged (`weekly:  # from the profile`). A comment *inside* the
braces of a multi-line mapping is dropped, because no block line corresponds
to it; a single-line flow mapping cannot carry one.

### WHY the Scan Is Checked Against `yaml.safe_load`

A text scan can misread syntax the module never meant to support — explicit
keys (`{ ? a : 1 }`), a duplicated key, a key YAML types (`{ true: 1 }`).
So the mapping is also parsed, and the scanned key list must equal the
parsed one; otherwise the edit is refused with its own message ("the flow
mapping on the key line could not be rewritten as a block") rather than a
wrong rewrite or the misleading scalar message. A mapping that does not
parse at all gets the same refusal. The writer's per-leaf read-back after the
edit is the second guard for whatever the scan still gets wrong.

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
both parse to the same value. The renderer only ever sees the caller's value
(a leaf or the chain of new keys above it); text the file already holds is
copied, never re-rendered — see the flow-mapping section above.

## WHY Line Endings Follow the File

A CRLF config gets CRLF insertions, determined from the file's first line,
so one file never mixes endings (the `templates-include` precedent).
