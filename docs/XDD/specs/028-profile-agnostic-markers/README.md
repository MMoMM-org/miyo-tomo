# Specification: 028-profile-agnostic-markers

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-07-01 |
| **Current Phase** | Implemented |
| **Last Updated** | 2026-07-02 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | F-16 (#34) + F-55 (#35) batched |
| solution.md | completed | Per-script channel (ADR-1); 3 ADRs confirmed 2026-07-01 |
| plan/ | completed | 4 phases, 18 tasks; single live-test in P4 |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-01 | Batch F-16 + F-55 into one spec/delivery | Single live-test cycle — user wants to minimize live runs against Kado |
| 2026-07-01 | FOOTER_CALLOUTS stays hardcoded (out of scope) | moc-tree-builder.py comment already declares it not a F-55 config knob |
| 2026-07-01 | Delivery channel = per-script resolution + suggestions-doc conventions block (ADR-1); NOT shared-ctx | shared-ctx has no non-reducer Python consumer for these values (YAGNI) |
| 2026-07-01 | No shared-ctx.schema.json bump | shared-ctx is not the marker channel; builder only reads suffix internally |
| 2026-07-01 | PLAN complete — 4 phases, 18 tasks, ready to implement | PRD+SDD+PLAN all approved; ADRs confirmed |
| 2026-07-02 | Implementation complete — all 4 phases shipped + both review gates passed | 1933 tests green; miyo byte-identity guard-tested; verified on genuine live item (Meine PKM-Prinzipien). Live run also exposed unrelated bug #116 (stale cross-run state) — not a 028 regression |
| 2026-07-01 | Seam-map miss found in Phase 4 grep: two literals outside the SDD's 10 seams | `suggestions-render.py:147` (`f"{topic} (MOC)"`) + `moc-proposal-parser.py:132` (`if "up::" in cb_text`) |
| 2026-07-01 | DEVIATION: fixed `suggestions-render.py` in-scope (cheap, reads conventions block); DEFERRED `moc-proposal-parser.py` | Renderer is user-facing F-55 path. Parser is pure future-proofing (both profiles use up:: → zero today-impact) and needs its own delivery-channel design (no --config/--profile); deferred to backlog to avoid new scope pre-live-test |

## Context

Epic #20 (Profile-Agnostic Pipeline). Makes relationship markers (`up::`/`related::`) and the MOC title suffix (`" (MOC)"`) read from profile YAML instead of hardcoded, so non-miyo profiles (starting with lyt) get correct behavior.

**Grounding from completed seam-map (2026-07-01):**
- Profiles already define `relationship_defaults.parent.marker`/`peer.marker` (miyo.yaml:106-113, lyt.yaml:98-105).
- Markers are IDENTICAL across both current profiles (`up::`/`related::`) → F-16 is future-proofing, zero behavioral change today.
- Only the MOC suffix differs today: miyo `" (MOC)"` vs lyt `""`.
- Hardcoded seams: `lib/up_parse.py:55`, `lib/render_actions.py:110-111,169,274,319-369` (writer paths), `lib/topic_clusters.py:32`, `suggestions-reducer.py:483-528`, `shared-ctx-builder.py:261`, `moc-discovery.py:888-891` (`_PROFILE_TITLE_SUFFIX`) & `:1410`, `suggestion-parser.py:1211`.
- **Design problem for SDD:** none of the 4 core scripts currently receive shared-ctx (instruction-render → vault-config.yaml; moc-discovery → loads profile directly; moc-tree-builder + suggestion-parser → nothing). A marker/suffix delivery channel must be designed per script.
- New profile key to add: `map_note.name_suffix` (both profiles).

**Constraints:** near-MVP additive-only; test scope = personal vault; offline unit tests preferred over live runs.

---
*This file is managed by the xdd-meta skill.*
