# WHY: lib/review_hashi_text.py

> Rationale for decisions in `tomo/scripts/lib/review_hashi_text.py`.
> The module reads a note's text the way Hashi's parser reads it — lines,
> fences, headings, the spec 045 marker line — and turns one kept review item
> into the lines that land (spec 045 T4.1, spec 046 T5.2 split). No Kado, no
> clock, no file I/O.

## WHY a Module of Its Own (spec 046 T5.2)

Two planners read a note: `review_actions` (spec 045's "Tomo Review") and
`review_section_plan` (spec 046's mapped sections). Both must agree on where a
heading, a fence or a marker is, or a plan that passes one fails the other in
Hashi. The mirror lived in `review_actions.py`, so the section planner imported
`review_actions` while `review_actions` imported the section planner — a cycle —
and both files were at their size limits (500 and 350 lines). Moving the mirror
here gives both one parse and one import direction: this module imports only
`review_doc` (for `neutralised` and the id pattern of `item_lines`) and is
imported by `review_section_plan`, `review_new_note` and `review_actions`.
Only text handling lives here; nothing that plans an action.

## WHY Headings Are Parsed by Hashi's Rule, Not `review_md`'s

Every heading this module emits as an anchor value, or matches a configured
anchor, `setup.heading` or an own section against, must be the heading Hashi
will resolve — otherwise a plan that passes every check here fails in Hashi
with `anchor not found`, or lands under a different heading. Hashi's reading
is `Hashi/src/actions/markdownStructure.ts`: `parseHeadings` takes the text
after the hashes, trimmed, and KEEPS closing hashes (`## Woche ##` is
`Woche ##`); `fencedLineMask` toggles on every line that opens with optional
whitespace and ``` or ~~~, whatever the fence character or its length, with
no `>` prefix (a quoted fence is not a fence to Hashi). `anchorResolver.ts`
(`resolveHeading`) and `sectionLocator.ts` then take the FIRST heading whose
text equals the anchor value exactly, over the whole file content including
the frontmatter — a YAML comment `# x` in the frontmatter is a level-1
heading to Hashi, so it is one here too.

`review_md.headings` reads for `review_day` — a CommonMark-shaped parser that
strips closing hashes and closes a fence only with its own character. Its
reading of a daily is never handed to Hashi, so it stays as it is; feeding
its headings into an anchor would emit `Woche` for a note whose heading Hashi
reads as `Woche ##`. The two parsers differ exactly where notes differ in the
wild (closing hashes, a ``` opened and ~~~ closed, a fence inside a
blockquote), so this module carries its own mirror of Hashi's two regexes
(`hashi_headings`, `fenced_mask`), and the planners use nothing else for the
target, the marker search and the template of a new note. The mirror has no behaviour of
its own: when Hashi's parser changes, this one changes with it.

The mirror is exact down to the character classes, because Python's `re`
and ECMAScript read the same two regexes differently in three places, and
each difference makes Tomo emit an anchor Hashi cannot resolve:

- Line terminators. Hashi splits the file on `\n` only, so a CRLF note
  keeps its `\r` at the end of every line, and ECMAScript's `.` does not
  match `\r` (nor U+2028, U+2029) while its `$` without the `m` flag matches
  only at the end of the string — `## Woche\r` is NOT a heading to Hashi.
  Python's `.` matches `\r` and `str.strip()` removes it, so the naive mirror
  found `Woche` and emitted it, and Hashi answered `anchor not found`. The
  text group is therefore `[^\r\n  ]*`, anchored with `\Z`, and the
  split stays `\n` only: a CRLF target has no headings at all, which the
  plan reports as `place-missing` (with an empty heading list) instead of
  emitting an anchor that fails downstream. The same holds for a heading
  line that contains U+2028 or U+2029.
- Whitespace. ECMAScript's `\s` and `String.prototype.trim` share one set:
  WhiteSpace (U+0009, U+000B, U+000C, U+FEFF and Unicode `Zs`) plus
  LineTerminator (U+000A, U+000D, U+2028, U+2029). Python's `\s` and
  `str.strip()` use `str.isspace()`, which adds U+001C to U+001F and U+0085
  and lacks U+FEFF. So a BOM after the hashes is whitespace to Hashi (the
  heading is found, the BOM trimmed) but text to Python, and a NEL or a
  file separator is the opposite. `JS_WS` holds the ECMAScript set as a
  literal (the `Zs` members have been stable since Unicode 6.3 dropped
  U+180E; a test compares the literal with `unicodedata` so a drift shows),
  both regexes use it in place of `\s`, and the heading text is trimmed with
  `str.strip(JS_WS)`. The V8 oracle for every edge character is in the test
  file's docstring.
- Only the mirror uses `JS_WS`. Tomo's own marker match (`line.rstrip() ==
  marker`, column 0) stays Python's: the marker line is Tomo's signature,
  not something Hashi resolves.

## WHY Every Item Line Is Escaped Again, Idempotently

The landed section is Markdown Hashi later re-parses for headings and
sections. An item line that starts with `#`, `- [`, `>` or a fence would be a
heading, a checkbox, a quote or an open fence inside the periodic note — and
a heading would end Tomo's section early. `review_doc` escaped such lines
when it wrote the document; the user may have added lines since. The same
predicate (`review_doc.neutralised`, made public for this) runs over every
landed line, first and continuation lines alike, and a line that already
starts with the backslash is not structure, so it passes through unchanged:
one backslash, never two. The count reported is of the lines this module
escaped (F5-AC2).

## WHY Ids Are Stripped and the Text Is Otherwise Verbatim

`%%t<n>%%` is the document's bookkeeping (ADR-13); the periodic note gets the
text the user left (Rule 2) without it. Continuation lines are re-indented by
two spaces under their bullet — the document's own indentation — and nothing
else changes: links stay, wording stays, a line the user escaped stays
escaped.
