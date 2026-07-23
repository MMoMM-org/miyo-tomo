# WHY: garden-audit.py

> Rationale for decisions in `tomo/scripts/garden-audit.py`.
> The script is the scan orchestrator for the knowledge-garden audit skill (spec 030).
> It runs six checks over the MOC-structure cache, kado-graph-audit results, and
> listDir modified times, applies GardenExclusions, and emits `garden-audit-doc.json`.
> That intermediate doc feeds `garden-audit-render.py` (report + wire).

## Data-Source Split — Three Sources, No Overlapping Calls (ADR-5)

WHY each check has a fixed data source and never crosses into another source's domain:

- **Cache-only** (`broken_up`, `unparented`, `duplicate_stem`): these checks require
  only the MOC-structure YAML cache that the container already loaded — no network call
  to Kado. `broken_up` in particular MUST NOT trigger a graph_audit call; the broken
  `up_target` is already recorded in `up_target` on the cache entry. Triggering a graph
  call would incur unnecessary latency and Kado 429 risk on a check that is fully
  answerable from the cache (SDD ADR-5 Rule 1).
- **Graph-dependent** (`orphan`, `dead_link`): these require the `kado-graph-audit`
  MCP tool, which walks the full vault link graph server-side. They cannot be answered
  from the cache alone (a note can be cache-absent because it was just added; dead
  links require live link resolution). A single `graph_audit_fn()` call gathers both;
  the caller injects this as a callable so tests can stub it without a live Kado server.
- **listDir** (`stale_moc`): requires per-file `modified` timestamps, which only Kado's
  `listDir` surface provides. The cache records structure but not modification time.

WHY the split matters for the graceful-partial guarantee: cache checks always run even
when graph_audit or listDir raises. A Kado outage degrades to cache-only findings rather
than a full failure.

## Batch Orphan Suggestions, Not Per-Orphan Calls (S1)

WHY `_check_orphan` calls `emit_orphan_suggestions` ONCE over an augmented entry list
rather than N calls for N orphans: `emit_orphan_suggestions` clusters all candidate
notes against all MOCs in one pass — O(entries × MOCs). Calling it per orphan would
make it O(N_orphans × entries × MOCs), which is prohibitive on large vaults. The
augmented list appends one fake "absent note" entry per orphan path so the scorer
treats each orphan as needing a parent, then the results are indexed by path. The base
entries are deduplicated to avoid double-counting any entry that happens to share a
path with a graph orphan.

## ID Re-Sequencing After Severity Sort (ADR-5 Tier Ordering)

WHY findings are assembled in a temporary severity order (integrity → structure →
advisory), then IDs are re-sequenced (F01, F02, …) over the final sorted list rather
than assigned sequentially per check: each check runs independently and may produce
findings in cache-traversal order (not severity order). Re-sequencing after the sort
gives the user stable, severity-ordered IDs in the report — F01 is always the most
severe finding. The intermediate `counter` list tracks a running monotonic count so
per-check helpers produce unique IDs during scan; the re-sequence loop then overwrites
them in the final order.

## Graceful Partial on Graph and listDir Errors (SDD Error Handling)

WHY both graph-dependent checks and the `stale_moc` check catch `Exception` broadly
instead of a specific exception type: the injected `graph_audit_fn` and `list_dir_fn`
can raise any exception (OSError from network, RuntimeError from MCP timeout, ValueError
from malformed response). Catching narrowly would silently re-raise on unexpected error
types and abort the scan entirely. The pattern records the failure in `skipped_checks`
and `skipped_checks_reason` so the render step can surface the degradation to the user.
This is the same "not run (X unavailable)" pattern used by inbox-triage for optional
Kado enrichment (CON-5).

## Duplicate-Stem Exclusion is Per-Path, Not Per-Stem

WHY `_check_duplicate_stem` filters excluded paths individually before deciding whether
a finding exists: a user may want to exclude `Archive/Old Note.md` from duplicate-stem
detection while keeping `Notes/Old Note.md` in scope. Excluding at the stem level would
suppress the entire duplicate group as soon as any member is excluded — silently hiding
the remaining conflict. Per-path exclusion preserves the finding for non-excluded members;
the finding is only suppressed when fewer than two non-excluded paths remain.

## cwd-relative defaults + --no-exclusions (spec 030, 2026-07-21)

WHY `--config`, `--output` default to instance-cwd-relative paths
(`config/vault-config.yaml`, `tomo-tmp/garden-audit-doc.json`) and `--no-exclusions`
(store_true) replaced the old "omit --exclusions" idiom: the standing Tomo standard
(docs/ai/memory/general.md 2026-06-24) is that runtime scripts use instance-correct
cwd-relative DEFAULTS so the agent calls bare `scripts/garden-audit.py` — no constant paths
stuffed into the agent on every call; switches are host/test overrides only. argparse defaults
never override an explicitly-passed value, so host runs and tests that pass paths keep working.

WHY `--exclusions` uses a `None` sentinel (defaults to `None`, not the path string) even
though its effective default is `config/garden-audit-exclusions.yaml`: the spec requires
distinguishing "the default file is just absent" from "the user pointed at a file that
doesn't exist". A string default cannot tell those apart — both would look identical. With the
sentinel, `main()` computes `explicit = args.exclusions is not None`: an explicit missing path
is a hard ERROR (exit 1); a defaulted-but-absent path runs UNFILTERED (exit 0, warn). A
present file at either path is loaded normally; `--no-exclusions` skips loading entirely
(the wizard first-run unfiltered scan).

## Version 0.3.1

WHY: 0.3.1 (spec 030) — `--exclusions` uses a `None` sentinel so an explicitly-passed missing
path errors (exit 1) while a defaulted-absent one runs unfiltered (exit 0). 0.3.0 added
cwd-relative defaults for `--config`/`--exclusions`/`--output` + `--no-exclusions` (agent calls
bare). 0.2.0 was the batch-orphan fix (S1) + per-path duplicate-stem exclusion; 0.1.0 initial
spec-030 implementation. `update-tomo.sh` skips unchanged versions.

## Version 0.4.0 — opt-in Apply + settings wiring + ledger merge (2026-07-23)

WHY `_finding` now emits `selected: False` (was True): user decision 2026-07-23 — Apply is
opt-in everywhere. Pre-ticked Apply on a no-candidate orphan was a no-op trap (parser skips it
with a warning), and opt-out review pressure was the wrong default for destructive-ish fixes.
Spec 030 Feature 3 AC revised accordingly; the "Pre-selected best fix" Should-Have is retired
(the scan candidate remains the fallback TARGET, only the pre-ticking was dropped).

WHY main() now always builds `GardenExclusions.from_paths(exclusions, ledger)` even when the
exclusions file is absent (previously `None` → unfiltered): the pushback ledger and the settings
defaults must work without a wizard-written exclusions file. An empty instance preserves the
unfiltered semantics (no rules) while carrying `stale_moc_days` / `advisory_pushback_days` into
`run_scan` — this also finally WIRES the `stale_moc_days` param main() never passed (the spec's
"config deferred" note is superseded). `--no-exclusions` still skips both files: the wizard
first-run preview must show the unfiltered truth, including ledgered advisories.

WHY the doc carries `advisory_pushback_days`: the renderer labels the Acknowledge checkbox with
the window ("pause this advisory for N days") and must stay a pure doc→artifact projection — the
scan injects the value so the renderer never loads config.
