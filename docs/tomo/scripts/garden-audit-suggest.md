# WHY: garden-audit-suggest.py

> Rationale for decisions in `tomo/scripts/garden-audit-suggest.py`.
> The `--suggest` second-pass helper (spec 030 Phase 7, T7.4): reads a published
> garden-audit report + its wire + the local MOC-structure cache, enriches
> Suggest-ticked findings with candidate pick lists, writes the enriched report.

## A separate deterministic helper (mirrors garden-audit-configure.py)

WHY `--suggest` is its own script rather than a mode inside `garden-audit.py` or
`garden-audit-render.py`: `garden-audit.py` is the SCAN orchestrator (needs a live Kado +
the whole cache to produce the doc); `garden-audit-render.py`'s `main()` renders FROM a
doc.json. The suggest pass does neither — it operates on the ALREADY-published report +
wire, with no re-scan. Giving it its own helper mirrors `garden-audit-configure.py` (also a
deterministic mode-support helper the agent invokes) and keeps each script's `main()`
contract single-purpose.

## Reuse enrich_report_with_suggestions (SSoT)

WHY this script imports `garden-audit-render.enrich_report_with_suggestions` rather than
re-implementing the block rewrite: the enrichment logic (which blocks to touch, where to
insert the pick list, byte-for-byte preservation, idempotency) is one algorithm and lives
with the renderer that owns the report format. This helper is a thin I/O + CLI wrapper: read
three files, call the shared function, write one file. The hyphen-named module is loaded via
`importlib` (same pattern the tests use) because `garden-audit-render` is not an importable
package name.

## run_suggest() is pure file I/O for testability

WHY the core is `run_suggest(report_path, wire_path, cache_path) -> str` (returns the enriched
report, does not write): it lets tests exercise the join + enrichment without a subprocess or a
Kado client. `main()` is the thin CLI shell that writes the result and prints the
`enriched N finding(s)` count. This mirrors the mock-at-orchestrator testing posture used across
the garden-audit scripts.

## Graceful degrade on unreadable wire/cache

WHY an unreadable wire or cache yields no candidates (warn to stderr) instead of crashing:
the agent still needs a valid report to re-upload. A missing wire means "no structure to join"
(no picks); a missing cache means "no stems to match against" (no picks). Either way the
report is returned intact — the user simply gets no suggestions, not a broken run. Only an
unreadable REPORT is a hard error (exit 1) — there is nothing to enrich or re-upload.

## Version 0.1.0

WHY: Initial spec-030 Phase 7 (T7.4) implementation. `update-tomo.sh` skips unchanged versions.
