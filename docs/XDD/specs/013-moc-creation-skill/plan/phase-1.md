---
title: "Phase 1: Cross-Repo Handoff & Foundation"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: Cross-Repo Handoff & Foundation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Constraints; lines: CON-9]` — Hashi destination-collision dependency.
- `[ref: SDD/Architecture Decisions/ADR-3]` — NEW Hashi requirement.
- `[ref: SDD/Data Storage Changes]` — vault-config additions, squelch state schema.
- `[ref: SDD/Pattern Documentation]` — `obsidian-markdown` skill registration.
- `[ref: SDD/Solution Strategy]` — extracted `topic_clusters()` pattern.
- `[ref: PRD/Feature 6]` — Hashi guard requirement.
- `[ref: PRD/Feature 7]` — Configurable thresholds.

**Key Decisions**:
- **ADR-3**: Hashi guard is cross-repo handoff — must be sent before F-43 launch.
- **ADR-8**: Squelch state lives at `tomo-instance/state/moc-squelch.json` (sidecar, atomic-write).
- **L1 Operations**: Cross-repo handoffs go through `_outbox/for-<repo>/`; direct edits not allowed.

**Dependencies**:
- None — this phase establishes foundations consumed by Phases 2-5.

---

## Tasks

This phase establishes cross-repo handoff, configuration schema, sidecar state, the lazy-loaded reference skill, and a refactored shared `topic_clusters()` function — the structural prerequisites for everything downstream.

- [x] **T1.1 Hashi destination-collision guard handoff** `[parallel: true]` `[component: hashi]` `[activity: cross-repo-handoff]` ✅ DONE 2026-05-07: `_archive/outbox/2026-05/2026-05-07_tomo-to-hashi_create-moc-collision-guard.md` (sent + ACK'd + reply closed). Hashi 0.2.0 shipped the guard (`createMoc.ts:40` emits "destination already exists: <path>"; `planner.ts:217` cascades `add_relationship`→`create_moc`). T6.4 launch gate satisfied.

  1. Prime: Read SDD ADR-3 + Risks/Cross-repo dependency `[ref: SDD/Architecture Decisions/ADR-3]` `[ref: SDD/Risks/Hashi destination-collision guard not implemented before F-43 ships]`. Read PRD AC-6.1, 6.2, 6.3 `[ref: PRD/Feature 6]`.
  2. Test: N/A (handoff artefact, not code). Done = `_outbox/for-hashi/2026-05-07-create-moc-collision-guard.md` exists with required sections (context, requirement, AC, contract reference).
  3. Implement: Create `_outbox/for-hashi/2026-05-07-create-moc-collision-guard.md` describing: (a) F-43 context (one-paragraph summary of `/moc-propose`), (b) requirement ("Hashi MUST verify `create_moc.destination` does not exist before write; on collision return `applied: false` + `error_msg`; dependent `add_relationship`/`link_to_moc` actions for the same MOC also fail"), (c) AC mapping to PRD-AC-6.x, (d) reference to `tomo/schemas/instructions.schema.json#create_moc`, (e) status `pending`, (f) **explicit receipt protocol**: Hashi team confirms by either (i) flipping front-matter `status: pending` → `status: received` + `received_by:` + `received_at:` + `target_version:` (semver Hashi will ship the guard in) on the same file in their `_inbox/from-tomo/` copy, AND/OR (ii) writing a sibling reply file `_outbox/for-tomo/2026-MM-DD-create-moc-collision-guard-ACK.md`. The reply MUST surface a Hashi version commitment (e.g., `target_version: 0.4.0`) — F-43 Phase 6 launch gate (T6.4) checks for one of these signals before proceeding.
  4. Validate: File present in `_outbox/for-hashi/` with explicit receipt-protocol section. Commit on `main` permitted (path is gitignored exempt per `.gitignore`).
  5. Success: Hashi handoff item filed `[ref: PRD/Feature 6]` `[ref: SDD/Risks]` with explicit receipt protocol. F-43 launch (T6.4) gate verifies one of: (a) `status: received` flag in the handoff doc, OR (b) a `2026-MM-DD-create-moc-collision-guard-ACK.md` reply in `_inbox/from-hashi/`, with a stated target version.

- [ ] **T1.2 `vault-config.yaml::tomo.moc_proposal` schema additions** `[parallel: true]` `[activity: configuration]`

  1. Prime: Read SDD `Data Storage Changes` `[ref: SDD/Data Storage Changes]`. Read existing `tomo/scripts/shared-ctx-builder.py` for config-loading pattern. Read existing `tomo-instance/config/vault-config.yaml` to identify insert location.
  2. Test: `tests/test_moc_proposal_config.py::test_defaults_when_block_missing` (loader returns spec defaults `min_notes=3`, `confidence_threshold=0.15`, `max_results=5`, `candidate_cap=200`, `cache_miss_max_batches=5`, `squelch_runs=3` when `tomo.moc_proposal` block is absent); `test_user_overrides_take_precedence` (user-provided values override defaults); `test_unknown_keys_logged_and_ignored` (unknown keys produce warning, do not crash).
  3. Implement: Add `tomo.moc_proposal` block defaults inline-documented in `tomo/config/templates/vault-config.example.yaml` (or sibling config-defaults file). In `tomo/scripts/shared-ctx-builder.py` (or sibling loader), expose `load_moc_proposal_config(vault_config_path) -> MocProposalConfig` returning a typed dict / dataclass. Bump `# version:` per `feedback_bump_version_on_managed_file_edit.md`.
  4. Validate: `pytest tests/test_moc_proposal_config.py -v`; `ruff check tomo/scripts/shared-ctx-builder.py`.
  5. Success: Loader returns spec defaults when block missing `[ref: PRD/AC-7.2]`; user overrides take precedence `[ref: PRD/AC-7.1]`.

- [x] **T1.3 Squelch sidecar state file (schema + atomic-write helper)** `[parallel: true]` `[activity: state-management]` ✅ DONE 2026-05-07: `tomo/scripts/lib/squelch.py` (load/save-atomic/decrement/add-or-replace/is_active) + `tests/test_squelch_registry.py` (7 tests passing). Stdlib-only; tmp-then-rename via `tempfile.mkstemp` + `os.replace`; missing/corrupt → empty registry + stderr warning.

  1. Prime: Read SDD `state/moc-squelch.json` schema `[ref: SDD/Data Storage Changes]`. Read existing `tomo/scripts/state-update.py` for atomic-write convention (tmp-then-rename).
  2. Test: `tests/test_squelch_registry.py::test_load_missing_returns_empty` (absent file → empty registry, no exception); `test_load_corrupt_returns_empty_with_warning` (corrupt JSON → empty registry + stderr warning, no crash); `test_atomic_write_roundtrip` (write then load yields equal data); `test_decrement_and_remove_zero` (entries with `runs_remaining=0` after decrement are removed); `test_signature_collision_replaces` (writing same signature twice replaces, no duplicates).
  3. Implement: Create `tomo/scripts/lib/squelch.py` with: `load_registry(path) -> dict[str, SquelchEntry]`; `save_registry_atomic(path, registry) -> None` (tmp-then-rename); `decrement_all(registry) -> dict[str, SquelchEntry]`; `add_or_replace(registry, entry)`; `is_active(signature) -> bool`. Use stdlib only (no new deps).
  4. Validate: `pytest tests/test_squelch_registry.py -v`; `ruff check tomo/scripts/lib/squelch.py`.
  5. Success: Squelch state file roundtrips correctly `[ref: SDD/Data Storage Changes]` `[ref: PRD/AC-8.1]` `[ref: PRD/AC-8.2]`.

- [ ] **T1.4 `obsidian-markdown` reference skill** `[parallel: true]` `[activity: skill-author]`

  1. Prime: Read existing skill `tomo/dot_claude/skills/obsidian-fields/SKILL.md` for format precedent. Read `feedback_skill_format_distinction.md` (skills must be `<name>/SKILL.md`, not flat `<name>.md`). Read SDD `Pattern Documentation` `[ref: SDD/Pattern Documentation]`.
  2. Test: N/A (reference content). Done = file exists with correct frontmatter (`user-invocable: false`, model + effort, descriptive `description`); `update-tomo.sh` syncs it into `tomo-instance/.claude/skills/`.
  3. Implement: Create `tomo/dot_claude/skills/obsidian-markdown/SKILL.md` documenting Obsidian-specific markdown syntax: callouts (`> [!note]`, `> [!warning]`), wikilinks (`[[stem]]`, `[[stem|alias]]`, `[[#heading]]`), embeds (`![[stem]]`, `![[stem#heading]]`), dataview inline-fields (`field:: value`, alternative `(field:: value)`). Frontmatter: `name: obsidian-markdown`, `user-invocable: false`, `description: "Reference for Obsidian markdown syntax — callouts, wikilinks, embeds, dataview inline-fields. Lazy-loaded by moc-architect agent."`, `model: sonnet`, `effort: low`. Add `# version: 0.1.0`.
  4. Validate: Run `./scripts/update-tomo.sh`; verify `tomo-instance/.claude/skills/obsidian-markdown/SKILL.md` is created.
  5. Success: Skill loadable as a side-effect via agent frontmatter `skills:` reference `[ref: SDD/Pattern Documentation]`.

- [ ] **T1.5 Extract `topic_clusters()` to a pure function** `[activity: refactor]`

  1. Prime: Read `tomo/scripts/suggestions-reducer.py` lines 508 (declaration), 598-651 (algorithm) `[ref: SDD/Implementation Examples; suggestions-reducer.py:598-651]`. Understand current callsite shape: `(topic, count, parent, tags)` tuple grouping with `min_notes` threshold.
  2. Test: `tests/test_topic_clusters.py::test_threshold_excludes_small_clusters` (threshold=3; 2-note cluster excluded); `test_normalised_topic_grouping` (different casings collapse to one cluster); `test_pure_function_no_side_effects` (call twice with same input → identical output, no global state); `test_existing_inbox_run_regression` (load a real inbox-run fixture, verify same clusters as pre-refactor).
  3. Implement: Extract algorithm from `suggestions-reducer.py:598-651` into a new module `tomo/scripts/lib/topic_clusters.py` with signature `def build_topic_clusters(items: list[ClusterCandidate], threshold: int) -> list[Cluster]`. Refactor existing reducer code to call the new function (no behavioural change). Bump `# version:` on `suggestions-reducer.py`.
  4. Validate: `pytest tests/test_topic_clusters.py -v`; **regression check** — re-run any existing tests that exercise the reducer's clustering path (e.g., `tests/test-008-phase1.py` or sibling); `ruff check`.
  5. Success: New pure function consumable by both `suggestions-reducer.py` (existing inbox flow) and `moc-discovery.py` (Phase 2 task T2.4) `[ref: SDD/Solution Strategy]` `[ref: SDD/Implementation Examples]`. Existing inbox-clustering behaviour unchanged.

- [ ] **T1.6 Phase 1 Validation** `[activity: validate]`

  Run `pytest tests/test_moc_proposal_config.py tests/test_squelch_registry.py tests/test_topic_clusters.py -v`. Run `ruff check tomo/scripts/`. Verify `_outbox/for-hashi/2026-05-07-create-moc-collision-guard.md` exists and is committed. Verify `tomo/dot_claude/skills/obsidian-markdown/SKILL.md` syncs to instance via `./scripts/update-tomo.sh`. Verify no regression in existing reducer tests.
