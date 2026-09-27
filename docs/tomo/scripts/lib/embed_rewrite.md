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

WHY fenced-code detection is one `re.finditer` pass producing `(start, end)`
spans, checked with a simple containment test per embed match, rather than a
line-by-line "am I inside a fence" state machine: the two fences this module
needs to distinguish are "opening backtick-run line" and "the next backtick-
run line", and a single `DOTALL`/`MULTILINE` regex captures exactly that
without maintaining parse state across the whole body. It does not attempt to
handle nested or differently-fenced (backtick vs. tilde, mismatched length)
constructs — none of that is reachable from a Tomo-rendered template body, and
handling it would add a real state machine for markdown edge cases no
production template produces.

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
