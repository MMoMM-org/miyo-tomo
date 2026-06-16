---
title: "Phase 5: Live walk + regression"
status: pending
version: "1.0"
phase: 5
---

# Phase 5: Live walk + regression

## Phase Context

**GATE**: Read referenced files before starting.

**Specification References**:
- `[ref: requirements.md/Success Metrics; AC-3, AC-6, AC-7, AC-9, AC-10, AC-11, AC-13]` — the measurable quality gate
- `[ref: solution.md/Complex Logic — Traced walkthrough]` — the strong (FPT) / weak (Sapporo) / no-footer cases
- `[ref: solution.md/Risks and Technical Debt — stale cache]` — rebuild the MOC cache before the walk; stale-cache symptoms are NOT gate bugs
- Memory `project_spec022_live_walk_targets` — test note `100 Inbox/First Principles Thinking.md`, footer-less `Concepts (MOC)`, the Japan-`Content` failure

**Key Decisions**:
- This proves the redesign end-to-end against the real vault (standing "real walks > synthetic fixtures" rule). It is the gated, interactive task — needs the running container, live Kado, Obsidian, and user confirmation at the gates.
- **Rebuild the MOC structure cache via `/explore-vault` FIRST** so `has_footer` (Phase 2) populates and the gate scores fresh headings. Without the rebuild, `has_footer` is absent → tier-2 degrades to the 022 footer placeholder (no-footer path won't engage).
- No new Hashi wire shape — the walk exercises the unchanged `line`/`after` and `callout`/`before` shapes; no Hashi handoff required.
- Run host-vs-live-Kado with sandbox off (URL + token from `tomo-instance/.mcp.json`).

**Dependencies**: Phases 1-4 complete and synced to the instance via `update-tomo` (full pipeline must emit + render + resolve + count correctly).

---

## Tasks

Closes the 022 gap end-to-end and guards the full suite against regression.

- [ ] **T5.1 Live-validation walk** `[cross-repo]` `[needs-hashi]` `[activity: validate]`

  1. Prime: Confirm `100 Inbox/First Principles Thinking.md` exists; **rebuild the MOC structure cache (`/explore-vault`)** so headings AND `has_footer` are fresh. Pick the cases: strong fit (FPT → `Concepts (MOC)` `Thinking Frameworks`); the regression (a Japanese-city note → `Japan (MOC)`, structural headings incl. `Content`, HAS a footer); and the no-footer case (a note → footer-less `Concepts (MOC)`).
  2. Test (red): run `/inbox` Pass-1 → the strong fit lands tier-1 with `(confidence: NN%)` on the Placement line (AC-11); the city note does NOT land under `## Content` — proposed as a new section showing `(before the footer)`, with `Content` in the "Other sections" advisory (AC-5, AC-6, AC-13); a footer-less target shows `(at the end of the MOC)` (AC-9, AC-13); the tier-2 path fires on a real MOC (AC-7).
  3. Implement (green): execute the walk; confirm Pass-2 resolves the new section (footer-callout text OR last body line) and — through Hashi — it lands before the footer / after the last body line with correct spacing and the link under it (AC-9, AC-10). Log the run cost to `docs/evolution/inbox-cost-log.md`.
  4. Validate: vault-state diff matches the emitted `instructions.json`; intra-cluster consistency holds (the Japanese-city cluster gets the same tier decision); the telemetry line shows ≥1 rejected→tier-2; `fit_confidence` does not appear in any `instructions.json` action anchor.
  5. Success:
     - [ ] 0 content notes filed under a structural heading where a new section is warranted `[ref: Success Metrics — Quality]`
     - [ ] ≥1 genuine tier-2/#28 trigger validated end-to-end `[ref: AC-7; Success Metrics — Coverage]`
     - [ ] no-footer new section resolves + applies after last line, correct spacing `[ref: AC-9, AC-10]`
     - [ ] tier-1 confidence % and tier-2 destination shown in the doc `[ref: AC-11, AC-13]`

- [ ] **T5.2 Phase Validation + full regression** `[activity: validate]`

  - Run the full `./venv/bin/python -m pytest tests/` suite (true baseline ~840 pass; only known failures are the 8 pre-existing `tests/ide_bridge`). Confirm no new regressions. Verify `update-tomo` synced every edited managed file — grep the instance copies of `moc-tree-builder.py`, `shared-ctx-builder.py`, `inbox-analyst.md`, `suggestions-reducer.py`, `instruction-render.py` for the bumped `# version:` (and the schema). Confirm `fit_confidence` does not appear in any generated `instructions.json` action anchor.
