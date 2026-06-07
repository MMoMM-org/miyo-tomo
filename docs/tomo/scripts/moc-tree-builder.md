# WHY: scripts/moc-tree-builder.py

> Rationale for decisions in `tomo/scripts/moc-tree-builder.py`.
> Rebuilt for spec 021 (T1.4): now the MOC-structure-cache builder that
> orchestrates `lib/moc_scan`, `lib/up_parse`, and `lib/placeholder_detect`.

## Rebuilt as MOC-Structure-Cache Builder, Not Just the Cache-Builder Feed (C2)

WHY: Before spec 021, moc-tree-builder.py produced only the
`cache-builder-shaped map_notes JSON feed` (stdout) consumed by `cache-builder.py
--mocs`. It had no separate output: the MOC-structure cache (`moc-structure-cache.yaml`)
did not exist. The rebuild adds a second, independent output: the
`MocStructureCache` YAML, a unified `entries` list with a `kind` discriminator
("moc" | "note"). This cache is what `moc_cache_loader` reads for `/moc-propose`.

The legacy stdout feed must continue to work (vault-explorer Step 9 calls
`moc-tree-builder.py > moc-output.json` then `cache-builder.py --mocs
moc-output.json`). C2 requires that `kind==moc` entries carry `classification`
and `linked_notes` as an int so `cache-builder.build_classifications` and
`build_scan_stats` keep working without modification. Both fields are always
present on moc-kind entries; `classification` stays `None` (faithful to the
legacy value and to the live cache — Dewey derivation is not in T1.4 scope).

## Dual-Output: stdout JSON Feed + `moc-structure-cache.yaml` — Same Run

WHY: Running the builder once to produce both outputs avoids a double scan of
the vault (one for the YAML, one for the JSON). The single `run_with_client()`
call produces `(cache, feed)` from the same `ScanResult`; `run()` then writes
the YAML atomically and dumps the feed to stdout. ALL progress/warnings go to
stderr — stdout carries the JSON feed only. This is the
`feedback_never_redirect_stderr_into_json` rule in concrete form: mixing
progress lines into stdout would corrupt the `json.load` in the
vault-explorer Step 9 pipeline.

## `placeholder_mocs` Persisted in BOTH Outputs (W1)

WHY: The placeholder list from `placeholder_detect.detect_placeholders` is
returned from `build_entries` as a first-class value and placed in both the
`moc-structure-cache.yaml` (top-level `placeholder_mocs` field) and the
stdout JSON feed (as `feed["placeholder_mocs"]`). cache-builder.py's
`build_placeholder_mocs` lift reads it from the feed; the moc-structure-cache's
copy feeds Condition C in the inbox-analyst (via shared-ctx). Both consumers
see the same list from the same run, eliminating the divergence that occurred
when the two files had different data.

## Reuses `cache-builder.py` TTL/Timestamp and Atomic-Write Primitives

WHY: Reuse, not reinvention. `utc_now_iso` is imported from cache-builder.py
via `importlib` (the hyphen in the filename prevents a direct import). The
atomic-write mechanism in `write_cache_atomic` replicates the tmp-rename
pattern from cache-builder.py's `write_cache_atomic` because the file header
differs (`moc-structure-cache.yaml` vs `discovery-cache.yaml`), but the
underlying contract is identical: a torn/partial write never reaches the
`_load_yaml` staleness check in `moc_cache_loader`, because the file is
either fully written or not replaced at all.

## `tags` Populated from Frontmatter in the Same Read Round-Trip (T7.1 / ADR-13)

WHY: Each cache entry carries its note's real `tags` list (extracted from the
frontmatter that is already read during `read_note_raw()`). No extra per-note
round-trip is needed: `parse_frontmatter(content)` yields the tags from the
same content string that supplies title, wikilinks, and the raw text for
`up_parse`. The `extract_tags(fm)` helper normalises both list-form and
scalar-form tags; a note with no frontmatter tags produces `[]`, never `None`.

The concrete reason tags are stored here and not computed on demand:
**ADR-13 introduces two exclude-tag filters** (`MiYo/Tomo/exclude/moc` and
`MiYo/Tomo/exclude/note`) that must read each entry's `tags` at filter time
in `lib/orphan_link.emit_orphan_suggestions` and `moc-discovery._handle_scan`.
Computing tags on demand at filter time would require an additional Kado read
per entry, breaking the single-read-per-note contract the builder was designed
around (C1) and risking rate-limit pressure on large vaults. Caching them in
the MOC-structure-cache (metadata-only — Constitution L1 satisfied) lets both
filters operate directly on the pre-loaded entry without any vault I/O.

Spec: 021 Phase 7 T7.1, PRD Feature 8 AC7.

## `up_state` Resolved by Caller, Not by `up_parse` (M1)

WHY: `up_parse.parse_up_from_content` returns `{target, source}` only.
`_resolve_up_state` in this builder maps the target against the MOC stem set
(`moc_stem_set`) to produce "absent" / "valid" / "broken". The stem set is
built once in `build_entries` and reused for all notes. This keeps up_parse
independent of vault state (testable in isolation) while keeping the resolution
logic co-located with the data that makes it possible.
