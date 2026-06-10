---
phase: 5
title: "Integration & live validation"
status: completed
---

# Phase 5: Integration & live validation

## Phase Context

**GATE**: Read all referenced files before starting. Phases 1–4 complete.

**Specification References**:
- `[ref: PRD/A8]` — E2E smoke test against a test vault
- `[ref: PRD/Validation hooks §11]` — Privat-Test, real-vault latency, empty-vault, budget stress, conflict-precedence
- `[ref: SDD/Deployment View]` + `[ref: SDD/Constraints/CON-5]` — Kado `listNotes` release gate
- `[ref: PRD/§7 Success signals]` — no Pass-1 cost regression vs F-32

**Key Decisions**: T5.1 (fixture E2E) runs now against fakes/fixtures. T5.2 (live) is
**GATED on the Kado `listNotes` release** reaching the Tomo instance's Kado (CON-5) — do not
block plan completion on it.

**Dependencies**: Phases 1–4.

## Tasks

### T5.1 — End-to-end pipeline integration test `[activity: testing]`

1. **Prime**: Read all four pipeline stages' public entry points. Read `[ref: PRD/A8]` and the SDD traced walkthrough. Read memory `feedback_fixture_from_live_render` (fixtures mirror real output) and `feedback_mock_at_orchestrator_not_helper` (test through the public entry point).
2. **Test**: `tests/test_f34_e2e.py`: drive a fixture vault (fake `KadoClient` returning a known `listNotes` set + `dataview-inline-field` map) through scanner → `cache-builder` → `shared-ctx-builder` → assert `accumulation_index` content; then feed that shared-ctx to the Step-4 contract check and assert a Condition-B `needs_new_moc` for a matching item. Include: the SDD traced-walkthrough vault (search/games clusters); an empty vault (A6 — byte-identical, no field); a budget-stress vault (A4 — trimming + log); a conflict vault (placeholder + accumulation on one item → C wins, A7).
3. **Implement**: Test code + fixtures only (no product code — all built in P1–P4). Fixtures live in `tests/fixtures/f34/`.
4. **Validate**: `pytest tests/test_f34_e2e.py -v`; full suite `pytest tests/ -q` green; `ruff check`.
5. **Success**: Full pipeline produces correct proposals end-to-end `[ref: PRD/A8]`; all four scenarios pass `[ref: PRD/§11]`.

### T5.2 — Live validation against real vault `[activity: validation]` `[GATED: Kado listNotes release]`

1. **Prime**: Confirm the Tomo instance's Kado exposes `listNotes` (Kado branch `feat/listnotes-search-op` merged + released + instance updated — CON-5). If not yet available, STOP and record the block; the rest of the plan is shippable without this task.
2. **Test**: Manual/scripted live run — `/explore-vault` against `Privat-Test/` (known cluster) then Marcus's real ~281-note vault.
3. **Implement**: (a) Run `/explore-vault`; confirm `discovery-cache.yaml.unclassified_topic_clusters` is populated and plausible. (b) Measure added `/explore-vault` latency (real-vault cost — PRD §11). (c) Run `/inbox` with an item matching a known cluster; confirm a Proposed-MOC suggestion appears (PRD §7 boardgames-style signal). (d) Confirm `/inbox` Pass-1 token cost shows no regression vs F-32 baseline (use `scripts/measure-*`/`tomo-session-stats.py` — memory `reference_token_cost_measurement_tool`, `reference_inbox_cost_log`).
4. **Validate**: live cluster surfaces a real proposal `[ref: PRD/§7]`; no Pass-1 cost amplification `[ref: PRD/§7, §10]`; attach the live-validation result to backlog F-34.
5. **Success**: Condition B fires on the real vault without intervention `[ref: PRD/§7]`; MSP feature (A+B+C) end-to-end complete; F-34 marked code-complete with live result.

> **Plan completion note:** Phases 1–4 + T5.1 are fully implementable and verifiable now.
> T5.2 is the only Kado-release-gated item — track it as the final live gate, not a blocker
> for merging the implementation behind the additive guards (CON-1: no-index ⇒ today's behaviour).

---

## T5.2 status — DEFERRED (user-driven live validation)

- **Kado gate: OPEN.** Per `_inbox/from-kado/2026-06-04_kado-to-tomo_listnotes-inline-fields-decision.md`,
  `listNotes` and `kado-read operation="dataview-inline-field"` both already ship in the
  current Kado; no Kado change is pending. The scanner's per-candidate `dataview-inline-field`
  classification path (ADR-5 / A5) is confirmed correct and "locked" by that decision.
- **Why deferred:** T5.2 is a live run of `/explore-vault` + `/inbox` against the real ~281-note
  vault inside the Tomo Docker instance + cost comparison via `tomo-session-stats.py`. It must be
  executed by the user in the runtime instance (host dev session cannot reach the vault/container).
  Consistent with the "test scope = personal vault" pre-launch rule.
- **Open question to watch during the live run:** SDD Risk §2 — whether `dataview-inline-field`
  returns **callout-embedded** `up::`. If it does NOT, A5 needs a fallback and the SDD must record it.
- **Status:** F-34 is **code-complete; live-validation pending** (mirrored in `docs/XDD/backlog.md`).
