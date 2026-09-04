# WHY: garden-auditor agent

> Rationale for decisions in `tomo/dot_claude/agents/garden-auditor.md`.
> The agent is the `/garden-audit` orchestrator: it routes arguments to `garden-audit.py`
> (scan), `garden-audit-render.py` (report + wire), and `kado-write-file.py` (transport),
> and runs the first-run exclusion wizard when no config exists.

## Orchestration Agent, Not Analysis Agent (ADR-6)

WHY the agent description states "You MUST NOT perform vault analysis yourself — the
scan script handles all Kado access and cache reads": the garden-auditor is a pure
orchestrator in the same sense as `moc-architect` and `instruction-builder`. An LLM
performing vault lookups inline would produce non-deterministic analysis, duplicate Kado
calls already made by the scan script, and potentially generate findings that contradict
the deterministic scan output. ADR-6 explicitly mirrors the `/moc-propose` track: scan
→ render → transport, with the LLM responsible only for routing, error surfacing, wizard
Q&A, and the fixed output report. Every finding in the delivered report originates from
`garden-audit.py`, not the agent.

## Transport via kado-write-file.py, Not Inline kado-write (STRICT)

WHY the agent is prohibited from reading the report and inlining it into a `kado-write`
tool call: observed live on the `/moc-propose` track (2026-06-06), a 136 KB proposal-doc
exhausted the output-token budget when inlined as tool-call args — the content was
correct on disk but never reached the vault. The garden-audit report can exceed that
threshold when a large vault has many findings across all seven checks. `kado-write-file.py`
reads the file from disk and pushes it through its own Kado client (`operation=note` for
`.md`, `operation=file` for `.json`), so the content never routes through the agent's
token budget. The STRICT comment documents the failure mode in one line per the STRICT
protocol.

## No stderr Redirect on Script Invocations (STRICT)

WHY Step 4 and Step 6 carry `STRICT: Do NOT append 2>&1`: stderr carries diagnostic
messages from the scan and render scripts (`[garden-audit] Scan complete.`, per-finding
counts). Redirecting stderr into stdout would merge these into the captured stdout,
corrupting any JSON or structured output the agent captures. The garden-audit scripts
follow the established Tomo convention: structured output on stdout, diagnostics on
stderr.

## Exclusion Wizard Writes to Skill Config, Never /inbox (STRICT)

WHY the agent is prohibited from routing exclusion decisions through `/inbox`: exclusion
config (`config/garden-audit-exclusions.yaml`) is skill-side configuration — it is
created and owned by the garden-auditor agent on behalf of the user's preference, not a
vault note that Tomo's 2-pass model should process. Routing it through `/inbox` would
trigger inbox-triage, which would classify it as a new note to process, not a config
file to write. ADR-2 specifies that exclusion config is "skill-owned instance exclusion
config (seed, create-only), filter-before-render, managed only in-skill." Wizard Step D
delegates to `garden-audit-configure.py --write`, never the `Write` tool directly on
the exclusions YAML — see `docs/tomo/scripts/garden-audit-configure.md` for the Bug-B
rationale (Write-tool read-before-write trap on the existing seed config).

## First-Run Detection Before Scan (Step 3)

WHY the agent checks for `config/garden-audit-exclusions.yaml` before running the scan
(Step 3) rather than after: on a first run, the scan must run WITHOUT the `--exclusions`
flag to produce unfiltered findings for the wizard to cluster. If the existence check
ran after the scan, the agent would have already passed `--exclusions` to the scan (or
omitted it at the wrong moment), producing a scan result that either fails with a
missing-file error or silently filters nothing. Detecting first-run before the scan
means Step 4 can conditionally add or omit `--exclusions` based on a known state.

## Fixed Output Block (STRICT)

WHY the agent MUST end every run with the structured output block rather than
conversational prose: the fixed output block is the machine-readable receipt for the
`/inbox` track that follows — vault path of the report, wire path, finding counts,
error notes. Without a fixed format the team-lead (or a future integration) cannot
reliably parse the outcome. The STRICT annotation ensures the LLM cannot paraphrase
or reorder the block even when the model tends toward narrative summaries. The
`## Output` section doubles as a schema for the fields, matching the `suggestion-conductor`
fixed-output pattern.

## AskUserQuestion Max-4 Rule in the Wizard

WHY Wizard Step B splits check selection across two `AskUserQuestion` calls (integrity
checks first, advisory second) when the user picks "Exclude specific checks": the
Claude Code `AskUserQuestion` tool caps at 4 options per call. Six check names exceed
that limit. Splitting into integrity (broken_up, dead_link, unparented, orphan) and
advisory (duplicate_stem, stale_moc) groups the checks by the same tier taxonomy the
report uses, which is cognitively consistent for the user.

## Marker-Based First-Run Detection — `configured` Flag (v0.1.1, 2026-07-20)

WHY Step 3 changed from pure file-absence (`test -f`) to a `grep -q "^configured:
true"` pattern: the create-only seed (ADR-2, CON-4) always ships the file at
`config/garden-audit-exclusions.yaml` with `configured: false`. A fresh or updated
instance therefore always has the file present, so `test -f` returned `exists` and
the first-run wizard never triggered. The `configured` boolean marker distinguishes
"seeded-but-unconfigured" from "user-configured" without requiring the agent to parse
YAML (which would be fragile LLM-mediated). The grep pattern `^configured: true` is
line-anchored to avoid false positives from comment text or nested values.

WHY the wizard always writes `configured: true` even when the user confirms no
exclusions: without it, every subsequent audit re-triggers the wizard (grep finds no
match → first-run), forcing the user through Q&A every time. Writing `configured:
true` + `exclusions: []` is the correct "intentionally empty" signal.

WHY the agent uses `grep` instead of parsing the YAML value: the pattern is sufficient
and robust for a boolean flag. The `GardenExclusions` loader ignores the `configured`
key (it reads only `exclusions`), so there is no risk of the loader interfering with
the marker. The schema accepts `configured: boolean` as an optional property (added
2026-07-20).

## Version 0.1.0 → 0.1.1

WHY 0.1.0: Initial spec-030 Phase 5 implementation. The agent was authored against the
`moc-architect` STRICT/MUST/NEVER style to ensure runtime-deviation-critical paths
are guarded. `update-tomo.sh` skips unchanged versions; the agent is in the container's
`.claude/agents/` and loads at session start.

WHY 0.1.1: Marker-based first-run detection (`configured` flag). Step 3 rewritten
from `test -f` to `grep -q "^configured: true"` to fix the seed-defeats-wizard bug.
Wizard Step D updated to always emit `configured: true`.

## Suggest Mode Re-uploads BOTH Artifacts (v0.7.0, 2026-07-23)

WHY S.4 now re-uploads the wire `.json` alongside the report (superseding the earlier
"Do NOT re-upload the wire — the wire is unchanged"): that sentence predated
`garden-audit-suggest.py` 0.3.0, which started writing `decision.candidates` (and, since
0.4.0, the `decision.suggested` ran-marker) into the wire. With the old rule, the enriched
wire never reached the vault — the Tomo-Editor's candidate chips and "no suggestions found"
state (Hashi spec-005 T5.3/T5.4) could never see data in a real `--suggest` round-trip
(2026-07-23 Hashi handoff, Gap B).

WHY the S.3 stop rule is "`N` = 0 → stop" against the NEW count (processed findings, not
markdown `Pick one` lists): a requested finding with zero candidates still changes both
artifacts (no-suggestions note + `suggested` marker) and MUST be uploaded — under the old
"Pick one"-count, such runs read `N=0`, the agent stopped, and the enrichment was silently
dropped (Gap C). `N` > 0 with `M` = 0 is explicitly called out as a valid proceed-case in
the runtime file because an LLM reading "0 with candidates" plausibly reasons "nothing to
upload" and stops — the imperative pre-empts that deviation.

WHY the Mode:suggest output block emits `Wire: <WIRE_VAULT> (enriched)` (was `(unchanged)`):
the fixed output block is PRD-locked shape; the annotation now reflects that the wire is a
first-class enriched artifact of suggest mode.

## Silent verification + no-preamble output block (v0.8.0, 2026-07-25)

WHY Step 7 + the `## Verification` intro now forbid ANY prose before the output block and mark
the verification checks as silent: a live run narrated "All verification checks passed. Here is
the fixed output block:" — the LLM echoed the internal step name (`## Verification`) and the
internal term "fixed output block" as a user-facing preamble. The old spec only said "no prose
AFTER it", leaving a lead-in sentence unguarded, and used "fixed output block/report" as an
imperative the model parroted. Fix: the final message is EXACTLY the block, no lead-in, never
announce verification or name the block; the mode-step imperatives dropped "fixed" ("emit the
output block") to lower parrot risk. The observed bad string is quoted in the STRICT `Why:` so the
guard's failure mode is self-documenting (guardrails: STRICT blocks carry the one-line why).

## Bare /garden-audit auto-detects a suggest run (v0.9.0, 2026-07-25)

WHY Step 1 rule 3 now runs `garden-audit-detect-suggest.py` instead of grepping the markdown for a
`- [x] Suggest targets` box (and dropped the enrich-vs-fresh AskUserQuestion): the Tomo-Editor
writes suggest requests to the WIRE (`suggest_pending`), never the markdown box, so the old
markdown grep missed every editor-driven request and bare `/garden-audit` fell through to a fresh
scan. Design intent (user, 2026-07-25): bare `/garden-audit` RECOGNISES the suggest run and runs it
directly (no ask); `--suggest`/`suggest` is the identical force alias; `/garden-audit audit` forces
a fresh scan. Step S.1 no longer asks the user which report — it uses Step 1's detected path, or
re-runs the helper for an explicit token. See docs/tomo/scripts/garden-audit-detect-suggest.md for
the wire-vs-markdown and fail-open rationale.
