# WHY: lib/note_paths.py

> Rationale for decisions in `tomo/scripts/lib/note_paths.py`.
> The module holds the path rules of `/note` (spec 044): which strings are a
> relative vault folder, a relative vault note path, or a safe title, and
> whether a path lies inside a folder.

## WHY the Rules Live in One Module

Two scripts store `/note` folders. `note-instructions.py` validates
`--destination`, the process file's `destination`, `concepts.atomic_note` and
`concepts.inbox`; `note-process.py write` stores the `destination` of a process
file. Until spec 044 T2.4 each had its own normaliser, and the process-file one
only trimmed and appended `/`. So `note-process.py write --destination ../../x`
saved a file that `note-instructions.py new` then ignored as unsafe: the user's
save stopped working without a word. One module means a folder one script
accepts is a folder the other accepts, byte for byte.

## WHY a Folder Is Refused

`vault_folder()` strips the value once and rejects it when:

- it starts with `/` or `~`, or with a drive letter (`C:`). These are the
  absolute forms of rule 1 of the Path Shape Contract (`docs/instructions-json.md`),
  which every path field of an instruction set follows, and Hashi refuses a
  drive letter as escaping the vault.
- it contains `\`, the Windows separator, which would hide a `..\` from the
  segment check.
- a segment is blank or starts with `.` after stripping. That covers `.` and
  `..` (traversal), `a//b`, and every hidden name: Kado's folder listing treats
  a path with a dot-led segment as missing, Obsidian does not show it, and Hashi
  refuses `.obsidian`, `.git` and `.trash` at the vault root. A note filed under
  one would vanish from the vault view.
- it contains `{{` or `<%`, the template syntax `_check_path_shape` refuses
  (rule 3): a destination such as `Meetings/{{date}}/` would create a folder
  literally named `{{date}}`.
- it contains an unsafe character (see below).

One trailing `/` is allowed and the accepted value is returned with exactly
one. Checking the stripped value is the point: an earlier check on the raw value
let `" /etc"` become `/etc`, and an unstripped segment let `a/ ../b` through.
Python counts a newline, U+2028 and U+2029 as whitespace, so stripping removes
them at either end; inside the value they are rejected.

`vault_note()` applies the same rules to the whole path, file name included, so
`In/.hidden.md` and `In/.md` are refused, and requires `.md`.

The functions return `None` rather than raising: what a refusal means depends
on the caller (exit 2 for a flag, a fallback for a process file), so the caller
decides.

## WHY Unsafe Means Cc, Cf, Zl and Zp, Except the Two Joiners

`has_unsafe_char()` is the one predicate for folders, note paths and titles.
Control characters (Cc: newline, tab, NUL) corrupt the wire and break
wikilinks. Format characters (Cf: zero-width space, bidi overrides, the
byte-order mark, the soft hyphen) are invisible: two paths that look the same
can name different files, and a bidi override can make a path display as
something it is not. Line and paragraph separators (Zl, Zp) break a line as a
newline does. Combining marks (Mn) are not unsafe, so a decomposed `ö` passes.

The zero-width joiner (U+200D) and the zero-width non-joiner (U+200C) are
allowed. Owner decision, spec 044 Decisions Log 2026-11-05: "titles and folders
reject invisible format characters, line and paragraph separators, but allow
the zero-width joiner and non-joiner (U+200D, U+200C)". The joiner builds emoji
sequences such as the technologist emoji, and the non-joiner is part of Persian
and Indic spelling; refusing them made such titles and folders impossible. The
look-alike risk they carry is accepted for these two only; every other Cf
character stays refused, a joiner next to it included. Until `note_paths`
0.1.1 (`note-instructions.py` 0.1.4) both were refused.

## WHY Unicode Is Not Normalised

The validators never normalise Unicode: a name in NFC and the same name in NFD
both pass, each in the form it arrived in. They decide whether a path is safe;
they do not rewrite vault paths. A rewritten form may not match the name the
vault holds, and on a file system that keeps the two forms apart it names a
different file. Comparisons that must treat both forms as one name use
`lib/vault_paths.path_key`, as `is_inside()` does.

## WHY is_inside Compares path_key on a Segment Boundary

`is_inside(path, folder)` compares `path_key` values (NFC, then casefold),
because the vault may be case-insensitive and macOS hands back decomposed
names. The folder comes from `vault_folder()` and so ends in `/`, which puts
the comparison on a segment boundary: `100 Inbox Archive/x.md` is not inside
`100 Inbox/`. Subfolders are inside, as in recursive inbox discovery (spec 034).
