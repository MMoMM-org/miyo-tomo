# WHY: kado-discovery-patterns

> Rationale for decisions in `tomo/dot_claude/skills/kado-discovery-patterns/SKILL.md`.

## Recipes as Scripts, Not MCP Tool Calls

WHY: The skill teaches agents to write Python scripts that use KadoClient rather than calling MCP tools directly. This is a deliberate choice: MCP tool calls from agent context go through the Claude Code permission layer, which prompts the user for each call. A Python script using KadoClient makes the same HTTP calls but runs as a single Bash invocation — one permission prompt for the entire batch. For fan-out patterns that query N states, this reduces N permission prompts to 1. The "write a script to tomo-tmp/, then run it" pattern is the standard Tomo approach for any multi-step Kado interaction.

## Caching Pattern for Batch Reads

WHY: The caching pattern (read via Kado, write to tomo-tmp/inbox-cache/, build manifest.json) exists because Kado calls are expensive — each one is an HTTP roundtrip through the MCP gateway to Obsidian. The triage script (inbox-triage.py) already reads every relevant doc once and caches the bodies. The caching recipe in this skill is for agents that need to do ad-hoc discovery outside the triage pipeline (e.g. vault-explorer, moc-architect). The manifest with checksums enables drift detection: re-read and compare to detect vault edits since the cache was built.

## Error Handling — Skip and Continue, Not Abort

WHY: The error handling pattern catches KadoError per-item and continues the batch rather than aborting. This is because vault state is inherently racy — a user might rename or delete a note between the listing call and the read call. Aborting the entire batch because one note was moved would force the user to re-run the pipeline. Logging the error and continuing means the pipeline processes everything it can and reports the skips. The only exception is KadoConnectionError (Kado server unreachable), which aborts immediately because no further calls will succeed.

## Strict Equality Caveat — Repeated from tomo-lifecycle-states

WHY: The byFrontmatter strict-equality constraint is documented in both this skill and tomo-lifecycle-states. This is intentional redundancy — kado-discovery-patterns is loaded for general Kado queries (not just lifecycle), and an agent loading only this skill (without tomo-lifecycle-states) still needs to know the wildcard limitation. The tomo-lifecycle-states skill focuses on what values to query; this skill focuses on how to query.

## Outside inbox-triage.py Scope

WHY: The skill description says "Load when making Kado discovery calls outside of inbox-triage.py." This boundary exists because inbox-triage.py is the authoritative discovery mechanism for the /inbox pipeline — it handles all standard queries (fresh sources, pending approvals, state scanning). The skill is for agents that need vault access for non-pipeline purposes: vault-explorer building a vault map, moc-architect scanning MOC structures, or any future agent that queries the vault ad-hoc. Loading this skill inside the /inbox pipeline would duplicate logic that inbox-triage.py already handles deterministically.
