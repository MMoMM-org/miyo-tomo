# F-43 Integration Test Suite — Producer-Side E2E

## Overview

This directory contains producer-side end-to-end (E2E) integration tests for the `/moc-propose` pipeline (F-43, spec `013-moc-creation-skill`).

**Scope decision (locked 2026-05-08):** Producer-side only. Tests assert Tomo's pipeline:

```
moc-discovery.py (discovery phases)
  → suggestions-reducer.py --moc-proposal-mode (proposal-doc render)
    → suggestion-parser.py (parse accepted proposal)
      → instruction-render.py (emit create_moc + add_relationship actions)
```

Tests do **not** spawn Hashi or run Obsidian. Hashi-side correctness is covered by Hashi 0.2.0's own contract tests + manual T6.2 live-vault validation.

## How to Run

```bash
# All integration tests
pytest tests/integration/ -v -m integration

# Performance subset only
pytest tests/integration/ -v -m "integration and perf"

# Full suite (integration + unit), including untagged env-invariant test
pytest tests/integration/ -v

# Skip integration tests (unit suite only)
pytest tests/ -v -m "not integration"
```

## Test Inventory

| Test | PRD AC | Description |
|------|--------|-------------|
| `test_privat_test_reachable` | — | Env invariant: Privat-Test is mounted and has ≥3 Dataview notes |
| `test_tag_mode_e2e` | AC-1.1, AC-3.1–3.3 | `tag:` mode produces correct proposal-doc |
| `test_folder_mode_e2e` | AC-1.2 | `folder:` mode produces correct proposal-doc |
| `test_class_mode_e2e` | AC-1.3, AC-2.1, AC-2.3 | `class:` mode with Dewey classification |
| `test_title_mode_e2e` | AC-1.4, AC-2.5 | `title:` mode — verbatim user title with profile suffix |
| `test_freetext_e2e` | AC-1.5, AC-1.7 | free-text input (no recognised prefix) |
| `test_no_args_e2e` | AC-1.6, AC-3.4 | whole-vault scan — multi-cluster, overflow footer |
| `test_zero_candidates_aborts_no_file_written` | AC-3.5 | abort path: 0 candidates |
| `test_cache_empty_aborts_no_file_written` | AC-3.5 | abort path: cache missing/empty |
| `test_override_flow_e2e` | AC-4.2, AC-4.4 | Override checkbox rendering + parsing |
| `test_collision_guard_e2e` | F6 / AC-6.1 | Pre-existing destination file stays untouched |
| `test_squelch_e2e` | AC-8.1, AC-8.2 | Propose → reject → 3× suppress → 4th re-allow |
| `test_accept_flow_emits_create_moc_action` | AC-5.3 | Full pipeline → `create_moc` action with `applied: false` |
| `test_no_accept_emits_no_actions` | AC-5.4 | No Accept ticked → parser returns [] |
| `test_multi_cluster_partial_accept` | AC-3.4, AC-5.3 | 1 of 2 clusters accepted → 1 proposal |
| `test_perf_cache_warm_under_45s` | SDD Quality | Cache-warm dry-run < 45s (1.5× SDD target 30s) |
| `test_perf_pass2_apply_under_25s` | SDD Quality | Render+parse+build_actions < 25s (1.5× SDD target 15s) |
| `test_perf_multi_cluster_render_under_8s` | SDD Quality | 5-cluster render ×3 < 8s (1.5× SDD target 5s) |

## Privat-Test Invariants Required

Tests that use the `privat_test_clone` fixture require:

- `/Volumes/Moon/Coding/MiYo/temp/Privat-Test/` is mounted and readable
- `Atlas/202 Notes/2611 Code Snippets/` contains ≥3 notes matching `Dataview - *.md`
- `Atlas/200 Maps/` exists (can be empty for non-collision tests)
- `100 Inbox/` exists (can be empty)

The `privat_test_clone` fixture copies a small slice into a `tmp_path`/vault subdirectory.  
The real Privat-Test directory is **never mutated** — all writes go to `tmp_path`.

## 1.5× CI Tolerance Rationale

Performance targets in the SDD are measured against Marcus's local development machine (Apple Silicon, fast SSD, warm Python interpreter). CI runners (GitHub Actions `macos-latest` or Linux `ubuntu-latest`) are typically 1.5-3× slower due to:

- Cold Python interpreter startup on each subprocess call
- Shared CI runner resources (CPU throttling, memory pressure)
- Network filesystem latency when running on mounted volumes

The 1.5× CI tolerance is set conservatively:

| SDD Target | CI Tolerance | Regression Threshold |
|------------|-------------|---------------------|
| Cache-warm < 30s | < 45s | > 45s = fail |
| Pass-2 apply < 15s | < 25s | > 25s = fail |
| 5-cluster render < 5s | < 8s | > 8s = fail |

A test that consistently needs > 2× the SDD target is a signal of a real performance regression, not runner variability.

To run perf tests and measure wall-clock on your machine:

```bash
pytest tests/integration/ -v -m "integration and perf" -s
```

The `-s` flag lets you see the `time.perf_counter` timing output in test assertions.

## Scope: Out of Scope (Hashi)

The following behaviours are **not tested here** and are covered by Hashi 0.2.0's contract tests and manual T6.2:

- `create_moc` action execution (Hashi creates the MOC in `Atlas/200 Maps/`)
- `add_relationship` / `link_to_moc` application to vault notes
- Destination-exists collision returning `applied: false` from Hashi
- `up::` / `related::` field mutations on child notes in the vault

These tests verify that Tomo emits the **correct shapes** — Hashi verifies correct **execution**.
