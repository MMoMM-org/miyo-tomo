---
title: "Phase 1: Baseline run and builder"
status: in_progress
version: "1.1"
phase: 1
---

# Phase 1: Baseline run and builder

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-1]` — the delivered `name`, the collision rule, sort by path
- `[ref: SDD/ADR-4]` — budget shedding removed, size guards
- `[ref: SDD/ADR-5]` — exclude filter, MOC folders, `is_excluded_moc`
- `[ref: SDD/ADR-7]` — `placeholder_targets`, always written
- `[ref: SDD/ADR-9]` — schema edits, golden baseline
- `[ref: SDD/Implementation Examples; "assigning names (traced)"]`
- `[ref: SDD/Implementation Gotchas]` — every caller and test this phase breaks
- `[ref: PRD/Success Metrics]` — the before/after bar and how each criterion is verified

**Key Decisions**:
- The baseline runs (T1.2) happen before anything from this branch is synced to `tomo-instance`. Once the instance carries new code, the "before" cannot be measured.
- Phases 1–4 ship together. After this phase alone the analyst would still read `--field mocs` (now uncut, above the spill size) and `placeholder_links` (now gone). Nothing is synced to the instance until Phase 6.
- Per-item baseline details (MOC paths, titles) stay out of git (owner decision): they go to `tomo-instance/spec-040-baseline/` (gitignored). Git gets counts and comparison figures only.
- Assertions already true on `main` are marked **guard**; every task names at least one assertion that fails on `main`.

**Dependencies**: none.

---

## Tasks

Records the "before" picture with a tool that can see spills, then gives the context its new shape: eligible MOCs only, sorted, each with a delivered name, uncut detail, placeholder targets always present, and size warnings instead of shedding.

- [x] **T1.1 Transcript read-size scanner** `[activity: backend-api]` `[parallel: true]`

  1. Prime: `scripts/measure-inbox-phase-b-token-cost.py` (how it finds a run's subagent transcripts); `scripts/tomo-session-inspect.py:81`; memory "Docker session transcripts"; the spill marker as it appears in a real transcript (inspect one analyst `agent-*.jsonl` from session 790a0265) `[ref: PRD/Tracking Requirements; PRD/KPIs Quality]`
  2. Test (RED — script does not exist): for a fixture transcript, reports per analyst subagent every `read-shared-ctx.py` call with its mode (`--field mocs`, `--moc-names`, `--mocs-from`, `--fields`), result bytes, and whether it was delivered as a preview; a run-level summary counts previews; output contains no note content (paths of transcript files and byte counts only)
  3. Implement: `scripts/measure-shared-ctx-reads.py` (user-invoked, host-side, so `scripts/`), `--session-latest` / `--run-id` like its sibling; WHY docstring; `# version: 0.1.0`; docs page `docs/tomo/scripts/measure-shared-ctx-reads.md` only if `docs/tomo/scripts/` mirrors `scripts/` (check the convention first)
  4. Validate: RED → GREEN; ruff clean
  5. Success: the "zero previews" KPI is measurable `[ref: PRD/KPIs Quality]`

- [x] **T1.2 Baseline runs on the test instance** `[activity: validate]`

  1. Prime: T1.1; `docs/evolution/inbox-cost-log.md`; `scripts/measure-inbox-phase-b-token-cost.py --help`; memory notes "sync before any live walk", "reset tomo-tmp before a live run" `[ref: PRD/Success Metrics; How each criterion is verified]`
  2. Test: n/a (measurement). Checklist: a fixed inbox set of 10–12 items, **including one seeded item** whose obvious new-MOC proposal is an existing MOC's name (for F3-AC1), copied to `tomo-instance/spec-040-baseline/inbox-set/`; `tomo-instance` on current `main`; **two** before-runs on the same set; per run record run id, per-item union of `candidate_mocs` paths with `pre_check`, proposed MOC names, T1.1 scanner output, per-item cache-write tokens and $
  3. Implement: owner runs `/inbox` twice; per-item details to `tomo-instance/spec-040-baseline/before-{1,2}.json`; counts, agreement between the two before-runs, and cost figures to `docs/XDD/specs/040-relevant-mocs-per-item/baseline.md` (no paths, no titles)
  4. Validate: both run ids in the cost log; inbox set archived
  5. Success: before-picture and run-to-run variance measured `[ref: PRD/KPIs Quality, Business Impact]`

- [x] **T1.3 MOC folder helper and exclude predicate** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: `tomo/config/vault-example.yaml:48-55`; `tomo/scripts/vault-scan.py:46-90` (the shapes of `concepts.map_note`); `lib/moc_scan.read_scope_paths` (why it is not reused); `lib/moc_tags.py`; `moc-tree-builder.py` `extract_tags` (tags arrive without `#` from frontmatter, inline form via `parse_inline_tags`) `[ref: SDD/ADR-5; SDD/Interface Specifications "lib/moc_tags.py", "lib/moc_folders.py"]`
  2. Test (RED — neither function exists): `moc_folder_prefixes` normalises `{paths:[...]}`, `{path: str}` and bare `str`; strips whitespace; adds trailing `/`; drops empties; missing key → `()`; `in_moc_folders` true for a nested path, false for `Atlas/200 Maps2/`; `is_excluded_moc` true for `MiYo/Tomo/exclude/moc`, `#MiYo/Tomo/exclude/moc`, `miyo/tomo/exclude/MOC`; false for `MiYo/Tomo/exclude/note`, `MiYo/Tomo/exclude/mocs`, `[]`, `None`
  3. Implement: `tomo/scripts/lib/moc_folders.py` (WHY docstring, `# version: 0.1.0`); `is_excluded_moc` in `lib/moc_tags.py` and its B-moc comment updated (superseded for inbox candidates by spec 040 ADR-5), version bumped; `docs/tomo/scripts/lib/moc_folders.md`
  4. Validate: RED → GREEN; ruff clean
  5. Success: one place decides "inside the MOC folders" and "excluded" `[ref: SDD/ADR-5]`

- [ ] **T1.4 Eligibility, names and placeholder targets in the builder** `[activity: backend-api]`

  1. Prime: `shared-ctx-builder.py` `build_mocs`, `build_placeholder_links`, `main`; `tomo/schemas/shared-ctx.schema.json`; every caller and test listed under SDD Implementation Gotchas (`generate.py:102-103`, `test_shared_ctx_no_accumulation.py:289-339`, `test_inbox_analyst_no_condition_b.py:190-248`, `test_shared_ctx_feature5.py`, `test_shared_ctx_moc_detection.py:61-80`, `test-shared-ctx-placeholders.py`, `test_shared_ctx_inventory.py:98-232`); spec 021 ADR-13 `[ref: SDD/ADR-1, ADR-5, ADR-7, ADR-9; SDD/Data Storage Changes]`
  2. Test:
     - RED: an entry tagged `MiYo/Tomo/exclude/moc` (each variant from T1.3) is absent from `mocs`; `exclude/note` alone stays; the six-row SDD example yields exactly its six names; every `name` is unique; `mocs` is sorted by path; `placeholder_targets` is present, sorted, unique, and `[]` for a cache with none; `placeholder_links` is not emitted; the schema validates a built context and rejects one with `placeholder_links` or without `placeholder_targets`
     - guard: an entry without `tags` is kept; classification MOCs keep `is_classification:true`; `/moc-propose`'s cache-based candidate pool still contains the excluded MOC (F5-AC2)
  3. Implement: `build_mocs(cache, moc_folders=())` filtering with `is_excluded_moc`, sorting, `assign_names`; `build_placeholder_targets`; `main` passes `moc_folder_prefixes(vault_cfg)`; schema edits (required `mocs[].name`, required root `placeholder_targets`, `placeholder_links` removed); update the callers and tests above deliberately, each with the reason in its docstring (including the "pure projector, not a filter" wording); regenerate `tests/fixtures/021-ac-baseline/` with the updated `generate.py` and record why in its README; add a one-line "superseded for inbox candidates by spec 040 ADR-5" note at spec 021 ADR-13 B-moc; bump the builder version
  4. Validate: RED assertions fail on `main` (swap in `git show main:` copies), pass here; full builder test set green; ruff clean
  5. Success: `[ref: PRD/F1-AC2, F1-AC3, F1-AC4, F1-AC7, F5-AC1, F5-AC2, S1-AC1]`

- [ ] **T1.5 Size guards replace budget shedding; summary line** `[activity: backend-api]`

  1. Prime: `shared-ctx-builder.py` `enforce_budget`, module docstring (`:15-18`, "≤ max-bytes"), summary print in `main`; `tests/test_shared_ctx_inventory.py:264-384`; `tests/test_tracker_config_durability.py:182-241`; `tests/test_shared_ctx_no_accumulation.py:143-252` (including `test_max_bytes_default_is_40960`); `tests/test-004-phase2.sh:161-193` (parses the summary line); `docs/tomo/scripts/shared-ctx-builder.md:81-118` `[ref: SDD/ADR-4; SDD/Interface Specifications "shared-ctx-builder.py"; PRD/C1]`
  2. Test:
     - RED: a 512-MOC synthetic cache (MOCs duplicated with distinct paths, as in #173) builds with every thematic MOC keeping the headings and callouts `build_mocs` gives it; a name list over `--max-bytes` produces one WARN line naming the read (`names`) and its size, and the file is still written; the summary line carries exactly the SDD's field list in order (`eligible`, `excluded`, `collisions`, `names_bytes`, `detail_bytes`, `placeholder_targets`; no `mocs_included`, `topics_dropped`, `placeholder_links`); `--max-bytes` default is 32768
     - guard: tracker keyword lists are never altered
  3. Implement: **first** rewrite the WHY in `docs/tomo/scripts/shared-ctx-builder.md` (why shedding existed, why it is gone, why guards sit at the single-read level); **then** remove the three shedding passes; add `size_guards`; new default and help text; module docstring; summary line; update the shedding-order tests to assert *no* shedding with the reason; adjust `test-004-phase2.sh` to the new fields; bump version
  4. Validate: RED on `main`, GREEN here; ruff clean
  5. Success: `[ref: PRD/F2-AC2, C1-AC1]`; `[ref: SDD/Quality Requirements; Fidelity]`

- [ ] **T1.6 Phase Validation** `[activity: validate]`

  - Full suite green (`./venv/bin/python -m pytest -q tests`), ruff clean. Build a context from `tomo-instance/config/discovery-cache.yaml` with `--skip-reconcile` into `$TMPDIR` and check it validates against the schema. Do **not** sync to the instance in this phase.
