# WHY: tomo-lifecycle-states

> Rationale for decisions in `tomo/dot_claude/skills/tomo-lifecycle-states/SKILL.md`.

## State Machine as Reference Skill

WHY: The Tomo lifecycle state machine (F-47) is the foundation of the entire inbox pipeline — triage routes based on state, conductors flip state, and the user sees state reflected in their vault. Before this skill existed, each agent carried its own partial copy of valid states and transitions, leading to drift (one agent recognized a state another didn't). The skill is the single source of truth for "which doc types exist, what states are valid, and what transitions are allowed." It is loaded by any agent or conductor that reads or writes lifecycle state.

## State-Promoter as Only Write Path

WHY: The skill documents state-promoter.py as the exclusive mechanism for state transitions. Direct frontmatter edits (even via KadoClient.write_frontmatter) could produce invalid transitions — e.g. jumping from `captured` to `applied` without going through the approval flow. State-promoter validates the transition against the state machine, checks the approval checkbox before flipping to terminal states, and retries on optimistic-concurrency failure. Agents are told to call the script, never to build frontmatter themselves. This is the enforcement mechanism for the ADR-5 rule (F-47): "every frontmatter mutation routes through write_frontmatter(mode='merge')."

## Strict Equality Caveat on byFrontmatter Queries

WHY: The skill includes query recipes that fan out to separate byFrontmatter calls per state value rather than using wildcards. This is a Kado platform constraint — byFrontmatter is strict equality only, no glob or prefix matching. `tomo.state=pending-*` returns zero hits. The fan-out pattern (one call per known state, merge client-side) is the documented workaround, and STATE_MACHINE is the authoritative list of values to query.

## check-tick Before State Flip

WHY: The `check-tick` subcommand exists because the approval checkbox is a user-facing signal in Obsidian, but frontmatter state is the machine-facing truth. They can diverge — a user might tick the checkbox but the pipeline hasn't run yet, or the pipeline might run before the user ticks. check-tick returns exit codes (0 = ticked, 10 = not ticked, 11 = unreadable) so the conductor can branch deterministically. Flipping state without checking the checkbox would bypass user approval, violating the 2-pass model (Tomo proposes, user approves).

## No build_tomo_block in Agent Context

WHY: The skill explicitly states that "direct calls to build_tomo_block are not needed from agent context." This is because state-promoter.py internally calls build_tomo_block and write_frontmatter — the agent should not duplicate this logic. Exposing build_tomo_block to agents invites improvisation where the LLM constructs partial frontmatter blocks, which is the exact failure mode that caused the frontmatter_newline_guard bug class (ADR-5, F-47).
