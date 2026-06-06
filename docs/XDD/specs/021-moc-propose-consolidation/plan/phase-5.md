---
title: "Phase 5: Usable whole-vault scan (orphan-only, cache-sourced) + cap reframe"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: Usable whole-vault scan (orphan-only, cache-sourced) + cap reframe

## Phase Context

**GATE**: Read before starting.

**Specification References**:
- `[ref: SDD/ADR-11]` — scan = cache-sourced orphans; scoped = all; cap default 500; Phase-2 topic-index incl. note entries
- `[ref: PRD/Feature 6; M1, M9]`
- `[ref: SDD/Runtime View Primary Flow scan]`

**Key Decisions** (ADR-11, user-confirmed 2026-06-06):
- `scan` mode → candidates = `cache.entries[kind=="note", up_state=="absent"]` (orphans), cache-sourced; NO live `list_dir`.
- Scoped modes (`folder`/`tag`/`class`/`title`) → ALL in-scope notes (orphan-filter is scan-only).
- `candidate_cap` default 200 → 500; counts the (orphan-filtered for scan) set; abort message unchanged.
- Phase-2 `_build_topics_index` indexes `cache.entries` (incl. `kind==note`) → scan candidates carry topics from the cache (no per-candidate LLM extraction).

**Why this phase** (post-live-validation, 2026-06-06): a plain `/moc-propose` aborted `candidate-cap-exceeded` (209 atomic notes > 200) because Phase 1 counted *every* note incl. the 70 already MOC-linked. The cap measured vault size, not "notes needing a MOC". Fold the fix into 021 rather than shipping a feature that aborts on any mature vault.

**Dependencies**: Phases 1–4 (the cache carries `kind==note` entries with `up_state` + `topics` — verified on the real vault: 276 note entries, 206 absent).

---

## Tasks

- [ ] **T5.1 `scan` = cache-sourced orphans + Phase-2 topic-index over note entries + cap default** `[activity: backend-api]` `[ref: SDD/ADR-11; PRD/F6; moc-discovery.py:495 _handle_scan, :547 phase1_select_candidates, :644 _build_topics_index, :583 cap]`
  1. Prime: `_handle_scan` (`:495`, live `list_dir`), `phase1_select_candidates` (`:547`, receives `cache`), `restrict_to_atomic_note_paths` (`:515`), `_build_topics_index` (`:644`, indexes `map_notes` only), the `candidate_cap` default (`:583`), `Candidate` dataclass (`:353`, has `topics`), `_candidate_from_path` (`:382`). Confirm cache entry shape (`kind`, `up_state`, `topics`, `path`, `stem`, `title`).
  2. Test (RED) — extend the moc-discovery Phase-1/Phase-2 test suite:
     - scan mode: candidates == `entries[kind=="note" and up_state=="absent"]` (orphans); a `valid` and a `broken` note are EXCLUDED; assert NO `kado_client.list_dir` call in scan (spy/fake client records calls → 0 for the atomic-note scan path).
     - scan candidates arrive with `topics` populated from the cache (no empty-topics / no LLM-extraction path triggered).
     - scoped modes (`folder`/`tag`/`class`/`title`): UNCHANGED — all in-scope notes considered (a `valid` note in the folder is STILL a candidate). Regression guard.
     - `_build_topics_index` indexes note entries: a `kind==note` path resolves to its cached topics (was a miss against `map_notes`).
     - cap: default is 500; orphan set of 501 → `candidate-cap-exceeded`; 500 → passes.
  3. Implement: thread `cache` into `_handle_scan`; in scan, build Candidates from `cache.entries[kind=="note", up_state=="absent"]` carrying `topics`/`stem`/`title` (skip the live `list_dir`). Keep scoped handlers live + all-notes. Extend `_build_topics_index` to index `cache.entries` (notes + mocs), not only `map_notes`. Raise `candidate_cap` default 200 → 500. Ensure the orphan-filter is applied ONLY for `mode=="scan"` (scoped modes keep `restrict_to_atomic_note_paths` over all candidates, no up_state filter). Bump `# version:` on moc-discovery.py.
  4. Config: raise `tomo.moc_proposal.candidate_cap` default to 500 in `tomo/config/vault-example.yaml` (+ instance) and update the `--candidate-cap` help string. Bump version where edited.
  5. Validate: `./venv/bin/python -m pytest <moc-discovery scan/phase tests> -v`; full suite (only 8 pre-existing ide_bridge); `ruff check`.
  6. WHY → update `docs/tomo/scripts/moc-discovery.md` (or create) + `docs/tomo/scripts/lib/moc_cache_loader.md` scan-mode note (supersede the "kept live list_dir" rationale). CON-4: imperatives only in runtime.
  7. Success: scan = orphans cache-sourced, no live pull `[ref: PRD/AC F6#1-2, M1, M9]`; scoped = all `[ref: F6#3]`; cap 500 `[ref: F6#4]`; topics from cache `[ref: F6#5]`.

- [ ] **T5.2 Phase 5 validation + live runbook refresh** `[activity: validate]`
  - Full `pytest` + lint under the venv. Confirm: scan selects orphans only with 0 live `list_dir`; scoped selects all; cap default 500; Phase-2 resolves note topics from cache. Update `LIVE-VALIDATION-RUNBOOK.md` (and M9): a plain `/moc-propose` on the real vault now proposes from the ~206 orphans (no `candidate-cap-exceeded`), and document the scoped-run behaviour. Re-confirm no A/C regression (golden baseline) and Phases 1–4 suites stay green.
