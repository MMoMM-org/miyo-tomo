# WHY: lib/moc_discovery_around.py

> Rationale for decisions in `tomo/scripts/lib/moc_discovery_around.py`.
> The module holds the `--around` builders: seed resolution, the MOC-extension payload, the 3-note floor, the new-MOC cluster and its report fields.

## Split Out of moc-discovery.py (#216)

WHY this module exists: `moc-discovery.py` had grown to 2560 lines, past the
constitution's ~300-500 LOC guidance for dense logic (#216). It was split along
its phase seams; the moved code is unchanged, and `moc-discovery.py` re-exports
every name so tests and callers that load the script keep working. The
decision rationale for the behaviour itself stays in
`docs/tomo/scripts/moc-discovery.md`.

## Builders Here, Lookup in the Script

WHY: `_around_lookup`, `_run_around_extension`, `_build_around_note` and `_run_around`
call `_build_kado_client` and `LinkLookup`, which tests patch on the script
module. They stay in the script; everything they do with the lookup result is
pure and lives here.
