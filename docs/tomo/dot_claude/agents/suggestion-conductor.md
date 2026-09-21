# WHY: suggestion-conductor

> Rationale for decisions in `tomo/dot_claude/agents/suggestion-conductor.md`.

## Two Modes in One Agent (suggest + fan-resolve)

WHY: Both suggest and fan-resolve are analysis work — they dispatch inbox-analyst subagents to classify items and produce suggestions-family documents. Splitting them into separate agents would duplicate the shared-context build, fan-out dispatch, reduction, and rendering steps. The only differences are: (a) the input bucket (fresh_sources vs force_atomic_items), (b) the force_atomic flag on dispatch, and (c) the reducer's --fan-resolve flag. A single agent with a mode branch keeps the orchestration DRY while the routing plan's action field makes the branch deterministic.

## Impersonated, Not Dispatched

WHY: The conductor must run in the main session context because it needs the Agent tool to dispatch inbox-analyst and voice-transcriber leaf agents. The Anthropic platform prevents subagents (dispatched via the Agent tool) from using the Agent tool themselves — empirically confirmed: a dispatched agent's transcript shows "Agent tool is not available in this execution context." The only working dispatch depth is: main session (impersonated conductor) -> leaf agents. If the conductor were dispatched as a subagent, it would lose fan-out capability and fall back to serial processing.

## Opus for Leaf Agents, Sonnet for Conductor

WHY: The conductor is pure orchestration — it reads JSON, dispatches agents, calls scripts, and checks exit codes. This requires no deep reasoning and runs well on Sonnet. The inbox-analyst leaf agents perform the actual classification work (reading note content, reasoning about PKM categories, matching against the vault's MOC structure) which benefits from Opus-level reasoning quality. Since the conductor is impersonated (inherits the session model), its frontmatter `model: sonnet` serves as documentation of intent; the actual model used depends on the session. The leaf agents, dispatched via the Agent tool, DO honour their frontmatter model setting.

## Skills Instead of Inline Knowledge

WHY: The conductor contains only orchestration logic (routing, dispatch, branching, script calls). All domain knowledge — lifecycle state rules, suggestions doc format, force-atomic handling patterns, Kado query recipes — lives in skills that are lazy-loaded via the frontmatter `skills:` list. This satisfies AC-9 (conductors contain only orchestration logic) and keeps the agent spec small (~150 lines vs the legacy orchestrator's 760). Skills are also reusable across conductors — both suggestion-conductor and synthesis-conductor load routing-plan-consumer.

## Voice Transcription as Step 2 (Before Run-ID)

WHY: Voice transcription runs before generating the run-id and building shared context because it may produce a stop-gate (new transcripts created -> exit for user review). Generating the run-id and building shared context are expensive operations that would be wasted if the stop-gate fires. Placing voice first short-circuits the pipeline when audio needs human review.

## Vault Writes via mcp__kado__kado-write

WHY: The conductor writes suggestions/fan documents to the vault. These are markdown files that must go through Kado's permission chain (the security model). The `mcp__kado__kado-write` MCP tool with `operation: "note"` is the correct interface for markdown vault writes. Using Bash heredocs or the local Write tool would bypass Kado's ACL and feature gates. The conductor reads the rendered markdown via the Read tool, then passes the content to kado-write — the same pattern the legacy inbox-orchestrator used.

## mark-captured Runs Immediately After Vault Write

WHY: Source items must be tagged as `tomo.state=captured` immediately after the suggestions doc is written to vault. If this step is deferred or skipped, the next /inbox run will re-discover the same sources as "new" and produce duplicate suggestions. The mark-captured script uses KadoClient.write_frontmatter(mode='merge') which is idempotent — re-running it on already-captured items is a no-op, not an error.

## No Resume Logic in the Conductor

WHY: The legacy inbox-orchestrator contained resume detection (Phase 0b) with AskUserQuestion branching. In the 018 redesign, resume state is handled by inbox-triage.py before the conductor is ever invoked. The triage script inspects the state file, determines whether work remains, and either routes to the conductor with the appropriate action or reports idle. The conductor always runs a fresh pipeline from the routing plan's work buckets.

## No State-Promotion in the Conductor

WHY: The legacy inbox-orchestrator contained state-promotion logic (Phase A2.5e) that scanned pending docs, checked approval checkboxes, dispatched instruction-builder, and flipped states. In the 018 redesign, all of this moves to inbox-triage.py (checkbox scanning, approval detection) and synthesis-conductor (instruction building, state flipping). The suggestion-conductor only handles the analysis side — producing suggestions and fan documents from unclassified sources.

## Why the conductor runs no setup of its own

The agent used to carry a "Step 2 — Common setup" that built `tomo-tmp/items`,
pulled a RUN_ID, ran `shared-ctx-builder.py` and read two config fields. Both
skills it branches to — `suggest-handling` and `force-atomic-handling` — carry
the same setup at their own step 2. The agent's copy was therefore never the
one that counted.

It was worse than redundant. `suggest-handling` opens with
`rm -rf tomo-tmp/items tomo-tmp/inbox-state.jsonl`, so everything the agent
had just produced was deleted, and the RUN_ID the agent captured was
superseded by a second one seconds later. A live run on 2026-09-14 shows both
values printed to the user — `…09-28-49Z-3f655f` and `…09-29-05Z-995f74` — and
`shared-ctx-builder.py` walking the vault twice, which is what pushed that run
into a Kado `HTTP 429`.

Nothing downstream was corrupted, because the second setup won cleanly and the
whole pipeline used its RUN_ID. The cost was a doubled Kado budget and a log
that reads as though the run restarted itself.

**Why removal rather than removing it from the skills.** The skill is where the
flow lives: it knows whether it needs `BATCH_SIZE` (suggest does, fan-resolve
does not), it owns the deletion that must precede the setup, and it is the unit
that gets loaded when the action is known. The agent is a router — it reads the
routing plan and picks a skill. A router that also does the work has to be kept
in sync with two skills forever.

The replacement is a `STRICT` telling the agent to run no setup commands at
all. Without it the removal reads as an omission, and an LLM that has just been
told "the skill has the complete pipeline" still tends to prepare the ground
first.
