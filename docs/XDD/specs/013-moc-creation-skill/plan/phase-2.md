---
title: "Phase 2: Discovery Script `moc-discovery.py`"
status: in_progress
version: "1.0"
phase: 2
---

# Phase 2: Discovery Script `moc-discovery.py`

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View/Primary Flow]` — full discovery sequence diagram.
- `[ref: SDD/Complex Logic]` — moc-discovery main flow algorithm (10 steps).
- `[ref: SDD/Implementation Examples/Example 3]` — Phase 6 Jaccard duplicate detection.
- `[ref: SDD/Application Data Models]` — `DiscoveryReport` shape.
- `[ref: SDD/Internal API Changes]` — `moc-discovery.py` CLI surface.
- `[ref: PRD/Feature 1]` — multi-mode CLI surface.
- `[ref: PRD/Feature 2]` — profile-aware proposals.
- Brainstorm spec §6 (6 phases) `[ref: docs/XDD/ideas/2026-05-06-moc-creation-skill.md; lines: 93-153]`.

**Key Decisions**:
- **ADR-6**: `kado-read listDir` `.md` filter is client-side.
- **ADR-7**: `kado-search byTag` prefix-match uses glob suffix `*` (e.g., `tag:topic/applied/zsh` → `#topic/applied/zsh*`).
- Topic-extraction is cache-first; LLM cache-miss is bounded (5 batches × 10 notes = 50 ceiling).

**Dependencies**:
- T1.5 (extracted `topic_clusters()` pure function) — consumed by T2.4.
- T1.2 (vault-config loader) — consumed by all tasks.
- T1.3 (squelch helper) — consumed by T2.6 (Phase 6 dup-detection precursor; full wiring deferred to Phase 5).

---

## Tasks

This phase delivers `tomo/scripts/moc-discovery.py` — Phases 1-6.5 of the discovery flow. Tasks are sequenced because each phase consumes the previous phase's output. Output: `DiscoveryReport` JSON to stdout, suitable for piping to `suggestions-reducer.py --moc-proposal-mode`.

- [ ] **T2.1 CLI scaffolding + mode routing** `[activity: backend-cli]`

  1. Prime: Read sibling script `tomo/scripts/moc-tree-builder.py` lines 1-32 for argparse + KadoClient + JSON conventions `[ref: SDD/Implementation Context/Code Context; tomo/scripts/moc-tree-builder.py]`. Read SDD `Internal API Changes` for CLI surface `[ref: SDD/Internal API Changes]`.
  2. Test: `tests/test_moc_discovery_cli.py::test_route_tag_mode` (`--tag topic/applied/zsh` → `mode="tag"`, `trigger_arg="topic/applied/zsh"`); `test_route_folder_mode`; `test_route_class_mode`; `test_route_title_mode`; `test_route_freetext_when_unknown_prefix` (`foo:bar` → `mode="free-text"`, `trigger_arg="foo:bar"` per AC-1.7); `test_route_no_args` (mode = `"scan"`); `test_dry_run_emits_json_to_stdout_and_skips_kado` (with `--dry-run`, prints minimal `DiscoveryReport`, no Kado calls); `test_exit_code_2_on_missing_profile`.
  3. Implement: Create `tomo/scripts/moc-discovery.py` with: shebang + `# version: 0.1.0` + module docstring (per sibling pattern). `argparse` with mutually-exclusive group for `--tag/--folder/--class/--title`, optional positional for free-text, common flags `--config`, `--profile`, `--cache`, `--dry-run`, `--candidate-cap`. Mode-routing helper `route_input(args) -> (mode, trigger_arg)`. Stub Phases 1-6.5 with `NotImplementedError` placeholders. Stdout = JSON `DiscoveryReport`; stderr = progress logs. Exit codes per SDD: 0 success, 1 partial-failure, 2 fatal.
  4. Validate: `pytest tests/test_moc_discovery_cli.py -v`; `ruff check tomo/scripts/moc-discovery.py`; `python3 tomo/scripts/moc-discovery.py --dry-run` exits 0 with valid JSON.
  5. Success: Mode routing correctly classifies all 6 input shapes `[ref: PRD/AC-1.1, AC-1.2, AC-1.3, AC-1.4, AC-1.5, AC-1.6, AC-1.7]`.

- [ ] **T2.2 Phase 1 — Candidate selection (5 modes + pre-filter + caps)** `[activity: backend-discovery]`

  1. Prime: Read `tomo/scripts/lib/kado_client.py` lines 298-322 (`_search_all` pagination) `[ref: SDD/Implementation Context/lib/kado_client.py]`. Read profile shape `tomo/profiles/miyo.yaml` (`concept_defaults.atomic_note.{base_path,subdirectories}`, `classification.categories`).
  2. Test: `tests/test_moc_discovery_phase1.py::test_tag_mode_appends_glob_suffix` (with mocked Kado, `--tag topic/applied/zsh` produces query `#topic/applied/zsh*` per ADR-7); `test_folder_mode_md_filter_clientside` (Kado returns mixed `.md`/`.canvas`/folder entries; only `.md` files retained per ADR-6); `test_class_mode_resolves_subdir_via_profile`; `test_title_and_freetext_topic_match_against_cache` (matches `discovery-cache.yaml::map_notes[].topics`); `test_no_args_scans_atomic_note_paths_only`; `test_pre_filter_outside_atomic_note_warns_and_intersects` (folder outside scope → warning + intersection); `test_candidate_cap_exceeded_aborts` (>200 candidates → `abort_reason="candidate-cap-exceeded"`, no proposal); `test_zero_candidates_aborts` (0 candidates after filter → `abort_reason="zero-candidates"`).
  3. Implement: In `moc-discovery.py`, implement `phase1_select_candidates(mode, trigger_arg, profile, cache, kado_client, config) -> list[Candidate]`. Sub-handlers: `_handle_tag`, `_handle_folder`, `_handle_class`, `_handle_title_or_freetext`, `_handle_scan`. Strict pre-filter helper `restrict_to_atomic_note_paths(paths, profile)`. Hard-cap check before returning.
  4. Validate: `pytest tests/test_moc_discovery_phase1.py -v`; `ruff check`. Manual sanity: `python3 tomo/scripts/moc-discovery.py --tag <real-tag> --dry-run` against Privat-Test fixture.
  5. Success: All 5 modes produce filtered candidate sets; abort messages match spec `[ref: PRD/AC-1.x]` `[ref: PRD/AC-3 abort paths]` `[ref: SDD/Error Handling]`.

- [ ] **T2.3 Phase 2 — Cache lookup + LLM cache-miss extraction (bounded)** `[activity: backend-discovery]`

  1. Prime: Read `discovery-cache.yaml` shape (live file at `tomo-instance/config/discovery-cache.yaml`) `[ref: SDD/Implementation Context/discovery-cache.yaml]`. Read `tomo/scripts/topic-extract.py` for existing LLM extraction pattern.
  2. Test: `tests/test_moc_discovery_phase2.py::test_cache_first_hit_no_llm` (all candidates in cache → 0 LLM calls); `test_cache_miss_batched` (50 candidates not in cache → 5 batches of 10); `test_cache_miss_cap_exceeded_aborts` (60 cache-miss candidates with cap=5×10 → `abort_reason="cache-miss-cap-exceeded"`); `test_cache_empty_aborts_at_startup` (cache file missing or empty → `abort_reason="cache-empty"` BEFORE Phase 1).
  3. Implement: In `moc-discovery.py`, add `phase2_extract_topics(candidates, cache, config, llm_client)`. Cache-empty pre-check at module start (before any phase). Helper `_batch_llm_extract(candidates, batch_size=10)` calling `topic-extract.py` or sibling.
  4. Validate: `pytest tests/test_moc_discovery_phase2.py -v`; mock LLM client; verify caps fire deterministically.
  5. Success: Cache-first lookup minimises LLM cost; abort paths fire when caps exceeded `[ref: PRD/AC-3 cache-empty case]` `[ref: PRD/Constraints/Cache prerequisite]` `[ref: SDD/Quality Requirements/Performance]`.

- [ ] **T2.4 Phase 3 — Cluster detection (consumes T1.5)** `[activity: backend-discovery]`

  1. Prime: Read SDD/Solution Strategy (extracted `topic_clusters()`) `[ref: SDD/Solution Strategy]`. Read T1.5 deliverable `tomo/scripts/lib/topic_clusters.py`.
  2. Test: `tests/test_moc_discovery_phase3.py::test_cluster_threshold_default` (default `min_notes=3`); `test_multi_cluster_shared_notes_highest_weight_wins` (note in 2 clusters → assigned to highest-weight per existing reducer algorithm); `test_zero_clusters_returns_empty_report_not_abort` (clusters below threshold → empty, not an abort).
  3. Implement: In `moc-discovery.py`, add `phase3_cluster(candidates_with_topics, config) -> list[Cluster]` calling `lib.topic_clusters.build_topic_clusters` from T1.5.
  4. Validate: `pytest tests/test_moc_discovery_phase3.py -v`.
  5. Success: Clustering reuses extracted pure function; threshold honoured `[ref: PRD/Feature 7]` `[ref: SDD/Implementation Examples/Example 3]`.

- [ ] **T2.5 Phase 4-5 — Title generation + parent resolution** `[activity: backend-discovery]`

  1. Prime: Read `docs/XDD/reference/tier-3/lyt-moc/new-moc-proposal.md` §7 (title patterns) and `moc-matching.md` (scoring) `[ref: SDD/Implementation Context/Documentation Context]`. Read profile classification keywords (`miyo.yaml::classification.categories.keywords`).
  2. Test: `tests/test_moc_discovery_phase4.py::test_miyo_title_appends_moc_suffix`; `test_lyt_title_plain`; `test_title_mode_uses_user_input_verbatim`; `test_scan_multi_cluster_one_title_per_cluster`. `tests/test_moc_discovery_phase5.py::test_classification_keyword_match_top_parent` (MiYo profile, cluster topics include `shell` → 2600 classification offered top); `test_no_keyword_match_returns_null_parent`; `test_top_3_parents_offered`.
  3. Implement: In `moc-discovery.py`, add `phase4_title(cluster, profile, mode, trigger_arg)` and `phase5_resolve_parents(cluster, profile, cache) -> list[ParentOption]`. Reuse existing `slugify()` from `instruction-render.py:115-124` (import cleanly, do not duplicate).
  4. Validate: `pytest tests/test_moc_discovery_phase4.py tests/test_moc_discovery_phase5.py -v`.
  5. Success: Profile-aware titles + parent resolution `[ref: PRD/AC-2.1, AC-2.2, AC-2.3, AC-2.4, AC-2.5]`.

- [ ] **T2.6 Phase 6 — Duplicate detection (Jaccard ≥ 0.80) + squelch hookup (read-only)** `[activity: backend-discovery]`

  1. Prime: Read SDD `Implementation Examples/Example 3` (Jaccard) `[ref: SDD/Implementation Examples/Example 3]`. Read `tomo/scripts/lib/squelch.py` from T1.3.
  2. Test: `tests/test_moc_discovery_phase6.py::test_exact_title_match_skips_cluster`; `test_jaccard_overlap_above_80_skips_cluster` (with traced fixture: cluster topics `{shell,zsh,terminal,dotfiles}` vs MOC topics `{shell,zsh,terminal,dotfiles,fzf}` → Jaccard 0.80, skip); `test_jaccard_overlap_below_80_includes_cluster`; `test_squelch_active_signature_skips` (mocked active squelch entry → cluster not in output); `test_squelch_inactive_includes_cluster`.
  3. Implement: In `moc-discovery.py`, add `phase6_dedupe(clusters, cache, squelch_registry, config) -> list[Cluster]`. Helper `_jaccard(a, b) -> float`. Helper `_compute_topic_signature(cluster) -> str` per SDD Example 2. Squelch is **read-only** in this phase — actual decrement/persist/append happens in Phase 5 wiring (T5.1, T5.2).
  4. Validate: `pytest tests/test_moc_discovery_phase6.py -v`. Trace the Jaccard fixture for one positive and one negative case.
  5. Success: Duplicate skipping correct on traced fixture; squelch read-path integrated `[ref: PRD/Feature 8]` `[ref: SDD/Implementation Examples/Example 3]`.

- [ ] **T2.7 Phase 6.5 — Existing-`up::` validation per candidate** `[activity: backend-discovery]`

  1. Prime: Read SDD `Implementation Examples/Example 1` (per-child existing-up extractor) `[ref: SDD/Implementation Examples/Example 1]`. Read brainstorm §6.5 `[ref: docs/XDD/ideas/2026-05-06-moc-creation-skill.md; lines: 147-153]`.
  2. Test: `tests/test_moc_discovery_phase65.py::test_no_up_marker_state_absent`; `test_valid_up_resolves_state_valid`; `test_broken_up_state_broken` (target file missing → state="broken"); `test_malformed_multi_up_uses_first_with_warning`.
  3. Implement: In `moc-discovery.py`, add `phase65_validate_existing_up(clusters, kado_client) -> list[Cluster]`. Helper `_extract_first_up_marker(content) -> str | None`. Per-cluster decoration with `existing_up_state ∈ {"absent", "valid", "broken"}` and `existing_up_target` per child.
  4. Validate: `pytest tests/test_moc_discovery_phase65.py -v`. Mock Kado read with realistic note bodies.
  5. Success: Per-child existing-`up::` state correctly classified; broken-up:: handled gracefully `[ref: PRD/AC-4.3]` `[ref: SDD/Implementation Examples/Example 1]`.

- [ ] **T2.8 Phase 2 Validation** `[activity: validate]`

  Run all `tests/test_moc_discovery_*.py`. Run `ruff check tomo/scripts/moc-discovery.py`. Manual smoke: `python3 tomo/scripts/moc-discovery.py --tag <real-tag>` against Privat-Test (or live cache copy) to confirm a complete end-to-end JSON `DiscoveryReport` is produced. Verify `DiscoveryReport` schema matches SDD `Application Data Models`.
