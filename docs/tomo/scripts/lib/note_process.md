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
so the folder is accepted and normalised to exactly one trailing "/" on read
and on write. The schema says the same (no trailing-slash pattern), so the
documentation does not call a file broken that the reader accepts.

## WHY destination Goes Through note_paths.vault_folder on Write and Read

Until 0.1.2 the module had its own `_folder()`, which only trimmed and appended
"/". So `../../x`, `/` and `a//b\c` were written, and `note-instructions.py new`,
which validates every folder with `lib/note_paths.vault_folder`, ignored them:
the user's save silently stopped working. Now both directions use
`vault_folder`, so the two readers cannot disagree.

On write, a refused destination raises `DestinationError` before anything is
written; `note-process.py` reports it as a bad invocation (exit 2). An absent
destination (`None`) writes no `destination` key; an empty or blank one is a
value and is refused, so a caller that meant "none" has to say so by omission.

On read, a stored destination that `vault_folder` refuses (written by hand, or
by an older version) makes the file broken: `exists: true`, `error:
"destination is not a relative vault folder"`, every other field empty, the
same shape as a YAML error. Returning the other fields with an empty
destination was the alternative; it was not taken because the error field
already means "this file was not used", `note-instructions.py new` already
falls back to the atomic-note path on it with one stderr line (F7-AC4), and a
half-used file would hide the mistake. The read contract (never raises, exit 0
in the CLI) is unchanged.

## WHY the Errors Are Dedicated ValueError Subclasses

`TemplateStemError`, `DestinationError` and `OutlineError` let the CLI map each
to its own message instead of turning every ValueError into "malformed template
stem", which would mislabel any other ValueError. They subclass ValueError so
`note-instructions.py`, which catches ValueError around `read_process`, keeps
working unchanged. Each carries a fixed or field-name-only message.

## WHY the Outline Shape Check Lives Here

`check_outline` and `outline_points` belong together: the points are only
meaningful for an object whose `frontmatter`, `headings` and `tokens` are lists
of objects. The CLI calls `check_outline` after parsing the JSON. `outline_points`
also skips a field that is not a list and an item that is not an object, so a
direct caller that skips the check gets fewer points rather than an
AttributeError.

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
