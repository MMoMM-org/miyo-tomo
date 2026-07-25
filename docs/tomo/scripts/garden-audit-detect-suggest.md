# WHY: garden-audit-detect-suggest.py

> Rationale for decisions in `tomo/scripts/garden-audit-detect-suggest.py`.
> Called by the garden-auditor agent at Step 1 (mode resolution) on a bare `/garden-audit`
> to decide whether the next action is a suggest enrichment (not a fresh scan).

## Wire signal, not the markdown box (2026-07-25)

WHY detection keys on the WIRE's top-level `suggest_pending` rather than grepping the markdown
`- [x] Suggest targets` box: the Tomo-Editor writes suggest requests into the WIRE
(`decision.suggest_requested`, top-level `suggest_pending`) and NEVER ticks the markdown box — it
stays `- [ ]`. The old Step-1 rule grepped the markdown, so every editor-driven request was missed
and bare `/garden-audit` fell through to a fresh scan (observed on 2026-07-25_0745: wire
`suggest_pending: true`, all markdown boxes unticked). The design intent is that a bare
`/garden-audit` RECOGNISES the suggest run; `--suggest`/`suggest` is only the explicit force alias.

## Two channels (parity with inbox-triage)

WHY it also checks the markdown (`- [x] Suggest targets` block without a `Pick one` / `No
suggestions found` marker): the `.md`-only user (no editor) ticks the markdown box, which never
sets the wire's `suggest_pending`. Same two-channel predicate as
`inbox-triage._garden_suggest_pending` — the wire is the primary signal, the markdown the fallback.

## Fail-open, stdout contract

WHY the helper prints the report `.md` path on stdout (else nothing) and always exits 0: the agent
branches on stdout — a path → suggest mode on it, empty → fresh audit. Any failure (no report,
Kado unreachable, unreadable wire) prints nothing → the agent safely falls through to a fresh scan
rather than blocking. Diagnostics go to stderr. The `*_garden-audit.json` name filter keeps a
vault-wide byName glob from matching unrelated `.json` (e.g. Tsukai insight notes are `.md`).

## Newest report wins

WHY it picks the newest `*_garden-audit.json` by mtime: a bare `/garden-audit` acts on the current
report. A forgotten OLDER pending report is not auto-enriched over a fresh intent — only the newest
is considered; `/garden-audit audit` is the explicit fresh-scan escape.
