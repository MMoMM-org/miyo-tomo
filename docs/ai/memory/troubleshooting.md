# Troubleshooting — Tomo
<!-- Known issues and proven fixes. Updated: 2026-06-29 -->
<!-- Format: ## [Issue title] — Status: open/resolved — [fix description] -->
<!-- Resolved entries are archived by /memory-cleanup, not deleted. See archive/YYYY-MM/ -->

<!-- 2026-05-01 -->

## `instruction-render.py:1254` `read_template("asset")` auto-renders the asset block — Status: open

`read_template("asset")` is a Fallstrick: any caller reading the asset template inadvertently emits the rendered result, even when only the template structure was needed. Side effect is invisible from the call site. Action: separate template-read from template-render, or rename the function to make the side effect explicit (`render_asset()` vs `read_asset_template()`). Surfaced 2026-05-01 during `/inbox` Pass 2 debugging.

## Pipeline field-drop pattern: `result.json → suggestions.md → instructions.json` — Status: open

When a new field flows through the Pass-2 pipeline, every transformation stage must explicitly preserve it. Today `position` was dropped at the suggestions-reducer step, then re-emitted only via post-fix patching. Risk: every new field added upstream silently disappears unless the reducer + parser are updated in lockstep. Mitigation: write a fields-contract document (which fields each pipeline stage must passthrough) and add a regression fixture that exercises every passthrough field. Surfaced 2026-05-01 (`link_to_moc.position` regression).

## `docs/instructions-json.md` tracker examples — multiple inconsistencies — Status: open

(2026-04-29 review) (a) `update_tracker.syntax / inline_field` example shows duplicate `- Sport:: true` line. (b) `callout_body` syntax is missing the `> - Temperature:: 4.8` example variant. (c) Doc implies trackers are at the start of a line; trackers can also appear inline elsewhere in the line — never assume position. (d) Missing tracker syntax variant: `- For Me::` (label-style, no value following the `::`). Touch points: `docs/instructions-json.md` § Tracker Conventions; verify renderer + parser handle each variant before updating the doc.
