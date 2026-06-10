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
