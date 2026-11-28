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

Pass 2 (same session): `parse` approved, `preview`, `deliver` into `Calendar/302 Weekly/2026-W13.md` (block replaced, 0 escaped lines, 0 problems); stage after delivery: `meta.json` only. Applied with Hashi by the owner. Main sonnet $0.34 (session $0.98 − Pass 1 $0.64), peak 103,496 (guidance ≤ $0.85).
Owner after the apply (point 2, carried marks and once-only): ok for now — wrong marks in this kind of document show only over time.

### R2 — month 2026-03 (2026-11-27, session f98baafd) — Pass 1 written

Instance at a80650f8. Stage stem `2026-03_review` (046-walk `meta.json` replaced by the new read). The applied R1d document was listed as `applied`, not offered.

| Row | Count |
|---|---|
| Days read / not read (size / other) | 31 / 0 (0 / 0) |
| Units | 6 (2026-W09 … 2026-W14) |
| Previous notes found / carryover items | 2 / 22 (2026-02 10, 2025-Q4 12); carried into the document 19 (10 + 9) |
| Units dispatched per message | 6 digesters + 1 carryover in one message; proposer alone |
| Agents self-started | 0 |
| Main-session Read/Grep/Bash on stage files | 0 (only `review-doc.py write --proposals <stage file>`) |
| `check` rounds / retries | 2 / 1 (W09: `source-outside-unit`, passed on retry) |
| Not-condensed units | 0 |
| Proposals | open 4, themes 0, done 0; 16 sections, 41 items; 0 rejected; weekly only 2, not in weekly 0 |
| Vault growth | script-built: 29 items (→ #274) |
| Agents run in the background | yes (no harm) |
| Content files after write | 0 (only `meta.json`) |

Cost / time per step: main sonnet $0.81, 679 s, peak 90,445; digesters haiku $0.05 / 26 s / 22,584, $0.05 / 24 s / 22,717,
$0.18 / 94 s / 57,935, $0.19 / 99 s / 55,395, $0.07 / 35 s / 29,357, $0.19 / 97 s / 57,347, W09 retry included;
carryover sonnet $0.12 / 20 s / 15,397; proposer opus $4.45 / 286 s / 61,700. Pass 1 total $6.27, 8.3 min
(guidance ≤ $2.00 / 7 min: over by $4.27 and 1.3 min; the proposer alone $4.45).

Pass 2 (same session): `parse` approved, `preview`, `deliver` into `Calendar/303 Monthly/2026-03.md` (block replaced, 0 escaped lines, 0 problems); stage after delivery: `meta.json` only. Applied with Hashi by the owner. Main sonnet $0.52 (session $1.33 − Pass 1 $0.81), peak 120,282 (guidance ≤ $0.85).

Finding F-R2-1 (owner, R1d/R2 cost → T9.3): the opus proposer is most of every Pass 1 (week $1.50 of $2.40, month $4.45 of $6.27); the owner asks whether sonnet suffices. Fixed for test in c647935f: `review-proposer` runs on `sonnet` (0.2.1), ADR-7 amended (solution.md v1.11), WHY and privacy docs updated. Spec review PASS, code review PASS; full suite 12,438 passed, 1 known failure. Check: R2b re-runs month 2026-03 on sonnet; the owner compares it with the opus document (delivered in R2) — on quality loss opus comes back.

### R2b — month 2026-03 on the sonnet proposer (2026-11-27, session 3ff157fb) — Pass 1 written

Instance at 0ab8f070 (`review-proposer` 0.2.1, sonnet). The opus document and Pass 2 files of R2 were copied outside the vault and the repo first (owner's comparison copy, not recorded here).

| Row | Count |
|---|---|
| Days read / not read (size / other) | 31 / 0 (0 / 0) |
| Previous notes found / carryover items | 2 / 23 (2026-02 10, 2025-Q4 13); carried into the document 23 (10 + 13) |
| Units dispatched per message | 6 digesters + 1 carryover in one message; proposer alone |
| Agents self-started / main-session reads of stage files | 0 / 0 |
| `check` rounds / retries | 1 / 0 |
| Proposals | open 3, themes 1, done 3; 15 of 16 sections filled, 55 items; 0 rejected; weekly only 1, not in weekly 4 |
| Vault growth | 29 items (script-built, same as R2) |
| `write` | first refused `doc-name-taken` (the file at `100 Inbox/2026-03 Review.md` did not read as Tomo's review then); the owner removed the old files, the second `write` passed |
| Content files after write | 0 (only `meta.json`) |

Cost / time per step: main sonnet $0.89, 498 s, peak 105,441; digesters haiku $0.05–$0.21 each ($0.87 together); carryover
sonnet $0.12 / 18 s / 15,572; proposer sonnet $0.95 / 237 s / 63,897. Pass 1 total $2.83, 7.3 min to the first `write`
(8.2 min with the owner's answer). Against R2 (opus): total $6.27 → $2.83, proposer $4.45 / 286 s → $0.95 / 237 s.

Count comparison, opus (R2) → sonnet (R2b): section items 41 → 55; open 4 → 3; themes 0 → 1; done 0 → 3; carried 19 → 23;
weekly only 2 → 1; not in weekly 0 → 4; rejected 0 → 0.

Quality (owner: "looks ok"; orchestrator side-by-side, no text recorded): sonnet uses the groups (done, themes, open) and places the not-in-weekly items in their own group where opus put them into the Plan section; it places more carried items in sections. Weaker: weighting in two sections (smaller wins, the month review thinner), one less precise energy line, more day links, two trivial items, two statements to check against the dailies. Outcome: sonnet stays for R3; proposer rules revisited only if the weak points recur.

Finding F-R2-2 (→ backlog R-47g): the first `write` refused `doc-name-taken` on the applied R2 document; cause not found, not reproduced, nothing overwritten.

### R3 — quarter 2026-Q1 on the sonnet proposer (2026-11-27, session 85bfdc98) — Pass 1 written, partly condensed

Instance at 0ab8f070. Stage stem `2026-Q1_review` (046-walk `meta.json` replaced). The applied R2b month was listed as `applied`.

| Row | Count |
|---|---|
| Days read / not read (size / other) | 90 / 0 (0 / 0); read 137 s |
| Units | 15 (W04 split into W04a/W04b) |
| Previous notes found / carryover items | 1 (2025-Q4) / 14; carried into the document 13 |
| Units dispatched per message | 15 digesters + 1 carryover in one message; the 4 retries + carryover in one message; proposer alone |
| Agents self-started / main-session reads of stage files | 0 / 0 |
| Main-session Read of other files | 1: the harness-persisted `review-read.py` output (30,858 B, too big for the Bash result; paths and counts, no note text) |
| `check` rounds / retries | 2 (the bound) / 5: W01, W06, W08 `source-outside-unit` → passed; carryover `carry-source-unknown` on every item → passed; W04a `schema (/growth)` twice → **failed** |
| Not-condensed units | 1: W04a (4 days, 2026-01-19 … 2026-01-22) — named in the document |
| Proposals | open 8, themes 0, done 3; 14 sections, 63 items; 0 rejected; monthly only 0, not in monthly 0 |
| Vault growth | 746 created notes, 1 MOC changed, 3 newly linked → **526 items, 460 of them a bare single-note link** (notes no digest candidate covers) |
| Content files after write | 0 (only `meta.json`) |

Cost / time per step: main sonnet $1.71, 1,096 s, peak 131,575; 19 digester runs haiku $0.09–$0.44 each ($3.53
together, peak up to 113,285); carryover sonnet $0.08 + $0.07; proposer sonnet $1.19 / 270 s / 95,701. Pass 1 total
$6.48, 15.2 min (guidance ≤ $5.00 / 20 min: cost over by $1.48, time within).

Finding F-R3-1 (→ T9.3): the Vault growth group does not scale to a quarter. A unit's digest holds ≤ 15 candidates of
≤ 10 notes (≤ 150 notes); the quarter created 746, so 460 land as one bare link each (F-R1-3 lists every created note).
Finding F-R3-2 (→ T9.3): a `schema (/growth)` error fails the whole unit — W04a lost its 4 days of condensing over the
growth candidates, which only group links the script builds anyway.
Owner decisions: F-R3-1 — uncovered notes one item per folder with a count, no links; F-R3-2 — drop only the growth candidates. Fixed: F-R3-2 in f8e91450 (`review_digest.py` 0.3.0, `review-digest.py` 0.2.0; notice `growth-dropped`), spec review PASS, code review PASS (4 mutations caught); F-R3-1 in 180708f1 (`review_growth.py` 0.3.0, `review_doc.py` 0.7.3; no golden changed), spec review PASS, code review PASS (3 mutations caught); ADR-4 and ADR-6 amended (solution.md v1.12). Full suite 12,472 passed, 1 known failure. R3 re-run (R3b) pending.

### R3b — quarter 2026-Q1 after the F-R3 fixes (2026-11-27, session 27684b9f) — Pass 1 stopped at replace

`review-digest.py check`: all 15 units passed, W04a with notice `growth-dropped` (F-R3-2 works live). `write` → `review-exists` (the R3 document); owner chose Replace; `replace --confirm` → `stopped`, `kado-write-failed`, `KadoToolError`, 3 calls. Kado audit: two frontmatter reads (target, document), no write entry. Nothing written; stage and proposals kept.

Finding F-R3b-1 (→ T9.3): `replace` wrote over Tomo's own document without `expectedModified`; Kado refuses an update of an existing file without it (CONFLICT, `concurrency-guard.ts`). Present since spec 045; the fake vault never applied Kado's guard. Fixed in a1678a69 (`review-doc.py` 0.11.2: the document's `modified` is sent; the stopped result carries `error.code`, a closed uppercase token only); the shared fake (`tests/note_fake_vault.py`) now enforces the guard. Spec review PASS, code review PASS (mutation caught).

Finding F-R3b-2 (→ T9.3, found by the stricter fake): Pass 2 overwrote `<stem>_review_instructions.md` unstamped on a re-delivery and on a drop. Owner: fix now. Fixed in 0061346f (`review_state.py` 0.7.1 `md_modified`, `review_instructions_deliver.py` 0.1.2, `review-instructions.py` 0.6.2; +1 Kado call on those two paths only); the fake's exemption removed. Spec review PASS, code review PASS. Full suite 12,487 passed, 1 known failure.

Retry (2026-11-28, session 63e0739c): `/review 2026-Q1` listed the R3 document `open` and asked Continue · Start over · Abort; Continue → `parse` of the R3 document (612 kept, not approved) → stop. Nothing written; R3b stage kept.

Finding F-R3b-3 (→ T9.3): a Pass 1 whose write stopped leaves `proposals.json` staged, but the open-review question had no path to write it: Continue parses the old document, Start over reads the period anew. Owner: fix the flow. Fixed in 948f8bf5 (`review_state.py` 0.7.2 `new_read` when the stage holds `proposals.json`; `periodic-review` 0.3.1 asks Replace with the new read · Continue · Start over · Abort, Replace → `replace --confirm`). Spec review PASS, code review PASS (3 mutations caught). Full suite 12,494 passed, 1 known failure. Open (minor): on that Replace path the step 5 `proposals-invalid` re-dispatch and the `previous` report lines assume `plan` and step 4 ran in the session.

Replace (2026-11-28): the R3b document was written. Owner on Vault growth: 65 candidate items, the creation-day daily link reads as a duplicate note, and `Calendar/301 Daily: 44` counts only the dailies no candidate covered.

Finding F-R3b-4 (→ T9.3, closes #274): owner decision: Calendar folders as counts only, other folders as note links up to 10 notes, else a count; MOC items kept; the digester's growth candidates dropped. Fixed in d65be732 (`review_growth.py` 0.4.0, `review_config.py` 0.3.3 `calendar_base`, `review-doc.py` 0.11.3, `review_digest.py` 0.4.0, `review-digest.py` 0.3.0, `review-digester` 0.2.0, `periodic-review` 0.3.2, digest schema without `growth`). Spec review PASS, code review PASS (5 mutations caught). Full suite 12,442 passed, 1 known failure. Open: `weeks.json` still counts the growth files in the unit byte budget, and a day with only a created note still takes part (a digester run with nothing to condense for it).

### R3c — quarter 2026-Q1 after F-R3b-3 and F-R3b-4 (2026-11-28, session d191014e) — Pass 1 written

`/review 2026-Q1` listed the R3b document `open` (`new_read: false`); owner chose Start over → `review-read.py --fresh` (15 units, 121 s, moved to the background at the 120 s Bash timeout and finished there) → `plan` → 15 digesters (haiku) + carryover (sonnet) in one round → `check`: 14 of 15 passed, W05 `retry` (3 `source-outside-unit`) → one re-dispatch → second `check` all 15 passed, carryover passed → proposer (sonnet) → `write` `review-exists` → owner Replace → `replace --confirm` `replaced`, 3 Kado calls. W04a condensed. Counts: 14 section groups, done 6, open 5, themes 0, habits 12, growth 29 (R3b 65): 11 Calendar count items, 1 other folder over 10 notes as a count, 15 items with note links (folders ≤ 10 notes, MOCs). Previous: 2025-Q4 found, 14 carried. Stage after write: `meta.json` only; main session read no stage file. Owner: Pass 1 looks good.

Cost $4.93 (main sonnet 35 turns $1.75, proposer $1.06, 16 digester runs $2.03, carryover $0.08); active time 9.9 min machine (11:39:12 → 11:50:45 minus 1.7 min owner choice at Replace). Observations: the main session posted one status line per agent notification (16 lines, a miscount 17 → 16 corrected mid-run), which is most of its 35 turns; `review-read.py` on the quarter now runs right at the Bash timeout.

Pass 2 (same session d191014e): `/review 2026-Q1` → `open` → Continue → `parse`: approved, 18 groups, 116 items, 116 kept, 0 edited, 0 owner items → `preview` → owner Deliver → `deliver` `delivered`, 13 sections, mode `replace` (`block-replaced`), 0 problems, 0 escaped lines, 0 dropped; set `.json` + `.md` in the inbox. Cost $1.03 (main only; the session carried the Pass 1 context, peak 171,768), 1.3 min machine time. Hashi apply (owner): 14 of 14 actions `applied`, 14 of 14 boxes ticked; target has 1 `## Tomo Review` heading and 1 `tomo-review 2026-Q1` marker. Observation: the set's `.md` frontmatter still reads `state: pending-apply` after the apply.

### R4 — week 2026-W14 (2026-11-28, session d309c979) — Pass 1, Pass 2, Hashi apply

Fresh session. `start`: the 2026-Q1 review listed `applied`, no question → `review-read.py` (1 unit, 5 s) → `plan` → 1 digester (haiku) + carryover (sonnet) → `check`: unit passed, carryover passed (2026-W13 20 items, 2026-02 9 items) → proposer (sonnet) → `write` `written`, target `Calendar/302 Weekly/2026-W14.md` absent. Counts: 12 section groups, done 0, open 0, themes 0, habits 12, growth 6; previous: 2026-W13 found (read report `partly_read`), 20 carried; 2026-02 found, 9 carried. Pass 1 $1.05 (main $0.53, digester $0.07, carryover $0.14, proposer $0.31), 2.2 min.

Pass 2 (same session): Continue → `parse` approved, 55 kept, 0 unticked, 0 deleted, 0 added → `preview` → Deliver → `deliver` mode `new-note`, 0 problems, 0 escaped lines, notice `templater_hint`. $0.33, 0.4 min machine time. Hashi apply (owner): target created, 1 `tomo-review 2026-W14` marker, 1 of 1 box ticked. Stage after write: `meta.json` only; main session read no stage file.

## KPI table

| KPI | Limit | Kind | R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|---|---|---|
| Days not read because of size | 0 | hard | 0 | 0 | 0 | 0 | |
| Sample / grep fallbacks | 0 | hard | 0 | 0 | 0 | 0 | |
| Main-session reads of stage files | 0 | hard | 0 | 0 | 0 | 0 | |
| Carried items placed twice / without previous link | 0 / 0 | quality | 0 / 0 (R1d, owner) | | | | |
| Content files left after write, abort, drop | 0 | quality | 0 after write | 0 after write | 0 after write | 0 after write | |
| Weekly Pass 1 cost | ≤ $0.80 | guidance | $2.40 (R1d; R1c $2.84, R1b $2.80, R1a $1.25 failed) | — | — | $1.05 / 2.2 min | — |
| Monthly Pass 1 cost / time | ≤ $2.00 / 7 min | guidance | — | $6.27 / 8.3 min | — | — | |
| Quarterly Pass 1 cost / time | ≤ $5.00 / 20 min | guidance | — | — | $6.48 / 15.2 min (W04a not condensed); R3c $4.93 / 9.9 min | — | — |
| Pass 2 cost | ≤ $0.85 | guidance | $0.34 (R1d) | $0.52 | $1.03 (R3c session, Pass 1 context carried) | $0.33 (same session as Pass 1) | |
| Cost, time, peak context per step (main, digesters, carryover, proposer) | recorded | F8-AC1 | R1a above | | | | |
| Owner: at least as useful as the spec 046 document | yes/no | quality | | | yes (R3c, owner 2026-11-28) | — | — |
