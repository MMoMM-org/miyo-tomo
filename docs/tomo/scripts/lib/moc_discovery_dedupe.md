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

## Folder-Home Check (Phase 6, third skip)

WHY: some vaults collect a folder's notes through a folder-home note, a MOC
named like its folder (`Atlas/202 Notes/2821 Quotes/2821 Quotes.md`) that lists
the folder with a Dataview table. Its notes carry no `up::`, so `/moc-propose`
saw them as orphans and proposed a new "Quote (MOC)" over all 63 of them. The
existing checks missed it: the titles differ, and the topic overlap with
`2821 Quotes` scored 0.22 against the 0.80 threshold, because the folder-home
carries more topics than the cluster. The folder-home's name cannot change to
match, since it has to equal the folder.

- A folder-home is an existing MOC whose stem equals its folder's name, compared
  case-insensitively.
- A cluster is that MOC's duplicate when at least 80 % of its members with a
  known path sit inside the folder or its subfolders. The threshold matches the
  other Phase 6 and D3 thresholds. The folder must match whole path segments,
  so `2821 Quotes Archive/` is not inside `2821 Quotes/`.
- The skip is reported as `reason="folder-home"` with the folder-home's title in
  `existing_moc`, in the same `duplicates_skipped` shape as the other reasons.
- WHY container roots are excluded: the configured concept folders
  (`concepts.atomic_note`, `concepts.map_note`, read with
  `moc_scan.read_scope_paths`) and their ancestors hold every atomic note. In
  the test vault `202 Notes.md` and `Atlas.md` are named like their folders;
  without the exclusion every cluster would be dropped as their duplicate.
- WHY the check is a skip and not an extension proposal: the folder-home
  already lists the members through its query, so adding `up::` links to them
  would duplicate what the vault shows.
- The check runs only when the caller passes `member_paths`. The scan pipeline
  passes the Phase 1 candidates' paths.
