# WHY: lib/vault_paths.py

> Rationale for decisions in `tomo/scripts/lib/vault_paths.py`.
> The two destination-join helpers every vault-path comparison is built
> with. Only non-obvious decisions are recorded here.

## Why a Module of Its Own (spec 039 T1.4, SDD K15)

`_dest_join` and `_asset_dest_join` lived in `render_actions.py`. The shared
folder lookup (`lib/vault_folder_lookup.py`) keys its views by them, and
`render_actions` imports that lookup for `make_folder_listing` — so the
helpers moved below both to break the cycle. `render_actions` re-exports
them under the same names; the leading underscore is kept so every existing
import and reference reads unchanged.

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
`_check_path_shape` (the wire-level path validator in `render_actions.py`) has no basename
check, so nothing downstream would have caught a bare-folder destination
before it reached Hashi as an instruction to move a file *to* a directory.
`_build_move_asset_actions` catches the `ValueError` and routes that one
attachment through the same skip-and-report path as a destination collision
(`render_actions.md`, "Destination Collision") rather than letting it abort the whole render.
