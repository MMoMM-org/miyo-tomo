---
title: "Phase 4: Pass-2 Consumer Extensions"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: Pass-2 Consumer Extensions

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View/Secondary Flow]` — Pass-2 reconciliation sequence.
- `[ref: SDD/Implementation Examples/Example 1]` — render-time existing-`up::` algorithm + traced walkthrough (Rule 4.1 to 4.5).
- `[ref: SDD/Architecture Decisions/ADR-1]` — render-time Kado read.
- `[ref: SDD/Architecture Decisions/ADR-5]` — Step 2b filter placement.
- `[ref: PRD/Feature 4]` — bidirectional linking with `up::` preservation.
- `[ref: PRD/Feature 5]` — pre-filter and skip-flag integration.
- `[ref: PRD/Detailed Feature Specifications/Feature 4]` — 6 business rules + 5 edge cases.

**Key Decisions**:
- **ADR-1**: Renderer queries Kado per accepted child to extract existing `up::` (no schema change).
- **ADR-4**: Parser dispatches on filename `tomo-moc-proposal-*` OR frontmatter `type: tomo-proposal`.
- **ADR-5**: Skip-flag check at Step 2b (after Kado read), not Step 0.

**Dependencies**:
- T3.4 produces a real rendered proposal-doc fixture in `tomo-tmp/` — consumed by T4.1 parser tests.
- T1.5 (refactored `topic_clusters`) — not directly consumed but shares interface conventions.

---

## Tasks

This phase wires the Pass-2 consumer path: Pass-2 parser dispatches on the new doc type, instruction-render emits per-child up::-preservation actions, inbox-analyst skips proposal-docs cleanly. The three tasks T4.1, T4.2, T4.3 modify different files and run in parallel.

- [x] **T4.1 `suggestion-parser.py` — pre-parse dispatch + `parse_moc_proposal_doc`** `[parallel: true]` `[activity: backend-parsing]`

  1. Prime: Read `tomo/scripts/suggestion-parser.py` lines 29-32 (`RE_SECTION_HEADER`), 96-122 (action normalisation), 198-202 (`in_moc_list` flag), 642-680 (main entry) `[ref: SDD/Implementation Context/suggestion-parser.py]`. Read T3.4 fixture in `tomo-tmp/` for live shape (per `feedback_fixture_from_live_render.md`).
  2. Test: `tests/test_suggestion_parser_moc_branch.py::test_dispatch_on_filename_pattern`; `test_dispatch_on_frontmatter_type`; `test_skip_when_only_some_clusters_accepted` (multi-cluster doc, 1 of 3 accepted → only 1 confirmed proposal returned); `test_no_clusters_accepted_returns_empty` (parser returns empty list, eligible for squelch); `test_parse_children_list_extracts_ticked_only`; `test_parse_parent_single_select_first_check_wins`; `test_parse_override_toggle_extracts_bool`; `test_editable_text_fields_extracted` (Title/Location/Template extracted as inline `**Field:**` lines).
  3. Implement: In `suggestion-parser.py`: (a) Add pre-parse dispatch in `main()` after frontmatter read but before `split_into_sections` — if filename matches `tomo-moc-proposal-*` OR frontmatter `type: tomo-proposal`, route to new `parse_moc_proposal_doc(content, frontmatter) -> list[ConfirmedMOCProposal]`. (b) New helper `_parse_children_list(section_text) -> list[str]` (multi-select, all `[x]` items). (c) Extend action normaliser to recognise `Bestehende up:: behalten` text → `override_preserve_existing_up: bool`. (d) Extend `RE_SECTION_HEADER` (or new MOC-only regex) to match `### MOCxx — Title` (numeric MOC ID, em-dash separator). Bump `# version:`.
  4. Validate: `pytest tests/test_suggestion_parser_moc_branch.py -v`; **regression** — run all existing `suggestion-parser` tests to confirm `S##`/`A1` dispatch unchanged.
  5. Success: Parser routes proposal-docs to MOC branch and produces `ConfirmedMOCProposal[]` `[ref: PRD/AC-5.1, AC-5.2, AC-5.3, AC-5.4]`.

- [x] **T4.2 `instruction-render.py` — per-child existing-`up::` emission (Rule 4.x)** `[parallel: true]` `[activity: backend-rendering]`

  1. Prime: Read `tomo/scripts/instruction-render.py` lines 374-400 (`_build_create_moc_actions`), 452-532 (`link_to_moc` builder), 969-1005 (`supporting_items` backfill) `[ref: SDD/Implementation Context/instruction-render.py]`. Read SDD `Implementation Examples/Example 1` traced walkthrough end-to-end.
  2. Test: `tests/test_instruction_render_up_preservation.py` — one test per Rule 4.x:
     - `test_rule_41_no_up_default` — Override unchecked, no existing → 1 action `up:: <newMOC>`;
     - `test_rule_42_valid_up_default` — Override unchecked, valid existing → 2 actions: `up:: <newMOC>` + `related:: <X>`;
     - `test_rule_43_broken_up_default` — Override unchecked, broken target → 1 action `up:: <newMOC>` (no related);
     - `test_rule_44_no_up_override` — Override checked, no existing → 1 action `up:: <newMOC>` (Override no-op);
     - `test_rule_45_valid_up_override` — Override checked, valid existing → 1 action `related:: <newMOC>` (existing `up::` kept);
     - `test_rule_46_per_child_individual_target` — multi-child cluster: each child's existing `up::` preserved individually, group flag flips direction only;
     - `test_self_link_skipped` — existing `up::` already targets new MOC → no action;
     - `test_child_missing_at_render_time` — Kado raises NOT_FOUND → action emits `applied:false` with `error:"child-missing"`, other children proceed.
  3. Implement: In `instruction-render.py`, add `emit_up_preservation_actions(child_stem, new_moc_stem, override_flag, kado_client, counter) -> list[Action]` matching the SDD pseudocode in Example 1 verbatim. Wire into the `create_moc` consumer code path so that when a `ConfirmedMOCProposal` is processed, this function is called for each accepted child. Helper `extract_first_up_marker(content) -> str | None` (regex match on the first `^up::` line in the body — non-greedy, ignore frontmatter). Bump `# version:`.
  4. Validate: `pytest tests/test_instruction_render_up_preservation.py -v`; **regression** — existing `instruction-render` tests for create_moc + link_to_moc still pass.
  5. Success: All 6 Rule 4.x outcomes produce correct action sequences `[ref: PRD/AC-4.1, AC-4.2, AC-4.3, AC-4.4, AC-4.5, AC-4.6]` `[ref: SDD/Implementation Examples/Example 1]`.

- [x] **T4.3 `inbox-analyst.md` — Step 2b additive pre-filter** `[parallel: true]` `[activity: agent-edit]`

  1. Prime: Read `tomo/dot_claude/agents/inbox-analyst.md` lines 55-63 (Step 0), 75-81 (Step 2 Kado read), 83-109 (Step 3+) `[ref: SDD/Implementation Context/inbox-analyst.md]`. Read `feedback_near_mvp_no_breakage.md` (additive only on hot path).
  2. Test: Manual: simulate inbox-analyst run on a proposal-doc fixture (frontmatter `tomo_skip_inbox_analysis: true`); verify the agent's run-log records a Step-2b skip with no Steps 3-12 invocation. Also: run inbox-analyst on a normal note (frontmatter without the flag); verify Steps 3-12 execute as before (regression).
  3. Implement: In `inbox-analyst.md`, add a new Step 2b section between Step 2 (Kado read) and Step 3 (classify type): "If frontmatter contains `tomo_skip_inbox_analysis: true`: write `state-update.py --status done`, write a stub `result.json` with empty `actions: []`, return `OK stem=<stem> actions=0` (no analysis)." Use STRICT/MUST wording per `feedback_agent_format_enforcement.md`. Do NOT modify Steps 3-12. Bump `# version:`.

     **Deviation (recorded 2026-05-08, commits a2fe5d2 + aa4e176):**
     - Step 2b does NOT write a stub `result.json`. The result-schema (`tomo/schemas/item-result.schema.json:33`) declares `actions: { minItems: 1 }`, so `actions: []` would have been schema-invalid. `tomo/scripts/suggestions-reducer.py:758` already handles missing result files via "skip gracefully" — the state-file `done` transition alone is sufficient to signal completion for skipped items.
     - Step 11 also touched (defensive `--path` argument added) — the original "do NOT modify Steps 3-12" guard was about behavior, not correctness; the script's argparse spec requires `--path` on `running`/`done` transitions and Step 0 + Step 2b + Step 11 are now consistent.
  4. Validate: Run `./scripts/update-tomo.sh`; restart container. Run `/inbox` over a vault containing a proposal-doc; verify run-log shows Step-2b skip; verify a sibling normal note is processed normally.
  5. Success: Skip-flag pre-filter additive; existing inbox-analyst behaviour preserved on non-proposal docs `[ref: PRD/AC-5.1]` `[ref: SDD/ADR-5]`.

- [x] **T4.4 Phase 4 Validation** `[activity: validate]`

  Run all parser + instruction-render tests. Run regression suites for the existing inbox flow. **End-to-end Pass-2 dry run**: take the T3.4 fixture proposal-doc, run `suggestion-parser.py` → `instruction-render.py` → produced `instructions.json`; verify the JSON contains exactly 1 `create_moc` + N `add_relationship` actions per accepted child + the expected `link_to_moc` actions. Open the produced `instructions.json` in `tomo-tmp/` for visual inspection.
