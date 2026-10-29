# WHY: lib/moc_discovery_phase1.py

> Rationale for decisions in `tomo/scripts/lib/moc_discovery_phase1.py`.
> The module holds Phase 1 candidate selection: the per-mode handlers, the atomic-note pre-filter, the zero / cap checks and the `validate_cache_loaded` predicate.

## Split Out of moc-discovery.py (#216)

WHY this module exists: `moc-discovery.py` had grown to 2560 lines, past the
constitution's ~300-500 LOC guidance for dense logic (#216). It was split along
its phase seams; the moved code is unchanged, and `moc-discovery.py` re-exports
every name so tests and callers that load the script keep working. The
decision rationale for the behaviour itself stays in
`docs/tomo/scripts/moc-discovery.md`.

## Kado Client Passed In, Never Built Here

WHY: tests replace the Kado client by patching `_build_kado_client` on the loaded
script module. Phase 1 receives the client as an argument, so that patch reaches
it without this module knowing the name.
