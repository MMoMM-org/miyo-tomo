# WHY: lib/moc_discovery_uplinks.py

> Rationale for decisions in `tomo/scripts/lib/moc_discovery_uplinks.py`.
> The module holds the `--check-moc-uplinks` audit: the orphan link-or-create pass over `kind == "moc"` entries and the display cap `_cap_orphans`.

## Split Out of moc-discovery.py (#216)

WHY this module exists: `moc-discovery.py` had grown to 2560 lines, past the
constitution's ~300-500 LOC guidance for dense logic (#216). It was split along
its phase seams; the moved code is unchanged, and `moc-discovery.py` re-exports
every name so tests and callers that load the script keep working. The
decision rationale for the behaviour itself stays in
`docs/tomo/scripts/moc-discovery.md`.

## No Kado Client Needed

WHY: the audit reads only the MOC-structure cache and the orphan rules in
`lib/orphan_link.py`. With no client and no lookup it has no patched names, so the
whole entry point (`_run_moc_uplink_check`) moved.
