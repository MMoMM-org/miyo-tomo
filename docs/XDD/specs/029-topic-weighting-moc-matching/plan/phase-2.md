---
title: "Phase 2: Both-Site Integration"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Both-Site Integration

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Interface Specifications — Internal API Changes]` — `_find_jaccard_match(+cluster_title)` + call site
- `[ref: SDD/Runtime View — Flow A + Flow B]`
- `[ref: SDD/Cross-Cutting Concepts — Squelch-Signature Invariance]`
- `[ref: SDD/ADR-4 + ADR-7]` — two substrates; agent-author edit
- `[ref: PRD/Feature 2 + Feature 3]`

**Key Decisions**:
- ADR-4 (Site 1 exact; Site 2 simplified Option A). ADR-7 (analyst edit via `tcs-helper:agent-author`, rationale to `docs/tomo/`). Squelch signature frozen.

**Dependencies**:
- Phase 1 (`lib/topic_match.weighted_overlap`) complete.
- T2.1 and T2.2 touch **disjoint files** (`moc-discovery.py` vs `inbox-analyst.md`) → run in parallel.

---

## Tasks

Wires the one weighting rule into both match sites and locks the zero-disturbance guarantee.

- [x] **T2.1 Site 1 — deterministic dedupe wiring** `[parallel: true]` `[activity: backend-api]`

  1. Prime: Read `_find_jaccard_match` (~1174), `_moc_topic_set` (~1118), and the `phase6_dedupe` call site (~1264-1290) `[ref: SDD/Interface Specifications; Runtime View Flow A]`.
  2. Test (RED) — add to `tests/test_topic_match.py` (or a sibling `tests/test_moc_discovery_dedupe.py`):
     - `_find_jaccard_match` now consumes `cluster_title` and delegates to `weighted_overlap`; a flat-≥0.80-but-titles-disagree cluster is NOT flagged, a title-agreeing cluster IS flagged `[ref: PRD/Feature 1; SDD/Traced walkthrough 2]`
     - **squelch-invariance golden hash**: capture `GOLDEN_HASH` from `compute_topic_signature` on **pre-F-05 `main`** (record how it was captured), then assert post-change output is byte-identical — this proves invariance to prior behavior, not mere self-consistency `[ref: PRD/Feature 3; SDD/Squelch-Signature Invariance]`
     - **malformed / title-less entry**: feed `_find_jaccard_match` a `map_notes` entry with no `title` key (and a non-dict entry) → scores on base weights with no `KeyError`/`TypeError` `[ref: SDD/Runtime View — Error Handling]`
     - first-match early-return and exact-title short-circuit preserved `[ref: SDD/Implementation Gotchas]`
  3. Implement (GREEN): add `cluster_title: str` param to `_find_jaccard_match`; per-entry `weighted_overlap(cluster_topics, cluster_title, _moc_topic_set(entry), entry.get("title") or "")`; call site passes `cluster.get("title") or ""`. Keep threshold `0.80` and early-return. Update the `phase6` log line if "jaccard" wording becomes misleading.
  4. Validate (REFACTOR): `./venv/bin/python -m pytest tests/ -q`; `./venv/bin/ruff check tomo/scripts`; confirm `lib/topic_signature.py` untouched and no cache-shape change.
  5. Success:
     - [x] Weighted dedupe rejects incidental overlap, keeps true dups `[ref: PRD/Feature 1]`
     - [x] Squelch keys byte-identical; no schema/version bump `[ref: PRD/Feature 3]`

- [x] **T2.2 Site 2 — analyst recipe wiring** `[parallel: true]` `[activity: prompt-engineering]`

  1. Prime: Read `inbox-analyst.md` Step 4 "Match MOCs" (lines ~114-120) and confirm `shared_ctx.mocs[]` carries `.title` + `.topics` `[ref: SDD/Runtime View Flow B; ADR-4]`.
  2. Test (RED): define the worked example the recipe must satisfy — an item with a title-theme match to MOC-A and an incidental content-keyword match to MOC-B must rank MOC-A above MOC-B `[ref: PRD/Feature 2]`. **Lock the decision-direction as a unit test**: run this same worked example through Site 1's `weighted_overlap` and assert MOC-A scores higher than MOC-B (ADR-4 decision-equivalence) — this makes the prose recipe the only untestable residue, not the whole feature `[ref: SDD/ADR-4]`. (The recipe wording itself is validated by the `agent-author` audit + Phase 3 live run.)
  3. Implement (GREEN) via `tcs-helper:agent-author`: edit Step 4 so a topic is weighted ×2 if title-derived on **either** side (Option A); redefine `overlap_ratio = weighted_shared / weighted_union`; **preserve** the `≥ 0.15` keep-gate, `top 3` cap, and `+0.1` depth bonus; state `W_TITLE`/`W_BASE` inline. Bump `# version` in `inbox-analyst.md`. Write the WHY-doc at `docs/tomo/dot_claude/agents/inbox-analyst.md` (rationale, ADR-4 asymmetry, spec ref).
  4. Validate (REFACTOR): run the `agent-author` audit; confirm gate/cap/bonus unchanged and version bumped.
  5. Success:
     - [x] Recipe ranks title-theme match above incidental keyword match `[ref: PRD/Feature 2]`
     - [x] Gate, cap, depth bonus preserved; `# version` bumped `[ref: SDD/Must Preserve]`
     - [x] WHY-doc written; runtime file stays imperative-only `[ref: SDD/CON-5; ADR-7]`

- [x] **T2.3 Phase Validation** `[activity: validate]`

  - Run `./venv/bin/python -m pytest tests/ -q` and `./venv/bin/ruff check tomo/scripts scripts`. Verify both sites express the same weighting rule (ADR-4 decision-equivalence). Confirm no change to `lib/topic_signature.py` or the cache schema.
