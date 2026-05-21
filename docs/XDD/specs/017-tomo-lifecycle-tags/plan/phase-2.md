---
title: "Phase 2: Producer-Side Writes (F-47.P1)"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Producer-Side Writes (F-47.P1)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Solution Strategy; lines: 269-278]` — producers emit `tomo:` block; consumers untouched in this phase (additive)
- `[ref: SDD/Building Block View/Components]` — Producer Scripts box
- `[ref: SDD/Directory Map; lines: 349-401]` — MODIFY list per producer script
- `[ref: SDD/Architecture Decisions/ADR-5]` — `tag-captured.py` → `mark-captured.py` rename + rewrite
- `[ref: SDD/Architecture Decisions/ADR-6]` — P1 ships additively; legacy detection paths stay live until P2
- `[ref: SDD/Cross-Spec Coordination; lines: 962-970]` — 012 fan-doc renderer extension; `doc_type=suggestions-fan` enum value
- `[ref: PRD/Feature 1, Feature 6]` — `tomo:` block on every producer + write_frontmatter wrapper convergence
- `[ref: PRD/AC-1.1, AC-1.2, AC-1.3, AC-1.4, AC-1.5, AC-6.2]` — producer-side acceptance criteria
- `[ref: docs/ai/memory/decisions.md; "scripts produce, agents transport"]` — Tomo vault-write pattern: scripts render to tomo-tmp/, agents kado-write to vault

**Key Decisions**:
- **ADR-5**: Rename `tag-captured.py` → `mark-captured.py`. Reflects what it does after F-47 (sets `tomo.state=captured`, no tag). Preserve git history via `git mv`.
- **ADR-6 (P1 atomicity)**: Producers can ship before consumers switch over. The legacy state-init / Auto-Discovery body-read paths stay live in this phase — Phase 3 (P2) removes them.
- **PRD v1.2 lock**: Producers emit `tomo:` block ONLY. No mirrored lifecycle tag in `tags:` array.
- **`run_id` continuity**: instructions docs emit a NEW `run_id` (the Pass-2 invocation's), not the upstream suggestions' `run_id`. Upstream `run_id` is recoverable via `tomo.source_suggestions → read frontmatter` per SDD §Implementation Gotchas.

**Dependencies**:
- **Hard**: Phase 1 (state-machine module + schema + KadoClient extensions) must be merged.
- T2.1 (mark-captured.py rename) blocks tests touching that filename — do it first or in parallel with rename-aware tests.
- T2.6 (agent prompt updates) consumes T2.2/T2.3/T2.4/T2.5 outputs — sequence after the renderer tasks.

---

## Tasks

This phase makes every Tomo producer emit a schema-valid `tomo:` block via `kado_client.write_frontmatter()`. The phase is **additive** — running `/inbox` after Phase 2 merges still works because the legacy consumer paths haven't been removed yet. The schema-validation gate (dev mode) is the load-bearing check that each producer is correctly wired.

- [ ] **T2.1 Rename `tag-captured.py` → `mark-captured.py` + rewrite to use `write_frontmatter`** `[activity: refactor]`

  1. Prime: Read `tomo/scripts/tag-captured.py` end-to-end. Note lines 96-184 (the regex YAML edit) — this is the `feedback_frontmatter_newline_guard` bug class being eliminated `[ref: PRD/Feature 6 + Risks]`. Read SDD ADR-5 rationale `[ref: SDD/Architecture Decisions/ADR-5; lines: 1095-1098]`. Read all current callers via `rg "tag-captured" tomo/ scripts/ tests/ install-tomo.sh` to seed the rename sweep `[ref: feedback_rename_sweep_needs_repo_wide_rg]`.
  2. Test: `tests/test_mark_captured.py::test_writes_tomo_state_captured` (mock KadoClient, assert one `write_frontmatter` call per item with `{"tomo":{"doc_type":"source","state":"captured","run_id":...,"updated_at":...}}` and `mode="merge"`); `test_idempotent_on_already_captured` (second call against same path is a no-op write — schema validation passes, merge-mode preserves existing state field, no exception); `test_no_legacy_tag_written` (verify `#<prefix>/captured` tag is NOT in the frontmatter payload — v1.2 lock); `test_run_id_propagated_from_argv`; `test_no_regex_yaml_edit` (grep the file's source: zero references to YAML-edit-by-regex patterns from the old `tag-captured.py:131-177`).
  3. Implement: `git mv tomo/scripts/tag-captured.py tomo/scripts/mark-captured.py`. Rewrite body: import `KadoClient` from `lib.kado_client`, `build_tomo_block` from `lib.doc_frontmatter`. For each input path, call `client.write_frontmatter(path, {"tomo": build_tomo_block(doc_type="source", state="captured", run_id=...)}, mode="merge")`. Delete the regex-YAML-edit block entirely. Bump `# version:` to a clean `0.x.0`. Sweep all references: `install-tomo.sh`, `update-tomo.sh` (if any tracked-files list), agent prompts mentioning the old name (search `tomo/dot_claude/agents/`), evolution log entries (leave historical mentions as-is per `feedback_rename_sweep_needs_repo_wide_rg`).
  4. Validate: `pytest tests/test_mark_captured.py -v`; `git log --follow tomo/scripts/mark-captured.py | head` confirms history preserved across rename; `rg tag-captured tomo/ scripts/` returns only `_archive/` / historical hits; `ruff check tomo/scripts/mark-captured.py`. Run `./scripts/update-tomo.sh` and verify `tomo-instance/scripts/mark-captured.py` is present and `tomo-instance/scripts/tag-captured.py` is gone.
  5. Success: Source items get `tomo.state=captured` via the wrapper, never via regex YAML edit `[ref: PRD/AC-1.1, AC-6.2]`. `feedback_frontmatter_newline_guard.md` failure mode is no longer reproducible on the captured-write path `[ref: PRD/Success Metrics row "Bug elimination"]`. Git history follows the rename `[ref: SDD/ADR-5]`.

- [ ] **T2.2 `suggestions-render.py` emits `tomo:` block** `[parallel: true]` `[activity: backend-implementation]`

  1. Prime: Read `tomo/scripts/suggestions-render.py` end-to-end, particularly the frontmatter-assembly section. Read PRD AC-1.2 + flow diagram §6.1 Phase C3 `[ref: PRD/Feature 1; AC-1.2]` `[ref: PRD/§6.1; lines: 401-411]`. Confirm the renderer already has access to `run_id` from its inputs (`tomo-tmp/suggestions-doc.json` or argv).
  2. Test: `tests/test_suggestions_render_tomo_block.py::test_emits_tomo_block_with_correct_fields` (render a fixture suggestions-doc.json; parse output frontmatter; assert `tomo.doc_type=suggestions`, `tomo.state=pending-approval`, `tomo.run_id` matches input, `tomo.updated_at` is a valid ISO-8601 with `Z` suffix); `test_no_mirrored_lifecycle_tag` (assert no `#<prefix>/suggestions/pending-approval` tag in the rendered tags array — v1.2 lock); `test_schema_validation_failure_in_dev_mode_blocks_render` (force an invalid state via monkey-patch → render must raise `SchemaValidationError` when `TOMO_SCHEMA_STRICT=1`); `test_frontmatter_yaml_well_formed` (parse output via `yaml.safe_load`, assert no trailing-newline issues per `feedback_frontmatter_newline_guard`).
  3. Implement: In `tomo/scripts/suggestions-render.py`, import `build_tomo_block`. At the frontmatter-assembly step, add `tomo: <built block>` to the rendered YAML before serialisation. Use the existing YAML serialiser (don't regex-edit). Bump `# version:`. The `tomo:` block is keyed at the same top level as `tags:`, `up::`, etc.
  4. Validate: `pytest tests/test_suggestions_render_tomo_block.py -v`; render a real fixture (or a `--dry-run` against an existing tomo-tmp/) and inspect by eye for shape; `yaml.safe_load(open(rendered).read().split("---")[1])` returns a dict containing `tomo.state=pending-approval`; `ruff check tomo/scripts/suggestions-render.py`.
  5. Success: Every `<ts>_suggestions.md` produced by `/inbox` carries the validated `tomo:` block with `state=pending-approval` `[ref: PRD/AC-1.2, AC-1.5]` `[ref: SDD/Components/SuggRender]`.

- [ ] **T2.3 `instruction-render.py` emits `tomo:` block + `source_*` cross-refs** `[parallel: true]` `[activity: backend-implementation]`

  1. Prime: Read `tomo/scripts/instruction-render.py` end-to-end. Note `instruction-render.py:388/416` calls `resolve_stem_to_path()` / `path_exists()` — these are missing on KadoClient (latent bug, **NOT** F-47 scope per SDD §Risks/Known Technical Issues; surface for follow-up, don't fix here). Read PRD AC-1.3 + flow diagrams §6.1 + §6.2 for source-ref cases. Confirm how the renderer knows whether the upstream is a suggestions doc, a suggestions-fan doc, or a moc-proposal (input field name or argv flag).
  2. Test: `tests/test_instruction_render_tomo_block.py::test_emits_tomo_block_from_suggestions_source` (input metadata indicates upstream = suggestions doc; output frontmatter has `tomo.doc_type=instructions`, `tomo.state=pending-apply`, `tomo.source_suggestions="<vault-relative path>"`, no other `source_*` keys); `test_emits_tomo_block_from_moc_proposal_source` (upstream = moc-proposal; output has `tomo.source_moc_proposal=<path>`); `test_emits_tomo_block_from_suggestions_fan_source` (upstream = XDD 012 fan-doc; output has `tomo.source_suggestions_fan=<path>`); `test_new_run_id_not_upstream_run_id` (instructions' `run_id` is the Pass-2 run, NOT the upstream's — per SDD §Implementation Gotchas); `test_schema_validation_blocks_invalid_state_in_dev_mode`.
  3. Implement: In `tomo/scripts/instruction-render.py`, import `build_tomo_block`. Detect upstream type from input metadata (existing field). Construct the `tomo:` block with the right `source_*` key. Add to frontmatter before serialisation. Bump `# version:`. Do NOT touch the `resolve_stem_to_path` / `path_exists` call sites — that bug is out of F-47 scope.
  4. Validate: `pytest tests/test_instruction_render_tomo_block.py -v`; render three fixtures (suggestions / moc-proposal / suggestions-fan) and `yaml.safe_load` each — confirm exactly one `source_*` key per case; `ruff check`.
  5. Success: Every `<ts>_instructions.md` carries `tomo: { doc_type: instructions, state: pending-apply, source_*: <path>, run_id, updated_at }` with EXACTLY ONE `source_*` cross-ref per upstream type `[ref: PRD/AC-1.3, AC-5.1]` `[ref: SDD/Implementation Gotchas; lines: 1179]`.

- [ ] **T2.4 `suggestions-reducer.py --moc-proposal-mode` emits `tomo:` block** `[parallel: true]` `[activity: backend-implementation]`

  1. Prime: Read `tomo/scripts/suggestions-reducer.py` `--moc-proposal-mode` rendering branch (the F-43 proposal-doc producer). Read PRD AC-1.4 + flow diagram §6.2 (Step 7 — render proposal-doc with `tomo:` block) `[ref: PRD/§6.2; lines: 480-485]`. Confirm interaction with `moc-architect.md` Step 7.5 kado-write (transport pattern per `docs/ai/memory/decisions.md`).
  2. Test: `tests/test_suggestions_reducer_moc_proposal_tomo_block.py::test_proposal_doc_emits_tomo_block` (run reducer in `--moc-proposal-mode` against a discovery-report fixture; parse output frontmatter; assert `tomo.doc_type=moc-proposal`, `tomo.state=pending-accept`, `tomo.run_id`, `tomo.updated_at`); `test_no_legacy_tag_emitted` (v1.2); `test_existing_moc_proposal_fields_preserved` (proposal-doc still carries clusters, supporting_items, narrative — backwards-compat with F-43 parser); `test_schema_validation_dev_mode`.
  3. Implement: In `suggestions-reducer.py --moc-proposal-mode` branch, import `build_tomo_block` and add `tomo:` to the YAML frontmatter on the rendered proposal-doc. Bump `# version:`. Preserve all existing F-43 fields.
  4. Validate: `pytest tests/test_suggestions_reducer_moc_proposal_tomo_block.py -v`; render a real F-43 discovery-report and inspect; `pytest tests/test_suggestion_parser_moc_branch.py -v` (F-43 parser regression — the new `tomo:` block must not break parser); `ruff check`.
  5. Success: Every proposal-doc produced by `/moc-propose` carries `tomo: { doc_type: moc-proposal, state: pending-accept, run_id, updated_at }` `[ref: PRD/AC-1.4]`. No regressions in F-43 parser tests.

- [ ] **T2.5 `suggestions-reducer.py --fan-resolve` emits `tomo:` block (XDD 012 extension)** `[parallel: true]` `[activity: backend-implementation]`

  1. Prime: Read `docs/XDD/specs/012-force-atomic-synthesis/solution.md` for the fan-doc renderer call site. Read SDD Cross-Spec Coordination 012 entry `[ref: SDD/Cross-Spec Coordination; lines: 962-970]`. Confirm `doc_type=suggestions-fan` is in T1.1's STATE_MACHINE. Locate `--fan-resolve` branch in `suggestions-reducer.py`.
  2. Test: `tests/test_suggestions_reducer_fan_resolve_tomo_block.py::test_fan_doc_emits_tomo_block` (assert `tomo.doc_type=suggestions-fan`, `tomo.state=pending-approval`, `tomo.run_id`, `tomo.updated_at`); `test_distinguishable_from_main_suggestions` (parse two fixtures — main suggestions and fan-doc — assert the two `doc_type` values differ and that byFrontmatter queries targeting only `doc_type=suggestions` would not match the fan-doc); `test_schema_validation_dev_mode`.
  3. Implement: In `suggestions-reducer.py --fan-resolve` branch, import `build_tomo_block` and add `tomo:` block with `doc_type="suggestions-fan"`. Bump `# version:`. Preserve all existing 012 fan-doc fields.
  4. Validate: `pytest tests/test_suggestions_reducer_fan_resolve_tomo_block.py -v`; verify 012's existing fan-doc tests still pass (`pytest tests/test_force_atomic*.py -v` or sibling); `ruff check`.
  5. Success: Fan-doc produced by 012's force-atomic flow carries `tomo: { doc_type: suggestions-fan, state: pending-approval, ... }` and is distinguishable from main suggestions doc in byFrontmatter queries `[ref: SDD/Cross-Spec Coordination "Recommended: (a) new enum value"]`.

- [ ] **T2.6 Agent prompt updates: `moc-architect.md`, `instruction-builder.md`** `[activity: agent-prompt-update]`

  1. Prime: Read `tomo/dot_claude/agents/moc-architect.md` (Step 7.5 kado-write — proposal-doc transport from `tomo-tmp/` to vault). Read `tomo/dot_claude/agents/instruction-builder.md` (Pass-2 dispatch — receives suggestion-doc or proposal-doc path, produces instructions doc). Confirm the agents are the **transport** layer (they don't render — they call `kado-write operation=note` with the script-rendered body) per `docs/ai/memory/decisions.md` 2026-05-20 entry "scripts produce, agents transport". Read `feedback_skill_spec_explicitness.md` and `feedback_orchestrator_impersonate_vs_dispatch.md` — agent prompts must be explicit; LLMs follow specs literally.
  2. Test: N/A (prompt content). Done = agents instruct the LLM to: (a) **NOT** re-render the `tomo:` block — the renderer scripts already produce a complete frontmatter; (b) preserve the rendered file byte-identical when kado-writing; (c) `instruction-builder` instructs the LLM to invoke `instruction-render.py` with the upstream-type flag so the renderer can emit the right `source_*` key.
  3. Implement: In `moc-architect.md` Step 7.5, add STRICT/MUST language: "The proposal-doc body produced by `suggestions-reducer.py --moc-proposal-mode` already contains the complete `tomo:` block. Do NOT add, modify, or re-emit any frontmatter — kado-write the rendered file byte-identical." In `instruction-builder.md` Pass-2 step, ensure it passes the upstream-type flag to `instruction-render.py` so AC-1.3 sources are emitted correctly. Bump `# version:` per `feedback_bump_version_on_managed_file_edit`.
  4. Validate: Run `./scripts/update-tomo.sh` and confirm both agent files reach `tomo-instance/.claude/agents/`. Restart Claude (per `feedback_restart_after_agent_sync`) before the next live-validation run.
  5. Success: Agents transport `tomo:` block intact; do not re-render or add legacy tags `[ref: PRD/AC-1.4, AC-1.3]` `[ref: docs/ai/memory/decisions.md; "scripts produce, agents transport"]`.

- [ ] **T2.7 Phase 2 Validation — additive ship check** `[activity: validate]`

  Run `pytest tests/test_mark_captured.py tests/test_suggestions_render_tomo_block.py tests/test_instruction_render_tomo_block.py tests/test_suggestions_reducer_moc_proposal_tomo_block.py tests/test_suggestions_reducer_fan_resolve_tomo_block.py -v`. Run full `pytest tests/ -v` — **zero regressions** allowed in legacy state-init / Auto-Discovery tests (per ADR-6: P1 ships additively, legacy paths still live). Run `ruff check tomo/scripts/`. Run `./scripts/update-tomo.sh` and verify the instance copy of every modified script. **Live-validation smoke**: in `tomo-instance/`, run `/inbox` against a single fresh source item — verify the produced `<ts>_suggestions.md` carries `tomo.state=pending-approval` AND the source item now carries `tomo.state=captured`. Run `pytest tests/test_suggestion_parser_moc_branch.py -v` (F-43 regression). Schema-CLI check three real produced files against `tomo/schemas/doc-frontmatter.schema.json` — all pass. Confirm `feedback_frontmatter_newline_guard` is no longer reproducible on `mark-captured` (write a 1-line frontmatter doc, mark it captured, parse it — no malformed YAML).
