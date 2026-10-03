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
has no variable-length backreference comparison.

| Fault | Old behaviour | Now | Closed by |
|---|---|---|---|
| Closing run shorter than opening | fence ended early, interior embed rewritten | fence stays open | the line scan |
| CRLF closing line | `\r` defeated the `$` anchor; fence never closed and swallowed the rest of the note, so a later real embed was missed | closes normally | the line scan |
| Unclosed fence | matched nothing; everything after a dangling fence treated as live body | runs to end of note, as Obsidian renders it | **the previous commit**, preserved here |

The last row's attribution matters and the first version of this table got it
wrong: it listed all three as "closed at once" by the line scan, when the
unclosed-fence fix was a `|\Z` alternative added to the old regex one commit
earlier. The line scan preserves that behaviour rather than introducing it.
Recorded because a WHY doc is also the history a future reader trusts, and
crediting the wrong change makes `git log` and the prose disagree.

Tilde support is a third change but not a fault the old regex *had* — it never
claimed `~~~` at all.

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

## A Refused Typed Name Rewrites No Embed (spec 038 T4.3, v0.4.1)

WHY `rewrite_renamed_embeds` now calls `check_typed_name` itself, and why the
docstring's "bare basename, never a path" guarantee needed **two** mechanisms
named rather than one.

`proposed_name` is substituted verbatim — this function has no basename step.
Before T4.3 that guarantee rested on a single mechanism, Pass 1's producer
(`_propose_asset_name` emits a basename by construction), and spec 038 opened a
second producer: the owner's keyboard. **So the docstring asserted a property the
code did not have.** A typed `Archive/karte.png` was substituted whole, hard-coding
a folder into every rewritten body — the exact thing the sentence promises never
happens — while `_build_move_asset_actions` refused the same record and emitted no
move. The note's body then pointed at a file the run never created.

That is why the gate lives in this function rather than in the
`instruction-render.py` caller. The guarantee being broken is stated in this
function's docstring; the function is the one T4.4's convergence criterion is
about; and a gate in the caller leaves the library wrong for the next caller.

### The Cost: Two Gates That Must Keep Agreeing

`check_typed_name` is now called from here AND from `_build_move_asset_actions`,
and nothing in the type system makes the two agree. T3.2 produced the defect above
by changing one and not the other, so this is a measured risk, not a theoretical
one. The two gate on the same condition — `name_is_owner_supplied` truthy, then
`check_typed_name` — and the agreement is pinned by execution instead of by types:
`tests/test_038_t4_3_refused_name_rewrites_no_embed.py` carries one case that
feeds a **single** refused name to both halves and asserts the builder emits
`typed_name_refused` **and** the body comes back byte-identical. That is the test
that fails if the two conditions drift apart, and no per-half test can catch it.

Deciding the refusal once upstream and carrying the verdict on the remedy record
is the better design — one verdict, one producer, no agreement to maintain. It
changes the wire contract, so it is in `docs/XDD/backlog.md` rather than in this
spec.

### Known Gap: Run-Level Withholdings Are Still Uncovered

The gate covers the typed-name verdict and nothing else. A move withheld for a
**run-level** reason this per-note pass cannot see still leaves the body
rewritten for an attachment that is never filed:

- `kind: collision` — two different source paths resolve to one destination, and
  the second is skipped;
- `kind: no_basename` — the inbox path has no filename to join.

Both predate T4.3 and neither is closed by it. The reason they cannot be closed
the same way is mechanical: both depend on `_build_move_asset_actions`' `claimed`
map, which is **global to the run**, while this function sees one note's
attachments and the remedy records for them. It cannot know whether another
note's attachment already claimed the destination. Closing them therefore needs
the single-verdict record described above — the same backlog item — and not a
second local gate.

### Where the T4.3 Rationale Lives

The function's docstring keeps three things and only three, because a maintainer
editing it needs them in front of them: the two-mechanism explanation (it is the
direct rationale for the `name_is_owner_supplied` branch), one line that the two
gates must keep agreeing, and one line naming the gap above. Everything else on
this page — what broke before the fix, the test pointer, the backlog aside, and
the `claimed`-map mechanics — moved here in T4.4 (2026-10-03) under the routing
rule in `CLAUDE.md`. The move ran before the trim, which is the repo's required
order: WHY reaches `docs/tomo/` first and leaves the runtime file second, because
strip-first destroys it.

The same pass compressed the 037-era paragraphs in that docstring (basename
matching, the bare-basename ruling, the fenced-code guard) to their operative
statements. Nothing was lost: every one of those arguments is already on this
page, above, in more detail than the docstring carried — which is precisely the
"no copy in both" rule, and the reason the docstring went from 67 lines to 36.
