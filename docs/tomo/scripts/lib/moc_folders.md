# WHY: lib/moc_folders.py

> Rationale for decisions in `tomo/scripts/lib/moc_folders.py`.
> Decides which folders count as "the configured MOC folders" and whether a
> path lies inside them. Only non-obvious decisions are recorded here.

## Why It Exists (spec 040 ADR-1, ADR-5)

The shared-ctx builder gives every MOC one delivered name: its title, or its
vault path when another eligible MOC has the same title. When titles collide,
the MOC that lives in the configured MOC folder keeps the bare title and the
others carry their path (owner decision, 2026-10-23: in LYT and MiYo vaults
nearly every MOC lives in one folder, so the folder MOC is the one people mean).
That rule needs one answer to "inside the MOC folders?", so it lives here
rather than inline in the builder.

## Why Not `lib.moc_scan.read_scope_paths`

`read_scope_paths` returns the *scan scope* for the MOC-structure cache: the
MOC folders plus the atomic-note folders, because a MOC tagged
`type/others/moc` may sit among the notes. That is the right universe for
discovering MOCs and the wrong one here — a MOC in the notes area is exactly
the "outside the MOC folder" case the collision rule distinguishes.

## Why Three Config Shapes

`concepts.map_note` appears as `{paths: [...]}` (canonical, plus `tags`),
`{path: str}`, or a bare string — the same shapes `vault-scan.py`
`extract_all_paths` accepts. Real configs also carry trailing whitespace in
paths (`"Calendar/301 Daily/ "` was seen in a live vault-config), so entries are
stripped before the trailing `/` is enforced.

## Why `path_key` for Membership

`lib.vault_paths.path_key` (NFC, then casefold) is the one comparison key for
vault paths. A folder configured as `Atlas/200 Maps/` must match a cache path
spelled `atlas/200 maps/…`; using a second normalisation here would let the
two disagree. The trailing `/` on every prefix stops `Atlas/200 Maps2/` from
matching `Atlas/200 Maps/`.

## Related: `lib.moc_tags.is_excluded_moc`

The exclude predicate sits with the tag constant in `lib/moc_tags.py`, not
here. It compares case-insensitively and accepts one leading `#`, because
Obsidian tags are case-insensitive and an inline tag can arrive with its `#`.
`lib/orphan_link.py` still compares `EXCLUDE_MOC_TAG` by exact list membership;
aligning it is outside spec 040.
