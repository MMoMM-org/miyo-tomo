---
title: "Phase 5: Runtime prose, end-to-end and live validation"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: Runtime prose, end-to-end and live validation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View; moc-architect / moc-propose prose]`, `[ref: SDD/Quality Requirements]`
- `tomo/dot_claude/commands/moc-propose.md:24-46`; `tomo/dot_claude/agents/moc-architect.md:45-55, :84-94, :283-294`; `tomo/dot_claude/commands/tomo-help.md:152-157`
- Root `CLAUDE.md` runtime-file rules; memory: sync only `--instance tomo-instance`, never `tomo-privat`

**Key Decisions**:
- Prose holds imperatives only; every rationale was written to `docs/tomo/dot_claude/...` first.
- The STRICT six-field block keeps its fields; link counts go on the `Discovery:` line.
- Live validation is in the container against the test vault through Kado; heavy host runs are avoided (per-IP limiter).

**Dependencies**: Phases 1-4.

---

## Tasks

Delivers the user-facing entry, the proof across the whole chain, and the close-out.

- [x] **T5.1 Prose: around: routing and the Discovery line** `[activity: docs]` `[component: moc-architect, moc-propose]`

  1. Prime: WHY sections first in `docs/tomo/dot_claude/commands/moc-propose.md` and `docs/tomo/dot_claude/agents/moc-architect.md`
  2. Test: `tests/test_042_prose.py` (new, pattern of `tests/test_040_skill_prose.py`) (RED): `around:` is in the whitelist and the mode mapping, lowercase exact `[ref: PRD/F2-AC4]`; around runs take the single-pass branch; the STRICT block still has six fields and the `Discovery:` template contains `links: <K> members, <L> lookups` with the `(S skipped: budget)` suffix rule and the K = 0 case `[ref: PRD/F7-AC1, F7-AC2]`; `tomo-help.md` lists `around:` and no longer lists the removed "placeholder" mode
  3. Implement: prose edits; bump `# version:` on each file; pass `--config config/vault-config.yaml` to the reducer call in moc-architect.md (matches every discovery call)
  4. Validate: tests green; `/skill-author`-style audit of the agent file; ruff clean
  5. Success: `[ref: PRD/F2-AC4, F7-AC1, F7-AC2]`

- [x] **T5.2 End-to-end through the pipeline** `[activity: test]`

  1. Prime: `tests/integration/test_moc_propose_e2e.py`
  2. Test: extend it (RED → GREEN) with a graph-capable fake vault: (a) tag run → doc with link members → tick one, Accept → `moc-proposal-parser` → `instruction-render` → instructions contain `add_relationship` for the ticked link member and nothing for the unticked one; (b) `around:<MOC>` → extension doc → tick 2 of 3 (one already linked) → instructions: 2 relationship sets, 1 `link_to_moc`; instructions-diff green; (c) budget 0 → doc still written, `skipped_budget` reported
  3. Implement: test-only, plus fixes for any defect found (each with its own RED test)
  4. Validate: integration test green; full suite green; ruff clean
  5. Success: every ticked member reaches the instructions `[ref: PRD/Success Metrics; Business Impact]`

- [ ] **T5.3 Live validation on tomo-instance** `[activity: validate]`

  1. Prime: memory notes on syncing (`update-tomo` is version-gated, needs `--yolo`), container visibility, per-IP limiter
  2. Test: sync with `./scripts/update-tomo.sh --instance tomo-instance --yolo` (never `tomo-privat`); in the container run a default scan, `/moc-propose around:<a real hub note>`, `/moc-propose around:<a real MOC>`; record per run the `Discovery:` line verbatim (byte-copied), proposals with link members, attempts, 429 count, wall time
  3. Implement: fixes for any defect found, each with a RED test first
  4. Validate: ≥ 3 default-scan proposals carry a link member, or the shortfall is recorded with its cause; attempts ≤ 120 per run; 0 rate-limit aborts; no periodic note, MOC, attachment or out-of-scope note proposed (checked against the doc); owner reviews one doc and ticks — the tick ratio is recorded `[ref: PRD/Success Metrics]`
  5. Success: KPIs recorded in `docs/XDD/specs/042-moc-propose-link-members/live-validation.md` with verbatim output lines

- [x] **T5.3a Pass 2 exit 1 is a partial result, not a failure** `[activity: runtime-prose]` `[parallel: true]`

  1. Prime: `tomo/scripts/moc-discovery.py` exit codes (docstring: 0 clean, 1 partial, 2 fatal); `tomo/dot_claude/agents/moc-architect.md` Steps 3 and 3c; live run 2026-10-29 stopped on exit 1 after D3 dropped 104 duplicate clusters `[ref: SDD/Error Handling]`
  2. Test: prose tests — Steps 3 and 3c treat exit 2 as fatal (surface stderr, stop) and parse stdout on exit 0 or 1; the Discovery fill rules print `(<P> sampled: budget)` from `link_stats.clusters_sampled` when > 0
  3. Implement: WHY in `docs/tomo/dot_claude/agents/moc-architect.md` first; then the prose; bump `# version:`
  4. Validate: prose tests green; full suite green; ruff clean
  5. Success: a scan whose D3 drops clusters reaches the reducer

- [ ] **T5.3b Fair-share link budget (ADR-4 v1.2)** `[activity: backend]` `[parallel: true]`

  1. Prime: `tomo/scripts/lib/link_members.py` (`augment_clusters`, `_augment_one`, `LOOKUP_BUDGET`); `tomo/scripts/moc-discovery.py` `_augment_rendered_clusters`; SDD ADR-4, Complex Logic, Error Handling `[ref: SDD/ADR-4; Complex Logic]`
  2. Test: budget 120; share = remaining // clusters still to do; memoised members free; first `share` uncached members in item order → `sampled`; share 0 → `skipped_budget`; unused share flows on; `link_stats.clusters_sampled`; ≥ 2 hits counted among looked-up members only; around seed unchanged
  3. Implement: WHY in `docs/tomo/scripts/lib/link_members.md` and `docs/tomo/scripts/moc-discovery.md` first; then code; bump `# version:`
  4. Validate: focused + full suite green; ruff clean; host re-run of Pass 2 on the live Phase-1 file shows all rendered clusters looked up and attempts ≤ 120
  5. Success: no rendered cluster is skipped while budget remains

- [ ] **T5.4 Close-out** `[activity: docs]`

  - `close-out.md`: every one of the 29 PRD criteria traced to a test node id that was actually executed (one pytest invocation, count recorded) or to a T5.3 live record; any criterion no test could fail gets a RED-proven assertion before the spec is finalised. Update `docs/ai/memory/memory.md` Critical Documentation; README phase → Implemented via xdd-meta Finalize.
