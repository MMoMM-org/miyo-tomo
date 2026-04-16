# Phase 3 — inbox-analyst three-way classification

## Goal

The per-item subagent evaluates tracker / log_entry / log_link in one
pass, emits polymorphic `updates[]`, handles multi-daily splits via the
log-format heuristic, and respects the cutoff filter.

## Acceptance Gate

- [ ] Subagent emits `update_daily` with three-kind mixed `updates[]`
  when the content qualifies for multiple dimensions.
- [ ] Subagent emits ZERO `update_daily` actions for items older than
  `daily_log.cutoff_days`.
- [ ] Subagent emits N `update_daily` actions for content with ≥ 2
  date-prefixed short lines (log-format heuristic hit).
- [ ] Subagent uses `description` + `positive_keywords` /
  `negative_keywords` from shared-ctx for tracker matching (not the old
  field-name heuristic).
- [ ] Subagent attaches `time` (and `time_source`) to log_entry /
  log_link when extractable.
- [ ] Validator passes for all emitted results.

## Tasks

### 3.1 Rewrite `inbox-analyst.md` Step 8b

Split the former "date + tracker detection" into four sub-steps:

- **8b.1 — Date detection** (unchanged behaviour).
- **8b.2 — Cutoff gate**: if `date_relevance.date < today - cutoff_days`
  → skip the rest of 8b entirely, proceed to Step 9 atomic-note
  evaluation.
- **8b.3 — Three-way classifier**:
  - For each tracker_field, match via `positive_keywords` (AND not
    `negative_keywords`). Fall back to whole-word description match when
    keywords are empty.
  - Decide log_entry vs log_link from `atomic_note_worthiness` (computed
    in Step 7).
  - Extract time via `time_extraction.sources` priority chain; fallback
    per config.
- **8b.4 — Multi-daily split**: run log-format heuristic; if positive,
  split into N updates (one per referenced date) AFTER applying cutoff
  per-date.

### 3.2 Add log-format heuristic

New section in `inbox-analyst.md`:

```
LOG-FORMAT HEURISTIC (pure regex, no LLM cost):
  line_count(non_empty)
  dated_lines = count where /^(\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{4}-\d{2}-\d{2})\s/
  short_lines = count where len(line.strip()) ≤ 200
  If dated_lines >= 2 AND dated_lines / line_count(non_empty) >= 0.6
     AND short_lines / line_count(non_empty) >= 0.6:
    → IS LOG FORMAT; emit per-date updates.
  Else:
    → prose mode; emit single update at most-recent mentioned date
      (or today if "heute" appears).
```

### 3.3 Per-update `reason` field

Every emitted update gets a `reason` (short free-text). This is user-
facing in the Suggestions doc ("Why did Tomo suggest this?"). Keep it
under 80 chars.

### 3.4 Update the template

Phase 1 already regenerated the template with one example of each update
kind. The subagent reads the template in Step 10 as usual.

### 3.5 Tests

`scripts/test-005-phase3.sh` — fixtures:

1. Short run-log item ("5k run this morning") → `update_daily` with
   tracker(Sport=true) + log_entry("5k run this morning"). Confidence
   captured per entry.
2. Substantive reading-notes item → tracker match negative_keyword
   ("read about", `Sport` NOT triggered); atomic-note action + log_link.
3. Year-old item (date_relevance > cutoff) → zero update_daily actions;
   atomic-note still emitted.
4. Multi-date log item
   (`10.03.2026 shopping\n13.03.2026 Amazon\n15.03.2026 vacation`) →
   3 separate `update_daily` actions, one per date.
5. Prose with dates ("am 15.03. waren wir in Düsseldorf, am 17.03.
   wieder") → 1 `update_daily` at 2026-03-17.
6. Filename with time (`20260415-0700_run.md`) → log entry has
   `time: "07:00"`, `time_source: "filename"`.

## Tests

- [ ] `bash scripts/test-005-phase3.sh` exits 0.
- [ ] `bash scripts/test-004-phase3.sh` still passes.

## Hand-off to Phase 4

Phase 4 reducer groups the polymorphic updates into the top-of-doc
Daily Notes Updates block.
