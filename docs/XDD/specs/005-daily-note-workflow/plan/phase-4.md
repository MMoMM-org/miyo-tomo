---
phase: 4
title: "Reducer + render"
status: completed
depends_on: [1, 3]
---

# Phase 4 — Reducer + orchestrator render

## Goal

Suggestions document gains a `## Daily Notes Updates` top-level section
grouping updates per daily note, with strict order
(Create-first → Trackers → Log Entries → Log Links). Per-item sections
gain a mirrored `Material für [[DAILY]]` sub-block for every log_link.

## Acceptance Gate

- [ ] `suggestions-doc.json` has a new `daily_notes_updates[]` top-level
  field grouping per `daily_note_stem`.
- [ ] Orchestrator render emits `## Daily Notes Updates` section BEFORE
  `## Suggestions`.
- [ ] Each daily-note block in order: Create-first (if missing) →
  Possible Trackers → Possible Log Entries → Possible Log Links.
- [ ] Per-item section has `**Material für [[<daily>]]**` sub-block for
  every log_link.
- [ ] Reducer surfaces the missing-daily-note case with a checkbox
  before any updates for that daily note.

## Tasks

### 4.1 Reducer data model extension

`suggestions-doc.json` gains:

```json
"daily_notes_updates": [
  {
    "daily_note_stem": "2026-04-15",
    "exists": true,
    "trackers": [ { "field": "Sport", "value": true, "reason": "...", "source_stem": "...", "source_section": "S03" } ],
    "log_entries": [ { "time": "07:00", "content": "...", "reason": "...", "source_stem": "...", "source_section": "S03" } ],
    "log_links": [ { "target_stem": "...", "time": null, "reason": "...", "source_stem": "...", "source_section": "S03" } ]
  }
]
```

`exists` comes from a `kado-search listDir` probe — one call per unique
daily-note path (cache results).

### 4.2 Reducer rendering

Add `render_daily_notes_updates_block()`:

```
## Daily Notes Updates

### [[2026-04-15]]

- [ ] Create daily note [[2026-04-15]] first     (only when exists=false)

**Possible Trackers:**
- **Sport** → `true`
  - Reason: <reason>
  - Source: [[<source_stem>]] (S03)
  - [ ] Accept

**Possible Log Entries (inline text):**
- 07:00 — <content>
  - Reason: <reason>
  - Source: [[<source_stem>]]
  - [ ] Accept

**Possible Log Links (reference substantive notes):**
- [[<target_stem>]]
  - Time: <time or "end of day">
  - Reason: <reason>
  - [ ] Accept
```

### 4.3 Per-item `Material für` mirror

In `render_create_atomic_note()` and `render_update_daily()`, after the
existing content, append:

```
**Material für [[2026-04-15]]:**
- Reason: <reason>
- Time: <time or "end of day">
- [ ] Accept (add link from daily log)
```

Only when the item produced a `log_link` update.

### 4.4 Decision-precedence note in doc header

Update the Suggestions doc preamble (rendered by the orchestrator) with
a short note: "If you Accept in either the top-of-doc Daily Notes
Updates block or the per-item Material block, the decision is captured
once." The parser honours top-of-doc wins.

### 4.5 Orchestrator render-rules update

`inbox-orchestrator.md` gains an explicit render-rules section pinning
the strict order:

1. Document frontmatter + `- [ ] Approved` + Summary
2. `## Daily Notes Updates` (when any)
3. `## Suggestions` (per-item sections)
4. `## Proposed MOCs` (when any)
5. `## Needs Attention` (when any)

### 4.6 Tests

`scripts/test-005-phase4.sh`:

- Fixture with 2 daily notes mentioned → 2 blocks, date-sorted.
- Fixture with one daily-note missing → Create-first checkbox appears.
- Fixture with a log_link → mirror appears in both top-of-doc AND per-item.
- Fixture with empty trackers + non-empty log entries → Trackers
  sub-header omitted; Log Entries present.

## Tests

- [ ] `bash scripts/test-005-phase4.sh` exits 0.
- [ ] `bash scripts/test-004-phase{3,4}.sh` still pass.

## Hand-off to Phase 5

Phase 5 delivers the wizard + Pass-2 handlers + end-to-end validation.
