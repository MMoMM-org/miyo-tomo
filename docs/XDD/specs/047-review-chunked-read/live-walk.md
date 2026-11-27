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

Finding F-R1-2 (owner, after reading the R1b document → T9.3): the callout's previous-note lines name the note as a link (`Letzter Rückblick · Woche [[2026-W12]]: …`; not found stays plain text) and the callout gets a blank line before and after it. Fixed in da12572a (`review_doc.py` 0.6.3; spec 046 T4.2 unmapped-doc golden re-recorded, +2 blank lines per file only). Spec review PASS, code review PASS; full suite 12,407 passed, 1 known failure. R1 Pass 1 redone on the new format (R1c), Pass 2 of R1b skipped.

### R1c — week 2026-W13 (2026-11-26, session 74652cb2) — Pass 1 written

Instance at 12e9a7bc (F-R1-2 synced).

| Row | Count |
|---|---|
| Days read / not read (size / other) | 7 / 0 (0 / 0) |
| Previous notes found | 2; carryover items 21 (2026-W12 12, 2026-02 9) |
| Units dispatched per message | 1 digester + 1 carryover in one message; proposer alone |
| Agents self-started | 0 |
| Main-session Read/Grep/Bash on stage files | 0 (only `review-doc.py write --proposals <stage file>`) |
| `check` rounds / retries | 1 / 0 (digest 10,278 B raw) |
| Carried items placed / per mark | 20 / still open 12, not mentioned again 7, done 1 |
| Proposals | groups open 5, themes 2 (no `done`, no `growth`); sections 26 items |
| Vault growth | 8 candidates / 43 notes; 33 named in the proposals, no growth group, 10 not named (same as R1b) |
| Interruption | the container's login expired while the digester ran (~9 min wait); the digest was already written and `check` passed it |
| Content files after write | 0 |

Cost / time per step: main sonnet $0.53, 962 s (incl. the login wait), peak 89,280; digester haiku $0.13 / 76 s;
carryover sonnet $0.12 / 18 s / 16,112; proposer opus $2.06 / 142 s / 21,571; Pass 1 total $2.84.

Finding F-R1-3 (owner, R1b/R1c → T9.3): the document always holds the Vault growth group with every created note of the period; the proposer built none and 10 of 43 created notes appeared nowhere. Fixed: `review-doc.py write` builds the group from the digests' growth candidates (`lib/review_growth.py`, c6f09d56 + 61e0ac20); the proposer no longer proposes `growth` (`review-proposer.md` 0.2.0); spec 046 T4.2/T4.3 month goldens re-recorded (proposed growth item gone, ids shifted). Spec review PASS; code review FAIL (digest-read paths untested) → fixed → PASS.

Finding F-R1-4 (owner → T9.3): the group also shows the period's MOC changes — "MOCs changed" and "MOCs newly linked" items, links only, each MOC once (2ecc78bb, `review_growth.py` 0.2.0). Spec review PASS, code review PASS; full suite 12,436 passed, 1 known failure. SKILL.md's `growth` in a section row's groups left as is (a proposer hint; the config schema allows it).

### R1d — week 2026-W13 (2026-11-27, session db09291c) — Pass 1 written

Instance at a80650f8 (F-R1-3 and F-R1-4 synced). Stage stem `2026-W13_review`.

| Row | Count |
|---|---|
| Days read / not read (size / other) | 7 / 0 (0 / 0) |
| Previous notes found / carryover items | 2 / 24 (2026-W12 15, 2026-02 9); carried into the document 21 (12 + 9) |
| Units dispatched per message | 1 digester + 1 carryover in one message; proposer alone |
| Agents self-started | 0 |
| Main-session Read/Grep/Bash on stage files | 0 (only `review-doc.py write --proposals <stage file>`) |
| `check` rounds / retries | 1 / 0 |
| Not-condensed units | 0 |
| Proposals | open 7, themes 0, done 0; 12 sections, 22 items; 0 rejected |
| Vault growth | script-built: 8 items (all 43 created notes once, plus the MOC lines); owner: fits for now, later analysis in #274 |
| Agents run in the background | yes again (no harm) |
| Content files after write | 0 (only `meta.json` and the empty harness `.claude` folder) |

Cost / time per step: main sonnet $0.64, 376 s, peak 89,488; digester haiku $0.13 / 61 s / 50,712; carryover sonnet
$0.13 / 21 s / 16,289; proposer opus $1.50 / 98 s / 21,137; Pass 1 total $2.40 (guidance ≤ $0.80).

## KPI table

| KPI | Limit | Kind | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|---|---|
| Days not read because of size | 0 | hard | 0 | | | | |
| Sample / grep fallbacks | 0 | hard | 0 | | | | |
| Main-session reads of stage files | 0 | hard | 0 | | | | |
| Carried items placed twice / without previous link | 0 / 0 | quality | — (R1a no document) | | | | |
| Content files left after write, abort, drop | 0 | quality | 0 after write | | | | |
| Weekly Pass 1 cost | ≤ $0.80 | guidance | $2.40 (R1d; R1c $2.84, R1b $2.80, R1a $1.25 failed) | — | — | | — |
| Monthly Pass 1 cost / time | ≤ $2.00 / 7 min | guidance | — | | — | — | |
| Quarterly Pass 1 cost / time | ≤ $5.00 / 20 min | guidance | — | — | | — | — |
| Pass 2 cost | ≤ $0.85 | guidance | | | | | |
| Cost, time, peak context per step (main, digesters, carryover, proposer) | recorded | F8-AC1 | R1a above | | | | |
| Owner: at least as useful as the spec 046 document | yes/no | quality | | | | — | — |
