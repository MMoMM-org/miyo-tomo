# WHY: lib/render_resolve.py

> Rationale for decisions in `tomo/scripts/lib/render_resolve.py`.

WHY `resolve_section_names` indexes in-set `create_moc` actions by
`lib.vault_paths.path_key` (NFC, then casefold) and looks `target_moc_path` up
the same way (CON-6, spec 034 T6.0, spec 039 W7): it is the paired consumer of
`_build_create_moc_actions`' `by_dest`. If the two keys disagree, a
`link_to_moc` whose target differs from the `create_moc` destination only in case
or Unicode normalisation form misses the in-set template and loses its anchor.
Tests: `tests/test_034_t6_0_case_folded_destination_keys.py`,
`tests/test_039_t4_7_nfc_target_keys.py`.

## Extend-MOC Targets Are Verified Before the Build (spec 042, T4.4)

WHY `filter_missing_extension_targets` runs before any action is built: an
`extend_moc` item gives every ticked member an `up::` to the MOC and a line in
the MOC body. If the MOC does not exist, or is not one definite note, those
writes point at nothing or at the wrong file, so the item is judged first and
withheld whole.

- **Exact-stem `.md` search.** The MOC is looked up with `client.search_by_name`
  and the hits are narrowed by `render_helpers.exact_stem_paths`: only `.md`
  hits whose file stem equals the MOC stem count. A name search is fuzzy, so a
  substring hit (`Health MOC Archive` for `Health MOC`) or an attachment must not
  verify the target.
- **Three verdicts.** One exact hit: the target exists, keep the item. Zero hits:
  `absent` (renamed or deleted). Two or more: `ambiguous`, because the wikilink
  `[[<MOC>]]` Obsidian resolves would be a guess. A search that raises (transport
  or validation error) is `unverifiable`: Kado not answering is not evidence the
  note is missing, and the remedy differs (re-run once Kado answers, versus fix
  the name). Each verdict has its own reason (`EXTENSION_WITHHELD_REASONS`) and
  its own remedy line in `render_md._WITHHELD_EXTENSION_REMEDIES`.
- **Withheld with a cause.** A withheld item is not dropped silently. The record
  carries id, `target_moc`, `kind`, `reason`, the exact-stem `paths` found and
  `member_count`: metadata only, no note content. `instruction-render.py` prints
  a `[skip]` line to stderr, and `render_md` lists it under "MOC extension not
  applied" so the owner learns that no `up::` and no MOC line were written.
- **`target_moc_path` stamped.** A kept item gets the single verified path as
  `target_moc_path`. `render_actions` reuses it for the already-linked check and
  for every `link_to_moc` action, so the build does not search again and cannot
  resolve a different note than the one verified here. It repeats the search only
  for an item that arrives without the stamp.
- **No client keeps everything.** With `client is None` (offline render) nothing
  can be verified and nothing is withheld; the check is a guard, not a gate on
  rendering. Items of any other action pass through untouched.
