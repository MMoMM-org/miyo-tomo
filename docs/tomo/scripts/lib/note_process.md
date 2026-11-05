# WHY: lib/note_process.py

> Rationale for decisions in `tomo/scripts/lib/note_process.py`.
> The module owns `config/note-processes/<template-stem>.md`, the optional
> per-template settings of `/note` (spec 044, F7): reading, writing, decline
> markers and the required-point check against a template outline.

## WHY One Library Owns Process Files

`note-process.py` (`read`, `write`, `decline`) and `note-instructions.py new`
(which takes the default destination from it) both read process files. One parser
means both agree on what a decline marker is and which destination applies.

## WHY read Never Raises on a Broken File

A process file is user-editable. A typo in its YAML must not stop `/note`; F7-AC4
says the skill reports the error in one line and continues with the template
alone. `read_process` therefore returns `exists: true` with `error` set and every
other field empty. Wrong types (a string where `required` wants a list, an
`offer` other than `never`) count as broken too. The error names the problem
class, never the file text: process files may hold vault folder names or
guidance the user considers private, and script output reaches the model.

The same holds for exceptions: the ValueError for a malformed template stem uses
fixed text and never echoes the stem, which is a caller-supplied value that may
name a private template.

## WHY "offer: never" Alone Is the Decline Marker

The decline marker is a process file holding only `offer: never`: no other
field and no body (SDD glossary, F7-AC9). The "never" answer to "save this
process?" must persist, or the skill would ask again after every delivery.
Storing it as a process file keeps one file per template and one place to look.

An `offer: never` file with any other field (destination, required) or a body
reads as a normal process with `declined: false`: the user wrote a process by
hand, and discarding their settings because of a leftover marker would be worse
than offering once more.

## WHY destination Is Accepted Without a Trailing Slash

A user editing a process file by hand may write `destination: Efforts/Meetings`.
Rejecting that as broken would drop their whole process over a cosmetic slash,
so any non-empty folder path is accepted and normalised to exactly one trailing
"/" on read and on write. The schema says the same (no trailing-slash pattern),
so the documentation does not call a file broken that the reader accepts.

## WHY write Rejects Required Points Absent From the Outline

A required point the template does not have can never be filled; every later
`/note` would ask for it with no skip option (F3). `write_process` therefore
compares against the outline points and writes nothing when one is unknown,
returning the rejected names (F7-AC8). On `read`, the same comparison only
reports `missing_required` (F7-AC5): the template may have changed after the
file was written, and the skill continues without those points.

## WHY a Point Is a Heading, a Frontmatter Key or an Open Token

That is the TemplateOutline rule of the SDD: prefilled tokens (date, uuid,
vault values) are resolved by the script and never asked for, so requiring one
would be meaningless. Names are matched exactly after trimming whitespace,
because the skill offers required points from the outline itself.

## WHY Writing Goes Through yaml.safe_dump

Frontmatter is never assembled or edited by string or regex (repo rule). The
whole file is rebuilt from the given values, which also makes a write replace a
decline marker without any special case. The write is atomic (temp file plus
`os.replace`) so a crash never leaves a half-written process file.

## WHY the Schema Is Documentation

`tomo/schemas/note-process.schema.json` describes the frontmatter for users and
reviewers. The library validates the few fields itself so it needs no
`jsonschema` at runtime; a test validates written files against the schema so
the two cannot drift.
