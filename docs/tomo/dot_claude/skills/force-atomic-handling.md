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

## The dispatch prompt passes `item_key` and never names the result file

WHY: the per-item result file is named `<readable>-<8 hex>.result.json`, derived
from the item's `item_key` by `lib/item_key.to_filename` (spec 034 ADR-5). This
block used to instruct `tomo-tmp/items/<stem>.result.json`, which the reducer no
longer reads — and because both this skill and `inbox-analyst.md` are LLM-loaded
verbatim, the two contradicting each other produced nondeterministic behaviour
rather than an honest failure. The instruction now points at the analyst's own
Step 10, which shells out to `scripts/item-result-filename.py`; one derivation,
one place to change it.

WHY `item_key` is passed even though it equals `path`: it is a declared input of
the analyst's IO Contract (ADR-1 makes derivation the identity function), and
the analyst must never reconstruct it from `stem` — two inbox items in different
subfolders share a stem and would collide on one result file.

WHY the value is spelled `<inbox_path>/<stem>.md` here rather than a bare
`<path>` placeholder: this flow rebuilds the path from the FAN log entry, and
`item_key` must stay byte-identical to the `path` line directly above it.
