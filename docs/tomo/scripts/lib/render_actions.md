# WHY: lib/render_actions.py

> Rationale for decisions in `tomo/scripts/lib/render_actions.py`.
> Instruction-set action builders: turns the rendered manifest, confirmed
> items, and daily/skip inputs into the ordered `actions[]` list. Only
> non-obvious decisions are recorded here.

## `_asset_dest_join` Exists Because Neither Existing Path Helper Is Safe (spec 031)

WHY a third destination-join helper instead of reusing `_dest_join` or
`_ensure_md_extension`: both exist for NOTE paths, and both actively corrupt
an attachment path.

- `_dest_join` hardcodes a `.md` suffix (`f"{folder}{sanitize_stem(stem)}.md"`)
  — an attachment keeping its own extension (`.jpg`, `.m4a`, …) would come out
  as `karte.jpg.md`.
- `_ensure_md_extension` is the more dangerous trap because its failure mode
  looks like success on the obvious test case: for an extension already in
  `KNOWN_FILE_EXTENSIONS` (`lib/file_extensions.py`) — `.jpg` included — it is
  a silent NO-OP (`foto.jpg` → `foto.jpg`), so a fixture built around `.jpg`
  proves nothing. For any extension NOT in that allowlist — `.heic`, `.docx`,
  `.arw`, anything a phone or scanner produces that the note-path allowlist
  never anticipated — it silently appends `.md` (`scan.heic` → `scan.heic.md`).
  An earlier draft of this spec's own SDD had the hazard backwards (claimed
  `_ensure_md_extension` corrupted `.jpg` and no-op'd on everything else); the
  measured behaviour is the opposite. This is why `test_031_t2_1_asset_dest_join.py`
  pins the regression with `scan.heic`, not `.jpg` — the `.jpg` case cannot
  distinguish "safe" from "silently broken".

`_asset_dest_join` also does NOT run the basename through `sanitize_stem`
(unlike `_dest_join`): an attachment's filename already exists on disk and
the embed referencing it resolves by that exact name — rewriting it (even to
replace an Obsidian-forbidden character) would break the very embed the
feature exists to keep working.

`_asset_dest_join` raises `ValueError` when the source path has no basename
(empty, or ending in `/`) instead of silently returning a bare folder path.
This is reachable, not theoretical: `build_inbox_index` indexes a malformed
`listDir` entry like `{"path": "100 Inbox/Images/", "type": "file"}` — Kado
mistyping a folder as a file — under the key `""`, and `resolve_attachments`
returns index values verbatim, so a bad entry can reach this function.
`_check_path_shape` (the wire-level path validator, `:378`) has no basename
check, so nothing downstream would have caught a bare-folder destination
before it reached Hashi as an instruction to move a file *to* a directory.
`_build_move_asset_actions` catches the `ValueError` and routes that one
attachment through the same skip-and-report path as a destination collision
(below) rather than letting it abort the whole render.

## Global Dedup, Not Per-Item (spec 031)

WHY `_build_move_asset_actions`'s `seen` set spans the WHOLE manifest instead
of resetting per manifest entry, unlike the `audio_peer` precedent at `:927`
(`{mn.get("audio_peer") for mn in moves if mn.get("audio_peer")}`, which
dedups within one ORIGIN-STEM GROUP): an audio peer belongs to exactly one
origin note by construction, so per-group dedup is correct there. An
attachment has no such constraint — two entirely unrelated notes can embed
the same image — and PRD Feature 4 requires exactly one `move_asset` for it
regardless of how many notes embed it. Keying the `seen` set on the resolved
FULL PATH (never the basename) matters independently of dedup scope: two
different files sharing a basename in different folders must NOT collapse
into one entry (that is the destination-collision case below, a different
outcome). Tests exist for both failure directions — basename-keyed dedup and
per-item-scoped dedup — because each fails silently (no exception, just a
wrong count) if reintroduced.

## Destination Collision: Skip and Report, Never Overwrite (ADR-3)

WHY a destination-claim map (`claimed: dict[destination -> path]`) rather than
letting a second attachment silently overwrite the first at apply time: two
DIFFERENT source files can share a basename in different subfolders
(`Images/karte.jpg` and `Scans/karte.jpg`), and the flat asset folder gives
both the same destination filename. ADR-3 chose skip-and-report over
renaming (a Should-have, deferred) or failing the whole run: the first claim
wins, the second is skipped, printed as a `[warn]` to stderr, and returned in
`_build_move_asset_actions`' second return value (see below) so the user
sees it in the rendered document, not just in a log they may never read.

## `_build_move_asset_actions` Returns `(actions, skipped)`

WHY the function returns a tuple instead of always emitting an action (with
an `error` sentinel to be filtered post-hoc, the `filter_unappliable_relationships`
pattern used elsewhere in this codebase): that pattern exists because the
add_relationship failure (a missing or non-markdown child note) is discovered
at a LATER Kado-resolution step, after the action has already been built —
sentinel-then-filter is the only way to surface it. `_build_move_asset_actions`
knows whether an attachment is filable (basename present, no collision) at
build time, before it ever constructs an action dict, so it can simply not
emit the bad one and return the reason directly — no sentinel field ever
needs to reach (and then be stripped from) an action shaped for the wire.
`build_actions()` propagates this as its own second return value,
`skipped_assets`, which is why its signature changed from `-> list[dict]` to
`-> tuple[list[dict], list[dict]]` — every existing and new caller unpacks
the tuple.

`concepts.asset` is read via `cfg.get("concepts.asset", DEFAULT_ASSET_FOLDER)`,
not `cfg["concepts.asset"]` (unlike `cfg["concepts.inbox"]`, read by bracket
access a few lines above it): bracket access would `KeyError` on every
pre-existing test across the suite that builds a bare `cfg` dict for
`build_actions()` without that key — ten-plus call sites, most outside this
module's ownership. `DEFAULT_ASSET_FOLDER` is a module constant here
(`"Atlas/290 Assets/295 Attachments/"`) so `instruction-render.py`'s
`CONFIG_DEFAULTS["concepts.asset"]` can reference the SAME value instead of
restating the literal — two independent layers (`load_config()` for real
profile loads, this `.get()` for hand-built test cfgs) sharing one source of
truth rather than two copies that could silently drift apart.

## ADR-5 Makes an Attachment `delete_source` Structurally Impossible

WHY `_build_move_asset_actions` needed no `delete_source` guard code at all,
unlike `audio_peer` (which required an explicit exclusion elsewhere):
`_build_delete_source_actions` only ever reads `move_notes` (the list
`_build_move_note_actions` returns) as its source-of-truth for which origins
to delete — it never sees the manifest, and attachments never ride the
`move_note` action (ADR-5's `attachments` field lives only on `move_asset`,
built by a wholly separate function). There is no code path by which an
attachment path could reach `_build_delete_source_actions` at all, so ADR-6
("an attachment move never implies a deletion") holds by construction, not by
a filter someone could forget to update. `tests/test_031_t2_2_move_asset_emission.py`
pins this at the `build_actions()` level rather than merely assuming it —
mutation-tested by temporarily emitting a leaked `delete_source` for an
attachment path and confirming the test catches it.

## Every Inbox Path Goes Through One Resolver (spec 034 T5.0)

WHY the five sites that used to compose `<inbox>/<stem>` inline now all call
`render_helpers.resolve_source_path`: the composition was correct only while
inbox discovery ran at `depth=1`, which guaranteed every note sat at the inbox
root. Phase 3 made discovery recursive and removed that precondition — but not
the code, in four files that never adopted `item_key`. Five separate spellings
of the same assumption is how the same defect survives four task-level reviews:
each diff is locally correct and none of them shows the assumption.

The resolver takes `item_key` (the vault-relative path, verbatim — ADR-1) and
falls back to the reconstruction only when no key is present, so a suggestions
document produced before spec 034 still renders exactly as it did. Verified by
comparison against the pre-change builder: for a keyless input the emitted
action list is byte-identical; with a key, the action count and every action's
key set are unchanged and only path VALUES move (CON-4 — a correctness fix, not
a shape change).

`audio_peer` deliberately uses `resolve_sibling_path`, not `resolve_source_path`:
`item_key` is the note's path, and the audio file is not the note. Triage pairs
audio to a transcript by containing folder plus stem
(`inbox-triage.check_audio`), so the peer's folder is the note's folder — the
inbox root is wrong for it whenever the note is not at the root.

The tag-handler group site (source 4 of `_build_delete_source_actions`) routes
through the resolver too even though its `source_paths` are vault-relative by
contract and the fallback can never fire. One rule for every inbox path in the
module means there is no second spelling left to drift.

## `:967` Is the Site That Could Delete the Wrong Note (spec 034 T5.0)

WHY the daily-only `delete_source` gets a comment when the other four do not:
it is the only one of the five that emits a DELETE for a note the run never
rendered, and it had no bare-stem guard at all — it composed the inbox root
unconditionally. Reachability was established with a fixture before the fix
rather than assumed: a subfolder note whose content is fully captured in a
daily note produces exactly one `delete_source`, and on both parser paths it
named `<inbox>/<stem>.md`. With a same-named note at the inbox root that the
run did not include (one left over from an earlier run, say), that action names
the root note. Hashi executes instruction sets, so this is a wrong delete at
the CON-4 boundary.

A daily-only item gets no per-item section, so the display stem is the only
thing the rendered document carries for it — which is why its identity is
recovered from the structured doc rather than from the markdown
(`suggestion-parser.enrich_daily_updates_with_item_keys`).

## The Stem-Keyed Collections Are a Separate, Unfixed Concern

`_build_delete_source_actions` keys six collections by bare stem —
`confirmed_stems`, `expected_by_stem`, `keep_source_stems`, `seen`,
`daily_stems`, `moves_by_origin`. Recursive discovery makes two notes in
different subfolders share a stem, and these collide. Traced consequence for
two confirmed namesakes, one atomic each: both `move_note`s land in one
`moves_by_origin` bucket, the OQ6 completion gate passes (`2 >= 2`), and
`origin_path = moves[0]` emits a single delete — the second note is never
deleted. `keep_source` on either one suppresses the delete for both.

This is left as-is deliberately. Every direction traced fails SAFE (a file
stays in the inbox and is re-proposed next run, rather than the wrong file
being deleted), and re-keying the completion gate is a behaviour change to
OQ6's logic, not an addressing fix. It is a collision concern, distinct from
the addressing concern T5.0 closes.
