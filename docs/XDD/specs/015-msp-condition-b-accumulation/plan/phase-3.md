---
phase: 3
title: "Persistence + shared-ctx surface"
status: pending
---

# Phase 3: Persistence + shared-ctx surface

## Phase Context

**GATE**: Read all referenced files before starting.

**Specification References**:
- `[ref: SDD/Data Storage Changes]` — `unclassified_topic_clusters` + `accumulation_index` shapes
- `[ref: SDD/Internal Interfaces]` — `build_accumulation_index()`
- `[ref: SDD/Architecture Decisions/ADR-7]` — additive at `cache_version: 1`
- `[ref: PRD/A1, A2, A4, A6]` — cache field, shared-ctx surface, budget trim, empty-vault omit

**Key Decisions**: mirror the F-35 `placeholder_mocs` lift (cache-builder) and pass-through
(shared-ctx) exactly. `enforce_budget` gains an accumulation trim pass (A4). Additive — no
`cache_version` bump (ADR-7).

**Dependencies**: Phase 2 (the `{topic:[stems]}` JSON the scanner emits).

## Tasks

### T3.1 — `cache-builder` ingests the accumulation index `[activity: backend-data]`

1. **Prime**: Read `tomo/scripts/cache-builder.py` — `build_parser()` args (`--structure`, `--mocs`, `--orphans`), `load_json()`, and the `cache[...] = ...` assembly block (where `placeholder_mocs` is lifted). Read `[ref: SDD/Data Storage Changes]`.
2. **Test**: `tests/test_cache_builder_accumulation.py`: `test_accumulation_arg_lifts_clusters_onto_cache` (`--accumulation file` → `cache["unclassified_topic_clusters"]` equals file contents); `test_accumulation_absent_yields_empty_dict` (no arg → `{}`, A6); `test_cache_version_unchanged` (stays `1`, ADR-7); `test_malformed_accumulation_json_degrades_to_empty` (drift guard).
3. **Implement**: Extend `tomo/scripts/cache-builder.py`. Add optional `--accumulation PATH`; `load_json` it when present; set `cache["unclassified_topic_clusters"] = data or {}`. Default `{}` when arg absent. Additive — existing args/outputs unchanged.
4. **Validate**: `pytest tests/test_cache_builder_accumulation.py -v`; `ruff check tomo/scripts/cache-builder.py`; build a cache from fixtures, assert the field present + `cache_version: 1`.
5. **Success**: Field lifted onto cache `[ref: PRD/A1]`; absent → `{}` `[ref: PRD/A6]`; no version bump `[ref: SDD/ADR-7]`.

### T3.2 — shared-ctx surfaces + budget-trims the index `[activity: backend-data]`

1. **Prime**: Read `tomo/scripts/shared-ctx-builder.py` — `build_placeholder_mocs()` (the copy-template, ~229-250), `main()` conditional-add + stderr log (~678-706), `enforce_budget()` pass structure (~540-600). Read `tomo/schemas/shared-ctx.schema.json`. Read `[ref: SDD/Internal Interfaces]` and `[ref: PRD/A2, A4]`.
2. **Test**: `tests/test_shared_ctx_accumulation.py`: `test_build_accumulation_index_passthrough`; `test_build_accumulation_index_empty_when_absent` (A6); `test_build_accumulation_index_drift_guard` (non-dict → `{}`); `test_main_omits_field_when_empty` (no `accumulation_index` key in output, A2/A6); `test_main_includes_field_when_present` (A2); `test_enforce_budget_drops_smallest_clusters_first` (over-budget fixture → smallest dropped, alphabetical tiebreak, A4); `test_enforce_budget_logs_total_and_kept` (stderr `accumulation_clusters_total=N accumulation_clusters_kept=K`). Validate output against `shared-ctx.schema.json`.
3. **Implement**: Extend `tomo/scripts/shared-ctx-builder.py` (bump `# version:`). Add `build_accumulation_index(cache) -> dict` (mirror `build_placeholder_mocs` drift guard). In `main()`: `accumulation_index = build_accumulation_index(cache)`; `if accumulation_index: ctx["accumulation_index"] = accumulation_index`. Add a trim pass to `enforce_budget` AFTER the existing passes: drop clusters tail-first by smallest member-count, alphabetical tiebreak, until `<= max_bytes`; surface counts to the stderr log line. Update `tomo/schemas/shared-ctx.schema.json` with the optional `accumulation_index` field (object, additionalProperties = array of strings).
4. **Validate**: `pytest tests/test_shared_ctx_accumulation.py -v`; `ruff check tomo/scripts/shared-ctx-builder.py`; `python3 -m jsonschema -i <built shared-ctx> tomo/schemas/shared-ctx.schema.json` exits 0 both with and without the field; confirm a no-index run is byte-identical to pre-change (CON-1).
5. **Success**: Non-empty index surfaced, empty omitted `[ref: PRD/A2, A6]`; over-budget trims tail-first with logged counts `[ref: PRD/A4]`; schema accepts both shapes.
