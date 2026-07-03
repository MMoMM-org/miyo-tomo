---
title: "Phase 1: Core Weighted-Overlap Scorer"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Core Weighted-Overlap Scorer

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Interface Specifications — Internal API Changes]` — `weighted_overlap`, `title_tokens`, `_weight`, constants
- `[ref: SDD/Implementation Examples — weighted_overlap]` — reference implementation + traced walkthrough table
- `[ref: SDD/Runtime View — Complex Logic]` — the 6-step algorithm
- `[ref: PRD/Feature 1 + Detailed Feature Specifications — Edge Cases]`

**Key Decisions**:
- ADR-1 (substring title-derived test), ADR-3 (Ruzicka Σmin/Σmax, missing-side=0, exact flat-reduction only when no title-derived topic), ADR-6 (`W_TITLE=2`/`W_BASE=1` named constants).

**Dependencies**:
- None. This is the foundation; Phases 2 and 3 depend on it.

---

## Tasks

Establishes the standalone, pure weighted-overlap scorer that both match sites will use.

- [ ] **T1.1 `topic_match` scorer + unit suite** `[activity: domain-modeling]`

  1. Prime: Read the reference implementation and traced walkthrough `[ref: SDD/Implementation Examples — weighted_overlap]`; confirm `normalize()` matches the topic normalization in `moc-discovery.py` (`.strip().lower()` + whitespace-collapse) `[ref: SDD/Constraints CON-1]`.
  2. Test (RED) — write `tests/test_topic_match.py` first, all failing. **At least one assertion MUST falsify a flat no-op implementation** (a scorer that ignores titles and returns plain Jaccard must FAIL the suite) `[ref: SDD/Test Examples as Interface Documentation]`:
     - `test_dedupe_misfire_crosses_threshold` — **the discriminating test**: 8 shared content topics + 1 distinct title topic each side → `flat_jaccard ≥ 0.80` (a false dup today) BUT `weighted < 0.80` (fixed). A flat impl fails this `[ref: SDD/Traced walkthrough 2; PRD/Feature 1 misfire]`
     - `test_weighting_strictly_below_flat_on_title_disagreement` — shared topic title-derived on neither side, distinct title themes differ → `weighted < flat_jaccard` `[ref: PRD/Edge Cases "both sides different title themes, share a content keyword"]`
     - `test_reduces_to_flat_when_no_title_topic` — no title-derived topic on either side → score equals flat Jaccard exactly `[ref: PRD/AC Feature 1 "identical to flat"]`
     - `test_true_dup_title_agreement_survives` — shared title-derived topics → score `≥ 0.80` `[ref: PRD/AC Feature 1 no-regression]`
     - `test_empty_or_missing_title_uses_base_weights` — empty title → base weights, no error `[ref: PRD/Edge Cases]`
     - `test_empty_topic_set_returns_zero` — either side empty → `0.0` `[ref: PRD/Edge Cases]`
     - `test_weight_is_capped_regardless_of_title_length` — per-topic weight never exceeds `W_TITLE` for a long title `[ref: PRD/Edge Cases long-title]`
     - Provide a `flat_jaccard(a, b)` test helper (or import the pre-F-05 reference) used by the discriminating assertions `[ref: SDD/Test Examples]`
  3. Implement (GREEN): Create `tomo/scripts/lib/topic_match.py` with `weighted_overlap()`, `title_tokens()`, `_weight()`, `W_TITLE=2`, `W_BASE=1`. Stdlib only. Missing-side weight = 0 in both Σmin (numerator over ∩) and Σmax (denominator over ∪).
  4. Validate (REFACTOR): `./venv/bin/python -m pytest tests/test_topic_match.py -q` green; `./venv/bin/ruff check tomo/scripts` clean; function stays pure/total.
  5. Success:
     - [ ] All tests pass, INCLUDING the discriminating `test_dedupe_misfire_crosses_threshold` (flat ≥ 0.80 AND weighted < 0.80) — a flat no-op impl provably fails the suite `[ref: PRD/Feature 1 + Edge Cases]`
     - [ ] Exact flat-reduction property holds in the degenerate case `[ref: SDD/ADR-3]`
     - [ ] No new dependencies; stdlib only `[ref: SDD/CON-1]`

- [ ] **T1.2 Phase Validation** `[activity: validate]`

  - Run `./venv/bin/python -m pytest tests/test_topic_match.py -q` and `./venv/bin/ruff check tomo/scripts`. Verify the scorer matches the SDD traced walkthrough (misfire case scores 0.20 vs flat 0.33). Confirm `lib/topic_signature.py` was NOT modified.
