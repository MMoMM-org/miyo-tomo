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
