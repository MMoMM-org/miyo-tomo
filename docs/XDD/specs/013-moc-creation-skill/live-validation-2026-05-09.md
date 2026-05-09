---
title: "F-43 Live-Vault Validation"
spec: 013-moc-creation-skill
phase: 6
task: T6.2
date: 2026-05-09
status: in_progress
vault: <Marcus's real vault>
hashi_version: <fill: confirmed installed Hashi version, e.g. 0.2.0>
tomo_branch: feat/013-phase-4
tomo_commit: da86f71
---

# F-43 Live-Vault Validation

> Manual review against Marcus's real vault per T6.2. Per CON-8 (single-user pre-launch QA), Marcus's vault is the QA target — no synthetic test vault. Per CON-9, F-43 launch is gated on Hashi 0.2.0+ being installed and the collision guard being active.
>
> **Pre-flight checklist** (complete before running any /moc-propose):
> - [ ] Vault state snapshotted (git status / Obsidian sync / backup)
> - [ ] Hashi 0.2.0 (or later) installed and active in this vault (verify via plugin list)
> - [ ] Tomo container running (`./tomo-instance/begin-tomo.sh`)
> - [ ] No outstanding `/inbox` work that would interfere
> - [ ] `discovery-cache.yaml` is reasonably fresh (re-run `/explore-vault` if last run > 1 week ago)

---

## Performance Targets (PRD/SDD)

| Phase                                  | Target            | This run |
|----------------------------------------|-------------------|----------|
| `/moc-propose tag:X` cache-warm        | < 30s             | _<fill>_ |
| `/moc-propose tag:X` cache-miss path   | < 90s worst-case  | _<fill>_ |
| Pass-2 apply for 5-child MOC           | < 15s             | _<fill>_ |
| Multi-cluster `/moc-propose` render    | < 5s (5 clusters) | _<fill>_ |

---

## Per-Mode Runs

### Mode 1 — `tag:` (proactive single-cluster)

| Field                | Value                                                |
|----------------------|------------------------------------------------------|
| Trigger              | `/moc-propose tag:<your-tag>`                        |
| Wall-clock           | _<fill>_ s                                           |
| Proposal-doc path    | _<fill: 100 Inbox/tomo-moc-proposal-...md>_          |
| Cluster size         | _<fill: N children>_                                 |
| Cache state          | warm / miss                                          |

**Review checklist**:
- [ ] Proposal-doc parses in Obsidian (no broken dataview / wikilinks)
- [ ] Parent-resolution offered the right classification for MiYo profile
- [ ] Children list matches your mental model (precision/recall)
- [ ] No dataview-inline-field drift on existing files

**Notes** (anything surprising):

_<fill>_

---

### Mode 2 — `folder:`

| Field                | Value                                                |
|----------------------|------------------------------------------------------|
| Trigger              | `/moc-propose folder:<your-folder>`                  |
| Wall-clock           | _<fill>_ s                                           |
| Proposal-doc path    | _<fill>_                                             |
| Cluster size         | _<fill>_                                             |

**Review**:
- [ ] Proposal-doc parses in Obsidian
- [ ] Parent-resolution sensible
- [ ] Children list reasonable

**Notes**: _<fill>_

---

### Mode 3 — `class:`

| Field                | Value                                                |
|----------------------|------------------------------------------------------|
| Trigger              | `/moc-propose class:<your-classification>`           |
| Wall-clock           | _<fill>_ s                                           |
| Proposal-doc path    | _<fill>_                                             |
| Cluster size         | _<fill>_                                             |

**Review**:
- [ ] Proposal-doc parses
- [ ] Parent-resolution sensible
- [ ] Children list reasonable

**Notes**: _<fill>_

---

### Mode 4 — `title:` (placeholder seeding)

| Field                | Value                                                |
|----------------------|------------------------------------------------------|
| Trigger              | `/moc-propose title:<placeholder-title>`             |
| Wall-clock           | _<fill>_ s                                           |
| Proposal-doc path    | _<fill>_                                             |
| Cluster size         | _<fill>_                                             |

**Review**:
- [ ] Proposal-doc parses
- [ ] Title correctly used as the seed/placeholder
- [ ] Children inferred reasonably

**Notes**: _<fill>_

---

### Mode 5 — free-text (no prefix)

| Field                | Value                                                |
|----------------------|------------------------------------------------------|
| Trigger              | `/moc-propose <free-text-topic>`                     |
| Wall-clock           | _<fill>_ s                                           |
| Proposal-doc path    | _<fill>_                                             |
| Cluster size         | _<fill>_                                             |

**Review**:
- [ ] Proposal-doc parses
- [ ] Whitelist-only prefix routing correctly classified this as free-text
- [ ] Children inferred reasonably

**Notes**: _<fill>_

---

### Mode 6 — no-args (whole-vault scan)

| Field                | Value                                                |
|----------------------|------------------------------------------------------|
| Trigger              | `/moc-propose`                                       |
| Wall-clock           | _<fill>_ s                                           |
| Proposal-doc path    | _<fill>_                                             |
| Number of clusters   | _<fill>_ (PRD caps at 5)                             |

**Review**:
- [ ] Multi-cluster proposal-doc renders ≤ 5 sections
- [ ] Sections sorted by confidence (highest first)
- [ ] "Weitere N Cluster" footer present if more than 5 candidates
- [ ] Each cluster section parses cleanly in Obsidian

**Notes**: _<fill>_

---

## Override-Flow Scenario

> Pick a child whose existing `up::` points to a real classification MOC; tick **Override** in the proposal-doc; run `/inbox`; verify Hashi preserves the existing `up::` and adds `related:: <new MOC>`.

| Field                | Value                                                |
|----------------------|------------------------------------------------------|
| Test child note      | _<fill: vault path>_                                 |
| Pre-existing `up::`  | _<fill: classification target>_                      |
| Proposed new MOC     | _<fill>_                                             |
| Action ticked        | Override (preserve existing `up::`, new = `related::`) |
| Post-apply `up::`    | _<fill: should match pre-existing>_                  |
| Post-apply `related::` | _<fill: should match new MOC>_                     |

**Review**:
- [ ] Existing `up::` link preserved (Rule 4.x from PRD)
- [ ] New MOC link added as `related::`
- [ ] No double-link on `up::`
- [ ] Hashi did not write to the override-protected target

**Notes**: _<fill>_

---

## Pass-2 Apply Run

> Pick the proposal-doc with the largest accepted cluster (≥ 5 children); tick all Accept boxes; run `/inbox`; time the apply.

| Field                | Value                                                |
|----------------------|------------------------------------------------------|
| Proposal-doc         | _<fill>_                                             |
| # children accepted  | _<fill>_                                             |
| Wall-clock to apply  | _<fill>_ s                                           |
| Pass-2 target met?   | YES / NO (target < 15s for 5-child MOC)              |

**Review**:
- [ ] MOC created in `Atlas/200 Maps/` (or your configured location)
- [ ] All accepted children have `up:: [[<new MOC>]]`
- [ ] Hashi reported `applied:true` for all actions
- [ ] No silent overwrite of existing files (collision guard would have fired if so)

**Notes**: _<fill>_

---

## Risks (PRD/Risks and Mitigations)

For each risk in the PRD, mark fired-and-mitigated, not-fired-but-monitored, or N/A.

- [ ] Hashi destination-collision guard not implemented — _<not-fired (Hashi 0.2.0 active) | fired (give details)>_
- [ ] Render-time Kado read-per-child slows large MOCs — _<observation: actual seconds for largest tested cluster>_
- [ ] `discovery-cache.yaml` stale — _<not-fired | fired (cache age, refresh action taken)>_
- [ ] Squelch state grows unbounded — _<observation: current squelch entry count>_
- [ ] Multi-cluster proposal-doc renders very long — _<observation: lines for largest multi-cluster doc>_
- [ ] Parser regex changes break existing flow — _<not-fired | fired>_
- [ ] Hot-path `inbox-analyst` change breaks existing flow — _<not-fired | fired>_
- [ ] User runs `/moc-propose` without `/explore-vault` (cold cache) — _<intentionally tested? abort message verified?>_

---

## Regression Sanity Check

- [ ] Existing `/inbox` flow on a non-MOC-proposal note still works end-to-end
- [ ] Existing `/explore-vault` cache still loads without error
- [ ] No new noise in tomo container logs that wasn't there pre-F-43

**Notes**: _<fill>_

---

## Verdict

- [ ] All performance targets met
- [ ] All input modes worked end-to-end
- [ ] Override flow validated
- [ ] Pass-2 apply validated
- [ ] No regressions in existing inbox flow
- [ ] All applicable risks accounted for

**Overall verdict**: PASS / FAIL / PARTIAL — _<fill>_

**Launch gate decision**: GO / NO-GO — _<fill>_

**Findings to capture in memory** (non-obvious lessons for `/memory-add` in T6.3 Stream B):

1. _<fill>_
2. _<fill>_
3. _<fill>_

---

## Sign-off

- Validated by: Marcus
- Date: _<fill>_
- Hashi version verified active: _<fill>_
- Tomo commit: `da86f71` (T6.3 Stream A close)
