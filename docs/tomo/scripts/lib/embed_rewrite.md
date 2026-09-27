# WHY: lib/embed_rewrite.py

> Rationale for decisions in `tomo/scripts/lib/embed_rewrite.py`.
> The module is spec 037 T3.3's rewrite pass: given a rendered note body and
> the run's attachment-conflict remedies, rewrite `![[...]]` embed targets for
> whichever attachments the owner renamed. No such rewriter existed anywhere
> in this repo before this task — `lib/attachment_index.py` only reads
> `![[...]]` embeds, and has no fenced-code-block handling either.

## Called Between the Render and the Write, Not After `build_actions`

WHY `rewrite_renamed_embeds` is called from `instruction-render.py` between
line 518 (the body is produced) and 551 (it is written to disk), and consumes
`attachment_conflict_remedies` directly rather than the `move_asset` actions
`_build_move_asset_actions` eventually computes: `build_actions` — the only
thing that calls `_build_move_asset_actions` — does not run until every item
in the per-item render loop has already rendered and written its body
(`instruction-render.py:~607`). By the time a move action exists, the file it
would correct is already a fact on disk. The rewrite therefore recomputes the
new basename itself, straight from `remedy["proposed_name"]` — the same field
`_build_move_asset_actions` reads it from — rather than consulting a move
action that has not been built yet. See
`docs/tomo/scripts/instruction-render.md`, "The Embed Rewrite Lives Between
the Render and the Write" for the full trace and the accepted race this
ordering creates.

## Basename Matching, Not Full-Path Matching — and Where It Would Break

WHY the rename map is keyed by basename (`path.rsplit("/", 1)[-1]`) rather
than by the full resolved path in `item["attachments"]`: the note body holds
whatever the owner actually typed — bare, path-qualified, aliased, anchored —
while `item["attachments"]` holds only the resolved, inbox-relative path.
`inbox-triage.py` keeps the as-typed `embed_target` only for UNRESOLVED
references (`:325,340`); a resolved reference is never carried forward as
text, only as a path (`:321`). Matching the literal resolved path against body
text would therefore find nothing for the common case — a bare
`![[karte.png]]` — because the body simply does not contain the path.

This has one accepted failure mode: two attachments from *different* inbox
folders sharing one basename, both embedded in the same note with the SAME
literal text (e.g. both typed as bare `![[karte.png]]`), where only one of
them is renamed. Basename matching cannot tell which literal embed instance
corresponds to which source path in that situation, and could rewrite the
wrong occurrence or all of them. This is accepted rather than engineered
around: it requires the identical basename to appear twice in one run from two
different folders, which `_build_move_asset_actions`'s own `claimed` check
already treats as a destination conflict on the filing side — a rare,
reported situation independent of this module. A caller resolving each
embed's own full path (rather than only the note's flat `attachments[]`
list) could disambiguate this, but building that resolution was out of scope
for T3.3 (scope boundary: `instruction-render.py` and this one helper, not a
second embed-resolution pass).

## The Bare New Basename, Never the Full New Path or the Old Prefix (Owner Ruling 2026-09-27)

WHY a path-prefixed original embed (`![[Scans/karte.png]]`) becomes the bare
new basename (`![[karte (2).png]]`) rather than either the asset-folder-
qualified new path or the original folder prefix reapplied to the new name:
this is a standing owner ruling, not a default this module chose. The full
new path would hard-code `concepts.asset` into every rewritten body, breaking
the moment the asset folder configuration changes. The original prefix would
point at a folder the file has just left — reproducing, one level down, the
exact defect (a dangling cross-folder reference) this spec exists to close.
`lib/voice_render.py:112`'s `![[{audio_name}]]` (a bare basename, `audio_name
= result.audio_path.name`) is the existing precedent for writing an embed
target as a bare basename in this codebase.

## Alias and Anchor Are Preserved by Splitting on the First Separator, Not by Re-Deriving the Target

WHY `_target_and_suffix` finds the earliest of `|`, `#`, `^` and treats
everything from there onward as an opaque suffix to reattach verbatim,
instead of reusing `attachment_index._strip_alias_and_anchor`: that function
is built to *discard* the alias/anchor tail — exactly the text this rewrite
needs to keep. An embed's alias and anchor are the owner's own display text
and are not implicated in a filename rename at all; only the target segment
before the first separator identifies which file is embedded.

## Fenced-Code Guard Is a Regex Span Check, Not a Line-By-Line State Machine

WHY fenced-code detection is a line scan (`_fence_spans`) and not a regex —
**and why the original claim here was wrong.**

The first version of this module used one `DOTALL`/`MULTILINE` regex and this
section asserted that nested or mismatched-length fences were "not reachable
from a Tomo-rendered template body". That was false, and the T3.3
code-quality review measured it. The body is not template output: it is
`read_note_body(client, full_path)` at `instruction-render.py:483` — verbatim,
unmodified user vault content. A PKM note *about* markdown or code syntax
routinely opens a 4-backtick fence containing a bare 3-backtick line, and the
regex closed on the first run of 3+ backticks whatever the opening length. The
fence span ended early, `_in_fence` returned false for an embed still inside
the outer fence, and it was **rewritten**:

    Doc example:
    ````
    ```
    ![[Scans/karte.png]]     <- rewritten to karte (2).png
    ````

That is the inverse of the defect this whole task exists to close. T3.3 fixes a
stale reference surviving into a filed note; this silently corrupted a fenced
example the owner wrote. The wrong direction of an unreachability claim is the
expensive one: it reads as a considered decision and closes the question.

`_fence_spans` scans lines and tracks the opening run, because CommonMark's
closing rule is not expressible as a Python pattern — a fence closes only on a
run of the same character at least as long as the one that opened it, and `re`
has no variable-length backreference comparison. Three faults closed at once,
each pinned by its own test:

| Fault | Old behaviour | Now |
|---|---|---|
| Closing run shorter than opening | fence ended early, interior embed rewritten | fence stays open |
| Unclosed fence | matched nothing; everything after a dangling fence treated as live body | runs to end of note, as Obsidian renders it |
| CRLF closing line | `\r` defeated the `$` anchor; fence never closed and swallowed the rest of the note, so a later real embed was missed | closes normally |

Tilde fences (`~~~`) are recognised too. CommonMark allows them, and a note
discussing backtick syntax is exactly where one appears — the same reachability
argument that the original claim got backwards.

## `_EMBED_RE` Reused Verbatim — Regression Insurance on a Plain Link, Not New Coverage

WHY this module imports `attachment_index._EMBED_RE` rather than writing its
own wikilink regex: it is the one place in this repo that already
distinguishes `![[...]]` from `[[...]]` by capturing the leading `!` as its
own group (see `attachment_index.md`, "A Tenth Wikilink Regex"). Reusing it
means a plain `[[...]]` link is left alone by construction — the same
`bang` check that gates `extract_attachment_embeds` gates the rewrite here.
The corresponding test (`test_plain_link_without_the_bang_is_left_alone`) is
regression insurance on borrowed reader logic, not coverage of new rewrite
behaviour.

## An Unclosed Fence Runs to the End of the Note (v0.2.0, 2026-09-27)

`_FENCE_RE` originally required a closing run of backticks. The T3.3 compliance
review measured what that meant for a dangling fence: an unclosed ``` matched
**nothing at all**, so every `![[...]]` after it was treated as live body text
and rewritten.

The `|\Z` alternative closes it. Obsidian renders an unclosed fence as code to
the end of the note, so extending the fence to end-of-body is not the cautious
reading — it is the correct one, and it agrees with what the owner sees.

Pinned by `test_an_embed_after_an_unclosed_fence_is_left_alone`, whose named
mutation is removing that alternative. Closed-fence behaviour is byte-identical
either way, verified before the change: the two regexes return the same span for
a well-formed fence.

## Why the Two-Owner Assertion Lives in the Render Loop, Not Here (v0.2.0)

The plan requires that two different confirmed items embedding one renamed
attachment are both rewritten. The first test written for it called
`rewrite_renamed_embeds` twice with two bodies and asserted both came back
rewritten — and **could not fail**. This function is stateless: it rebuilds its
rename map from its arguments on every call, so "rewrite only the first owner"
is not expressible against it. The named mutation could never bite, which the
T3.3 compliance review spotted and measurement confirmed.

Being several owners is a property of the *loop*, not of this function —
`owner_source_items` (`render_actions.py:720`) is a list precisely because
several confirmed items can embed one attachment. So the assertion moved to
`test_two_confirmed_items_embedding_one_renamed_attachment_are_both_rewritten`,
which runs the real render loop over two items and reads both files off disk.
Its mutation — hoisting the call out of the per-item loop — fails that test and
**only** that test (measured 2026-09-27); the single-item end-to-end anchor stays
green under it, which is why the loop-level test was needed at all.
