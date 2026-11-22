# /review: chunked read, model-tiered agents, previous reviews

> Brainstorm result, 2026-11-22. Issue #270 (plus the owner's request to read the previous reviews).
> Input for `/xdd` (PRD → SDD → plan). Not a spec yet.

## 1. Problem

1. **The read does not fit.** A quarter's Pass 1 read files are 717 KB, about 390k tokens. `read-index.json`
   alone is about 82.5k tokens, and the Read tool's limit is 25k per call. Both 2026-Q1 runs of the spec 046 walk
   fell back to `grep` on a few per-day fields and reported a partial read. A month's read file is about 190 KB
   (about 100k tokens), so the month is over the limit too. The week fits today but costs about $0.70 against a
   $0.50 target.
2. **No continuity.** A review reads only the notes inside its period. The month marks against its weekly notes
   and the quarter against its monthly notes (`CHILD`, `tomo/scripts/lib/review_period.py:61`). No review reads the
   previous period's note, so it cannot say what was left open, whether intentions held, or how themes moved.

Deterministic trimming alone does not solve 1: it saves about 220 KB and still leaves about 270k tokens in one
context, which is more than the window.

## 2. Goals and success criteria

- **Hard:** every read day reaches the proposals (0 days in `not_read` because of size); no `grep` fallback.
- **Quality first.** The cost KPIs stay as guidance, not as gates: week Pass 1 ≤ $0.50; month Pass 1 ≤ $2.00 and
  ≤ 7 min; quarter Pass 1 ≤ $5.00 and ≤ 20 min.
- **One pipeline** for week, month and quarter. Only the number of week chunks differs.
- **Continuity.** Each review uses its previous reviews for three things:
  - following up open items (done, still open, no longer mentioned);
  - checking intentions and goals;
  - showing how themes developed.

  Which periods count as previous depends on the kind:

  | Review | Previous notes read |
  |---|---|
  | week | previous week, previous month |
  | month | previous month, previous quarter |
  | quarter | previous quarter |

## 3. Approaches considered

| | Approach | Verdict |
|---|---|---|
| **A** | Week as the unit of work, two stages: per-day files; one digest agent per week; then one proposer agent | **Chosen.** One flow for all kinds; the Read limit is gone structurally; the expensive model sees only condensed input. |
| B | Three stages (day → week → month → proposer) | Rejected for now. 14 digests at ~3k tokens (~40k) fit the proposer without a month stage. Each stage loses detail and adds latency, and the quarter would run a different flow than week and month. Parked. |
| C | No agents: trim deterministically, read in pieces into one context | Rejected. About 270k tokens remain in one context, more than the window. Previous reviews make it larger still. |

The key observation behind A: the 25k limit applies per **Read call**, not to the context. An agent can read seven
small day files one after the other.

## 4. Design

### 4.1 Flow and components

1. **Read:** `review-read.py`, rebuilt. It reads Kado once under the pacer, as today, and writes under
   `tomo-tmp/review/<stem>/`:
   - `days/<YYYY-MM-DD>.json` — one file per day: dailies, same-day linked notes, fields. Trimmed: no habits
     (the script computes them), no weekly `day_blocks` that repeat daily text.
   - `weeks.json` — the weeks of the period under the configured week rule. A week that crosses the period's
     edge is clipped to the period's days and still counts as one week. 2026-Q1 has 14 ISO weeks (W01–W14).
     A week without any read day gets no digester.
   - `context.json` — growth, open task notes, the child notes (a month's weekly notes, a quarter's weekly and
     monthly notes, with size-bounded month text), the link differences behind the child marks
     (`only_in_weekly_links`, `dailies_not_in_weekly`, `only_in_monthly_links`, `dailies_not_in_monthly`, computed
     over the whole period as today), the section setup, and a deterministic per-period aggregate for each
     `analysis` row.
   - `previous/` — the previous periodic notes of §2. Each entry has the state `found`, `empty` or `missing`.
   - The report on stdout, as today, extended by the previous-note states.

   Every file stays under a fixed byte limit, and each week's day files stay under a per-week input budget.
   The script checks both when it writes. Every file carries the read's id, so a later step can tell which read
   produced it.
2. **Condense:** the skill dispatches all of the following in **one** message (the batch pattern of
   `suggest-handling`):
   - one `review-digester` (haiku) per week of `weeks.json`. It reads that week's day files and the section setup
     and writes `digests/<week>.json`;
   - one `review-carryover` (sonnet). It reads `previous/` and writes `carryover.json`.

   Then `review-digest.py check` validates each file. On failure, exactly that agent is dispatched once more
   with the `errors`.
3. **Propose:** one `review-proposer` (opus). It reads the digests, `carryover.json`, `context.json` and the
   setup, and writes `proposals.json`. It does the cross-week work:
   - merges theme candidates and applies the "≥ 2 days" rule over the whole period;
   - judges "open" against later weeks;
   - matches the carryover items against the digests.
4. **Write:** `review-doc.py write`, as today. The `proposals-invalid` rewrite loop re-dispatches the proposer
   with the `errors` verbatim.

The skill (main context) orchestrates. No agent dispatches an agent; that is a platform constraint. The main
context never reads a day file. Read content rests only under `tomo-tmp/review/<stem>/`.

### 4.2 Contracts

- **Digest** `digests/<week>.json`:

  ```
  {read_id, week, days[],
   done[], open[],
   theme_candidates[{text, days[]}],
   section_candidates[{key, items[]}],
   notable[]}
  ```

  - Every entry is `{text, sources[]}`, and its sources are day stems from `days/`. "A source exists" means a
    day file exists, not that Kado has the path.
  - A theme candidate may name a single day.
  - Each group has a cap, aiming at about 3k tokens per digest. A section's cap in the digest is at least that
    section's `cap`.
  - The digest records only what the days say, without judgement.
- **Carryover** `carryover.json`:

  ```
  {read_id,
   notes[{path, kind week|month|quarter, state found|empty|missing}],
   items[{text, type open|intention|theme, source}]}
  ```

  - The model decides what counts as open or an intention. There is no setup marker.
  - A note that holds only template text counts as `empty`.
- **Proposals:** the current shape, plus three marks:

  | Mark | English label | German label |
  |---|---|---|
  | `from_previous_done` | "from the previous review: done" | "aus der Vor-Review: erledigt" |
  | `from_previous_open` | "…: still open" | "…: noch offen" |
  | `from_previous_gone` | "…: no longer mentioned" | "…: nicht mehr erwähnt" |

  - They are allowed for every kind and render as the existing ` · <label>` suffix
    (`tomo/scripts/lib/review_sections.py:229`), so Pass 2 needs no new parser.
  - A `from_previous_*` item needs at least one previous-note source instead of a daily of the period. The new
    days that confirm it are added to its sources when they exist.
  - A carried item is placed **once**: in its best-fitting user section, otherwise in a group. It never appears
    again under `done` or `open`.
- **Previous-note path:** taken from the setup folder and name format, the same way child notes are found today;
  there is no search. The previous month of a week is the month before the month in which the week starts.
  `Period.previous(rule)` (`tomo/scripts/lib/period.py:176`) gives the previous period of the same kind.
- **Roles:** each agent writes only its own file: `digests/<week>.json`, `carryover.json`, `proposals.json`.
  Scripts write everything else under `tomo-tmp/`. The skill's write rule (SKILL.md line 11) and the STRICT block
  (SKILL.md line 238) get exactly these exceptions. The skill itself no longer writes `proposals.json`.

### 4.3 The new layout replaces `read.json` (owner decision)

There is no slim `read.json` / `read-index.json` any more. `review-doc.py` and its libraries read `days/`,
`weeks.json`, `context.json` and `previous/` directly. This affects:

- `rrp.load` and `rrp.stage_files`;
- `Sources.of` (`tomo/scripts/lib/review_doc.py:204`), which also learns the previous notes;
- `check_item`, `period_of`, the habits and growth rendering, `sections-changed` and `read-invalid`;
- the Pass 2 `parse`, `deliver` and `drop` paths.

The owner accepted the larger risk. The plan therefore starts with a behaviour baseline: an end-to-end run for
week, month and quarter on fake Kado, green before the rebuild and green after it, with only the intended
differences.

### 4.4 Errors and resume

- **A digest fails validation twice, or is missing:** that week counts as not condensed. It goes into
  `not_read`, the document names it at its top, and the skill says so. New STRICT: never fall back to `grep` or
  read day files in the main context. Why: this is exactly what the spec 046 walk did.
- **Carryover fails:** the review continues without it, and the document says so at its top. The proposer skips
  the matching step, so no `from_previous_*` item is written.
- **A previous note is `missing` or `empty`, or Kado answers with nothing:** this is reported like `kado_empty`
  today, with the key-access hint.
- **The proposer fails twice with `proposals-invalid`:** the errors are shown verbatim and nothing is written, as
  today.
- **Resume:**
  - `days/`, `digests/` and `carryover.json` stay on disk.
  - Re-running `/review` for the same period condenses only the weeks that have no valid digest of the current
    `read_id`. A digest from an older read is invalid.
  - `sections-changed` invalidates the digests, because their section candidates depend on the setup.
  - A new read deletes all earlier stage files first.
  - Deliver and drop delete `days/`, `digests/`, `carryover.json`, `context.json`, `weeks.json` and `previous/`,
    as they delete the read files today.
- **The user aborts:** no further agent or script runs. The stage files stay until the next read.

### 4.5 Tests and measurement

- **pytest on fake Kado.** Every new test is seen RED by reverting its fix.
  - Each day file stays under the byte limit, and each week under the per-week budget, on 2026-Q1 of the test
    vault.
  - Week clipping, including a year boundary under a non-ISO week rule.
  - Previous-period resolution: the previous week across New Year, the previous month of a week that crosses two
    months, the previous quarter; the states `missing` and `empty`.
  - The validator for digest and carryover: one accepted case and one rejected case each; a digest with a stale
    `read_id` is rejected.
  - The `from_previous_*` marks: source rule, rendering in EN and DE, and the item passing through Pass 2.
  - The behaviour baseline end to end for week, month and quarter (§4.3).
- **Plugin evals:**
  - the digester writes only its own file;
  - the skill dispatches all week agents in one message;
  - there is no `grep` fallback when a digest is missing.

  These files are outside the CLAUDE.md eval gate; the evals are the proof for these rules anyway.
- **Live walk on the test vault:** 2026-W13, 2026-03 and 2026-Q1, Pass 1 and Pass 2.
  - Record cost, minutes and context per agent; 0 days in `not_read` is a hard condition.
  - The owner compares quality with the spec 046 documents.
  - The test-vault dailies end 2026-09-12 on purpose. The previous periods of these three lie in 2026-W12,
    2026-02 and 2025-Q4. The quarter walk covers the `missing` case unless a 2025-Q4 note exists; W13 and 2026-03
    must find their previous notes (`found`), so the walk checks they exist first.
- **PRIVACY.md:** name the new files under `tomo-tmp/review/<stem>/`, which hold content derived from notes, and
  that sub-agents on haiku, sonnet and opus see note content.

## 5. Open for the SDD

- **Limits:** the values of the per-file byte limit and the per-week input budget. The hard goal depends on them,
  and the Read limit of 25k tokens per call is the ceiling for the file limit. Measure them on 2026-Q1.
- **`read_id` checks:** whether `review-digest.py check` alone checks the `read_id`, or `review-doc.py write`
  checks it for `carryover.json` and `proposals.json` too.
- **Three new marks:**
  - add their labels to the words table in EN and DE;
  - add them to the mark validation (`group_reason`, `check_item`);
  - confirm that the Pass 2 `parse` accepts the suffix text.

## 6. Parking lot (not in this work)

- **#259** (trim the skill, polish the setup answers): build it on top of this redesign afterwards, because the
  redesign rewrites step 5 anyway.
- **A setup marker for intention sections:** rejected for now (the model decides). Revisit if the live walk shows
  poor detection.
- **The month stage** of approach B: only if digests are measured as too large.
- **The cost KPIs for week and Pass 2:** an owner decision, still open from spec 046's close-out. Decide it with
  the new measurements.
- **`dailies_not_in_*`** should leave out embeds that are not notes (spec 046 walk).

## 7. Decisions log (2026-11-22, owner)

| Topic | Decision |
|---|---|
| Use of previous reviews | follow up open items, check intentions, theme development (not "avoid repeats") |
| Source of the previous review | the previous periodic note as it stands in the vault |
| Detecting open items and intentions | the model decides; no setup marker |
| Where carried items go | the best-fitting section or group, marked |
| Week on the new pipeline | yes, one flow for all kinds |
| Success | quality first; cost KPIs as guidance |
| Approach | A (week unit, two stages) |
| Models | digester haiku, carryover sonnet, proposer opus |
| Contract of `review-doc.py` | the new layout replaces `read.json` |
| Finding the previous note | setup folder and format; previous month = the month before the week's start month |
| A carried item also found in new days | once, with the mark |
| An empty previous note | its own state `empty`, named at the document's top |
