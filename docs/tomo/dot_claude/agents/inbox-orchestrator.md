# WHY: inbox-orchestrator

> Rationale for decisions in `tomo/dot_claude/agents/inbox-orchestrator.md`. This file was created as part of
> XDD 018 (Inbox Routing Redesign) to preserve institutional knowledge before
> the legacy agent was replaced.

## Impersonation over Subagent Dispatch

WHY: The orchestrator must be impersonated by the main session — it cannot be dispatched as a subagent via the `Agent` tool. The Anthropic platform prevents nested agents from using the `Agent` tool themselves. When the orchestrator was dispatched as a subagent, its execution context lacked the `Agent` tool entirely, causing it to fall back to processing all inbox items serially in a single session. This destroyed the parallel fan-out that Phase B (batches of 3–5 concurrent `inbox-analyst` agents) depends on for performance. The only working dispatch depth is: main session → leaf agents (`inbox-analyst`, `voice-transcriber`). The orchestrator must live at the top level.

## Fan-out via Agent Tool, Never via Claude CLI

WHY: `inbox-analyst` subagents are dispatched via the `Agent` tool, never via `Bash(claude --agent-name ...)`. The CLI approach creates a separate OS process — it cannot share session state, is slower, more expensive in tokens, and requires user approval prompts. The `Agent` tool spawns in-process subagents that inherit MCP connections and run concurrently when dispatched in the same message. Concurrent dispatch is the entire point of fan-out.

## One Command per Bash Call — No Chaining

WHY: Claude Code's Bash validator rejects compound commands containing inline `python3 -c "..."` or `$(...)` substitutions and reports "Unhandled node type: string". This forces approval prompts on every such invocation, breaking unattended pipeline execution. Each pipeline step is a separate Bash tool call so each can be validated and approved independently. The `&&`, `;`, and `||` chaining operators are banned for the same reason.

## Never Redirect stderr into stdout on JSON-Captured Commands

WHY: Tomo's pipeline scripts (inbox-discovery, suggestions-reducer, instruction-render, etc.) intentionally print operational logs and warnings to stderr. When `2>&1` is appended to a command whose stdout is redirected to a file, those log lines land in the JSON file before the actual JSON blob. The script exits with code 0 (it succeeded), so the error only surfaces on the next step's `json.load` call as an opaque parse failure. The root cause becomes invisible. The fix is to leave stderr unredirected — the Bash tool surfaces stderr output directly in tool results where it is immediately visible to the orchestrator.

## Scratch Writes to tomo-tmp, Vault Writes via Kado Only

WHY: Vault files must only be written via the `mcp__kado__kado-write` MCP tool. Writing to vault paths via Bash heredocs or the `Write` tool would bypass Kado's permission chain — that chain is the security model, not an optional convenience. Scratch intermediates (parsed JSON, rendered markdown, state files) go under `tomo-tmp/` and use the local `Write` tool because they never enter the vault.

## Phase 0: Resolve Inbox Path First, Use Everywhere

WHY: The vault-relative inbox path varies per vault configuration and is stored in `vault-config.yaml`. Hardcoding `"Inbox"` or `"100 Inbox/"` in the agent would break any vault where the user configured a different path. Resolving it once in Phase 0 and threading the literal value through all subsequent phases (Phase 0a voice, Phase A discovery, Phase C write) prevents a second resolution from diverging from the first due to config changes during the run.

## Phase 0a: Voice Transcription Runs Before Resume Detection

WHY: Voice transcription (Phase 0a) runs before the resume-detection check (Phase 0b) so that newly-created transcripts are visible to all downstream phases regardless of whether this is a fresh run or a resume. If voice ran after resume detection, a resume run would discover the audio files but miss newly-produced transcripts that appeared after the interrupted run started.

## Phase 0a: Stop-Gate After Transcription

WHY: When new transcripts are produced, the run halts and asks the user to review them before processing. Audio transcripts frequently need human editing — the AI-produced text may misparse proper nouns, technical terms, or ambiguous speech. Treating unreviewed transcripts as ready-to-analyze would produce lower-quality suggestions. The user re-runs `/inbox` after editing, and the voice-precheck cache prevents re-transcribing already-processed audio.

## Phase 0a: Voice Failures Must Not Block Text Processing

WHY: Voice transcription is an opt-in feature. A broken transcription setup (missing API key, network timeout, unsupported codec) should not prevent the user from processing their text inbox items. Voice errors are logged to the summary file for the run report and the text pipeline continues normally. The inverse — aborting everything on a transcription failure — would make the voice feature a reliability tax on users who have it enabled.

## Phase 0b: AskUserQuestion for Resume vs Fresh Run

WHY: When a prior interrupted run is detected, the system cannot know whether the user wants to continue it or start over. Silently resuming could miss new inbox items that arrived after the interrupted run started. Silently restarting discards work already done and reprocesses items. Presenting the choice explicitly (Resume / Fresh run / Inspect) puts control in the user's hands. Plain text "reply yes/no" was rejected because it creates ambiguity about which choice is the affirmative one.

## Phase A: Skipped Entirely on Resume

WHY: Phase A builds shared context (a full vault scan via `shared-ctx-builder`) and runs inbox discovery. Both are expensive operations. On a resume run, the shared context from the interrupted run is still valid — the vault has not changed significantly in the interim — and the discovery results are already captured in the state file. Re-running Phase A on resume would waste tokens and API calls, and would also re-run state-promotion for docs that were already promoted, risking duplicate instruction-builder dispatches.

## Phase A: Truly-Empty Early Exit Before Shared-Context Build

WHY: Building shared context (`shared-ctx-builder`) performs a full vault scan — it is the most expensive operation in the pipeline. If discovery reveals that the inbox contains nothing this run can act on (no new sources, no pending-approval docs, no pending-accept docs, no captured docs), running the vault scan wastes tokens with no benefit. The early exit check runs after discovery and before the shared-context build, so the vault scan only happens when there is actual work to do.

## Phase A: State-Promotion Loop is Inline Orchestrator Logic, Not a Subagent

WHY: The state-promotion loop (A2.5e) is deterministic control flow — it reads item metadata, calls a state-check script, dispatches instruction-builder, and flips state. None of this requires LLM reasoning. Spawning a dedicated "state-promoter" subagent for each item would cost tokens proportional to the number of pending docs, introduce an extra agent-context boundary where state can be lost, and make error-handling more complex. Running it inline with Bash subprocess calls is cheaper, faster, and easier to reason about.

## Phase A: State-Promotion Processes Items Sequentially

WHY: Each item promoted in A2.5e gets a fresh instruction-builder dispatch that may write to the vault. Running promotions sequentially avoids concurrent writes to the same vault paths. An item promoted from `pending-approval → approved` must not be promoted again in the same run — sequential processing with a "promoted once" invariant makes this easy to enforce without coordination state.

## Phase B: State File is a Transition Log, Not a Seed

WHY: The `inbox-state.jsonl` file records status transitions written by `inbox-analyst` subagents during their execution. There is no seeding step that pre-populates "pending" rows before dispatch. An earlier design considered pre-seeding to allow simpler state queries, but it created a two-source-of-truth problem: discovery and the state file would both claim authority over which items need processing. The transition log approach keeps discovery as the single source for what needs processing and the state file as the record of what happened.

## Phase B: Batch Size Comes from Config, Not Hardcoded

WHY: The optimal number of concurrent subagents depends on the user's API tier, account rate limits, and vault size. Hardcoding a batch size would be wrong for some users. Reading from `tomo.suggestions.parallel` in `vault-config.yaml` lets the user tune this during install without touching the agent file.

## Phase B: 5-Minute Stuck Timeout

WHY: Subagents that hang (due to network issues, API timeouts, or model problems) would block the entire pipeline indefinitely if there were no timeout. Five minutes is long enough for a heavily-loaded API to recover and complete analysis of a typical inbox note. After timeout, the item is marked `failed` and the batch continues — it can be retried on resume.

## Phase C: Render Script is the Single Source of Truth for Document Format

WHY: If the orchestrator assembled the suggestions markdown itself, the document format would exist in two places: the render script (which was designed with explicit knowledge of all supported section types, field positions, and markdown conventions) and the orchestrator's LLM-generated template. LLMs drift from format specs silently. Using the render script deterministically eliminates the drift risk and ensures that format changes only need to happen in one place.

## Phase C5: Mark-Captured Runs Immediately After kado-write

WHY: The `mark-captured` step writes `tomo.state=captured` to each source note that was processed in this run. If the orchestrator were to defer this step or skip it, source items would remain in `tomo.state=new` and be re-processed in the next `/inbox` run, producing duplicate suggestions. The step is mandatory and must run in the same phase as the vault write. The error policy is permissive (report but do not abort) because the user can rerun the script manually; skipping it entirely would require a new Pass-1 run.

## Phase D: Suppress Voice Status for Non-Voice Users

WHY: Users who do not have voice transcription enabled should not see voice-related status lines in the run report. The conditional suppression based on `reason: "disabled"` and `reason: "no_audio"` keeps the report focused on what the user actually used. Showing "0 audio files transcribed" to a non-voice user adds noise and implies a feature they never enabled.

## Phase D: Parallel-Instructions Warning When Multiple Docs Pending

WHY: When multiple instruction documents are waiting to be applied, the user must apply ALL of them — applying only one leaves the vault in a partially-updated state that may be inconsistent (e.g. links added for notes that do not exist yet because a second instructions doc was not applied). The warning is emitted with the full path list and the explicit "Apply ALL of them" text. Path truncation is forbidden because a truncated list would hide instructions docs the user needs to process.

## jq Slurp Flag (-s) on JSONL Files

WHY: The state file `inbox-state.jsonl` is a JSONL file — one JSON object per line — not a JSON array. The `jq group_by` function requires all entries to be in a single array to group correctly across lines. Without the `-s` (slurp) flag, `group_by` runs per line and produces incorrect per-line groupings, making status aggregation silently wrong. Every jq query against the state file must use `-s` or `-rcs`.

## Discovery JSON as Phase B Input for Fresh Runs

WHY: Fresh runs read the items-to-dispatch list from `discovery.json`, which Phase A produced. Resume runs read from the state file instead, because items were seeded from discovery in the interrupted run and some may have already reached `done` — the state file has the current status. Using discovery for resume runs would re-dispatch already-completed items.

## --recover Flag Requires Explicit User Initiation

WHY: Tomo cannot automatically detect whether captured notes with no associated workflow doc are "drift" (something went wrong) or "steady state" (Hashi cleaned up the workflow doc after apply, and the notes are already processed). Auto-recovery would risk re-generating suggestions for already-processed items, resulting in duplicate workflow documents. The `--recover` flag puts the user in control of the decision.
