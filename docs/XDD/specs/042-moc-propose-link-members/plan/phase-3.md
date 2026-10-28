---
title: "Phase 3: around:<note>"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: around:<note>

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View; Secondary flows — around:<note>]`, `[ref: SDD/Error Handling]`
- `[ref: README/Decisions 2026-10-28 — around: details]` (not-found, title, periodic refused, no squelch)
- `tomo/scripts/moc-discovery.py:146` (scope group), `:255-282` (`route_input`), `:2059` (single-pass check branch), Phase 5 parent options (`:1020`)

**Key Decisions**:
- Single pass: no Pass 1, no topic extraction, no squelch.
- Target resolution uses the cache only; a vault path argument is accepted; no name-search fallback.
- Title is `<seed stem><profile name_suffix>`; parents come from Phase 5 on the seed's cached topics.

**Dependencies**: Phase 1 (lookup, eligibility). Independent of Phase 2's renderer work except the shared line contract (T2.2) — run after Phase 2.

---

## Tasks

Delivers F2: one new-MOC proposal built from a seed note's links.

- [ ] **T3.1 `--around` resolver and new-MOC builder** `[activity: backend-api]` `[component: around builder]`

  1. Prime: WHY section first in `docs/tomo/scripts/moc-discovery.md` — resolution rules, refusals, why no squelch, why single pass
  2. Test: `tests/test_moc_discovery_around.py` (RED):
     - resolution: stem, `[[stem]]`, `stem.md`, vault path; MOC+note same name → abort listing both paths; two notes same stem → abort listing both; uncached → `not-found` message naming the remedy `[ref: PRD/F2-AC3]`;
     - periodic seed → refusal message; MOC seed → routed to the extension path (stub assertion until Phase 4);
     - ≥ 2 eligible neighbours → one cluster: seed ticked, neighbours unticked with `linked_with=[seed]`, title `"<stem> (MOC)"` under the miyo profile, parent options from the seed's topics `[ref: PRD/F2-AC1]`;
     - < 2 eligible → no cluster, abort reason "fewer than 3 notes" `[ref: PRD/F2-AC2]`;
     - seed `neighbors` raising → abort reason "seed lookup failed", never "fewer than 3 notes" `[ref: PRD/F5-AC5]`;
     - exactly 1 attempt counted for a healthy seed; no squelch registry read or write.
  3. Implement: `--around` in the scope group and `route_input`; resolver + builder in `moc-discovery.py` reusing `LinkLookup` / `NodeEligibility`; report `around` field; bump `# version:`
  4. Validate: tests green; existing CLI/route tests unchanged; ruff clean
  5. Success: `[ref: PRD/F2-AC1, F2-AC2, F2-AC3, F5-AC5]`

- [ ] **T3.2 Reducer renders an around: proposal** `[activity: frontend-ui]` `[component: Reducer]`

  1. Prime: T2.2 line contract
  2. Test: extend `tests/test_reducer_moc_proposal_mode.py` (RED): an `around:` report renders one `### MOC01 — <stem> (MOC)` section with the seed `- [x]`, neighbours `- [ ] … — linked with [[seed]]`, `**Trigger:** around:<arg>`, and the Why sentence naming the seed
  3. Implement: whatever the reducer needs beyond T2.2 (trigger label, Why wording); bump version if changed
  4. Validate: reducer suite green; ruff clean
  5. Success: `[ref: PRD/F2-AC1]` visible in the doc

- [ ] **T3.3 Phase Validation** `[activity: validate]`

  - Full suite + ruff; drift check of Phase 3 against the SDD secondary flow and the README `around:` decisions.
