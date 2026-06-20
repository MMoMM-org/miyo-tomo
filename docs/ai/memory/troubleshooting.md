# Troubleshooting — Tomo
<!-- Known issues and proven fixes. Updated: 2026-05-01 -->
<!-- Format: ## [Issue title] — Status: open/resolved — [fix description] -->
<!-- Resolved entries are archived by /memory-cleanup, not deleted -->

<!-- 2026-05-01 -->

## `instruction-render.py:1254` `read_template("asset")` auto-renders the asset block — Status: open

`read_template("asset")` is a Fallstrick: any caller reading the asset template inadvertently emits the rendered result, even when only the template structure was needed. Side effect is invisible from the call site. Action: separate template-read from template-render, or rename the function to make the side effect explicit (`render_asset()` vs `read_asset_template()`). Surfaced 2026-05-01 during `/inbox` Pass 2 debugging.

## Pipeline field-drop pattern: `result.json → suggestions.md → instructions.json` — Status: open

When a new field flows through the Pass-2 pipeline, every transformation stage must explicitly preserve it. Today `position` was dropped at the suggestions-reducer step, then re-emitted only via post-fix patching. Risk: every new field added upstream silently disappears unless the reducer + parser are updated in lockstep. Mitigation: write a fields-contract document (which fields each pipeline stage must passthrough) and add a regression fixture that exercises every passthrough field. Surfaced 2026-05-01 (`link_to_moc.position` regression).

## `link_to_moc` placement default was `inside` instead of `after` — Status: resolved (commit `82fcf0a`)

Contract drift: the agreed default placement for `link_to_moc` actions was `after` (sibling line outside the callout); the analyst was emitting `inside` (within the callout body). Fixed in `82fcf0a fix: link_to_moc default placement = after; carry log_entry/log_link position`. Verification on next `/inbox` run: confirm emitted actions have `placement: "after"` not `"inside"`.

## `docs/instructions-json.md` tracker examples — multiple inconsistencies — Status: open

(2026-04-29 review) (a) `update_tracker.syntax / inline_field` example shows duplicate `- Sport:: true` line. (b) `callout_body` syntax is missing the `> - Temperature:: 4.8` example variant. (c) Doc implies trackers are at the start of a line; trackers can also appear inline elsewhere in the line — never assume position. (d) Missing tracker syntax variant: `- For Me::` (label-style, no value following the `::`). Touch points: `docs/instructions-json.md` § Tracker Conventions; verify renderer + parser handle each variant before updating the doc.

<!-- 2026-06-01 -->

## Unquoted tilde in a bash `case` pattern → doubled `$HOME` path — Status: resolved (commit `b3243db`)

A bare `~/` in a `case` *pattern* is tilde-expanded by bash: `case "$P" in ~/*)` becomes `case "$P" in /Users/<you>/*)`. It then wrongly matches absolute paths already under `$HOME`, and an arm like `P="$HOME/${P#\~/}"` prepends `$HOME` again → doubled path (e.g. `/Users/marcus//Users/marcus/Local/Obsidian/Privat`). Fix: **quote the tilde in the pattern** — `\~/*)` (or `"~/"*)`). Guard with an extraction-based regression test that asserts the arm stays quoted: `tests/test_install_vault_path.py` greps the live arm from `install-tomo.sh`, so it cannot drift. Surfaced 2026-06-01 in the `install-tomo.sh` vault-path prompt; the original fix had been written but stranded on an unmerged branch (see `tools.md` → "check unmerged branches for an orphaned fix").

<!-- 2026-06-06 -->

## Config-key drift between two consumers — `vault-scan` vs `moc_scan` read `atomic_note` differently — Status: resolved (commit `629047a`)

021's M8 set the canonical `concepts.atomic_note` shape to a dict with a single `path` key, and updated `lib/moc_scan.read_scope_paths` to read it — but `vault-scan.py` `extract_primary_path`/`extract_all_paths`, the OTHER consumer of the same concept config, still read only `base_path`/`paths`. So `path` resolved to `None` → `/explore-vault` reported `atomic_note` as `0 (path not resolved)` (281 live notes invisible). Fix: make `vault-scan` accept `path` alongside `base_path`/`paths`. Lesson (recurring — see auto-memory `feedback_schema_audit_all_consumers`): when you change a config-key shape, grep EVERY consumer of that key, not just the one you're editing. Two readers of one config accepting different key names is the trap.

<\!-- 2026-06-20 -->

## Instance `tomo-tmp` stale state poisons `/inbox` re-runs — and don't over-clear it — Status: resolved (process learning)

`tomo-tmp/` holds per-run scratch (`inbox-state.jsonl` ledger, `items/`, `parsed-suggestions.json`, `suggestions-doc.json`, `suggestions-fan-doc.json`, `rendered/`). Two failure modes seen in one live walk: (a) a `/inbox` run reused a PRIOR run's stale `tomo-tmp` and processed 21 ghost items (notes deleted from the inbox) instead of the 6 real sources — `/inbox` does NOT self-clear `tomo-tmp`, so after any inbox reset clear it before re-running. (b) Over-correction: clearing `tomo-tmp` wholesale also deletes the Pass-1 reducer outputs (`suggestions-doc.json` / `suggestions-fan-doc.json`) that Pass-2 synthesis needs — and `/inbox --force-pass2` does NOT regenerate them (Pass-1 doesn't re-run), so member/anchor recovery silently degrades to Placement-line fallback. When resetting between runs: clear run artifacts (state, items, rendered, instructions) but KEEP the structured Pass-1 docs, OR accept that a full re-run needs Pass-1 (LLM cost + re-approval). Also: after a closed-Obsidian FS restore, Kado's index lags — verify `list_dir` is stable before trusting discovery (already noted in auto-memory).

## Render↔parse field-name mismatch silently drops proposed-MOC members — Status: resolved (commit `41de668`)

`suggestions-render.py` emits a proposed MOC's members as `**Supporting notes:** <note titles>`, but `suggestion-parser.py:parse_proposed_mocs` read members from a `Supporting items:` field that is never rendered → `create_moc.supporting_items` came back empty → the new MOC was created with ZERO child down-links (the whole point of the proposed MOC). The member SNN ids only survive in the structured `suggestions-doc.json` (`proposed_mocs[].items` + `sections[].{id,stem}`), which is the SSoT for membership — NOT the human-facing markdown. Fix: recover members from the structured doc (topic → items → section stems), enrich INSIDE `parse_proposed_mocs` before its same-name merge (so a name merged from multiple topics keeps every member), then after fan reconciliation map stems → final confirmed ids and set `supporting_items`. Lesson (recurring, see "Pipeline field-drop pattern" above + auto-memory `feedback_schema_audit_all_consumers`): a producer label and a consumer label that disagree fail silently — when a field round-trips through a rendered doc, the render label and the parse key must match, or carry the machine data in the structured sibling and treat that as SSoT.
