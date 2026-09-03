# Troubleshooting — Tomo
<!-- Known issues and proven fixes. Updated: 2026-07-03 -->
<!-- Format: ## [Issue title] — Status: open/resolved — [fix description] -->
<!-- Resolved entries are archived by /memory-cleanup, not deleted. See archive/YYYY-MM/ -->

<!-- 2026-05-01 -->

## `instruction-render.py:1254` `read_template("asset")` auto-renders the asset block — Status: open

`read_template("asset")` is a Fallstrick: any caller reading the asset template inadvertently emits the rendered result, even when only the template structure was needed. Side effect is invisible from the call site. Action: separate template-read from template-render, or rename the function to make the side effect explicit (`render_asset()` vs `read_asset_template()`). Surfaced 2026-05-01 during `/inbox` Pass 2 debugging.

## Pipeline field-drop pattern: `result.json → suggestions.md → instructions.json` — Status: open

When a new field flows through the Pass-2 pipeline, every transformation stage must explicitly preserve it. Today `position` was dropped at the suggestions-reducer step, then re-emitted only via post-fix patching. Risk: every new field added upstream silently disappears unless the reducer + parser are updated in lockstep. Mitigation: write a fields-contract document (which fields each pipeline stage must passthrough) and add a regression fixture that exercises every passthrough field. Surfaced 2026-05-01 (`link_to_moc.position` regression).

## `docs/instructions-json.md` tracker examples — multiple inconsistencies — Status: open

(2026-04-29 review) (a) `update_tracker.syntax / inline_field` example shows duplicate `- Sport:: true` line. (b) `callout_body` syntax is missing the `> - Temperature:: 4.8` example variant. (c) Doc implies trackers are at the start of a line; trackers can also appear inline elsewhere in the line — never assume position. (d) Missing tracker syntax variant: `- For Me::` (label-style, no value following the `::`). Touch points: `docs/instructions-json.md` § Tracker Conventions; verify renderer + parser handle each variant before updating the doc.

<!-- 2026-07-01 -->

## `/inbox` self-triggered via model-improvised `ScheduleWakeup` — Status: resolved (#110)

`ScheduleWakeup` is a built-in Claude Code harness tool (it appears NOWHERE in the Tomo runtime — verified by grep). During a container `/inbox` run the model improvised `ScheduleWakeup(prompt:"inbox")` as a "fallback heartbeat while synthesis-conductor runs"; when it fired the `prompt:"inbox"` re-ran the **whole** `/inbox` command → re-triage → re-ingested Pass-2 rendered staging notes (`source_items 4 → 9`). It was NOT the `/loop` skill (that idled correctly with `<<autonomous-loop-dynamic>>`) and NOT a Tomo instruction — every `/inbox` route already ends in `Exit`. Fix: PreToolUse hook `dot_claude/hooks/block-inbox-selfschedule.sh` (matcher `ScheduleWakeup`) denies any wakeup whose `prompt` references `inbox` with a message that `/inbox` runs only on explicit user invocation; generic loop heartbeats pass through. Hooks load at **session start** — restart the container session after syncing. General lesson: when a plain `Exit`/imperative is observed failing against model improvisation of a built-in tool, a hard PreToolUse hook beats another soft prompt directive.

<!-- 2026-07-03 -->

## Empty stub notes generated from an approved suggestion doc with missing source notes — Status: open (needs repro)

Observed (2026-07-02): Tomo generated empty stub notes. Suspected trigger is an **approved suggestion document whose source notes are missing** — possibly a leftover temp state, or a suggestion doc that was approved without a matching instruction document. Root cause not yet confirmed. Desired behavior: Tomo must NOT emit empty stubs just because an approved suggestion doc exists while the source notes are absent — it should detect the missing sources and skip/flag rather than render empty placeholders. Action: recreate the exact conditions (approved suggestion doc + absent sources, ± instruction doc) to determine why the empty render fired, then add a guard + regression fixture. Related: Phase 0b stale-state detection (#37/F-51), stale-run re-ingestion fixes.

<!-- 2026-09-03 -->

## `edit_frontmatter` re-run returns `failed`, not `skipped-already` — Status: known, not a bug

Reported by Hashi 2026-09-03 (`_inbox/from-hashi/2026-09-03_hashi-to-tomo_up-source-routing-confirmed-and-one-rerun-asymmetry.md`), verified by them against `editFrontmatter.ts`. **Diagnostic note, not a defect on either side.**

Re-running an `edit_frontmatter` action that already applied does **not** come back `skipped-already`. It comes back **`failed`** with a "the note changed since the instruction set was written" reason:

```
{"operation": "remove", "expected": ["[[Philosophy MOC (kit)]]"]}
```

First run deletes the key. Second run finds the property absent while `expected` still names the old value, so the optimistic-lock guard reports a changed world and refuses. The same holds for `set` — the second run sees the new value where `expected` names the old one.

**What this means for triage:** a `failed` on a re-run is **not** evidence that Tomo emitted a wrong `expected`. When a user reports `edit_frontmatter` failures with "the note changed" reasons after re-running an instruction set, the first hypothesis is *"already applied, `applied` flag not persisted"* — not a mis-emission. Check the `applied` flag in the instruction set before suspecting the payload.

Hashi's real idempotency mechanism is the planner filter that drops every action carrying `applied: true` before the handler runs (`planner.ts:179`), so the failure needs a run where the vault edit landed but the flag did not persist. Neither side is loosening the guard: treating "expected a value, found absent" as success is exactly the silent-success shape spec 032 exists to remove.

Related: the `up_value`-never-normalised contract in `tomo/scripts/lib/render_actions.py::_construct_edit_frontmatter_fields` (rule 4) — Hashi's `expected` comparison is order-sensitive `deepEqual`, so a normalising change would fail guards at apply time, in a user's vault, with a green suite.
