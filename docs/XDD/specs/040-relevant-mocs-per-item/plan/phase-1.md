---
title: "Phase 1: Baseline run and builder"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Baseline run and builder

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-1]` — the delivered `name` and the collision rule
- `[ref: SDD/ADR-4]` — budget shedding removed, size guards
- `[ref: SDD/ADR-5]` — exclude filter, MOC folders
- `[ref: SDD/ADR-7]` — `placeholder_targets`
- `[ref: SDD/ADR-9]` — schema edits, golden baseline
- `[ref: SDD/Implementation Examples; "assigning names (traced)"]`
- `[ref: PRD/Success Metrics]` — the before/after bar

**Key Decisions**:
- The baseline run (T1.1) happens before anything from this branch is synced to `tomo-instance`. Once the instance carries new code, the "before" can no longer be measured.
- The builder keeps writing `mocs` (full detail) — only its cutting stops and `name` is added. Readers that still use `--field mocs` keep working until Phase 4 changes the prose; that keeps every phase shippable on its own.

**Dependencies**: none.

---

## Tasks

Records the "before" picture, then gives the context its new shape: eligible MOCs only, each with a delivered name, uncut detail, deduplicated placeholder targets, and size warnings instead of shedding.

- [ ] **T1.1 Baseline run on the test instance** `[activity: validate]` `[parallel: true]`

  1. Prime: `[ref: PRD/Success Metrics; Tracking Requirements]`; `docs/evolution/inbox-cost-log.md`; `scripts/measure-inbox-phase-b-token-cost.py --help`; memory notes "sync before any live walk", "reset tomo-tmp before a live run"
  2. Test: n/a (measurement). Checklist: a fixed inbox set of 10–12 items copied aside so the after-run uses the identical set; `tomo-instance` on current `main`; **two** before-runs on the same set (PRD Open Question: run-to-run variance); per run, record run id, per-item `candidate_mocs` paths with `pre_check`, proposed MOC names, Step-4 MOC read bytes and whether it spilled, per-item cache-write tokens and $
  3. Implement: owner runs `/inbox` twice on `tomo-instance`; results captured to `docs/XDD/specs/040-relevant-mocs-per-item/baseline.md` (metadata only: paths, names, numbers — no note content)
  4. Validate: both run ids present in the cost log; the inbox set is archived for the after-run
  5. Success: before-picture and variance measured `[ref: PRD/KPIs Quality, Business Impact]`

- [ ] **T1.2 MOC folder helper `lib/moc_folders.py`** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: `tomo/config/vault-example.yaml:48-55`; `tomo/scripts/vault-scan.py:50-80` (the three shapes of `concepts.map_note`); `lib/moc_scan.read_scope_paths` (why it is not reused) `[ref: SDD/ADR-5; SDD/Interface Specifications "lib/moc_folders.py"]`
  2. Test: `{paths:[...]}`, `{path: str}` and bare `str` all normalise; whitespace stripped (`"Atlas/200 Maps/ "`); trailing `/` added; empties dropped; missing `concepts.map_note` → `()`; `in_moc_folders` is prefix-true for a nested path and false for a sibling folder whose name merely starts the same (`Atlas/200 Maps2/`)
  3. Implement: `tomo/scripts/lib/moc_folders.py` with `moc_folder_prefixes`, `in_moc_folders`; file-level WHY docstring; `# version: 0.1.0`
  4. Validate: unit tests pass; ruff clean
  5. Success: one place decides "inside the MOC folders" `[ref: SDD/ADR-5]`

- [ ] **T1.3 Eligibility, names and placeholder targets in the builder** `[activity: backend-api]`

  1. Prime: `shared-ctx-builder.py:219-334, 780-910`; `lib/moc_tags.py`; `tomo/schemas/shared-ctx.schema.json`; `tests/test_shared_ctx_inventory.py:98-232`; `tests/test-shared-ctx-placeholders.py`; `tests/fixtures/021-ac-baseline/` + `generate.py` `[ref: SDD/ADR-1, ADR-5, ADR-7, ADR-9; SDD/Data Storage Changes]`
  2. Test (RED, prove against main): an entry tagged `MiYo/Tomo/exclude/moc` is absent from `mocs` (frontmatter and inline forms both arrive as `tags`); an entry without `tags` is kept; the six-row traced example from the SDD yields exactly the six names shown; every `name` is unique across `mocs`; classification MOCs keep `is_classification:true` and a bare-title name; `placeholder_targets` is sorted, unique, and drops non-MOC targets as today; `placeholder_links` is no longer emitted; the schema validates a built context and rejects one with `placeholder_links`
  3. Implement: `build_mocs(cache, moc_folders)` filters on `EXCLUDE_MOC_TAG`; `assign_names` per the SDD data model; `build_placeholder_targets`; schema adds required `mocs[].name` and `placeholder_targets`, removes `placeholder_links`; `lib/moc_tags.py` comment on B-moc says it is superseded for inbox candidates by spec 040; regenerate `tests/fixtures/021-ac-baseline/` with `generate.py` and record the reason in its README; update `test-shared-ctx-placeholders.py` deliberately; bump versions
  4. Validate: new tests RED on main, GREEN here; `test_shared_ctx_no_accumulation.py` green against the regenerated baseline; ruff clean
  5. Success: `[ref: PRD/F1-AC2, F1-AC3, F1-AC4, F1-AC7, F5-AC1, S1-AC1]`; `/moc-propose` tests unchanged and green `[ref: PRD/F5-AC2]`

- [ ] **T1.4 Size guards replace budget shedding; summary line** `[activity: backend-api]`

  1. Prime: `shared-ctx-builder.py:694-765, 875-905`; `tests/test_shared_ctx_inventory.py:264-384`; `tests/test_tracker_config_durability.py:183-241`; `tests/test_shared_ctx_no_accumulation.py:143-195`; `tests/test-004-phase2.sh:115-191`; `docs/tomo/scripts/shared-ctx-builder.md:81-118` `[ref: SDD/ADR-4; PRD/C1]`
  2. Test (RED): a 512-MOC synthetic cache (MOCs duplicated with distinct paths, as in #173) builds with every thematic MOC keeping the same headings and callouts it has before any budget step; a name list over `--max-bytes` produces one WARN line naming the read and its size, and the file is still written; the summary line carries `eligible`, `excluded`, `collisions`, `names_bytes`, `detail_bytes`, `placeholder_targets`; tracker keyword lists are never altered (keep that guarantee)
  3. Implement: remove the three shedding passes; add `size_guards(ctx, max_bytes)` for the names list, the Step-1 batch, the placeholder targets and 20 × largest MOC entry; `--max-bytes` default 32768 with new help text; extend the summary line; rewrite (not delete) the WHY in `docs/tomo/scripts/shared-ctx-builder.md` — why shedding existed, why it is gone, why the guards sit at the single-read level; update the shedding-order tests to assert *no* shedding, with the reason in their docstrings; adjust `test-004-phase2.sh` expectations; bump version
  4. Validate: RED on main for the no-shedding and summary tests; full builder test set green; ruff clean
  5. Success: `[ref: PRD/F2-AC2, C1-AC1]`; `[ref: SDD/Quality Requirements; Fidelity]`

- [ ] **T1.5 Phase Validation** `[activity: validate]`

  - Full suite green (`./venv/bin/python -m pytest -q tests`), ruff clean. The analyst still reads `--field mocs` at this point and still gets a valid (larger) list — confirm by building a context from `tomo-instance/config/discovery-cache.yaml` with `--skip-reconcile` into `$TMPDIR` and checking `--field mocs` resolves. Do **not** sync to the instance in this phase.
