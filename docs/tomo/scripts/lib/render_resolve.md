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
