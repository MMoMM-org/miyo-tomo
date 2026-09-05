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
