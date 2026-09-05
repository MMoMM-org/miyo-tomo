# WHY: lib/attachment_index.py

> Rationale for decisions in `tomo/scripts/lib/attachment_index.py`.
> The module is spec 031 Phase 1's pure detection/resolution library: find embed
> targets in a note body, classify them as attachment files (not notes), and
> resolve them against an inbox file index built from Kado's `listDir`.

## A Tenth Wikilink Regex — None of the Existing Nine Capture the Bang

WHY a new regex instead of reusing one of the nine wikilink regexes already in
this repo (`topic-extract.py`, `moc-proposal-parser.py`, `instructions-diff.py`,
`garden-audit-render.py`, `inbox-triage.py`, `moc-tree-builder.py`,
`garden-audit-parser.py`, `lib/up_parse.py`, `lib/render_actions.py`,
`suggestion-parser.py`): every one of them matches the inner `[[…]]` only. None
captures a leading `!`. Reusing any of them would silently treat an embed
`![[karte.jpg]]` as a plain link — the bang is thrown away before the caller
ever sees it. `_EMBED_RE` (`r"(!)?\[\[([^\[\]]+)\]\]"`) makes the bang an
explicit, optional capture group specifically so its presence or absence can be
tested. The distinction is not cosmetic: an embed is a dependency of the note
(the file it displays), a plain link is a deliberate reference to another note
— only the former is the attachment-filing signal (PRD Feature 1, business
rule). `extract_attachment_embeds` drops any match where `bang` is falsy before
target resolution even begins.

## Two-Step Classifier, Not a Membership Check (`md` Is in the Frozenset)

WHY `_is_attachment_target` tests
`ext in KNOWN_FILE_EXTENSIONS and ext not in _NOTE_EXTENSIONS` instead of a
single `ext in KNOWN_FILE_EXTENSIONS`: `KNOWN_FILE_EXTENSIONS` (see
`file_extensions.md`) contains `"md"`, because that allowlist's job elsewhere
in the codebase is "is this string plausibly a filename with an extension at
all", and a note file genuinely is a `.md` file. A naive membership check here
would therefore classify `![[Note.md]]` — a note embedded into another note —
as an attachment, and Phase 2+ would emit a `move_asset` instruction for a
note. Hashi rejects that outright, and rightly: notes are never something the
attachment-filing feature is supposed to relocate. `_NOTE_EXTENSIONS` names
`md`, `canvas`, and `base` as the note/note-container exclusion set. `canvas`
and `base` are not actually present in `KNOWN_FILE_EXTENSIONS` today, so they
already fail the first test on their own — they are named in the second test
anyway so the note/attachment partition is explicit in the code and survives
someone later adding `canvas` or `base` to the extension allowlist for an
unrelated reason.

## Path-Qualified Targets Keep Their Path — Unlike `_strip_link_target`

WHY `_strip_alias_and_anchor` strips `|alias` and `#heading`/`^block` but
deliberately does NOT strip any leading path segment, unlike
`topic-extract.py`'s `_strip_link_target`, which ends with
`.split("/")[-1]` to discard the path: those two functions serve opposite
goals. Topic extraction wants a bare stem to match against note titles — the
path is noise there. Here, a path-qualified embed target
(`![[Images/karte.jpg]]`) is already the answer the resolver needs: the user
(or an existing note) told it exactly where the file lives, and throwing that
away would force a resolution the caller doesn't need to attempt (PRD
Feature 2, criterion 2). Discarding the path here would also make a
path-qualified target indistinguishable from a bare one, silently losing
precision the input actually had.

## Ambiguity Is an Outcome, Not a Best-Guess

WHY `resolve_attachments` returns a distinct `"ambiguous"` status — with no
path and no action — rather than picking one of several same-basename
candidates: a wrong move is worse than no move, because a wrong move mutates
the vault. Worse than that: a fabricated best-guess resolution would be
counted as *covered* by the coverage audit built on top of this module, so the
mistake would be invisible until a user found a file moved somewhere they
didn't put it. `"ambiguous"` (basename matches two or more inbox files in
different subfolders) and `"unresolved"` (basename matches none) are kept as
two separate outcomes rather than collapsed into one "couldn't resolve"
bucket, because they call for different user responses: ambiguous means "tell
me which one", unresolved means "this file isn't in the inbox at all, or
doesn't exist yet".

## Path-Qualified Resolution Narrows Candidates, Not a Set-Membership Test — Correction to the SDD

WHY `resolve_attachments` looks up a path-qualified target's own basename and
then narrows the candidate list, instead of the literal read of `solution.md`
("Resolution — traced walkthrough", row 3), which describes a path-qualified
target as "used verbatim after verifying membership in the index's path set":
taken literally that reading is impossible to satisfy. Kado's `listDir`
always returns the full vault-relative path (verified against Kado source,
`src/obsidian/search-adapter.ts:34,245` — `path: file.path`), so
`build_inbox_index` only ever holds keys like
`100 Inbox/Images/karte.jpg`, never a bare `Images/karte.jpg`. A literal
global-path-set membership test against a partial path would therefore always
miss, making every path-qualified embed permanently unresolvable — which
contradicts PRD AC-F2.2 (path-qualified embeds must resolve). What the code
does instead: one dict lookup by the target's basename, then narrow that
basename's candidate paths to whichever end with the given target at a `/`
boundary (`path == target or path.endswith("/" + target)`).

Two consequences of that shape are worth stating plainly, since they are easy
to lose in a future refactor:

- The returned `resolved_path` is always a value *retrieved* from the index —
  never a string built by joining the target onto anything. That is what
  makes fabricating a path impossible by construction, rather than merely
  unlikely by convention or caught by a test.
- Narrowing to more than one candidate is `"ambiguous"`, not first-hit-wins.
  A basename suffix shared by two inbox paths is reported to the user rather
  than silently resolved to whichever one happened to be indexed first.
