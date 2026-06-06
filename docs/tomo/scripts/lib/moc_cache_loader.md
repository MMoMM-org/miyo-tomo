# WHY: lib/moc_cache_loader.py

> Rationale for decisions in `tomo/scripts/lib/moc_cache_loader.py`.
> The module sits between moc-discovery.py and `config/moc-structure-cache.yaml`,
> providing TTL-gated loading, inline rebuild-if-stale, and a backward-compat shim.

## TTL + Rebuild-If-Stale (ADR-1, ADR-3)

WHY: The MOC-structure cache can go stale when the user adds or renames MOCs
between sessions. Rather than forcing the user to manually run `/explore-vault`
before every `/moc-propose`, the loader checks the cache age against `ttl_days`
on every call. When stale, it invokes the real builder inline — one round-trip
to Kado, one YAML write — before continuing. ADR-3 specifies that
`/explore-vault` always force-rebuilds (it calls `moc-tree-builder.py run()`
directly); ADR-1 specifies that `/moc-propose` should not impose a live full
tree-build on every invocation when the cache is fresh. The loader is the
gate between these two modes.

## Cache-Rebuild-Failed Abort — NOT Re-Scan Every Run

WHY: When the builder raises an exception or the YAML file is still stale after
the rebuild attempt (unwritable path, broken clock, disk full), the loader
aborts with `"cache-rebuild-failed"` and returns `(None, abort_reason)`. It
does NOT fall back to a live Kado scan of the entire vault. A live fallback
would silently degrade performance on every invocation in a broken-cache
environment — the user would never notice the cache is broken and would never
run `/explore-vault` to fix it. An explicit actionable abort surfaces the
problem immediately. The rebuild is attempted exactly once; if it fails, the
caller surfaces the message and stops.

## Shim: `entries[kind=="moc"]` Projected onto `cache["map_notes"]` (ADR-1)

WHY: moc-discovery.py Phases 1–6 read `cache["map_notes"]` — a list of MOC
dicts. The new `moc-structure-cache.yaml` stores a unified `entries` list with
a `kind` discriminator ("moc" | "note"). To avoid rewriting all six phases of
moc-discovery.py simultaneously, `apply_shim` projects the moc-kind entries
onto `map_notes` before handing the cache dict back to the caller. The full
`entries` list is preserved on the dict so the case-(a) orphan pass (T2.3) and
the documented scan-mode rewire (M2) can access non-MOC entries without needing
a separate query.

## Clock-Skew Guard: Future `last_scan` Is Treated as Fresh

WHY: If the host clock jumps backward (NTP correction, Docker time sync issue,
timezone misconfiguration), the `last_scan` timestamp in the cache can appear
to be in the future. A naïve `age > ttl` check would trigger a pointless
rebuild on every invocation until the clock catches up. The guard
`if age_seconds < 0: return False` treats a future timestamp as fresh —
a rebuild is not triggered, and the system degrades gracefully. This follows
the SDD Error Handling clause on clock skew.

## Scan-Mode Stays on Live `list_dir` (M2, Documented Deferral)

WHY: moc-discovery's `_handle_scan` enumerates atomic-note candidates via a
live `list_dir` Kado call. The cache's `entries[kind=="note"]` already contains
the same in-scope note set (populated by `moc_scan.in_scope_note_paths`), so
scan-mode COULD be sourced from the cache to eliminate the live call. This
rewire is a moc-discovery change, not a loader change. The loader exposes the
full `entries` list specifically to make this future one-line projection
possible. Until it lands, M1 ("no full live tree-build when cache is fresh")
holds for the MOC tree-build specifically, and scan-mode remains live.
