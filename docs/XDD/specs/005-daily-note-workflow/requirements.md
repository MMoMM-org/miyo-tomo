---
title: "Daily-Note Workflow Extension"
status: ready
version: "1.0"
---

# Product Requirements Document

## Product Overview

### Vision

Let Tomo propose daily-note updates (tracker values, log entries, log-link
references) from inbox items in one pass, so the user's daily notes stay
current without manual cross-referencing.

### Problem Statement

Today's `/inbox` Pass 1 produces atomic-note suggestions and tracker-only
`update_daily` actions. Reality of the user's workflow:

- Many inbox items are short, date-stamped reflections that don't deserve
  their own atomic note but belong inline in that day's log.
- Some substantive inbox items should stay as atomic notes but should ALSO
  be cross-referenced from the relevant day's log (otherwise the day's
  narrative has no trace of them).
- Tracker suggestions today are heuristic keyword-match on field names
  alone. "Watched a video about yoga" wrongly sets `Sport: true`.
- Inbox contains year-old items; daily-note targeting should respect
  recency or explode in scope.

### Value Proposition

- **One pass, three dimensions:** per-item classification evaluates tracker,
  log-entry, and log-link candidacy in a single subagent call.
- **Semantic tracker matching:** user-authored tracker descriptions +
  positive/negative keywords eliminate false positives.
- **Log-level cohesion:** daily notes get inline reflections AND links to
  substantive notes from the same day, matching how humans actually keep
  journals.
- **Bounded scope:** configurable cutoff (default 30 days) keeps year-old
  items from polluting daily notes.
- **Wizard-managed config:** tracker semantics and daily-log config set up
  via `/tomo-setup` sub-wizards, not hand-YAML.

## User Personas

### Primary: Daily-note journaler

- Keeps a daily note per day at `Calendar/301 Daily/YYYY-MM-DD.md`.
- Uses tracker fields under `## Habit` (booleans + ratings) and a journal
  section under `# Daily Log` for inline reflections.
- Accumulates short thoughts, run logs, article references in the inbox
  throughout the week and processes them weekly.

## User Journey Map

### Primary Journey: weekly inbox review with daily-note updates

1. User runs `/inbox`.
2. Tomo's fan-out processes each item (existing Spec-004 pipeline).
3. Per item, the subagent evaluates: tracker match? log-entry candidate?
   log-link candidate? — alongside the atomic-note decision.
4. Reducer assembles the Suggestions document. **TOP** of the document
   has per-daily-note blocks:
   - Possible Trackers (field + value + reason + source + accept checkbox)
   - Possible Log Entries (inline text + time + reason + source + accept)
   - Possible Log Links (link + time + reason + accept)
   - Create-daily-note-first checkbox if the daily note doesn't exist
5. Per-item sections follow below with atomic-note decisions AND a
   cross-reference `Material für [[DAILY]]` block (approve in either
   place — both fields track the same decision).
6. User approves/edits/rejects; Pass 2 generates instructions that the
   user (or an external Obsidian plugin) applies.

## Feature Requirements

### Must Have

#### Feature 1 — Tracker-semantics config

- **User Story:** As a daily-note journaler, I want each tracker field to
  carry a semantic description plus positive/negative keywords, so the
  classifier doesn't mistake talking ABOUT exercise for doing exercise.
- **Acceptance Criteria:**
  - [ ] Given `vault-config.yaml` `trackers.daily_note_trackers.today_fields[].description` is set,
    When shared-ctx is built, Then `daily_notes.tracker_fields[].description`
    is present in the output.
  - [ ] Given `positive_keywords` and `negative_keywords` are set, When the
    subagent evaluates an item, Then a match requires at least one positive
    keyword AND zero negative keywords in the content window.
  - [ ] Given neither list is set, When the subagent evaluates, Then
    fallback is whole-word lowercase match against the field name (today's
    behaviour).

#### Feature 2 — Polymorphic `updates[]` with tracker / log_entry / log_link

- **User Story:** As a user, I want one inbox item to produce mixed daily-
  note updates (e.g. tracker + log_link), so nothing about the item gets
  lost.
- **Acceptance Criteria:**
  - [ ] Given an item matches a tracker AND atomic_note_worthiness ≥ 0.5,
    When the subagent builds the result, Then it emits BOTH a
    `create_atomic_note` action AND an `update_daily` action whose
    `updates[]` contains one `tracker` item AND one `log_link` item.
  - [ ] Given an item has date_relevance AND matches a tracker but is
    short/unstructured, When the subagent builds the result, Then
    `updates[]` contains one `tracker` AND one `log_entry` (no atomic note).
  - [ ] Given an item is purely a tracker signal (e.g. "slept 7h"), When
    the subagent builds the result, Then `updates[]` contains only the
    `tracker` entry.

#### Feature 3 — Multi-daily-note splitting (log-format heuristic)

- **User Story:** As a user, when my inbox contains a multi-day log file
  (e.g. `10.03 shopping; 13.03 Amazon`), I want each dated line to target
  its own daily note.
- **Acceptance Criteria:**
  - [ ] Given item content consists of date-prefixed lines with short
    entries, When the subagent classifies, Then it emits N `update_daily`
    actions (one per referenced date), each with its own `daily_note_stem`.
  - [ ] Given item content is prose that mentions dates ("am 15.03. waren
    wir in Düsseldorf"), When the subagent classifies, Then it emits
    ONE `update_daily` at the most-recent referenced date (or today when
    "heute" appears).
  - [ ] Given the subagent is uncertain, Then it defaults to ONE update at
    the most-recent referenced date.

#### Feature 4 — Cutoff filter

- **User Story:** As a user with year-old inbox items, I want daily-note
  actions suppressed for items older than a configurable cutoff.
- **Acceptance Criteria:**
  - [ ] Given `daily_log.cutoff_days` is set (default 30) and
    `date_relevance.date` is older than today−cutoff_days, When the
    subagent classifies, Then it emits NO `update_daily` action (neither
    tracker nor log).
  - [ ] Given the same item, Then atomic-note classification still proceeds
    — only the daily-note bridge is suppressed.
  - [ ] Given `date_relevance` is null, Then no `update_daily` action is
    emitted regardless of cutoff (no date → no daily note to target).

#### Feature 5 — Missing-daily-note checkbox

- **User Story:** As a user, when an item targets a daily note that doesn't
  exist yet, I want a `- [ ] Create daily note for YYYY-MM-DD first`
  checkbox in both Pass 1 and Pass 2, so I know to handle creation before
  applying updates. Tomo does NOT create the daily note itself.
- **Acceptance Criteria:**
  - [ ] Given Tomo resolves a daily-note path from `date_relevance.date`,
    When the daily note does not exist via `kado-search listDir`, Then the
    Suggestions doc's per-daily-note block starts with
    `- [ ] Create daily note [[YYYY-MM-DD]] first`.
  - [ ] Given Pass 2 generates instructions for that block, Then the
    instruction set repeats the create-first checkbox at the top of its
    daily-note section.
  - [ ] Given `daily_log.auto_create_if_missing.{past,today,future}` are
    all `false` (MVP), Then Tomo never invokes kado-write to create a daily
    note — always user-applied (or handled by an external plugin).

#### Feature 6 — Time-extraction for log entries

- **User Story:** As a user, I want log entries inserted at the right time
  slot when a time is present in the inbox item.
- **Acceptance Criteria:**
  - [ ] Given `daily_log.time_extraction.sources` is configured (e.g.
    `[content, filename]`), When the subagent processes an item, Then it
    tries sources in priority order and attaches the first found time to
    the `log_entry` or `log_link`.
  - [ ] Given no source matches and `fallback` is `append_end_of_day`,
    Then the update's `time` is null and the reducer places it at
    end-of-log.
  - [ ] Given `filename` is a source and the filename matches a time-prefix
    pattern (`YYYYMMDD-HHMM_*`), Then the extracted time is `HHMM`
    formatted `HH:MM`.

#### Feature 7 — Reducer top-of-doc daily-notes block

- **User Story:** As a user, I want all daily-note updates surfaced at the
  TOP of the Suggestions document, grouped per daily note, before the
  per-item sections.
- **Acceptance Criteria:**
  - [ ] Given any items have `update_daily` actions, When the reducer
    assembles, Then a `## Daily Notes Updates` top-level section appears
    before `## Suggestions` (per-item sections).
  - [ ] Given multiple daily notes are targeted, Then one
    `### [[YYYY-MM-DD]]` subsection appears per daily note, in ascending
    date order.
  - [ ] Given a daily-note block has entries, Then the order within the
    block is STRICT:
    1. `- [ ] Create daily note ... first` (only if missing)
    2. `**Possible Trackers:**` (if any)
    3. `**Possible Log Entries (inline text):**` (if any)
    4. `**Possible Log Links (reference substantive notes):**` (if any)

#### Feature 8 — Per-item `Material für [[DAILY]]` mirror

- **User Story:** As a user, I want every `log_link` to appear both in the
  top-of-doc block AND under the item's own section, so I can approve from
  either viewpoint.
- **Acceptance Criteria:**
  - [ ] Given an item emits a `log_link` update, When the reducer renders
    the item's section, Then it appends a `Material für [[YYYY-MM-DD]]`
    sub-block with the same accept checkbox.
  - [ ] Given the user checks Accept in the top-of-doc block, When the
    parser reads both, Then the per-item checkbox is ignored (top-of-doc
    wins). Decision-capture precedence is documented in the Suggestions
    doc header.

#### Feature 9 — `/tomo-setup` wizard coverage

- **User Story:** As a user, I want to configure tracker semantics and
  daily-log behaviour without editing YAML by hand.
- **Acceptance Criteria:**
  - [ ] Given the user runs `/tomo-setup trackers`, Then a sub-wizard
    walks every tracker field in vault-config, asking via AskUserQuestion
    for a short `description`, plus open-text prompts for positive and
    negative keywords.
  - [ ] Given the user runs `/tomo-setup daily-log`, Then a sub-wizard
    collects `section`, `heading_level`, `time_extraction.sources`,
    `time_extraction.fallback`, `cutoff_days`, and the three
    `auto_create_if_missing` flags.
  - [ ] Given `/tomo-setup` (full flow), Then after the existing Phase 3
    (user-rules) a new Phase 3b runs both sub-wizards when relevant
    config sections are missing.
  - [ ] Wizard skill names use `tomo-` prefix (`tomo-trackers-wizard`,
    `tomo-daily-log-wizard`) for repo convention.

### Should Have

- `/tomo-setup trackers` allows skipping individual trackers (pass-through
  with default behaviour).
- Subagent reports time-extraction source (`filename` vs `content`) in
  the `log_entry` / `log_link` for user sanity-check.

### Could Have

- `auto_create_if_missing` becomes MVP-enabled in a future spec — create
  the daily note via `kado-write` using a chosen template.
- `last N days` scan limit at the orchestrator level (not just per-item
  cutoff) — skip entire items with older dates before Phase B dispatch.

### Won't Have (this phase)

- Tomo creating daily notes (checkbox only — external plugin executes).
- Frontmatter/mtime time-extraction sources (only content + filename in MVP).
- Edit-existing-log-entries (only append).
- Automatic ordering re-shuffle of existing log entries in the daily note.

## Success Metrics

- **False-positive rate on tracker matches:** under 10% on the user's
  actual inbox (measured by how many tracker suggestions the user rejects
  on first real run).
- **Log-entry placement correctness:** time-sorted entries land within
  the right 15-minute window of the extracted time; 90%+ on extractable
  cases.
- **Cutoff effectiveness:** zero daily-note actions for items older than
  30 days on the default config.
- **Wizard completeness:** after `/tomo-setup trackers`, every
  `tracker_fields[]` entry has a non-empty `description`.

## Constraints and Assumptions

### Constraints

- Extends Spec 004 (fan-out refactor) — no rewrite of the orchestrator or
  the Phase-B dispatch model.
- MVP scope: Tomo proposes, user applies (or external plugin applies).
  Tomo never creates daily notes via `kado-write` in this spec.
- Backwards-compatible with existing `update_daily.updates[]` entries —
  old-shape entries (without a `kind` discriminator) are treated as
  `kind: "tracker"`.

### Assumptions

- User has daily notes enabled and configured (spec 004 Phase-A handles
  the missing case by omitting `daily_notes` from shared-ctx).
- Discovery cache is current (`/tomo-setup` prerequisite).
- `Calendar/301 Daily/YYYY-MM-DD` path pattern is representative of the
  common MiYo vault layout; other users override via vault-config.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Tracker-description quality varies by user; bad descriptions → worse matches than no descriptions | Med | Med | Wizard asks for concrete examples alongside description; validator warns on empty descriptions |
| Log-format heuristic misclassifies prose as log-format, splitting one prose item into N daily updates | Med | Low | Threshold: date-prefix must match a strict regex AND line length < 200 chars; otherwise single-date fallback |
| Year-old inbox items still surface atomic-note suggestions — not suppressed by cutoff | Low | Low | Cutoff is intentionally daily-scoped only (atomic notes still make sense historically); documented |
| Wizard gets long and users abandon | Low | Med | Sub-wizard structure; each tracker gets its own AskUserQuestion round; user can skip and revisit |
| Reducer render-order drift (trackers shown after log entries) | Low | Low | Strict acceptance-criterion in Feature 7; orchestrator's render-rules doc pins the order |

## Resolved Decisions

All six open questions from the 2026-04-15 sketch answered 2026-04-16:

1. **Tracker-description config depth:** `description` + `positive_keywords` + `negative_keywords`. Managed by `/tomo-setup trackers` sub-wizard, never hand-YAML.
2. **log_entry vs log_link threshold:** subagent heuristic on `atomic_note_worthiness` (≥ 0.5 → log_link, else log_entry).
3. **Time-extraction priority:** configurable chain. Marcus's default `[content, filename]`. Others can add `frontmatter`, `mtime`.
4. **Missing daily note:** surfaced as checkbox in both Pass 1 + Pass 2. Actual create by external plugin. Config flags `auto_create_if_missing.{past,today,future}` forced to `false` in MVP.
5. **Multi-daily split:** log-format heuristic (date-prefixed lines). Prose with date mentions → single most-recent. Uncertain → single most-recent. "Im Zweifel eins."
6. **Cutoff default:** 30 days. User hopes to converge toward 7 but 30 is MVP default.

## Supporting Research

- Spec 004 (fan-out refactor) — architecture this extends.
- Real-inbox dry run 2026-04-15 validated that the existing `update_daily`
  path produced tracker updates but missed the inline-log and
  link-from-log use cases the user actually needs.
