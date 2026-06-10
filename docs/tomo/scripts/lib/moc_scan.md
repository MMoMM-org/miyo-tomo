# WHY: lib/moc_scan.py

> Rationale for decisions in `tomo/scripts/lib/moc_scan.py`.
> The module implements tag-primary MOC discovery and builds the in-scope note
> universe consumed by the MOC-structure cache builder (spec 021, T1.2/T1.4).

## Tag-Primary Discovery — `#type/others/moc` as the Canonical Signal (ADR-5)

WHY: The legacy moc-tree-builder.py used path-based discovery: it walked every
folder listed in `concepts.map_note.paths` and collected all `.md` files found
there. This worked only if every MOC lived in a configured folder — a structural
assumption that Marcus's vault no longer satisfies cleanly (some MOCs live
outside the canonical map_note folders). The tag `#type/others/moc` is explicit
authorial intent: the user has actively tagged the note as a MOC. ADR-5 codified
tag-primary as the ground truth for the MOC-structure cache, with path-based
discovery remaining in the legacy `discover_via_paths()` path inside
moc-tree-builder.py for the discovery-cache.yaml pipeline.

## Exclude Wins Over Tag (OQ-5, Rule 8)

WHY: `byTag` has no server-side path filter — Kado returns every note matching
the tag regardless of folder. This means a daily-note or an archived MOC that
happens to carry `#type/others/moc` would appear in the result set even if its
folder is listed in `exclude_paths`. The client-side filter in
`_discover_moc_paths` enforces "exclude wins over tag" semantics: if a path
starts with any configured exclude prefix it is dropped from the MOC set,
regardless of its tags. Trailing spaces in prefixes are respected exactly — a
vault folder named "Calendar/301 Daily/ " (with trailing space) is a real-world
gotcha documented in OQ-5.

## Scalar-or-Dict `atomic_note` Normalisation (M8)

WHY: In vault-example.yaml, `concepts.atomic_note` is a scalar string (a single
folder path). In Marcus's real instance config, it is a dict with `path` or
`paths` keys because multiple atomic-note roots evolved over time. `read_scope_paths`
normalises both shapes to a flat list. The normalisation lives in this module
rather than in the builder because it is pure config-parsing logic with no Kado
dependency, and because both the builder and tests need the scope list before
any network call is made.

## Denial-Skip on Scope Path Errors (H4, AC-P2)

WHY: If Kado returns an error for one scope path (permission denied, missing
folder, transient network issue), the scan still succeeds for all other paths.
The failure is logged to stderr and the path is skipped. No fabricated entries
are added. This mirrors the `try/except` pattern in moc-tree-builder.py's
`discover_via_paths()` and enforces the AC-P2 accuracy constraint: partial but
honest results are always better than a silent all-or-nothing abort.

## Client-Side Filter Because `byTag` Has No Server Filter

WHY: Kado's `search_by_tag` endpoint does not accept a path-prefix parameter.
All tag-matched notes are returned unconditionally. Filtering in the server
would require a Kado API extension; filtering client-side is simpler, keeps
the module independent of any Kado version, and adds no noticeable overhead
given that MOC sets are typically 20-100 entries even in large vaults.
