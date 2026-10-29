# WHY: lib/moc_discovery_phase1_io.py

> Rationale for decisions in `tomo/scripts/lib/moc_discovery_phase1_io.py`.
> The module holds the two-pass Phase-1 file I/O: `_write_phase1_emit` (`--emit-phase1`) and `_load_phase1_input` (`--phase1-input`).

## Split Out of moc-discovery.py (#216)

WHY this module exists: `moc-discovery.py` had grown to 2560 lines, past the
constitution's ~300-500 LOC guidance for dense logic (#216). It was split along
its phase seams; the moved code is unchanged, and `moc-discovery.py` re-exports
every name so tests and callers that load the script keep working. The
decision rationale for the behaviour itself stays in
`docs/tomo/scripts/moc-discovery.md`.

## The File Format Has One Owner

WHY: the moc-architect agent fills cache-miss topics between the two passes. The
writer and the reader of that file sit together so the format cannot change on
one side only. The writer also enforces the cache-miss cap, because the
`--phase1-input` flow skips Phase 2's check.
