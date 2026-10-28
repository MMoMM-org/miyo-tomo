# Specification: 042-moc-propose-link-members

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-10-27 |
| **Current Phase** | SDD |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Last Updated** | 2026-10-27 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | v1.1; 6 Must, 1 Should, 1 Could; 29 acceptance criteria |
| solution.md | in_progress | v1.0 draft; 11 components, ADR-1…ADR-7 confirmed 2026-10-28; 29 EARS criteria, 1:1 with the PRD |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-27 | Adopt `kado-graph` in two steps; step 1 (existing `up::` target check) shipped as #214, this spec is step 2 | Owner decision on #82 ("Beides, nacheinander"). |
| 2026-10-27 | Start with PRD; research mode Standard (3 parallel agents: user flow, moc-discovery integration, Kado budget) | Owner choice. |
| 2026-10-27 | Shape: BOTH — link members augment the topic clusters of every existing mode, AND a new seed mode `around:<note>` | Owner decision ("Beides"); recommendation was augmentation only. |
| 2026-10-27 | 1-hop only (`neighbors`); no `related` in this spec | Owner decision. Live probe: 2-hop results dominated by periodic-note hubs; one call per seed. |
| 2026-10-27 | Provenance on the member line AND a link count in "Why this proposal" | Owner decision. |
| 2026-10-27 | Link-sourced members start unticked `- [ ]` | Owner decision: a link is weaker evidence than a shared topic; nothing changes without an explicit tick. |
| 2026-10-27 | Augmentation threshold: a note joins a topic cluster when it is linked with ≥ 2 of the cluster's members | Owner decision; 1 would pull in every neighbour of every member. |
| 2026-10-27 | `around:<note>` needs ≥ 3 notes (same as `min_notes`); below that, a clear message and no proposal | Owner decision. |
| 2026-10-27 | `around:<MOC>` proposes the MOC's MISSING members (a new proposal type: extend an existing MOC); ≥ 1 missing member suffices | Owner decision; recommendation was to refuse. Widens scope: new doc section type and apply path. |
| 2026-10-27 | Applying an extension: each ticked member gets `up:: [[MOC]]` (existing-up / Override rules unchanged) AND the MOC gets a link bullet | Owner decision; reuses `add_relationship` and `link_to_moc`. |
| 2026-10-27 | Budget exhausted: keep what was found, propose the rest without link members, say so in the report; no abort | Owner decision. |
| 2026-10-27 | PRD v1.1 approved; F5 gains: a rate-limited lookup waits Kado's stated retry time and retries before it counts as failed; retries count toward the budget | Owner: "bei Kado nur schauen, dass wir den Backoff unterstützen". |
| 2026-10-28 | SDD ADRs confirmed: ADR-1 live `kado-graph neighbors`; ADR-2 augment only the rendered top clusters, after D3 + sort, before Phase 6.5, memoised per member; ADR-3 eligibility offline from cache + profile, uncached nodes skipped and counted; ADR-4 budget 60 attempts per run incl. retries, ~0.3 s pacing, all-or-nothing per cluster; ADR-5 extension stays a `moc-proposal` doc (`### MOCxx — Extend [[X]]`, `**Extends:**`), parser emits `extend_moc`, not squelched; ADR-6 "MOC already links it" checked at render time via `outgoing(MOC)`; ADR-7 line format `- [ ] [[stem]] (up) — linked with [[A]], [[B]]`, link lines outside the squelch signature | Owner confirmed all recommendations. |
| 2026-10-28 | `around:` details: uncached target → not-found (no name-search fallback; a path argument works); new-MOC title = seed stem + profile MOC suffix; periodic seed refused; `around:` proposals are not squelched; link counts go on the existing `Discovery:` report line | Owner decisions. |
| 2026-10-27 | Kado limiter is per IP, 20 req / 5 s, in the container too; a per-run graph-call cap is required wherever the run happens | Research (Kado `server.ts:105-157`, `canonical.ts:685-686`), verified in code. Corrects the earlier "container has no limit" memory. |

## Context

Step 2 of #82 (part of epic #17, MOC Intelligence): `/moc-propose` gains
members found through the vault's link graph (`kado-graph` `related` /
`neighbors`), not only through tags, folders and topics.

Known at start:
- `KadoClient.graph(operation, path, limit)` exists (`tomo/scripts/lib/kado_client.py` 0.13.0, #214).
- `moc-discovery.py` Phase 1 candidates come from tag / folder / Dewey / topic / scan mode; no link signal anywhere (`moc-discovery.py:428-532`).
- Clustering groups by normalised topic (`lib/topic_clusters.py`); duplicates by `weighted_overlap` ≥ 0.80.
- `kado-graph` (verified live 2026-10-27): resolved path nodes, flat and deduplicated, may include the source itself, omits out-of-scope nodes; includes frontmatter links.
- Live probe 2026-10-27 (test vault): `neighbors` / `related` do not include the source; `related` nodes carry `via` as a **list** of 1-hop intermediates. From a plain note (`Energy Level (Thought).md`, 2 neighbours: a daily and a weekly note) all 32 `related` nodes were reached only through those periodic notes (planner, 5-year journal) — calendar notes act as hubs and dominate 2-hop results. From `021 Fleeting MOC.md`: 6 neighbours, 66 related. Calls took 6–29 ms; call count, not latency, is the limit.
- Host runs hit Kado 429 on many reads; full `/moc-propose` E2E runs in the container.
- Spec 040 rejected `kado-graph` as an `/inbox` relevance signal (fresh items carry no links); that decision stands.

---
*This file is managed by the xdd-meta skill.*
