# WHY: lib/placeholder_detect.py

> Rationale for decisions in `tomo/scripts/lib/placeholder_detect.py`.
> The module finds dead wikilinks in MOC bodies — links that don't resolve to
> any known note — and returns them as the `placeholder_links` list.

## Real-Vault Denominator Fixes 224 False-Positive Placeholders

WHY: The original `detect_placeholders` inside moc-tree-builder.py used the
MOC set (typically 89 notes in Marcus's vault) as the denominator for "does
this link resolve?" — if a link target wasn't a MOC, it was flagged as a
placeholder. This was wrong: the majority of wikilinks in MOC bodies point to
ATOMIC NOTES, not to other MOCs. Running the check against only the 89-MOC set
produced 224 false-positive placeholder entries (links to real atomic notes
that the old code incorrectly reported as missing). The fix — recorded in the
`key change` paragraph of the module docstring and confirmed via the spec 021
false-positive analysis — is to check the link target against the FULL in-scope
vault note set (`in_scope_vault_paths`), which includes both MOCs and atomic
notes. A wikilink resolves if it matches any note in that union; only then is
it genuinely missing.

## O(1) Stem Index — No Per-Link Scan (Review L1)

WHY: The previous implementation called `resolve_link_to_path()` for every
link inside every MOC body — an O(M) scan of the full MOC list per link. With
100 MOCs each carrying ~20 wikilinks, that is 2 000 linear scans per builder
run. `_build_stem_index` precomputes a `{stem.lower(): path}` dict once per
call and then resolves every link in O(1). The code-review finding L1 on T1.3
flagged the per-link scan as a performance issue; this is the fix.

## Anchor-Strip Before Resolution

WHY: Obsidian block-references and heading anchors take the form
`[[Note#^block-id]]` or `[[Note#Heading]]`. The link target, after anchor
strip, is just "Note". If the anchor is a same-note reference (`[[#Heading]]`
with no leading note stem), strip produces an empty string, which must be
skipped — it is not a link to a missing note. Both cases are handled by
`_strip_link_anchor` and the `if not note_target: continue` guard, matching
the anchor-handling logic in `_count_linked_notes` in moc-tree-builder.py.

## Per-(note, MOC) Deduplication

WHY: A MOC body may contain multiple anchored references to the same missing
note — e.g., `[[Missing#Section A]]` and `[[Missing#Section B]]`. After anchor
stripping, both reduce to "Missing" against the same MOC. Without dedup, the
placeholder list would have two entries for the same logical missing note,
inflating the placeholder count and producing duplicate Condition C triggers in
the inbox-analyst. The `seen: set[tuple[str, str]]` guard collapses them to
one entry per (missing-note, referencing-MOC) pair.
