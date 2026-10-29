# WHY: lib/moc_discovery_enrich.py

> Rationale for decisions in `tomo/scripts/lib/moc_discovery_enrich.py`.
> The module holds Phase 4 title generation, Phase 5 parent resolution and `_enrich_cluster`, which applies both plus the cluster metadata.

## Split Out of moc-discovery.py (#216)

WHY this module exists: `moc-discovery.py` had grown to 2560 lines, past the
constitution's ~300-500 LOC guidance for dense logic (#216). It was split along
its phase seams; the moved code is unchanged, and `moc-discovery.py` re-exports
every name so tests and callers that load the script keep working. The
decision rationale for the behaviour itself stays in
`docs/tomo/scripts/moc-discovery.md`.

## Title, Parents and Metadata in One Place

WHY: every proposed cluster, from the topic pipeline or from `around:<note>`, gets
its title, parent options, location and template from the same helpers.
`_moc_location` and `_serialise_parents` are shared by both paths, so they sit
with the phases that produce their inputs.
