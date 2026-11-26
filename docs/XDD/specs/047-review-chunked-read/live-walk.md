# Spec 047 live walk — tomo-instance, test vault

Counts only; no journal text. Runs in a fresh container session each, on `tomo-instance` (never `tomo-privat`).
Cost per step from `scripts/tomo-session-stats.py` (rates of `tomo-token-usage.py`); peak = input + cache_read.
Main-session tool calls on stage files counted with the `review-no-stage-read` grader-1 rule.

## Runs

### R1a — week 2026-W13 (2026-11-26, session da8d7684) — FAILED in Pass 1

Instance at 095b99a4 (T9.1 sync).

| Row | Count |
|---|---|
| Days read / not read (size / other) | 7 / 0 (0 / 0) |
| Previous notes found | 2 (2026-W12, 2026-02) |
| Units dispatched per message | 1 digester + 1 carryover, one message, twice (first try + retry) |
| Agents self-started | 0 |
| Main-session Read/Grep/Bash on stage files | 0 |
| `check` rounds | 2 (the bound) |
| Digester result | `digest-too-large` both times (9,871 B raw, 9,404 B compact, cap 8,192 B) → `failed` |
| Carryover result | first `/notes: carryover-notes-mismatch`, retry passed (2 notes, 14 + 8 items) |
| Outcome | `nothing-condensed` stop, no document (F6-AC8 behaviour as designed) |
| Agents run in the background | yes — the Agent calls returned "Async agent launched"; the skill waited for every report before `check` (no harm here) |

Cost / time per step: main sonnet $0.68, 396 s, peak 91,769; digester haiku $0.20 / 115 s / 50,561 and $0.13 / 62 s / 50,715;
carryover sonnet $0.11 / 19 s / 16,136 and $0.12 / 19 s / 16,113; total $1.25.

Finding F-R1-1 (→ T9.3): the digest cap counts note paths the digester cannot condense. Of the 9,404 compact bytes,
`growth` holds 3,243 (8 groups, 43 created-note paths) and the 89 `sources` entries 3,160; without the growth note
paths and every `sources` list the digest is 2,871 B. The quarter's cap per unit (114,688 / 15 = 7,645 B) and its
busiest growth day (32,745 B growth file) would fail the same way. Owner decision: paths outside the cap.
Fixed in T9.3 (861cf8fe, bc8cbf1d): `cap_bytes` measures the compact digest without the growth `notes` and every `sources` list; `source-duplicate` and `growth-note-duplicate` bound the paths; lone surrogates counted, not raised (`review_digest.py` 0.2.1, `review-digester.md` 0.1.4). Spec review PASS; code review FAIL (surrogate crash) → fixed → PASS. Full suite 12,397 passed, 1 known failure. Re-run of R1 pending.

### R1b — week 2026-W13 (2026-11-26, session f9802772) — Pass 1 written

Instance at 7b65942d (T9.3 fix F-R1-1 synced; stale R1a stage discarded with `review_stage.discard`).

| Row | Count |
|---|---|
| Days read / not read (size / other) | 7 / 0 (0 / 0) |
| Previous notes found / carried | 2 / 25 (2026-W12 16, 2026-02 9) |
| Units dispatched per message | 1 digester + 1 carryover in one message; proposer alone |
| Agents self-started | 0 |
| Main-session Read/Grep/Bash on stage files | 0 (one Bash passes `proposals.json` to `review-doc.py write`, allowed by the grader-1 rule) |
| `check` rounds / retries | 1 / 0 (digest 11,866 B raw, passed under the new measure) |
| Not-condensed units | 0 |
| Proposals | groups open 3, themes 2 (no `done`, no `growth` group); 11 sections, 26 items |
| Vault growth | 8 digest candidates / 43 created notes; 33 of them named in the proposals (in sections), no growth group, 10 not named — owner to judge (F2-AC1) |
| Agents run in the background | yes again — the main session noted it asked for foreground |
| Content files after write | 0 (only `meta.json` and an empty harness `.claude/.cc-writes` folder) |

Cost / time per step: main sonnet $0.55, 261 s, peak 89,613; digester haiku $0.17 / 92 s / 50,658; carryover sonnet
$0.13 / 22 s / 16,114; proposer opus $1.95 / 134 s / 22,794 (32,158 output tokens, 78,510 cache-write); Pass 1 total
$2.80 (guidance ≤ $0.80: over by $2.00, the proposer alone $1.95).

## KPI table

| KPI | Limit | Kind | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|---|---|
| Days not read because of size | 0 | hard | 0 | | | | |
| Sample / grep fallbacks | 0 | hard | 0 | | | | |
| Main-session reads of stage files | 0 | hard | 0 | | | | |
| Carried items placed twice / without previous link | 0 / 0 | quality | — (R1a no document) | | | | |
| Content files left after write, abort, drop | 0 | quality | 0 after write | | | | |
| Weekly Pass 1 cost | ≤ $0.80 | guidance | $2.80 (R1b; R1a $1.25 failed) | — | — | | — |
| Monthly Pass 1 cost / time | ≤ $2.00 / 7 min | guidance | — | | — | — | |
| Quarterly Pass 1 cost / time | ≤ $5.00 / 20 min | guidance | — | — | | — | — |
| Pass 2 cost | ≤ $0.85 | guidance | | | | | |
| Cost, time, peak context per step (main, digesters, carryover, proposer) | recorded | F8-AC1 | R1a above | | | | |
| Owner: at least as useful as the spec 046 document | yes/no | quality | | | | — | — |
