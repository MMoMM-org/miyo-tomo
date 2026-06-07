---
title: "Phase 7: Proposal coherence — drop per-note orphans, dedup clusters, exclusion tags"
status: pending
version: "1.0"
phase: 7
---

# Phase 7: Proposal coherence

## Phase Context

**GATE**: Read before starting. Full design rationale: `../phase-7-design-notes.md`.

**Specification References**:
- `[ref: SDD/ADR-13]` — drop per-note orphans from /moc-propose; inter-cluster member dedup; exclude tags
- `[ref: PRD/Feature 8]`
- `[ref: SDD/ADR-7]` (orphan pass, now check-only) · `[ref: SDD/ADR-12]` (cap/overflow, now check-only)

**Key Decisions** (ADR-13, user-confirmed 2026-06-07):
- **D1** `/moc-propose` = cluster→new-MOC only; the `### Oxx` note-orphan section is removed (orphan pass + ADR-12 cap stay, used ONLY by `check:moc-uplinks`).
- **D2** interactive note-orphan handling deferred → **Garden-Audit #30** (reuses 021 cache + `lib/up_parse` + `lib/orphan_link`). Per-note `create_new` deprecated.
- **D3** inter-cluster member-overlap dedup: drop the smaller proposed cluster when **≥80%** of its members are in a larger proposed cluster (→ `duplicates_skipped`).
- **D4** dedup `candidate_stems` within a cluster (each note at most once).
- **B-moc** `MiYo/Tomo/exclude/moc` = audit-only (skip in `check:moc-uplinks`, keep in cache/link-pool); root MOCs tagged, no heuristic.
- **B-note** `MiYo/Tomo/exclude/note` = filter at the scan candidate source (never clustered).
- Hardwired tag constants; cache builder must populate entry `tags`.

**Why this phase**: live review of `2026-06-07_0850` showed within-cluster duplicates (P1), 22 notes double-listed in both a cluster and the orphan section (P2), and near-identical clusters surviving (P4: MOC05⊆MOC02, MOC04 97%⊆MOC03). The proposal-doc must place each homeless note in exactly one coherent view.

**Dependencies**: Phases 1–6 (cache, `lib/orphan_link`, `check:moc-uplinks`, `phase6_dedupe`, the reducer orphan-section renderer). T7.2 depends on T7.1 (tags in cache).

---

## Tasks

- [ ] **T7.1 Cache builder populates entry `tags`** `[activity: backend-api]` `[ref: SDD/ADR-13 dependency; PRD/F8; moc-tree-builder.py run(), lib/moc_scan.py]`
  1. Prime: how `moc-tree-builder.py` assembles each `CacheEntry` (currently `tags: []`); `lib/moc_scan.py` discovery; Kado `operation='tags'` (kado_client) or frontmatter tags already read during build. Confirm cheapest source (avoid an extra per-note round-trip if tags arrive with an existing read).
  2. Test (RED): a built cache entry carries the note's real `tags` list (MOC + note); a note with no tags → `[]`.
  3. Implement: populate `tags` per entry from the data already pulled during the build (or one batched tags read). Bump `# version:` on the builder/lib touched.
  4. Validate: `./venv/bin/python -m pytest tests/test_moc_tree_builder.py -v`; rebuild the live cache (host→Kado) and confirm entries carry tags.
  5. WHY → `docs/tomo/scripts/moc-tree-builder.md` (or lib): why tags are cached (exclude-tag filters depend on them).
  6. Success: cache entries carry `tags` `[ref: PRD/F8 dependency AC]`.

- [ ] **T7.2 Exclude tags: `exclude/moc` (audit) + `exclude/note` (scan source)** `[activity: backend-api]` `[ref: SDD/ADR-13 B-moc/B-note; PRD/F8; lib/orphan_link.py emit_orphan_suggestions, moc-discovery.py _handle_scan]`
  1. Prime: `lib/orphan_link.emit_orphan_suggestions` (kind filter from T6.2), `moc-discovery._handle_scan` (scan candidate source), cache entry `tags` (from T7.1). Define hardwired constants `EXCLUDE_MOC_TAG = "MiYo/Tomo/exclude/moc"`, `EXCLUDE_NOTE_TAG = "MiYo/Tomo/exclude/note"` (single home, e.g. a small `lib/moc_tags.py` or top of each consumer).
  2. Test (RED):
     - `emit_orphan_suggestions(kinds=("moc",))` skips a MOC entry carrying `exclude/moc`; that MOC still appears in the `moc_entries` link-candidate pool (NOT removed).
     - root MOC tagged `exclude/moc` → not emitted by the audit.
     - `_handle_scan` skips a note entry carrying `exclude/note` (not a scan candidate → not clustered).
  3. Implement: in `emit_orphan_suggestions`, when building the orphan list, drop entries whose `tags` include the kind's exclude tag (moc→`exclude/moc`, note→`exclude/note`); keep the MOC in the candidate pool. In `_handle_scan`, skip note entries carrying `exclude/note`. Bump versions.
  4. Validate: `pytest tests/test_orphan_link.py tests/test_moc_discovery_scan_orphans.py -v`; live `check:moc-uplinks` after tagging a root MOC → it drops out.
  5. WHY → `docs/tomo/scripts/lib/orphan_link.md` + `moc-discovery.md`: audit-only semantics for `exclude/moc`; `exclude/note` at the candidate source.
  6. Success: B-moc audit-only + B-note never-clustered `[ref: PRD/F8 AC4-6]`.

- [ ] **T7.3 Dedup `candidate_stems` within a cluster (D4)** `[activity: backend-api]` `[parallel: true]` `[ref: SDD/ADR-13 D4; PRD/F8; moc-discovery.py phase3_cluster / _candidate_stems, lib/topic_signature.candidate_stems]`
  1. Prime: where a cluster's member/`candidate_stems` list is assembled (`phase3_cluster`, `_candidate_stems` `:~1134`, `lib.topic_signature.candidate_stems`). Find why a note enters twice (likely multi-facet topic match appends without dedup).
  2. Test (RED): a candidate matching a cluster via two facets appears once in the cluster's children/`candidate_stems`; the `#### Children (N)` count equals the unique count.
  3. Implement: dedup by path/stem when building the cluster member list (order-preserving). Bump version.
  4. Validate: targeted pytest; rebuild + render a scan doc → MOC children have 0 dupes.
  5. WHY → `docs/tomo/scripts/moc-discovery.md`: candidate_stems dedup.
  6. Success: no within-cluster duplicates `[ref: PRD/F8 AC3]`.

- [ ] **T7.4 Inter-cluster member-overlap dedup ≥80% (D3)** `[activity: backend-api]` `[ref: SDD/ADR-13 D3; PRD/F8; moc-discovery.py phase6_dedupe + _run_pipeline kept_clusters]`
  1. Prime: `phase6_dedupe` (`:~1196`, topics-vs-existing only), where `kept_clusters` is finalised in `_run_pipeline`, cluster member access (`_candidate_stems`). This is a NEW pass over the PROPOSED clusters — does not modify `phase6_dedupe`'s existing-MOC logic.
  2. Test (RED): two proposed clusters where the smaller's members are ≥80% inside the larger → smaller dropped, larger kept, drop recorded in `duplicates_skipped`; at 79% both survive (boundary); exact-subset (100%) dropped.
  3. Implement: after `phase6_dedupe`, add `_dedupe_overlapping_clusters(kept)` — for each pair (largest-first), if `|small ∩ large| / |small| >= 0.80`, drop the smaller, append to `duplicates_skipped`. Deterministic ordering (by size desc, then cluster_id). Bump version.
  4. Validate: targeted pytest; re-render the live scan → MOC05/MOC04-type near-duplicates gone (5→3 on the sample).
  5. WHY → `docs/tomo/scripts/moc-discovery.md`: inter-cluster member dedup (vs the topic/existing dedup).
  6. Success: overlapping proposals collapsed to the larger `[ref: PRD/F8 AC2]`.

- [ ] **T7.5 Drop the per-note orphan section from /moc-propose (D1)** `[activity: backend-api]` `[ref: SDD/ADR-13 D1; PRD/F8 AC1; moc-discovery.py _run_pipeline orphan block, suggestions-reducer.py render_moc_proposal_doc]`
  1. Prime: the orphan block in `_run_pipeline` (the Phase-6 `emit_orphan_suggestions(kinds=("note",))` + `_cap_orphans` + report `orphan_*` fields), `_run_moc_uplink_check` (the check path — KEEP), the reducer's orphan-section gate (`render_moc_proposal_doc` → `_render_orphan_section`).
  2. Test (RED): a cluster-mode DiscoveryReport (scan or scoped) renders NO `## Orphan Notes & MOCs` / `### Oxx` section; a `check-moc-uplinks` report STILL renders the MOC-uplink section (regression guard).
  3. Implement: remove the note-orphan pass from `_run_pipeline` (cluster path no longer emits `orphan_suggestions`); orphan suggestions are produced ONLY by `_run_moc_uplink_check`. Reducer renders the orphan section only when present (check-mode report) — verify the gate. Bump versions.
  4. Validate: `pytest tests/test_suggestions_reducer_orphan_render.py tests/test_moc_discovery_output_cap.py tests/test_reducer_moc_proposal_mode.py -v` (update any test asserting the orphan section in a cluster doc); full suite.
  5. WHY → `docs/tomo/scripts/moc-discovery.md` + `suggestions-reducer.md`: orphan section is check-mode-only (note-orphan flow → #30).
  6. Success: cluster proposal-doc has no note-orphan section; check-mode unaffected `[ref: PRD/F8 AC1]`.

- [ ] **T7.6 Phase 7 validation + sync + version bumps** `[activity: validate]`
  - Bump `# version:` on every edited managed file. `./scripts/update-tomo.sh --yolo` (agents/commands need sandbox-off — see memory `reference_update_tomo_sandbox_blocks_claude_dir`). Full `./venv/bin/python -m pytest -q` (only the 8 pre-existing ide_bridge failures allowed) + `ruff check`.
  - Live (host→Kado, mind the 429 — `reference_kado_429_blocks_host_full_pipeline`): rebuild cache (entries carry `tags`); render a scan proposal-doc → no `### Oxx` section, no within-cluster dupes, near-duplicate clusters collapsed; tag a root MOC `exclude/moc` → drops from `check:moc-uplinks`; tag a note `exclude/note` → absent from scan candidates.
  - Update `LIVE-VALIDATION-RUNBOOK.md` with the F8 checks. (021 finalize remains after the full in-container live pass — unchanged gate.)
