---
title: "Phase 2: Link members in topic proposals"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Link members in topic proposals

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View; Primary Flow]`, `[ref: SDD/Application Data Models]` (report fields)
- `[ref: SDD/ADR-2, ADR-7]`, `[ref: SDD/User Interface & UX; UI Visualization Guide]`
- `tomo/scripts/moc-discovery.py:1699-1841` (`_run_pipeline`), `:1793` (D3), `:1804` (sort), `:1431` (Phase 6.5), `:1598` (`_NullKadoClient`), `:329` (`empty_report`), `:1903-1949` (`--emit-phase1`)
- `tomo/scripts/suggestions-reducer.py:1447` (`_child_annotation`), `:1470-1563`, `:1654`
- `tomo/scripts/suggestion-parser.py:54, :1435, :1609`; `tomo/scripts/lib/squelch_persist.py:83-108`; `tomo/scripts/lib/topic_signature.py:70-77`

**Key Decisions**:
- Augmentation runs on `clusters[:max_results]` only, after D3 and the confidence sort; squelch, D3 and confidence never see link members.
- Docs without link members must be byte-identical to today's (every existing reducer test is the guard).
- `--emit-phase1` makes zero graph calls.

**Dependencies**: Phase 1.

---

## Tasks

Delivers F1, F4 and the run counters for every existing mode: rendered topic proposals gain unticked link members with their reason, and a rejected proposal still stays muted.

- [ ] **T2.1 Augmentation in the discovery pipeline** `[activity: backend-api]` `[component: moc-discovery]`

  1. Prime: WHY section first in `docs/tomo/scripts/moc-discovery.md` — insertion point, rendered slice, why squelch/D3/confidence stay topic-only `[ref: SDD/ADR-2]`
  2. Test: extend `tests/test_moc_discovery_main.py` (RED) with a graph-capable fake: a tag run whose top cluster has a note linked with 2 members → `topic_clusters[0].link_members` holds it with `linked_with`; clusters beyond `max_results` get `not_rendered` and cause no call; `link_stats` counts lookups/attempts/failed/skipped/members/uncached; `--emit-phase1` run → fake records zero graph calls; `_NullKadoClient.graph` raises → every rendered cluster `failed`, run exit unchanged; squelch signature and `confidence` of a cluster are identical with and without link members; members are re-checked by `NodeEligibility` before lookups (Pass 2 trusts `--phase1-input`); stem-collision case builds the map by path
  3. Implement: call `augment_clusters` between the sort and Phase 6.5 in `_run_pipeline`; additive report fields; `_NullKadoClient.graph`; bump `# version:`
  4. Validate: all `tests/test_moc_discovery_*.py` green unchanged except the new cases; ruff clean
  5. Success: `[ref: PRD/F1-AC1…AC4, F5-AC1, F5-AC4]` in the real pipeline; `[ref: SDD/ADR-2]`

- [ ] **T2.2 Rendering link members and the Why count** `[activity: frontend-ui]` `[component: Reducer]` `[parallel: true]`

  1. Prime: WHY section first in `docs/tomo/scripts/suggestions-reducer.md` — the line contract and why the member link stays first `[ref: SDD/ADR-7]`
  2. Test: extend `tests/test_reducer_moc_proposal_mode.py` (RED): link members render after topic members as `- [ ] [[stem]] (<annotation>) — linked with [[A]], [[B]]` `[ref: PRD/F4-AC1]`; an existing-`up::` annotation precedes the suffix `[ref: PRD/F4-AC2]`; "Why this proposal" gains "N more members came through links" only when N > 0 `[ref: PRD/F4-AC3]`; the Children count includes link members; a report without link members renders byte-identical to a fixture captured from the current renderer before the change
  3. Implement: link-member branch in `_render_cluster_section` and the Why sentence; bump `# version:`
  4. Validate: every existing reducer test green unchanged; ruff clean
  5. Success: `[ref: PRD/F4-AC1, F4-AC2, F4-AC3]`

- [ ] **T2.3 Parsing link lines; squelch stays topic-only** `[activity: backend-api]` `[component: suggestion-parser, squelch_persist, moc-proposal-parser]` `[parallel: true]`

  1. Prime: WHY sections first in `docs/tomo/scripts/suggestion-parser.md` and `docs/tomo/scripts/lib/squelch_persist.md` (create if missing) `[ref: SDD/ADR-7]`
  2. Test (RED):
     - `tests/test_squelch_rejection.py`: rejecting a doc with link members stores the same signature as rejecting the same doc without them;
     - `tests/test_suggestion_parser_moc_branch.py`: a link line is returned as a child (first wikilink = member) and excluded from `candidate_stems`;
     - `tests/test_moc_proposal_parser.py`: a ticked link line lands in `supporting_items`, an unticked one does not `[ref: PRD/F1-AC5]`;
     - the ` — linked with ` marker is one shared constant used by the reducer and both parsers.
  3. Implement: marker constant (single source), exclusion in `enumerate_all_moc_sections` / signature input, parser child handling; bump versions
  4. Validate: mutation check in a `git archive` copy — remove the exclusion and the squelch test must fail; ruff clean
  5. Success: `[ref: PRD/F4-AC4, F1-AC5]`; rejected proposals do not resurface `[ref: PRD/Risks]`

- [ ] **T2.4 Phase Validation** `[activity: validate]`

  - Full suite + ruff. Drift check of Phase 2 against SDD ADR-2/ADR-7. Confirm no change to `lib/topic_clusters.py`, `state-promoter.py`, `inbox-triage.py`, `synthesis-conductor.md`.
