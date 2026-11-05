# WHY: note-process.py

> Rationale for decisions in `tomo/scripts/note-process.py`.
> The script is the CLI over `tomo/scripts/lib/note_process.py` for the
> process files of `/note` (spec 044, F7): `read`, `write`, `decline` of
> `config/note-processes/<template-stem>.md`.

## WHY Process Files Are Only Written by This Script

WHY: F7-AC8 to F7-AC10. A process file written by the model directly could
carry a required point the template does not have, a hand-assembled YAML block
or a half-written file. The script routes every write through
`lib/note_process.py`, which checks required points against the outline,
serialises with `yaml.safe_dump` and replaces the file atomically. The skill
never writes into `config/note-processes/` itself.

## WHY the Script Holds No Parsing of Its Own

WHY: `note-instructions.py new` reads the same files for the default
destination. Both import `lib/note_process.py` so they cannot disagree on what a
decline marker is or which destination applies. The script only parses its
arguments, loads the outline and the guidance file and prints the result.

## WHY `write` Takes the Outline as a File

WHY: the `/note --process` algorithm (SDD) runs `template-outline.py --out
tomo-tmp/note/process-outline.json` once and hands the same file to `read` and
`write`, then removes it. Reading the template again here would spend a second
Kado call (CON-7) for the same outline, and passing the outline through an
argument would put template structure on the command line.

## WHY a Malformed Outline Exits 2

WHY: an outline that is missing, not JSON, or not the `template-outline.py`
shape (an object whose `frontmatter`, `headings` and `tokens` are lists of
objects) cannot say which points the template has. Treating it as "no points"
would make `write` reject every required point (exit 1, which the skill reports
as the user's mistake) and `read` report every required point as missing. It is
a bad invocation. The error object `template-outline.py` prints on failure
(`{template, error}`) lacks those lists and is rejected the same way, so a failed
outline run is never mistaken for an empty template.

## WHY `--required` Is Split on Commas

WHY: the SDD interface (`--required a,b`). Entries are trimmed and empty ones
dropped, so `a, b,` means `a` and `b` and an empty value means no required
points. A point name that itself contains a comma cannot be named: it is split
into two names, which the outline does not have, so `write` rejects them with
exit 1 and writes nothing. The failure is loud, never a silently wrong process
file. Template headings with commas are rare; a second argument form is YAGNI
until one turns up.

## WHY Guidance Comes From a File

WHY: guidance is free multi-line text the user wrote. On the command line it
would need shell quoting the model gets wrong (quotes, `!` in zsh, newlines),
and it would show up in process listings. The skill writes it to a file and
passes `--guidance-file`; the script reads it as UTF-8. A missing or unreadable
guidance file is a bad invocation (exit 2) rather than an empty guidance, so a
typo in the path never erases guidance the user gave.

## WHY a Rejected Write Exits 1 With Output

WHY: the SDD exit codes. `{written: false, rejected_required: [...]}` is the
answer the skill needs to tell the user which points the template lacks
(F7-AC8); exit 1 marks that nothing was written. The rejected names are point
names the user just chose, not file text.

## WHY Diagnostics Name the Problem Class Only

WHY: CON-3. Process files and outlines may carry private folder names, headings
or guidance. stderr on exit 2 names the problem (`outline is not JSON`,
`guidance file unreadable (FileNotFoundError)`), never a path's content, the
template stem or file text. `read` returns the guidance as the named output
field the SDD defines; nothing else echoes file text, and a broken process file
reads as `{exists: true, error: ...}` with the library's class-only message
(exit 0, F7-AC4).

## WHY a Malformed Template Stem Exits 2

WHY: a stem with `/`, `\` or a leading `.` could address a file outside
`config/note-processes/`. The library raises ValueError for it; the script
reports a bad invocation without echoing the stem.

## WHY Paths Are Relative to the Working Directory

WHY: the script runs with cwd = instance root, like the other `/note` scripts;
`config/note-processes/` and `tomo-tmp/note/` are resolved from there.

## WHY the JSON Is Written ASCII-Escaped

WHY: same as `note-session.py` — `ensure_ascii=True` cannot fail on a non-UTF-8
stdout or a lone surrogate from argv; any JSON reader decodes the escapes back.
