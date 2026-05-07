# XDD 015 — MSP Condition B: Accumulation Detection

**Status:** PRD draft — 2026-05-07
**Current phase:** requirements.md (PRD)
**Backlog origin:** F-34 (Must)

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

## Open questions before SDD

See requirements.md §8 (OQ1–OQ7). Tentative leans noted; stakeholder
input required before SDD locks the surface.
