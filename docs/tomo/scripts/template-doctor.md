# WHY: template-doctor.py

> Rationale for decisions in `tomo/scripts/template-doctor.py`.

## The `filled-note` Mode Exists (#169, spec 044 F3-AC7)

WHY: `/note` fills a template into a draft and must refuse delivery while
Templater code (`<%`), a `{{token}}`, a user-authored `tomo:` key or a broken
fence is left in it. The flow runs that check inside `note-session.py stage` and
`deliver`; `filled-note` is the same check as a manual and test entry point, so a
user or a test can ask "would this note be refused?" without starting a session.

## `filled-note` Delegates to `lib/template_syntax.py`

WHY: ADR-4 of spec 044 — one parser. `template-outline.py` offers a token as a
point and the filled-note check fails on that token when it is left over; both
only agree if they read the text the same way. `template-doctor.py` therefore
calls `filled_note_check` and adds no content check of its own in this mode.
The check list therefore comes from the library, including `code_fence_closed`
(every ``` or ~~~ code fence is closed), which `audit` does not have; a new
library check appears in this mode without a change here. Its older
parser stays for `audit` and `dry-render` until a later refactor moves them onto
the library (accepted trade-off in ADR-4).

## `filled-note` Takes `--note`, Not `--template`

WHY: the input is a filled note, not a template, and the report names it under
`note`. `--template` stays required for `audit` and `dry-render`; `filled-note`
requires `--note` and never needs `--template`, so the existing modes keep their
invocation unchanged.

## The Report Carries the Path, Not the Note

WHY: the MiYo constitution keeps note content out of traces. `note` is the path
passed in; only the `no_tokens` detail names leftover token names, which the
user needs to find them. There is no `rendered_preview` in this mode — nothing
is rendered.

## A Note That Cannot Be Read Is a `file` FAIL, Not a Crash

WHY: the caller parses stdout as one JSON object. A missing path, a directory,
an unreadable file (permissions) or bytes that are not UTF-8 each yield a single
`file` FAIL finding and exit 1, never a traceback. The detail is fixed text that
names only the path ("Note not found", "Note is not a file", "Note not
readable", "Note is not valid UTF-8"); the exception text is never echoed,
because a `UnicodeDecodeError` message quotes the offending bytes — note
content.
