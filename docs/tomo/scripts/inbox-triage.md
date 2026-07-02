# WHY: scripts/inbox-triage.py

> Rationale for decisions in `tomo/scripts/inbox-triage.py`.
> Deterministic inbox triage: partitions inbox files into frontmatter-state
> buckets, computes the routing action, and writes `routing-plan.json` for the
> conductors. Only non-obvious decisions are recorded here.

## `--recover` Folds `captured_hits` Into `fresh_sources` (not just the action)

WHY: `--recover` means "treat captured items as fresh — re-process them". Two
places must honour that, and originally only one did:

1. `determine_action` returns `"suggest"` on `recover and captured_hits`.
2. `build_routing_plan` builds the `fresh_sources[]` dispatch list.

The conductor (`suggest-handling` skill) dispatches **`fresh_sources[]` only**.
Before the fix, `build_routing_plan` populated `fresh_sources` from
`new_sources` exclusively — so `--recover` flipped the action to `"suggest"`
but handed the conductor an **empty** list: the run reported "suggest" and
dispatched nothing. The flag silently did nothing, and the only test
(`test_recover` in `test_inbox_triage.py`) checked the action decision, not the
dispatch list, so it passed while the feature was broken. Surfaced during spec
021 T4.3 live validation (2026-06-09): `/inbox --recover` produced
`fresh_sources: 0` and no new dispatch.

Fix: `build_routing_plan` now appends `captured_hits` to the dispatch sources
when `state.recover` is set. `new_sources` and `captured_hits` are disjoint by
construction (`compute_new_sources` excludes every frontmatter bucket, captured
included), but the fold dedupes by path so a future overlap can't
double-dispatch. Regression coverage:
`test_recover_folds_captured_into_fresh_sources` (must appear) +
`test_no_recover_excludes_captured_from_fresh_sources` (must not leak without
the flag).

Note: this is a pre-021 latent bug, fixed during 021 validation because that is
when a clean-vault re-process surfaced it.

## Discovery-Cache Staleness Warning (#36 / F-21)

WHY: The discovery cache (`config/discovery-cache.yaml`) is rebuilt by
`/explore-vault`, never by `/inbox`. So an `/inbox` run can silently rely on a
months-old vault map (MOC list, tag prefixes, structure) without the user
knowing. Step 8c reads the cache's `last_scan` and, when it is older than
`--stale-cache-days` (default 7), appends a `stale_cache` drift_indicator — the
same user-facing, non-blocking channel the conductors already surface ("surface
each warning but continue"). The message points the user at `/explore-vault`.

WHY a drift_indicator (not the statusline): the drift channel fires at the exact
moment the user is about to act on the cached map, is already surfaced by every
conductor, and is deterministically testable. It required one additive enum
value (`stale_cache`) in `routing-plan.schema.json` — backward-compatible, so
existing plans still validate.

WHY fail-open (missing / malformed / timestamp-less / future-dated → no
warning): a fresh install mid-setup has no cache yet and must not be nagged, and
a corrupt cache must never crash triage. Only a genuinely old, parseable
`last_scan` surfaces a warning. A `last_scan` in the future (clock skew) is
treated as fresh. The staleness check is `discovery_cache_staleness_drift`;
coverage in `tests/test_triage_cache_staleness.py`.
