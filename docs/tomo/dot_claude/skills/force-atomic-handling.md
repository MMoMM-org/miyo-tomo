# WHY: force-atomic-handling

> Rationale for decisions in `tomo/dot_claude/skills/force-atomic-handling/SKILL.md`.

## Self-Contained Sub-Flow

WHY: Force-atomic handling was originally inline logic in the monolithic inbox-orchestrator. During the 018 refactor it became a skill rather than a separate agent because it shares all infrastructure with the suggest flow — same shared-ctx build, same inbox-analyst dispatch, same reducer, same renderer. The only differences are: (a) the input bucket (`force_atomic_items` instead of `fresh_sources`), (b) the `force_atomic=true` flag on dispatch, and (c) the `--fan-resolve` flag on the reducer. A separate agent would duplicate the entire pipeline setup. A skill that the suggestion-conductor loads conditionally (only when `action == fan-resolve`) keeps the pipeline DRY.

## v0.3.0 Path Fix — Original Note, Not Suggestions Doc

WHY: The routing plan's `force_atomic_items[].source_path` points to the suggestions doc that contains the ticked checkbox, not the original inbox note. But inbox-analyst needs to read the original note (to classify its content), not the suggestions doc (which contains Tomo's analysis). v0.2.0 passed `source_path` directly, causing analyst to classify the suggestions doc's own analysis text — a feedback loop. v0.3.0 constructs the correct path as `<inbox_path>/<stem>.md` from the routing plan's `inbox_path` field and the item's `stem`. The STRICT block in the skill enforces this: "source_path in the routing plan is the suggestions doc — NEVER use it as path."

## Common Setup Before Fan-Out

WHY: The STRICT block requiring all setup commands (mkdir, run-id, shared-ctx, profile) before dispatching any subagent exists because the fan-out dispatch is parallel. If setup ran interleaved with dispatches, a race condition could produce shared-ctx.json while an analyst is already reading it (partial file). Sequential setup → parallel dispatch eliminates the race.

## Fan-Specific Reducer and Renderer

WHY: The `--fan-resolve` flag on suggestions-reducer.py produces a separate JSON document (suggestions-fan-doc.json) rather than appending to the primary suggestions output. This is intentional — fan resolutions are a companion artifact, not a modification of the original suggestions. The user reviews them side-by-side in Obsidian. Merging them would destroy the audit trail of what was originally suggested vs. what was expanded via force-atomic analysis.

## Vault Write as Timestamped Fan Doc

WHY: The fan output is written to `<inbox_path>/<YYYY-MM-DD_HHMM>_suggestions-fan.md` — a timestamped companion file. This follows the same naming convention as primary suggestions docs, making them sort chronologically in the inbox folder. The timestamp prevents collisions when multiple fan-resolve runs happen on the same day.
