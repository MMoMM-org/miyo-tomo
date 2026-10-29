# WHY: lib/moc_discovery_args.py

> Rationale for decisions in `tomo/scripts/lib/moc_discovery_args.py`.
> The module holds the CLI surface of `moc-discovery.py`: default paths, `build_parser`, `route_input` and `resolve_profile`.

## Split Out of moc-discovery.py (#216)

WHY this module exists: `moc-discovery.py` had grown to 2560 lines, past the
constitution's ~300-500 LOC guidance for dense logic (#216). It was split along
its phase seams; the moved code is unchanged, and `moc-discovery.py` re-exports
every name so tests and callers that load the script keep working. The
decision rationale for the behaviour itself stays in
`docs/tomo/scripts/moc-discovery.md`.

## The Parser Is a Contract

WHY: the flag set, defaults and help text are what `moc-architect.md` invokes. They
live in one module so a change to the contract is one diff, separate from the
orchestration in the script.

## `DEFAULT_SQUELCH_STATE_PATH` Resolves at Import

WHY: the squelch sidecar defaults to `$TOMO_INSTANCE/state/moc-squelch.json` (ADR-8).
It is read once at import, exactly as it was in the script, so the `--help` text
shows the resolved path.
