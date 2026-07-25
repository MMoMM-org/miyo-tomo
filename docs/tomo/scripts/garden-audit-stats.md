# WHY: garden-audit-stats.py

> Rationale for decisions in `tomo/scripts/garden-audit-stats.py`.
> The `/garden-audit stats` read-only overview (spec 030): aggregates a fresh scan
> doc + the exclusion config into a compact markdown overview relayed to the chat —
> NO vault write, re-runnable anytime.

## Reuses the scan, never re-implements it

WHY the agent runs `garden-audit.py` first and this script reads its `garden-audit-doc.json`,
rather than the stats script scanning the vault itself: the six-check scan (cache + graph_audit +
listDir, exclusions, graceful partial) is the single source of truth for findings. A second scan
path would drift from the audit path and double the Kado cost. The overview is a pure projection
of the same doc the audit/apply flow uses — no new analysis, no LLM.

## Ephemeral chat relay, no vault artifact

WHY the overview is printed to stdout and relayed to the chat instead of written to the inbox:
it is a status view the user glances at, not a reviewable document with checkboxes to apply. A
vault write would litter the inbox with throwaway status files and drag the doc through the
`/inbox` lifecycle it does not belong in. Re-runnable anytime = always fresh, never stale.

## Aggregate by AREA (first path segment) with an explicit cap

WHY findings are grouped by the first path segment (`Calendar/…` → `Calendar`; a root-level note →
`(root)`) and capped at top-N areas with a `… N more areas` / others-total row: a real vault can
produce hundreds of findings across dozens of folders. The first path segment is the natural
"area" a user reasons about ("my Calendar is noisy"). The top-N cap keeps the table chat-readable,
and the explicit others row (with its finding total) means the cap NEVER silently drops data — the
user always sees that more exist and how many. Ties break by area name ASC for deterministic output.

## today is threaded, never re-read at multiple sites

WHY `effective_today` is a required param on `render_stats` / `run_stats` and the days-remaining
math uses it, rather than each section calling `date.today()`: the `from_path` date-guard lesson —
two `date.today()` calls in one run can straddle midnight and disagree, and tests need a pinned
date. One value flows from `main()` (or a test) through every section, so the active/pushback/
days-remaining views are internally consistent and deterministic.

## --exclusions None-sentinel (parallels garden-audit.py)

WHY `--exclusions` defaults to `None` (not the path string) and `run_stats` takes an
`explicit_exclusions` flag: same distinction as `garden-audit.py`. A defaulted-but-absent config is
a normal "none configured" section (exit 0) — a fresh vault has no exclusions yet. An
EXPLICITLY-passed missing path is a user error (exit 1). A string default could not tell the two
apart. `_DEFAULT_EXCL_PATH` mirrors the scan's constant so both read the same config location.

## Version 0.1.0

WHY: Initial spec-030 stats-mode implementation. `update-tomo.sh` skips unchanged versions.
