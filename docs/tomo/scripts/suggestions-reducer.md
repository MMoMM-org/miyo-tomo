# WHY: suggestions-reducer.py

> Rationale for decisions in `tomo/scripts/suggestions-reducer.py`.
> The script reduces per-item result JSONs into a suggestions-doc, and (in
> `--moc-proposal-mode`) renders a DiscoveryReport into a MOC proposal-doc.

## Orphan Overflow Footer + MOC-Uplink Heading (ADR-12, T6.4)

WHY: A whole-vault scan can legitimately surface hundreds of note orphans
(verified real on the live vault — empty `up::` placeholders + notes with no
`up`). moc-discovery caps the rendered set at `orphan_display_cap` and reports
`orphan_overflow`. `_render_orphan_section` renders a footer when `overflow > 0`
so the doc is honest about truncation and points the user at a scoped re-run —
silent truncation would read as "these are all the orphans" when they are not.

`check_mode` (report `mode == "check-moc-uplinks"`) relabels the H1 and the
orphan section as a "MOC Uplink Check" — the same renderer serves both the
notes-discovery proposal and the on-demand MOC-parentage audit, because a
check-mode report is just a DiscoveryReport with no clusters and MOC-kind orphan
suggestions. The cap/overflow live in moc-discovery (config-driven); the reducer
only renders what the report carries (`orphan_overflow`), staying a pure
`(report, config) -> (filename, body)` function with no Kado access (CON-3).
