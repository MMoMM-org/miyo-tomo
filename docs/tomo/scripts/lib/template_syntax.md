# WHY: lib/template_syntax.py

> Rationale for `tomo/scripts/lib/template_syntax.py`.
> The module is the one parser for note templates and filled notes used by
> `/note` (spec 044, issue #169, ADR-4). Pure functions over text, no IO.

## Why the module exists

WHY: `/note` reads a template, asks the user for its open points, and checks the
filled note before it is delivered. Five scripts need the same reading of a
template: `template-outline.py` (the points), `template-doctor.py filled-note`
(the verdict), `note-session.py`, `note-process.py` (required points must exist
in the outline) and `note-instructions.py` (the deliver gate). The scripts have
hyphenated names, so none can import another. Shared code has to live in
`tomo/scripts/lib/`.

## Why one parser for the outline and the check

WHY: the outline says which tokens are points and the filled-note check fails on
any token left over. If two parsers decide differently what a token is, the outline
can skip a token that the check later fails on, or the check can pass a note with a
token the outline listed as open. Both read `tokens()` here, so they always agree.
Fenced code, an escaped `\{{x}}` and the inside of a Templater span count as text
in both. `token-render.py` protects only backtick fences when it renders; this
module also recognises `~~~` fences, as `template-doctor.py` does.

## Why the fence rules follow CommonMark

WHY: "outside fenced code" decides which tokens and headings are points, so a
fence that closes too early turns code into points and one that never closes hides
the rest of the template. The module follows CommonMark, as Obsidian renders: a
fence opens with three or more backticks or tildes; it closes only on a line with
the same character, a run at least as long as the opener's and nothing but
whitespace after it (so ```` ```python ```` inside a fence is content); a backtick
opener whose info string holds a backtick (```` ```inline``` ````) is inline code,
not a fence.

WHY a fence is recognised at any indent: CommonMark allows only zero to three
leading spaces before a fence marker; four or more make an indented code block.
The module accepts any indent on purpose, so a fence nested in a list item (which
sits deeper than three spaces) still counts. The cost is that a stray indented
```` ``` ```` inside prose is read as a fence. Templates do not carry those, and
reading one as a fence hides points rather than inventing them.

## Why an unclosed code fence fails the filled-note check

WHY: a code fence that opens and never closes runs to the end of the text, so
everything after it counts as fenced code. Without a separate check, a draft with a
stray ```` ``` ```` before a `{{title}}` passed `no_tokens` and was delivered with the
token unfilled, the exact broken draft the check exists to stop (F3-AC7). The
`code_fence_closed` check FAILs whenever a fence is still open at the end of the
text, with or without a token after it, because Obsidian would also render the rest
of the note as code. The detail names only the opening line number.

## Why some heading forms are not recognised

WHY: only ATX headings that start in column one count as points. Indented ATX
headings (one to three leading spaces, which CommonMark still renders as headings)
and setext headings (text underlined with `===` or `---`) are intentionally not
recognised; templates do not use them, and a `---` underline would collide with the
frontmatter fence.

## Why some frontmatter key forms are not recognised

WHY: a frontmatter key is a bare name at column one followed by `:`. Quoted keys
(`"my key": x`, `'k': x`) are not recognised as points; templates do not use them,
and reading them would need a YAML parser for a case no template has shown.

WHY a key has a value when a list follows at column one: YAML allows a block list
directly under its key without indentation (`tags:` then `- a`). Treating only
indented lines as nested content reported such a key as empty, so the outline would
offer an already-filled key as an open point. A `- ` line at column one directly
after the key, before the next key or the closing fence, counts as its value. A key
followed directly by another key is still empty.

## Why Templater spans are listed but never points

WHY: Tomo never runs Templater (`docs/template-syntax.md`, Rule 2). A `<% %>`,
`<%* %>` or `<%- %>` span is shown to the model as a hint about the template's
intent, never offered as a question, and never executed. The filled-note check
fails on any `<%` left in the note (F3-AC7), anywhere, fenced or not, because an
unclosed opener or a span in a code block would still reach the vault unrun. The
span listing uses the same "anywhere" rule, so a template that would fail the check
shows the cause in its outline. A span is matched over the raw text, so one that
opens inside a fence and closes after it still hides the tokens it covers; this is
pinned by a test rather than redesigned.

## Why prefilled tokens depend on the source

WHY: the script resolves generated tokens (`uuid`, `datestamp`, `updated`,
`date_iso`) and config tokens (`locale`, `vault`, `vault_version`, `profile`) itself;
asking the user for them would be noise. `source_path` and `source_link` exist only
when the material comes from an inbox note. With text given in the call there is no
source, so those tokens fall back to points the model fills, like every other token
(the SDD's "Prefilled tokens" table). Callers pass `has_source` explicitly; the
default is `False` because a template outline without a draft (`/note --process`)
has no source.

## Why the token regex is duplicated and pinned by parity

WHY: `template-doctor.py` and `token-render.py` keep their own parsers (ADR-4
trade-off; moving them onto this module is a later refactor). The regex here is a
copy of `token-render.py`'s `_TOKEN_RE`, because token-render decides what gets
substituted at render time. A drift would let the outline call something a token
that the renderer leaves alone, or the reverse. `tests/test_template_syntax.py`
asserts the two patterns are equal, so a change to one fails the suite until the
other follows. `template-doctor.py`'s looser regex (it allows spaces and capitals
inside the braces) is not the rendering contract and is not copied.

## Why findings echo token names and nothing else

WHY: a filled note is user text and may be sensitive (MiYo Constitution, privacy).
Findings name line numbers and fixed sentences only. The one deliberate exception
is `no_tokens`, whose detail lists the leftover `{{token}}` names: the model needs
them to fix the draft, and a token name is template syntax copied from the
template, not text the user wrote. No finding echoes the value of a `tomo:` key,
the content of a Templater span, or any other note text; a test pins this.

## Why the leading-fence rule matches `doc_frontmatter`

WHY: the deliver step stamps the `tomo:` block with
`merge_tomo_block_into_markdown`, which treats only a literal `---` on line 1 as a
leading fence and rejects a top-level `tomo:` key already in the block. The check
uses exactly those two rules, so a note that passes it can always be stamped.
