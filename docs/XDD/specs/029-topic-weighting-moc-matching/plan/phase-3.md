---
title: "Phase 3: Validation & Threshold Tuning"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Validation & Threshold Tuning

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-5]` — keep 0.80, validate in-scope; re-tune only on misseparation
- `[ref: PRD/Feature 4 + Success Metrics]`
- `[ref: SDD/Project Commands]`

**Key Decisions**:
- ADR-5 (threshold validated, not assumed). Validation scope = owner's personal vault (pre-launch).

**Dependencies**:
- Phase 2 complete (both sites wired). Requires a synced instance for the live run
  (`scripts/update-tomo.sh` after the `# version` bump in Phase 2).

---

## Tasks

Confirms the fix works end-to-end on real data and that the threshold still separates.

- [ ] **T3.1 Threshold separation validation** `[activity: validate]`

  1. Prime: `[ref: SDD/ADR-5]`. **Caveat (from validation):** `scripts/analyze-placement-confidence.py` measures spec-023 tier-1 heading `fit_confidence`, NOT dedupe-Jaccard separation — it does **not** directly validate the 0.80 dedupe cutoff. Use it only as a distribution-analysis pattern; the dedupe threshold must be measured on actual dedupe-candidate pairs.
  2. Test (measure): collect the weighted dedupe scores for cluster×existing-MOC candidate pairs from a real vault sample — either instrument `phase6_dedupe` to log each pair's `weighted_overlap`, or compute `weighted_overlap` offline over the discovery cache's `map_notes`. Hand-label each surfaced pair as **true-dup** or **incidental-overlap** (feasible on the single-user vault).
  3. Implement (decide): apply the **quantified criterion** — keep `JACCARD_DUP_THRESHOLD = 0.80` iff on the sample `max(incidental-pair score) < 0.80 ≤ min(true-dup-pair score)` (the 0.80 line cleanly separates the two classes). If that inequality is violated → re-tune the threshold to a value that satisfies it and record the deviation `[ref: plan/README — Deviation Protocol]`.
  4. Validate: decision (keep vs re-tune) + the separating evidence (min/max scores per class) recorded in the spec README decisions log.
  5. Success:
     - [ ] Quantified separation confirmed (`max incidental < 0.80 ≤ min true-dup`) or threshold re-tuned to satisfy it, with evidence `[ref: PRD/Feature 4]`

- [ ] **T3.2 Live `/inbox` end-to-end run** `[activity: validate]`

  1. Prime: sync the edited managed files into the instance (`scripts/update-tomo.sh`); confirm the analyst `# version` bumped and the new `lib/topic_match.py` shipped `[ref: SDD/Deployment View; project memory: sync-before-live-walk]`.
  2. Test: run one `/inbox` pass on the personal vault.
  3. Implement: observe dedupe outcomes and MOC-link rankings; confirm no incidental-overlap misfire and no regression on real matches; confirm no squelch churn.
  4. Validate: capture the run outcome; add an entry to `docs/evolution/inbox-cost-log.md` if a cost delta is measured `[ref: project memory: inbox cost log]`.
  5. Success:
     - [ ] Zero incidental-overlap misfires; no regression; no squelch churn `[ref: PRD/Success Metrics]`

- [ ] **T3.3 Final gates & spec closeout** `[activity: validate]`

  - Run full `./venv/bin/python -m pytest tests/ -q` and `./venv/bin/ruff check tomo/scripts scripts` — all green. Tick the plan/README phase checklist. Update `docs/XDD/specs/029-topic-weighting-moc-matching/README.md` to `Implemented`, reference the PR, and close issue #124. Update epic #17 checkbox for F-05 (#124).
