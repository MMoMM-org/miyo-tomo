# WHY: lib/moc_discovery_report.py

> Rationale for decisions in `tomo/scripts/lib/moc_discovery_report.py`.
> The module holds DiscoveryReport assembly: `empty_report`, `candidate_rows`, `build_pipeline_report`, `emit_report` and `_emit_abort_report`.

## Split Out of moc-discovery.py (#216)

WHY this module exists: `moc-discovery.py` had grown to 2560 lines, past the
constitution's ~300-500 LOC guidance for dense logic (#216). It was split along
its phase seams; the moved code is unchanged, and `moc-discovery.py` re-exports
every name so tests and callers that load the script keep working. The
decision rationale for the behaviour itself stays in
`docs/tomo/scripts/moc-discovery.md`.

## One Report Shape for Every Exit Path

WHY: the cluster pipeline, `--around`, `--check-moc-uplinks`, `--dry-run` and every
abort write the same DiscoveryReport keys in the same order, which the reducer
and the agent read. `empty_report` is the only place the key order is defined;
the builders only update existing keys, so key order cannot drift.

## Candidate Rows Built Once

WHY: the pipeline and `around:<note>` both serialised Candidates with the same six
fields in two inline copies. `candidate_rows` is the one copy.
