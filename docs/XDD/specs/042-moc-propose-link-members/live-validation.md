# Spec 042 — Live validation (T5.3)

Date: 2026-10-29. Target: `tomo-instance` (test vault `Privat-Test`), synced with
`./scripts/update-tomo.sh --instance tomo-instance --yolo`; `tomo-privat` untouched.
Final runtime versions: `moc-architect` 0.8.1, `moc-discovery` 0.24.3,
`lib/link_members` 0.3.1, `suggestions-reducer` 1.68.0.

Evidence sources: container transcripts under
`tomo-home/.claude/projects/-Volumes-Moon-Coding-MiYo-Tomo-tomo-instance/`
(sessions `d818bde9…` and `0ec5161a…`), `tomo-instance/tomo-tmp/`, and the docs in the
test vault's `100 Inbox/`. Lines quoted in code blocks are copied byte for byte.

## KPI summary

| KPI (plan T5.3 / PRD Success Metrics) | Result |
|---|---|
| ≥ 3 default-scan proposals carry a link member | ✅ 4 of 5 rendered (run 1b) |
| Attempts ≤ budget per run | ✅ 102 / 120 (scan), 1 (each `around:`) |
| 0 rate-limit aborts | ✅ 0; 429s occurred only on non-graph calls and were retried |
| No periodic note, MOC, attachment or out-of-scope note proposed | ✅ all 20 scan link members pass `NodeEligibility`, all under `Atlas/202 Notes/`; `around:` members likewise atomic notes |
| Owner review and tick ratio | ✅ 5 of 14 link members ticked in "Definition (MOC)" (36 %); 39 of 45 topic members kept |
| Every ticked member reaches the instructions | ✅ 44 / 44 ticked → `up::` + MOC body; 0 of 15 unticked; instructions-diff OK |

## Run 1a — default scan, first attempt (aborted)

`/moc-propose` stopped after Pass 2 returned exit 1. Cause: `moc-discovery.py` exit 1 means
"partial" (D3 dropped 104 overlapping clusters) and stdout held the full report, but
`moc-architect.md` Step 3c treated any non-zero exit as a process failure (rule from
F-43, predates 042). A host re-run of Pass 2 on the same Phase-1 file against live Kado
also showed the second finding: with 60 attempts all-or-nothing, 3 of 5 rendered
clusters (62 / 45 / 17 members) got no lookups and only 2 proposals carried link members.

```
[moc-discovery] links: rendered=5 not_rendered=40 lookups=55 attempts=55 failed=0 clusters_skipped_budget=3 members_total=19 skipped_uncached=0
```

Fixes (owner decisions in the README Decisions Log, SDD v1.2 / PRD v1.4):
- T5.3a — `moc-architect` 0.8.1 stops only on exit 2; exit 0 or 1 parses stdout.
- T5.3b — ADR-4 v1.2: budget 120, fair share per rendered cluster, larger clusters `sampled`.

## Run 1b — default scan (after T5.3a/T5.3b)

```
Discovery: OK — 214 candidates → 45 clusters; links: 20 members, 102 lookups (3 sampled: budget)
Proposal-doc: 100 Inbox/2026-10-29_1006_moc-proposal-quote-moc.md
```

| Cluster | Items | Status | Link members |
|---|---|---|---|
| (Quote) (MOC) | 62 | sampled | 1 |
| Definition (MOC) | 45 | sampled | 14 |
| 2611 Code Snippets (MOC) | 45 | sampled | 1 |
| Growth (MOC) | 20 | done | 4 |
| § (MOC) | 17 | done | 0 |

Wall time ≈ 2:40 min (Pass 2 ≈ 2 min). Pass 2 exited 1 and the agent continued as
designed. About 18 HTTP 429s, all on Phase 6.5 `kado-read` (outside the graph budget),
all retried; `lookups failed: 0`.

## Run 2 — `around:Mapping Method` (new MOC around a note)

```
Discovery: OK — 1 candidates → 1 clusters; links: 17 members, 1 lookups
Proposal-doc: 100 Inbox/2026-10-29_1040_moc-proposal-mapping-method-moc.md
```

18 children: the seed ticked, 17 neighbours unticked with `— linked with [[Mapping Method]]`;
6 neighbours with an `up::` to another MOC offered as `related::`. 1 attempt, no 429,
≈ 12 s.

## Run 3 — `around:Idea Emergence (MOC)` (extension)

First run:

```
Discovery: OK — 0 candidates → 1 clusters; links: 17 members, 1 lookups
Proposal-doc: 100 Inbox/2026-10-29_1059_moc-proposal-extend-idea-emergence-moc.md
```

Defect: the report's `link_stats.members_total` was 7 (missing members) but the agent
copied 17 from the stderr stats line, which `_around_lookup` printed before
`_run_around_extension` overwrote the count. Fixed in `moc-discovery` 0.24.3: one final
`links:` line built from the finished report (RED-proven test). Re-run:

```
[moc-discovery] links: lookups=1 attempts=1 failed=0 clusters_skipped_budget=0 clusters_sampled=0 members_total=7 skipped_uncached=0
Discovery: OK — 0 candidates → 1 clusters; links: 7 members, 1 lookups
Proposal-doc: 100 Inbox/2026-10-29_1136_moc-proposal-extend-idea-emergence-moc.md
```

Doc: `proposal_kind: moc-extension`, `### MOC01 — Extend [[Idea Emergence (MOC)]]`,
`#### Missing members (7)`, all unticked.

## Owner review and apply

The owner accepted only "Definition (MOC)" in run 1b's doc, kept 39 of 45 topic members
and ticked 5 of 14 link members (Authenticity, Autonomy, Connection, Gesundheit, Honesty).
`/inbox` Pass 2 rendered `2026-10-29_1216_instructions.json`:

- `create_moc` → `Atlas/200 Maps/Definition (MOC).md`, `supporting_items` = the 44 ticked members.
- 44 × `add_relationship` `up:: [[Definition (MOC)]]`, one per ticked member; none for the 15 unticked.
- The rendered MOC note lists all 44 ticked members and none of the unticked.
- instructions-diff: `create_moc 1 1 [OK]`, `TOTAL 1 1 [OK]`.

All ticked members had no prior `up::`, so the `related::` path was not exercised live
(covered by `tests/integration/test_moc_propose_e2e.py`).

The review surfaced a usability gap: the doc did not say what to do with it. T5.3c adds an
owner-approved `> **How to use this proposal**` block under `# MOC Proposal`
(`suggestions-reducer` 1.68.0). The four docs above predate it.

## Observations outside spec 042 (backlog candidates)

- Phase 6.5 labels an `up::` to an existing non-MOC note "existing up:: broken — ignored"
  (`moc-discovery.py` Phase 6.5: target not in the MOC stems → `broken`). Misleading wording;
  ticking such a member replaces that `up::`.
- Topic clustering yields titles such as "(Quote) (MOC)" and "§ (MOC)".
- The agent skipped Step 2 on repeated runs in one session and used `date +%s` instead of
  `run-id.py` for the run id; no effect on the output.
- The agent attributed the 429s to link lookups; they were Phase 6.5 reads.
- `around:` Discovery line reads "1 candidates → 1 clusters" / "0 candidates → 1 clusters".
- Sampled members follow Phase-1 candidate order, which depends on Kado's listing order;
  deterministic for a replayed Phase-1 file, not guaranteed across fresh scans.
- Code-review suggestions not taken: stderr tests for the seed-lookup and fewer-than-3
  aborts, a WHY sentence that resolve aborts log no `links:` line, a mid-cluster budget stop
  discarding a sampled cluster's partial hits (pinned behaviour).
