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

## --pass1/--pass2/--force/--recover Are Passed to Triage Verbatim (spec 039 T6.3, v0.20.0)

WHY: Step 1 runs `python3 scripts/inbox-triage.py $ARGUMENTS`; Claude Code substitutes `$ARGUMENTS` before the model sees the command, so the model has no flag to translate. `inbox-triage.py` accepts `--pass1`/`--pass2` as aliases of its `--force-pass1`/`--force-pass2` options (same destination), so the owner's words ARE triage's words. The triage script owns all override logic; the command forwards and routes on whatever action triage decides.

Why the translation was removed: live run 2026-10-13, the owner typed `/inbox --pass2 --force` twice and the model ran `inbox-triage.py --force-pass2`, dropping `--force`. The option name `--force-pass2` reads as "pass 2 plus force", so the model treated `--force` as already expressed. Without force, `determine_action` respects coverage and an already-rendered doc routes to `idle` -- so the before-apply remedy spec 039 prints in every withheld-attachment line (SDD K16) silently did nothing.

Why pass-through over a STRICT block telling the model to keep `--force`: a STRICT is a request to a model; pass-through removes the step where the model can err at all. Deterministic, and the owner's decision.

A flag triage does not know (a typo, `/inbox pass2`) is rejected by argparse: exit code 2 and a usage line on stderr, no `routing-plan.json` is written. The command's Bash step fails visibly in the transcript; there is no silent fallback to a default run.

## --pass2 Is Coverage/Drift-Respecting; --force Is the Sledgehammer (#78)

WHY: `--pass2` re-runs the synthesize phase but only for approved docs that are genuinely uncovered or content-changed (drifted) — if everything is already covered and unchanged, it resolves to `idle` rather than re-rendering an applied instruction set into a duplicate. This is the behavior users expect from "do Pass 2 again": redo what changed, not everything. The earlier behavior mapped `--pass2` to an unconditional synthesize that ignored coverage, which produced byte-for-byte duplicate instruction sets on a second run (live-walk finding 2026-06-20). `determine_action` now phase-selects pass2 (short-circuiting transcribe/suggest) but returns `synthesize` only when `to_process` is non-empty, else `idle`.

`--force` is a MODIFIER, not a standalone sledgehammer, so the flag matrix is symmetric and complete (each phase has a state-respecting form and a force-all form):

- `--pass1` = suggest phase, new sources only; `--pass1 --force` = re-suggest incl already-captured.
- `--pass2` = synthesize phase, coverage/drift-respecting (only changed); `--pass2 --force` = re-synthesize ALL approved, ignore coverage (this fills the "redo all of Pass 2 only" gap that a bare sledgehammer could not express).
- `--force` alone (no phase) = full rebuild: re-suggest (captured folded in) then synthesize.

Implementation: `determine_action` checks `--pass2` BEFORE the bare-`--force` branch, so `--pass2 --force` synthesizes (does not divert to suggest even when new sources exist); the captured-fold in `discover` is gated `force_all and not force_pass2` so `--pass2 --force` never re-intakes captured sources; and the work-list trim is skipped whenever `force_all` is set so all approved docs survive. `--recover` remains as a named convenience equivalent to `--pass1 --force`. The split exists because predictable recovery must be autonomous — the user picks "redo what changed" vs "redo all of a phase" vs "full rebuild" without Tomo having to ask.

WHY (drift baseline): drift is detected by comparing a recorded source checksum against the current doc. Both sides hash the doc BODY only (`lib.doc_frontmatter.body_after_frontmatter`), because `state-promoter` mutates the doc's `tomo:` frontmatter (state → approved, updated_at) after rendering. A frontmatter-inclusive hash would make every covered doc read as drifted on the next run, defeating coverage. Hashing the body means "drift" reflects a real content edit (approval, placement, item changes). This was inert until coverage came alive (#74) — empty `tomo.sources` meant detect_drift never ran.

## Why IMPERSONATE is defined at the routing table

The routing table has always said `IMPERSONATE suggestion-conductor`, and the
rule explaining what that word means sat at the very bottom of the file, past
the `Exit.` of the idle branch — roughly seventy lines after the decision it
governs.

A runtime file is read line by line as the work proceeds. On 2026-09-14 the
command reached the table, saw an unfamiliar verb next to an agent name, and
did the obvious thing: `Agent(subagent_type: "suggestion-conductor")`. Four
records later it caught itself — *"the routing table calls for impersonating
… let me stop that dispatch"* — and killed the task. By then the subagent had
loaded all seven of its skills, deleted `tomo-tmp/items` and drawn a RUN_ID.

The definition now sits directly under the table, with its counterpart for
DISPATCH beside it. The trailing block was deleted rather than left in place:
two statements of the same rule in one file is the state that let this one go
stale at a distance from what it governs.

Both halves are stated, not just the one that failed. A rule that names only
the exception reads as a special case; naming both makes `Agent()` for the
conductor and no-`Agent()` for the synthesis path a single distinction the
reader can apply.

## Step 3b Passes the Conductor's Report Through Unchanged (spec 039 T6.3, v0.19.0)

WHY Step 3b carries a STRICT block instead of "Report the output".

The live Pass 2 run of 2026-10-13 had two paraphrase layers. The
synthesis-conductor reworded the withheld-delete and withheld-attachment relay
lines into its own bullets (fixed in its Step 4), and then this command's
Step 3b reworded the report again into a table. Each layer dropped the remedy
sentence the relay line carries, so the owner saw what was withheld but not
what to do about it.

"Report the synthesis-conductor's output to the user" was the unadorned
imperative and it was observed to fail, which is what justifies a STRICT block
here. It requires the report to be output unchanged and every line beginning
`- ⚠️ **` to be copied character for character, one per line, with no table,
summary, or commentary standing in for them. A model can "pass the report
through" and still reformat the `- ⚠️ **` lines, so the block names those lines
by their literal prefix rather than leaning on the word "unchanged" alone.

Single source for the shell relay: SDD K16; traceability F2-AC5. Test:
`test_inbox_passes_the_conductor_report_through_unchanged` in
`tests/test_039_t5_1_reporting.py`.

