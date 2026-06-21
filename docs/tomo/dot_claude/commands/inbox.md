# WHY: inbox (command)

> Rationale for decisions in `tomo/dot_claude/commands/inbox.md`.

## Command is a Thin Router, Not an Orchestrator

WHY: The `/inbox` command file contains only three steps: run triage, read the routing plan, branch on action. All routing computation happens inside `inbox-triage.py` — the command is purely a consumer of the result. Earlier versions of the command contained their own auto-discovery logic (scanning markdown body for checkboxes, reading suggestion docs via Kado) and heuristics for deciding between Pass 1 and Pass 2. That logic was duplicating work the triage script already does, creating two independent sources of truth that could diverge. The router design eliminates the divergence by making triage the single routing computation (AC-4).

## Single Triage Call Before Any Dispatch

WHY: Routing must be deterministic. A single `inbox-triage.py` call produces `routing-plan.json` which the command reads once. The previous auto-discovery pattern ran multiple Kado calls (listDir, per-file reads) before deciding which agent to impersonate. Those calls had latency, could return inconsistent results between calls, and wasted tokens. The triage script consolidates all discovery into one invocation and outputs a structured plan the command can read cheaply with a local JSON parse.

## Impersonate Conductors, Never Dispatch Them

WHY: Both `suggestion-conductor` and `synthesis-conductor` must be impersonated by the main session, not dispatched as subagents. The Anthropic platform does not allow nested agents to use the `Agent` tool. When a conductor is dispatched as a subagent, its execution context lacks the `Agent` tool and it cannot dispatch leaf agents (inbox-analyst, voice-transcriber). Impersonation keeps the main session in control of all `Agent` tool dispatches. This is a hard 1-level nesting limit: main session dispatches leaf agents only.

## Transcribe Bypasses Conductors (Stop-Gate)

WHY: The `transcribe` action dispatches `voice-transcriber` directly from `/inbox` without going through any conductor. The reason is UX: audio transcription is a blocking pre-condition. Until transcripts exist, there is no text content for inbox-analyst to classify. Running the suggestion-conductor would either fail silently (no sources) or produce empty output. The stop-gate pattern makes the dependency explicit — transcribe, then re-run `/inbox` — instead of hiding a silent no-op behind a conductor invocation.

## Idle Surfaces Reasons to User

WHY: When the triage script determines there is nothing to process, the command reads `idle_reasons` and `pending_approval` from the routing plan and reports them directly to the user. This preserves the user's ability to understand why nothing happened. Earlier versions of the command impersonated the orchestrator unconditionally and relied on the orchestrator's own early-exit to surface "inbox is empty" — but that early-exit message was buried in orchestrator output and easy to miss. The idle branch in the router surfaces the reasons at the command level where they are immediately visible.

## Orphaned-State Drift Is Surfaced Prominently (#37)

WHY: `inbox-triage.py` emits an `orphaned_state` drift indicator when source items are marked `tomo.state=captured` but every downstream doc (suggestions / instructions) has vanished — typically a suggestions doc deleted before approval, which strands the Pass-1 analysis. Triage routes such a state to `idle`, so without explicit surfacing the loss would be silent. The command lifts the indicator's `detail` out of the generic warning list and pairs it with a `/inbox --recover` recommendation. It is advisory, not action-changing: a fully-applied-then-archived batch whose captured source items still linger in the inbox is indistinguishable from a genuinely orphaned one (source items have a single terminal state and Tomo never moves them out of the inbox), so the user — not the router — decides whether to recover.

## --pass1/--pass2/--force/--recover Are Flag Passthroughs to Triage

WHY: Force flags are passed through to `inbox-triage.py` (`--pass1` → `--force-pass1`, `--pass2` → `--force-pass2`, `--force` → `--force`, `--recover` → `--recover`). The triage script owns the override logic and produces the correct routing plan regardless. The command does not need to interpret these flags itself — it just forwards them and routes on whatever action the triage script decides. This keeps the override semantics in one place (triage) rather than split between the command and the script.

## --pass2 Is Coverage/Drift-Respecting; --force Is the Sledgehammer (#78)

WHY: `--pass2` re-runs the synthesize phase but only for approved docs that are genuinely uncovered or content-changed (drifted) — if everything is already covered and unchanged, it resolves to `idle` rather than re-rendering an applied instruction set into a duplicate. This is the behavior users expect from "do Pass 2 again": redo what changed, not everything. The earlier behavior mapped `--pass2` to an unconditional synthesize that ignored coverage, which produced byte-for-byte duplicate instruction sets on a second run (live-walk finding 2026-06-20). `determine_action` now phase-selects pass2 (short-circuiting transcribe/suggest) but returns `synthesize` only when `to_process` is non-empty, else `idle`.

`--force` is a MODIFIER, not a standalone sledgehammer, so the flag matrix is symmetric and complete (each phase has a state-respecting form and a force-all form):

- `--pass1` = suggest phase, new sources only; `--pass1 --force` = re-suggest incl already-captured.
- `--pass2` = synthesize phase, coverage/drift-respecting (only changed); `--pass2 --force` = re-synthesize ALL approved, ignore coverage (this fills the "redo all of Pass 2 only" gap that a bare sledgehammer could not express).
- `--force` alone (no phase) = full rebuild: re-suggest (captured folded in) then synthesize.

Implementation: `determine_action` checks `--pass2` BEFORE the bare-`--force` branch, so `--pass2 --force` synthesizes (does not divert to suggest even when new sources exist); the captured-fold in `discover` is gated `force_all and not force_pass2` so `--pass2 --force` never re-intakes captured sources; and the work-list trim is skipped whenever `force_all` is set so all approved docs survive. `--recover` remains as a named convenience equivalent to `--pass1 --force`. The split exists because predictable recovery must be autonomous — the user picks "redo what changed" vs "redo all of a phase" vs "full rebuild" without Tomo having to ask.

WHY (drift baseline): drift is detected by comparing a recorded source checksum against the current doc. Both sides hash the doc BODY only (`lib.doc_frontmatter.body_after_frontmatter`), because `state-promoter` mutates the doc's `tomo:` frontmatter (state → approved, updated_at) after rendering. A frontmatter-inclusive hash would make every covered doc read as drifted on the next run, defeating coverage. Hashing the body means "drift" reflects a real content edit (approval, placement, item changes). This was inert until coverage came alive (#74) — empty `tomo.sources` meant detect_drift never ran.
