# XDD 015 — MSP Condition B: Accumulation Detection

**Status:** PRD complete · open questions resolved (2026-06-04) · **SDD blocked on Kado capability**
**Current phase:** SDD pending — gated on Kado outlinks/headings response
**Backlog origin:** F-34 (Must)

> **⛔ Blocker (2026-06-04):** The scanner needs two per-note signals Kado does
> not serve today — **outlinks** (`[[wikilinks]]`) and **headings** (H1/H2).
> Both live in Obsidian's `metadataCache` (no body read). Capability ask sent:
> `_outbox/for-kado/2026-06-04_tomo-to-kado_metadatacache-outlinks-headings.md`.
> Tomo can build the indexer skeleton against `listDir` (tags + path) now, but
> topic quality stays degraded until the two signals land. SDD locks once Kado
> replies with a surface.

## Problem in one paragraph

The Mental Squeeze Point feature surfaces "you should make a MOC for
this" when topic clusters accumulate without organisation. Today only
**Condition A** (in-batch cluster of 3+ inbox items) and **Condition C**
(placeholder MOC trigger — F-35, shipped 2026-05-07) fire end-to-end.
**Condition B** — the case where the inbox item's topics match 2+
existing atomic notes that already sit in the vault without an `up::`
link — is unimplemented. Latent clusters keep growing, the user
discovers them retroactively, and Tomo misses the moment when surfacing
the cluster would have been most useful.

## Solution in one paragraph

Pre-compute an accumulation index once per `/explore-vault` run: a new
scanner walks atomic notes via Kado, runs the existing
`topic-extract.py`, checks for `up::` presence, groups notes by topic,
and emits clusters of size ≥ 2. The cache stores it; `shared-ctx-builder`
surfaces it (size-budgeted to fit the 15 KB envelope); `inbox-analyst`
Step 4 fires Condition B when an item's topic matches a cluster key —
setting `needs_new_moc=true` with `proposed_moc_topic = <topic>`. No
per-item Kado searches at /inbox time, so Pass-1 cost stays unchanged.

## Files

- [requirements.md](requirements.md) — product requirements (PRD), draft
- solution.md — technical design (SDD), pending
- plan/phase-N.md — implementation plan, pending

## Tracking

- Backlog entry: `docs/XDD/backlog.md` → F-34
- Architecture decisions (locked 2026-05-07):
  - **Option (b)** — accumulation index pre-computed in shared-ctx pipeline
  - **Index shape** — `topic → list of stems`
- Branch when implementation starts: `feat/f-34-msp-condition-b-accumulation`
- Related specs: F-35 (shipped 2026-05-07, commit `5b3a031`),
  F-36 (new section proposal — natural follow-up),
  F-43 (MOC-creation skill — complementary)
- Constraint memory: `feedback_near_mvp_no_breakage.md` —
  additive only on hot paths.

## Open questions — RESOLVED (brainstorm 2026-06-04)

All seven OQs from requirements.md §8 are locked. Stakeholder: Marcus.

| OQ | Resolution |
| --- | --- |
| OQ1 scanner home | New `atomic-note-indexer.py` (separate script — `moc-tree-builder.py` is already 722 LOC, near the Constitution L2 cap). |
| OQ2 note discovery | `kado-search listDir` on `atomic_note.base_path` (returns tags + path + mtime, no body read). |
| OQ3 run mode | **Always run** on `/explore-vault` (cold path; single code path; benchmark-then-reconsider). |
| OQ4 normalisation | Lowercase + whitespace-collapsed string equality (matches F-35). |
| OQ5 min cluster size | **Configurable** `vault-config.tomo.accumulation.min_cluster_size`, **default 3** (quieter than the spec literal of 2). |
| OQ6 read depth | **Dissolved** — no body reads. Scanner consumes structured signals: tags + path via `listDir` today; outlinks + headings via the pending Kado capability. |
| OQ7 cache schema | Additive at `cache_version: 1`, missing field = empty dict (F-35 precedent). |

**Design reshape:** The PRD assumed Tomo reads note *bodies* to extract topics
(OQ6 was "full body vs head-only"). The brainstorm reframed this — Tomo needs
four *structured* signals (title, headings, outlinks, tags), all present in
Obsidian's `metadataCache`. This is faster and more accurate than body-parsing,
at the cost of the Kado dependency above.

**Parking lot (SDD detail):** whether `topic-extract.py` gains a structured-input
mode vs the indexer synthesising pseudo-content from Kado's structured fields.

## Notes

**F-47 schema requirement (2026-05-21):** Any new renderer this spec introduces that emits workflow documents (suggestions-fan, instructions docs, or similar pipeline outputs) MUST emit the `tomo:` block per `tomo/schemas/doc-frontmatter.schema.json` (F-47 Phase 1 SoT). Use `build_tomo_block()` from `tomo/scripts/lib/doc_frontmatter.py`. When this spec reaches SDD/plan phase, renderer-touch tasks must include "emits `tomo:` block per F-47 schema". See `docs/XDD/specs/017-tomo-lifecycle-tags/solution.md` §Data Models for the canonical field definitions.
