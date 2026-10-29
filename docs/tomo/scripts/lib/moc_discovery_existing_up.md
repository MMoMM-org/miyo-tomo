# WHY: lib/moc_discovery_existing_up.py

> Rationale for decisions in `tomo/scripts/lib/moc_discovery_existing_up.py`.
> The module holds Phase 6.5: one Kado read per kept cluster child, classifying its declared parent as absent / valid / broken.

## Split Out of moc-discovery.py (#216)

WHY this module exists: `moc-discovery.py` had grown to 2560 lines, past the
constitution's ~300-500 LOC guidance for dense logic (#216). It was split along
its phase seams; the moved code is unchanged, and `moc-discovery.py` re-exports
every name so tests and callers that load the script keep working. The
decision rationale for the behaviour itself stays in
`docs/tomo/scripts/moc-discovery.md`.

## Read Through the Passed-In Client

WHY: the Kado client is a parameter, so the `_build_kado_client` patch tests apply
to the script module reaches this phase. The classification rule itself is
`lib/up_state.py`, shared with `moc-tree-builder.py`.
