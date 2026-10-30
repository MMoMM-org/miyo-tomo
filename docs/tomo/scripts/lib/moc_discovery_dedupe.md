# WHY: lib/moc_discovery_dedupe.py

> Rationale for decisions in `tomo/scripts/lib/moc_discovery_dedupe.py`.
> The module holds Phase 6 duplicate / squelch filtering against existing MOCs and the D3 inter-cluster member-overlap pass.

## Split Out of moc-discovery.py (#216)

WHY this module exists: `moc-discovery.py` had grown to 2560 lines, past the
constitution's ~300-500 LOC guidance for dense logic (#216). It was split along
its phase seams; the moved code is unchanged, and `moc-discovery.py` re-exports
every name so tests and callers that load the script keep working. The
decision rationale for the behaviour itself stays in
`docs/tomo/scripts/moc-discovery.md`.

## Phase 6 and D3 Share a Module, Not a Rule

WHY: both drop proposed clusters and both report into `duplicates_skipped`. Phase 6
compares proposals against existing MOCs, D3 compares proposals against each
other. They stay separate functions, as ADR-13 D3 requires.

## No Folder-Home Check Here

WHY: a cluster-level folder-home skip lived in Phase 6 from PR #220 until the
next fix. It let single folder-home notes through into mixed clusters, so the
rule moved to Phase 1, at the level of single notes. See
`docs/tomo/scripts/lib/folder_homes.md`.
