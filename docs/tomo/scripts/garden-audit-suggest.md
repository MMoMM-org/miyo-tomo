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

WHY the core is `run_suggest(report_path, wire_path, cache_path)` returning values (not
writing): it lets tests exercise the join + enrichment without a subprocess or a
Kado client. `main()` is the thin CLI shell that writes the results and prints the
`enriched N finding(s)` count. This mirrors the mock-at-orchestrator testing posture used across
the garden-audit scripts. (Return shape evolved: `str` → 0.3.0 `(report, wire)` → 0.4.0
`(report, wire, processed, with_candidates)` — see the version sections below.)

## Graceful degrade on unreadable wire/cache

WHY an unreadable wire or cache yields no candidates (warn to stderr) instead of crashing:
the agent still needs a valid report to re-upload. A missing wire means "no structure to join"
(no picks); a missing cache means "no stems to match against" (no picks). Either way the
report is returned intact — the user simply gets no suggestions, not a broken run. Only an
unreadable REPORT is a hard error (exit 1) — there is nothing to enrich or re-upload.

## cwd-relative defaults; --output defaults to --report in-place (spec 030, 2026-07-21)

WHY `--report`/`--wire`/`--cache` default to `tomo-tmp/suggest-report.md` /
`tomo-tmp/suggest-wire.json` / `config/moc-structure-cache.yaml` and `--output` defaults to the
resolved `--report` (in-place enrichment): the agent fetches the published report + wire into
those exact `tomo-tmp/suggest-*` paths (via `kado-read-file`), then calls this script bare (Tomo
default-path standard). Enriching in place means the same file the agent re-uploads is the one it
just enriched — no fourth path to thread. `--output` defaults to `None` and resolves to
`args.report` in `main()` because argparse can't reference another arg's value at declaration.

## Version 0.4.0 — suggested ran-marker + processed-count contract (2026-07-23 Hashi handoff)

WHY `run_suggest` now returns `(report, wire, processed, with_candidates)` and the stderr line
became `enriched N finding(s) (M with candidates, K without)`: two gaps surfaced by Hashi
building the suggest-card states (spec-005 T5.4).

**Ran-vs-pending was wire-identical (Gap A).** A finding *awaiting* a suggest run and one whose
run *returned empty* both read `{suggest_requested: true, candidates: []}` — the editor could
not render the PRD-required "no suggestions found" state. Fix: `enrich_wire_with_candidates`
stamps `decision.suggested: true` on every finding it processed (whatever the candidate count)
and clears the marker on findings not requested in the latest run (idempotency, mirroring the
existing candidates-clearing). `suggest_requested` stays untouched — Hashi renders
`suggest_requested && !suggested` → pending, `suggested && candidates==[]` → "no suggestions
found", `candidates.length > 0` → chips. Reset-only (clearing `suggest_requested` post-run) was
rejected as ambiguous against the initial state — Hashi's own analysis. `suggested` is excluded
from `compute_garden_audit_digest` automatically (the digest projects only the apply-decision
allowlist), so enrichment never reads as a user edit.

**"Pick one"-counting suppressed zero-candidate uploads (Gap C, found during verification).**
0.3.x reported `enriched N` by counting `"Pick one"` occurrences in the markdown; the agent
stops on `N=0`. But a requested finding with zero candidates writes a no-suggestions note
(markdown) and the `suggested` marker (wire) — both artifacts changed, yet N read 0, so the
agent stopped and neither channel was ever uploaded. Fix: N counts PROCESSED findings
(returned by `enrich_wire_with_candidates`); the `(M with candidates, K without)` split keeps
the relayed message honest. Degraded mode (unreadable wire) falls back to the markdown
pick-list count. Regression-pinned by
`test_garden_audit_suggest.py::TestSuggestCli::test_cli_zero_candidate_run_still_counts_as_processed`.

## Version 0.3.1 — do NOT re-stamp emit_digest (preserve user apply-edits, 2026-07-22)

WHY `run_suggest` leaves the wire's `emit_digest` UNTOUCHED (0.3.0 wrongly re-stamped it): candidates
are already EXCLUDED from `compute_garden_audit_digest`, so writing them never changes the digest —
re-stamping is unnecessary. Worse, it is HARMFUL: if the user edited an apply-decision (e.g.
`decision.file_under`) in the editor BEFORE running `--suggest`, re-stamping overwrites the Tomo
baseline with the edited state; a later `_is_wire_edited` recomputes the same value, reads
`stored == recomputed` → False → Pass-2 routes to `build_from_report` (empty markdown) and SILENTLY
DISCARDS the user's decision. Removing the re-stamp keeps the baseline correct in both cases (unedited
→ matches → not edited; pre-edited → mismatches → edited). Regression-pinned by
`test_garden_audit_tomo_editor.py::TestSuggestWritesWireCandidates::test_pre_edited_wire_survives_suggest`
(fails against the 0.3.0 re-stamp).

## Version 0.3.0 — writes candidates into the wire (spec 030 extension, 2026-07-22)

WHY `run_suggest` now returns `(report, wire)` and also enriches the WIRE (not only the markdown):
the Tomo-Editor reads the JSON (Hashi's channel), so `--suggest` must populate
`decision.candidates=[{stem,score}]` there for the editor to render. Findings are selected from the
UNION of markdown Suggest ticks and wire `decision.suggest_requested` (`_suggest_requested_ids`).
Candidate computation is SSoT'd via `garden-audit-render.enrich_wire_with_candidates` +
`_split_cache_entries` + `_candidates_for_block` — the markdown pick list and the wire candidates
never diverge. `--wire-output` defaults to `--wire` (in-place), mirroring `--output`→`--report`. An
unreadable wire yields `wire=None` (report still returned + written) — the agent re-uploads a valid
report.

## Version 0.2.0

WHY: 0.2.0 (spec 030) — cwd-relative defaults; `--output` defaults to `--report` (in-place).
0.1.0 initial Phase 7 (T7.4). `update-tomo.sh` skips unchanged versions.
