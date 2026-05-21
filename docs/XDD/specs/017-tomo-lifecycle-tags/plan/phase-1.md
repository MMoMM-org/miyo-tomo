---
title: "Phase 1: State Machine, Schema, and Kado Client Foundation"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: State Machine, Schema, and Kado Client Foundation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Solution Strategy]` — layered producer/consumer + shared state-machine
- `[ref: SDD/Building Block View/Components]` — Shared Libraries box (`tomo_lifecycle.py`, `kado_client.py`, schema)
- `[ref: SDD/Application Data Models; lines: 498-592]` — STATE_MACHINE constant + module function signatures
- `[ref: SDD/Internal API Changes; lines: 462-496]` — KadoClient.write_frontmatter / search_by_frontmatter signatures
- `[ref: SDD/Implementation Examples; lines: 624-758]` — byFrontmatter call shape, state-flip walkthrough, schema round-trip tests
- `[ref: SDD/Architecture Decisions/ADR-1, ADR-2, ADR-4]` — pure-data state machine, additive KadoClient API, jsonschema validation strategy
- `[ref: PRD/Feature 7]` — state-machine module + schema validation
- `[ref: PRD/AC-6.1, AC-7.1, AC-7.2, AC-3.4]` — wrapper convergence, single state-machine SoT, schema enforcement, transition rejection

**Key Decisions**:
- **ADR-1**: STATE_MACHINE is a plain dict-of-dicts; `validate_transition()` is a single lookup. No class hierarchy, no `transitions` library.
- **ADR-2**: `write_frontmatter` and `search_by_frontmatter` are NEW methods on the existing `KadoClient` — additive only; no existing call sites in this phase.
- **ADR-4**: Schema validation is dual-mode. Dev (`TOMO_SCHEMA_STRICT=1`) raises `SchemaValidationError`; prod (unset) emits stderr warning and lets the write through.
- **Constitution L2 Code Quality**: state-machine logic lives in **one** module and is imported everywhere — no duplication across producers/consumers.

**Dependencies**:
- None — this phase establishes foundations consumed by Phases 2-6.
- Tasks T1.1, T1.2, T1.3 are independent; can run in parallel.

---

## Tasks

This phase ships the three load-bearing libraries that every later phase consumes: the state-machine module, the `tomo:` block schema + helper, and the Kado client extensions. **No production caller changes yet** — those land in Phase 2 onward. Phase 1 must be additive enough that merging it alone causes zero behaviour change to a running `/inbox`.

- [ ] **T1.1 State machine module `tomo_lifecycle.py`** `[parallel: true]` `[activity: domain-modeling]`

  1. Prime: Read SDD Application Data Models STATE_MACHINE definition `[ref: SDD/Application Data Models; lines: 500-560]`. Read README Decisions Log entries for the 5 doc-types and their locked terminal states (`source.captured`, `suggestions.approved`, `suggestions-fan.approved`, `moc-proposal.accepted`, `instructions.applied`). Read SDD ADR-1 rationale `[ref: SDD/Architecture Decisions/ADR-1; lines: 1075-1078]`.
  2. Test: `tests/test_tomo_lifecycle.py::test_suggestions_pending_to_approved_legal`; `test_suggestions_pending_to_applied_rejected` (cross-doc-type transition rejected); `test_moc_proposal_pending_to_accepted_legal`; `test_instructions_pending_to_applied_legal`; `test_source_terminal_no_outgoing`; `test_suggestions_fan_pending_to_approved_legal` (XDD 012 doc_type added); `test_unknown_doc_type_returns_false`; `test_is_pending_returns_true_for_pending_prefix`; `test_is_pending_returns_false_for_terminal`.
  3. Implement: Create `tomo/scripts/lib/tomo_lifecycle.py` with `# version: 0.1.0`. Constants: `STATE_MACHINE` dict-of-dicts covering all 5 doc-types (`source`, `suggestions`, `suggestions-fan`, `moc-proposal`, `instructions`) with `initial`, `states`, `transitions` (list of `{from, to, trigger}` dicts), `terminal`. Functions: `validate_transition(doc_type: str, from_state: str | None, to_state: str) -> bool`; `is_terminal(doc_type: str, state: str) -> bool`; `is_pending(state: str) -> bool` (returns `state.startswith("pending-")`). Stdlib only — no new deps. Module docstring explaining ADR-1.
  4. Validate: `pytest tests/test_tomo_lifecycle.py -v`; `ruff check tomo/scripts/lib/tomo_lifecycle.py`; `python3 -c "from lib.tomo_lifecycle import STATE_MACHINE; assert 'suggestions-fan' in STATE_MACHINE"`.
  5. Success: All 5 doc-types covered, all locked transitions accepted, every cross-doc-type / illegal transition rejected `[ref: PRD/AC-3.4, AC-7.1]` `[ref: SDD/ADR-1]`. `suggestions-fan` doc_type present `[ref: SDD/Cross-Spec Coordination; lines: 962-970]`.

- [ ] **T1.2 `doc-frontmatter.schema.json` + `doc_frontmatter.py` helper** `[parallel: true]` `[activity: schema-design]`

  1. Prime: Read SDD Data Storage Changes `[ref: SDD/Data Storage Changes; lines: 434-458]` for the `tomo:` block shape. Read existing `tomo/schemas/instructions.schema.json` for jsonschema-draft-07 conventions and `additionalProperties` discipline. Read SDD ADR-4 dual-mode rationale `[ref: SDD/Architecture Decisions/ADR-4; lines: 1090-1093]`. Confirm `jsonschema` is already on Tomo's Python deps (else add to install requirements).
  2. Test: `tests/test_doc_frontmatter.py::test_build_tomo_block_minimum_fields` (auto-sets `updated_at`); `test_build_tomo_block_with_source_suggestions_ref` (instructions doc); `test_build_tomo_block_with_source_moc_proposal_ref` (MOC instructions doc); `test_build_tomo_block_with_source_suggestions_fan_ref` (XDD 012 fan-resolve instructions); `test_invalid_state_for_doc_type_rejected_dev_mode` (e.g. suggestions + state=applied → SchemaValidationError when `TOMO_SCHEMA_STRICT=1`); `test_invalid_state_warning_only_prod_mode` (same input, env unset → stderr warning, no raise); `test_parse_tomo_block_returns_none_when_absent`; `test_parse_tomo_block_returns_dict_when_present`; `test_round_trip_preserves_all_fields` (build → serialize → parse → equal). Use `monkeypatch.setenv` for env-flag tests.
  3. Implement: Create `tomo/schemas/doc-frontmatter.schema.json` (Draft-07) describing the `tomo:` block — required fields `doc_type`, `state`, `run_id`, `updated_at`; optional `source_*` keys (pattern `^source_[a-z_]+$`); `state` enum tied to `doc_type` via `oneOf` branches (one per doc-type, each constraining `state` to that doc-type's allowed values). Create `tomo/scripts/lib/doc_frontmatter.py` with `# version: 0.1.0`: `build_tomo_block(doc_type, state, run_id, **source_refs) -> dict` (auto-sets `updated_at = datetime.utcnow().isoformat() + "Z"`, validates against schema via `jsonschema.validate`, env-flag-driven raise vs warn); `parse_tomo_block(frontmatter: dict) -> dict | None` (returns the `tomo` sub-dict or `None`); `SchemaValidationError` exception class; `_SCHEMA_PATH = "tomo/schemas/doc-frontmatter.schema.json"` (resolved relative to repo root via `pathlib`). Module loads schema once on import.
  4. Validate: `pytest tests/test_doc_frontmatter.py -v`; `python3 -m jsonschema -i <(echo '{"tomo":{"doc_type":"suggestions","state":"pending-approval","run_id":"r","updated_at":"2026-05-21T00:00:00Z"}}') tomo/schemas/doc-frontmatter.schema.json` exits 0; same with `state=applied` exits non-zero; `ruff check tomo/scripts/lib/doc_frontmatter.py`.
  5. Success: Every valid `tomo:` block per the locked schema passes; every illegal state-for-doc-type combination is caught in dev mode and warned in prod mode `[ref: PRD/AC-1.5, AC-7.2]` `[ref: SDD/ADR-4]`. `source_*` extensibility verified for future F-44/45/46 doc-types (test passes when an unknown `source_garden_audit` key is supplied — schema permits the pattern).

- [ ] **T1.3 `KadoClient` extensions: `write_frontmatter` + `search_by_frontmatter`** `[parallel: true]` `[activity: api-development]`

  1. Prime: Read existing `tomo/scripts/lib/kado_client.py` end-to-end to understand `_call_tool()` shape, error mapping, `_unwrap_sse()`, and how `read_frontmatter` is structured (the natural sibling to the new `write_frontmatter`). Read `_inbox/from-kado/2026-05-21_kado-to-tomo_frontmatter-write-shipped-plus-bonus.md` for BOTH `kado-write operation=frontmatter` merge semantics (arrays replace, scalars replace, untouched keys preserved) AND `kado-search operation=byFrontmatter` query syntax + `filter.path` / `filter.modifiedAfter`. (The earlier 2026-05-20 notice that originally split these is rolled into the 2026-05-21 follow-up.) Read SDD Implementation Examples discover_pending + flip_state `[ref: SDD/Implementation Examples; lines: 624-707]`.
  2. Test: `tests/test_kado_client_frontmatter.py::test_write_frontmatter_merge_mode_call_shape` (mock `_call_tool`, assert JSON-RPC payload includes `operation=frontmatter`, `mode=merge`, the supplied dict, and `expected_modified` when given); `test_write_frontmatter_replace_mode_call_shape`; `test_write_frontmatter_concurrency_error_raises_KadoConcurrencyError` (mock returns Kado's `expectedModified` conflict shape → wrapper raises typed error); `test_search_by_frontmatter_query_call_shape` (verifies `operation=byFrontmatter`, `query` string, optional `filter.path`, optional `filter.modifiedAfter`); `test_search_by_frontmatter_returns_list_of_path_modified_frontmatter` (mock returns SSE shape; wrapper returns normalised list of dicts); `test_search_by_frontmatter_default_limit_is_500`. Mock `requests.post` / `_call_tool` — no live Kado in unit tests.
  3. Implement: Extend `tomo/scripts/lib/kado_client.py` (bump `# version:`) with two new methods on the `KadoClient` class: `write_frontmatter(self, path: str, frontmatter: dict, mode: str = "merge", expected_modified: int | None = None) -> dict` — wraps `kado-write operation=frontmatter`, returns `{path, modified}`; raises `KadoConcurrencyError` (new exception class, inherits from `KadoToolError`) on `expectedModified` mismatch; `search_by_frontmatter(self, query: str, *, path_prefix: str | None = None, modified_after: int | None = None, limit: int = 500) -> list[dict]` — wraps `kado-search operation=byFrontmatter`, returns list of `{path, modified, frontmatter}`. Both methods use the existing `_call_tool` plumbing + `_unwrap_sse`. DO NOT modify any existing call site of `KadoClient` — additive only.
  4. Validate: `pytest tests/test_kado_client_frontmatter.py -v`; `pytest tests/ -v` (no regression in pre-existing kado_client tests); `ruff check tomo/scripts/lib/kado_client.py`; `python3 -c "from lib.kado_client import KadoClient, KadoConcurrencyError"`.
  5. Success: Wrapper sends correctly-shaped JSON-RPC payloads `[ref: PRD/AC-6.1]` `[ref: SDD/ADR-2]`. Optimistic-concurrency error surfaces as a typed `KadoConcurrencyError` so callers can retry-once without parsing strings `[ref: SDD/Implementation Examples; lines: 690-697]`. `filter.path` server-side narrowing supported for AC-2.4 server-side scope discipline `[ref: PRD/AC-2.4]`.

- [ ] **T1.4 Phase 1 Validation** `[activity: validate]`

  Run `pytest tests/test_tomo_lifecycle.py tests/test_doc_frontmatter.py tests/test_kado_client_frontmatter.py -v`. Run `pytest tests/ -v` to confirm zero regressions in existing tests. Run `ruff check tomo/scripts/lib/`. Run `python3 -c "from lib.tomo_lifecycle import validate_transition, is_pending, is_terminal; from lib.doc_frontmatter import build_tomo_block, parse_tomo_block, SchemaValidationError; from lib.kado_client import KadoClient, KadoConcurrencyError"` — all imports succeed. Run `python3 -m jsonschema -i` against three crafted fixtures (suggestions/pending-approval, instructions/pending-apply, source/captured) — all pass; one negative fixture (suggestions/applied) — fails. Run `./scripts/update-tomo.sh` and confirm the three new module files plus the schema are present in `tomo-instance/` (per `feedback_bump_version_on_managed_file_edit.md` — ensure all three carry a `# version:` and the schema is referenced by relative path).
