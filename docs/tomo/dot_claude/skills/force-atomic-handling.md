# WHY: force-atomic-handling

> Rationale for decisions in `tomo/dot_claude/skills/force-atomic-handling/SKILL.md`.

## Self-Contained Sub-Flow

WHY: Force-atomic handling was originally inline logic in the monolithic inbox-orchestrator. During the 018 refactor it became a skill rather than a separate agent because it shares all infrastructure with the suggest flow — same shared-ctx build, same inbox-analyst dispatch, same reducer, same renderer. The only differences are: (a) the input bucket (`force_atomic_items` instead of `fresh_sources`), (b) the `force_atomic=true` flag on dispatch, and (c) the `--fan-resolve` flag on the reducer. A separate agent would duplicate the entire pipeline setup. A skill that the suggestion-conductor loads conditionally (only when `action == fan-resolve`) keeps the pipeline DRY.

## v0.3.0 Path Fix — Original Note, Not Suggestions Doc (superseded by v0.6.0)

WHY: The routing plan's `force_atomic_items[].source_path` points to the suggestions doc that contains the ticked checkbox, not the original inbox note. But inbox-analyst needs to read the original note (to classify its content), not the suggestions doc (which contains Tomo's analysis). v0.2.0 passed `source_path` directly, causing analyst to classify the suggestions doc's own analysis text — a feedback loop. v0.3.0 constructed the path as `<inbox_path>/<stem>.md` from the routing plan's `inbox_path` field and the item's `stem`. That diagnosis was right and that remedy was wrong: it only ever produced a real file while the inbox was flat. Under recursive discovery (spec 034) `100 Inbox/Places/Dresden.md` reconstructs to `100 Inbox/Dresden.md`, which does not exist — so Force Atomic was broken for every subfolder note, name clash or not. v0.6.0 replaces the reconstruction with the item's real path, carried in the routing plan. The STRICT block stays, because the hazard it names is unrelated to how the path is obtained: "source_path in the routing plan is the suggestions doc — NEVER use it as path."

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

WHY both lines are spelled `<item_key>` (v0.6.0): the two must stay
byte-identical, and the cheapest way to guarantee that is to give them one
source. ADR-1 makes the item key the note's vault-relative path verbatim, so
`item_key` IS the path — there is nothing to convert between the two lines, and
no second placeholder that could drift from the first. It also keeps
`force_atomic_items[]` at its existing three fields: a separate `path` field
would carry the same bytes under a second name, which is the duplication ADR-2
exists to prevent.

## v0.6.0 — The Path Is Carried, Not Reconstructed (spec 034 T4.1)

WHY the reconstruction had to go rather than be widened: there is no widening
available. `<inbox_path>/<stem>.md` is a guess at a location, and once the inbox
has subfolders the guess is wrong for every note that is not at the root. Any
variant of the guess is still a guess. The only correct answer is the path the
pipeline already knows, so `inbox-triage.py` now resolves it at extraction time
and puts it in `force_atomic_items[*].item_key`, and the skill reads it there.

WHY this also closes T2.1's inherited debt: T2.1 had to set `item_key` to the
REVIEW DOCUMENT's path, because that was the only path in scope at
`_extract_fan_items` / `_extract_fan_items_from_wire`. That made two FAN items in
one suggestions document share one key — a field holding something its name does
not describe (the exact hazard ADR-2 names). Nothing joined on it yet, so no
merge bug was live; the fix lands before one could be.

WHY the extraction sites can resolve a path at all, when the FAN checkbox carries
only a bare `Source: [[stem]]`: the run's single recursive inbox listing (ADR-3)
is already indexed by basename for attachment resolution, and `discover()` hands
that same index to `read_approval_state`. A stem resolves through it the way an
attachment target does — basename lookup, then narrowing when the reference is
path-qualified — so there is one resolution shape in this script, not two.
Spec 034 T5.1 will path-qualify source links on collision; the resolver already
accepts that form, so nothing here changes when it lands.

WHY an ambiguous reference declines instead of picking: two inbox notes named
`Dresden.md` make `Source: [[Dresden]]` genuinely unable to say which one is
meant. First-match-wins would rebuild, one layer up, the exact collision this
spec removes — and it would do it silently, writing a proposal from the wrong
note's content. PRD Business Rule 7 settles it: decline rather than choose.

WHY the decline is announced on stderr with the `[triage]` prefix: an approved
item that is never built, with nobody told, is the same class of defect as
building the wrong one. The line names the review document, the reference and
the number of candidates, so the user can act on it — rename one note, or
path-qualify the link. This matches how unresolved and ambiguous attachment
embeds are already reported by the same script.

WHY a FAN item whose note is not in the inbox listing also declines: the note it
names is gone (moved, renamed or already consumed). Reconstructing a path for it
would name a file that does not exist, which is where this whole defect started.

## WHY There Is No Cost-Recording Step Here (spec 034 T6.1)

A `fan-resolve` run's cost-history entry is written by
`suggestions-reducer.py` in step 4 (`--fan-resolve`), not by a step of its own.
This skill briefly gained a terminal step for it — this flow had no
state-writing step at all — and it was removed for the same reason it should
never have been added: a step in this file is executed by an LLM, and no test
can see whether it ran.

Do not re-add one. `inbox-triage.py` writes no entry for this action, so a
second append here would double-record the run. See
`docs/tomo/scripts/lib/cost_history.md`.
