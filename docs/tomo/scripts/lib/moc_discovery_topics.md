# WHY: lib/moc_discovery_topics.py

> Rationale for decisions in `tomo/scripts/lib/moc_discovery_topics.py`.
> The module holds Phase 2 topic extraction (cache-first lookup plus capped LLM batching) and Phase 3 cluster detection.

## Split Out of moc-discovery.py (#216)

WHY this module exists: `moc-discovery.py` had grown to 2560 lines, past the
constitution's ~300-500 LOC guidance for dense logic (#216). It was split along
its phase seams; the moved code is unchanged, and `moc-discovery.py` re-exports
every name so tests and callers that load the script keep working. The
decision rationale for the behaviour itself stays in
`docs/tomo/scripts/moc-discovery.md`.

## Phases 2 and 3 Together

WHY: Phase 3 consumes exactly what Phase 2 produces (candidates with topics), and
`_build_topics_index` is also used by the `--emit-phase1` writer. Keeping the two
phases together keeps the topic index next to its main consumer.
