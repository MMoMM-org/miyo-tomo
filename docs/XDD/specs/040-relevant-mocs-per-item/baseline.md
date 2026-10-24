# Spec 040 — Baseline runs

Figures only. Per-item details (MOC paths and titles, item stems) stay out of
git, in `tomo-instance/spec-040-baseline/` (gitignored), as decided on
2026-10-24 (public repo).

## Setup

| Field | Value |
|---|---|
| Vault | test vault (`Privat-Test`) |
| Instance code | `main` at be149c50 (synced 2026-10-24; includes #195 and `instruction-render.py` 0.67.1) |
| Inbox set | 12 items: the 2026-10-13 cost-baseline inbox (11) with all captured state removed, plus 1 seeded item for F3-AC1 |
| Reset between runs | `tomo-instance/spec-040-baseline/prepare-run.sh` (inbox restored from the set, previous content archived, `reset-tomo-tmp.sh --pass1`) |
| Discovery cache | unchanged across all runs (last scan 2026-09-14; 65 MOCs, 10 classification) |
| Context build | `mocs_included=65 topics_dropped=0`, no budget warning, reconcile clean |

A probe run with only 6 fresh items (2026-10-24T11-52-21Z-9d122e) showed that
four set items still carried `tomo.state: captured`; it is not part of the
baseline.

## Runs

| Run | run_id | Items | Reads | Spilled | Avg cache-write / item | Avg $ / item | Subagent total |
|---|---|---|---|---|---|---|---|
| before-1 | 2026-10-24T12-28-46Z-784e8b | 12 | 29 | 0 | 120,665 | 0.617 | $7.41 |
| before-2 | 2026-10-24T12-37-05Z-ead76f | 12 | 29 | 0 | 115,979 | 0.601 | $7.21 |
| **mean** | | | | **0** | **118,322** | **0.609** | |

Prices: the measurement script's Sonnet list rates. The orchestrator total is
not compared: both runs share one main session with the probe run in it.

before-2 was started with `/inbox --force` after the main session's model, which
still held the earlier runs in context, asked about the reset. Routing was
identical (12 fresh sources, 3 batches); the analyst subagents are fresh per
dispatch. **The after-run starts in a fresh Claude session** (a restart is
needed after the sync anyway).

## Reads per item (both runs identical)

- `--field mocs` result: 29,455 bytes per read (spill floor ~37,700).
- 8 of 12 analysts read Step 1, `mocs` and `placeholder_links`.
- 3 analysts read Step 1 only and skipped MOC matching entirely — one of them
  a regular note, which ended with no candidates and no `needs_new_moc`.
- 1 analyst read `mocs` but not `placeholder_links`, also ending with no
  candidates and no `needs_new_moc`. This is the
  unscripted zero-match path the SDD decision table (row 3) closes.

## Candidate agreement between the before-runs

Agreement = share of one run's candidate MOC paths (per-item union over all
actions) that appear in the other run's union for the same item.

| Direction | Hits / total | Agreement |
|---|---|---|
| before-1 → before-2 | 7 / 9 | 78% |
| before-2 → before-1 | 7 / 10 | 70% |

All five differing candidates are secondary picks scored 0.15–0.3, three of
them classification MOCs. Thematic candidates alone agree 6 of 7 (86%,
before-1 → before-2).

**After-run bar:** min(90%, 70%) = **70%** candidate agreement against each
before-run (PRD KPI), computed by `tomo-instance/spec-040-baseline/agreement.py`.

`needs_new_moc` flags: 4 (before-1), 5 (before-2). Proposed MOCs in the
document: 3 and 2.

## Seeded item (F3-AC1)

A German note whose natural new-MOC name is the German alias of an existing
English-titled MOC. Both runs linked the existing MOC instead of proposing a
new one (score 0.55 and 0.5, pre-checked both times; the probe run scored
0.4, unticked). No duplicate proposal in either run.

## Targets for the after-run

| KPI | Target |
|---|---|
| Candidate agreement vs each before-run | ≥ 70% |
| Duplicate proposals (cluster key equals an eligible thematic title) | 0 |
| Analyst MOC reads delivered as preview | 0 |
| Avg cache-write / item | ≤ 106,490 (≥ 10% below the 118,322 mean) |
| Avg $ / item | ≤ 0.603 |
| Seeded item | links the existing MOC, no proposal |

## After-run 1 (T6.3)

| Field | Value |
|---|---|
| run_id | 2026-10-24T15-41-07Z-f1879d |
| Session | fresh container session after `update-tomo.sh --instance tomo-instance` (analyst 0.27.0, builder 1.14.0, reader 0.3.1, reducer 1.61.0) |
| Inbox | the same 12-item set, restored by `prepare-run.sh` |
| Context build | 64 eligible, 1 excluded, `names_bytes=1189`, no size warning |

| Run | Items | Reads | Spilled | Avg cache-write / item | Avg $ / item | Subagent total |
|---|---|---|---|---|---|---|
| after-1 | 12 | 36 | 0 | 95,792 | 0.538 | $6.46 |

### Against the targets

| KPI | Target | After | Verdict |
|---|---|---|---|
| Candidate agreement vs before-1 | ≥ 70% | 6 / 9 = 67% | 🔴 missed |
| Candidate agreement vs before-2 | ≥ 70% | 6 / 10 = 60% | 🔴 missed |
| Duplicate proposals | 0 | 0 | 🟢 |
| MOC reads delivered as preview | 0 | 0 of 36 | 🟢 |
| Avg cache-write / item | ≤ 106,490 | 95,792 (−19% vs mean) | 🟢 |
| Avg $ / item | ≤ 0.603 | 0.538 (−12% vs mean) | 🟢 |
| Seeded item | links existing MOC | linked, score 0.9, pre-checked; no proposal | 🟢 |

**Agreement differences.** Every before-run candidate the after-run dropped was
a secondary pick scored 0.17–0.3: 3 against before-1 (two of them the
classification MOC 2900), 4 against before-2 (two classification). The
after-run lists more candidates (13 against 9 and 10) and scores them higher:
three pre-checked candidates against one in each before-run. Thematic
candidates alone agree 6 of 7 (86%) with before-1 and 5 of 7 (71%) with
before-2. The per-item list is in `tomo-instance/spec-040-baseline/after-1.json`.

**Proposals.** The document proposes `History` and `Places`, both
`placeholder_targets` entries (decision row 1), the same two the before-runs
proposed. No eligible thematic title equals either; `004 History` is a
dashboard note at the vault root. `duplicate_proposals_converted=0`.

**Names read (F1-AC1).** 8 of 12 analysts read `--moc-names`. The four that
did not: the daily-log item (`update_daily`, no MOC step), two empty test notes
(Step 1 only, as in both before-runs), and one content-free control note that
read `placeholder_targets` but skipped the names and proposed a new MOC. That
proposal never reached the document: the atomic scored 0.15 worthiness, and the
reducer suppresses sub-0.5 atomics before they can seed a Proposed MOC.
