---
title: "Inbox Fan-Out Refactor"
status: draft
version: "1.0"
---

# Product Requirements Document

## Product Overview

### Vision

Make `/inbox` processing scale to realistic inbox sizes (100+ items, mixed content)
on standard Claude context (~200K), by splitting the work into a fan-out pipeline
with minimal per-subagent context.

### Problem Statement

The current `/inbox` flow is monolithic: one agent holds the full discovery cache
(~75 KB → ~20K tokens), reads every inbox item into context via `kado-read`
(with SSE overhead), and carries all intermediate classification/matching results
until the Suggestions document is written.

At real-world vault scale (3,900+ notes, 37+ inbox items), this has already caused:

- Parser-abort errors when the agent tried to write the Suggestions document via a
  large Bash heredoc (evidence: current session — `Parser aborted (timeout, resource
  limit, or over-length)` on `cat <<'ENDOFSUGGESTIONS' > file`)
- Hallucinated tool availability (e.g., claiming `kado-write` was missing) — a
  context-pressure symptom
- Non-resumable runs — a single bad classification abandons the whole batch

The direct fix would be to require Claude Max (1M context). That shifts cost to
the user and does not address the root cause. We want correctness at standard
context budget.

### Value Proposition

- Runs reliably on standard (non-Max) Claude — no forced upgrade for users
- Resumable on crash or interrupt (per-item state markers)
- Parallelized — 3-5 subagents work concurrently, fronted by Kado's throughput
- Failures localized: one bad item does not poison the batch
- Deterministic, debuggable intermediate artifacts (`tomo-tmp/items/*.jsonl`,
  `tomo-tmp/items/*.result.json`)

## User Personas

### Primary Persona: Tomo user (PKM practitioner)

- **Demographics:** Obsidian user with an active vault (hundreds to thousands of
  notes), runs Tomo inside Docker, uses standard Claude (not Max)
- **Goals:** Process the inbox weekly/monthly without hitting context limits;
  trust that a 50-item inbox run will actually complete
- **Pain Points:** Current `/inbox` aborts or degrades silently on large batches;
  unclear which items were processed when a run fails partway

### Secondary Personas

- **Tomo developer:** needs debuggable intermediates, resumability for iteration
  on the classifier

## User Journey Maps

### Primary User Journey: Processing a real inbox

1. **Awareness:** User has accumulated 40+ items in the vault inbox over weeks
2. **Adoption:** Runs `/inbox` expecting one Suggestions document
3. **Usage:**
   - Tomo reports "processing 42 items in batches of 5"
   - Progress visible: N of 42 processed
   - If an item fails, Tomo reports which one and continues
   - Final Suggestions document covers every item (or marks those that failed)
4. **Retention:** User can re-run `/inbox` against the same inbox; already-
   processed items are skipped based on state-file markers

### Secondary User Journey: Developer iteration

1. Run `/inbox` against a fixture inbox
2. Inspect `tomo-tmp/items/<stem>.jsonl` to see what the subagent was given
3. Inspect `tomo-tmp/items/<stem>.result.json` to see what it produced
4. Tweak classification logic, re-run only the failed/changed items

## Feature Requirements

### Must Have Features

#### Feature 1: Phase A — Orchestrator state-file + shared context

- **User Story:** As a Tomo user, I want `/inbox` to enumerate inbox items and
  build a compact shared context once per run, so that per-item processing
  doesn't repeat expensive work.
- **Acceptance Criteria:**
  - [ ] Given an inbox with N items, When `/inbox` starts a run, Then Tomo
    writes `tomo-tmp/inbox-state.jsonl` with one line per item containing at
    least `{path, stem, status: "pending", run_id}`
  - [ ] Given a populated discovery cache, When Phase A builds shared context,
    Then Tomo writes `tomo-tmp/shared-ctx.json` ≤ 15 KB containing: MOC list
    `[{path, title, topics[]}]`, user-proposable tag prefixes
    `[{name, wildcard, known_values[]}]`, classification keywords
  - [ ] Given `vault-config.yaml` specifies
    `tomo.suggestions.proposable_tag_prefixes`, When shared-ctx is assembled,
    Then only prefixes in that list appear in `tag_prefixes[]` — structural
    prefixes (`type/*`, `status/*`, `projects/*`, etc.) are excluded by
    default
  - [ ] Given no `proposable_tag_prefixes` setting exists, When shared-ctx is
    assembled, Then the default `["topic"]` is used
  - [ ] Given a MOC has no `topics` extracted, When it is serialised into
    shared-ctx, Then its `title` is used as the sole topic fallback (never drop
    the MOC — classifier still needs to see it)
  - [ ] Given shared-ctx is assembled, When serialised, Then the file stays
    ≤ 15 KB; if size exceeds the budget, shorten `topics[]` per MOC before
    dropping any MOC entirely

#### Feature 2: Phase B — Per-item subagent fan-out

- **User Story:** As a Tomo user, I want items processed in parallel batches of
  3-5, each with minimal context, so that a 50-item inbox does not blow past
  standard context limits.
- **Acceptance Criteria:**
  - [ ] Given `inbox-state.jsonl` has N pending items, When the orchestrator
    dispatches Phase B, Then at most 5 subagents run concurrently
  - [ ] Given a subagent is dispatched for item `<stem>`, When it starts, Then
    its only input context is `tomo-tmp/shared-ctx.json` plus the note content
    it reads via `kado-read` for that single `<stem>`
  - [ ] Given a subagent completes classification for `<stem>`, When it finishes,
    Then it writes `tomo-tmp/items/<stem>.result.json` with fields:
    `{stem, type, confidence, moc_matches[], classification, tags_to_add[],
    needs_new_moc: bool, proposed_moc_topic?, issues[]}`
  - [ ] Given a subagent succeeds, When the orchestrator polls the state file,
    Then the item's status transitions `pending` → `done`
  - [ ] Given a subagent fails (exception, timeout, Kado error), When the
    orchestrator observes the failure, Then the item's status transitions to
    `failed` with an error message, and the run continues on remaining items
  - [ ] Given 3 items share a `proposed_moc_topic`, When Phase B completes,
    Then all three result files record the same topic string (for clustering
    in Phase C)

#### Feature 3: Phase C — Reduce to Suggestions document

- **User Story:** As a Tomo user, I want a single Suggestions document at the
  end, with per-item sections plus cross-item new-MOC proposals, matching
  today's output format.
- **Acceptance Criteria:**
  - [ ] Given all Phase B results are `done` or `failed`, When Phase C runs,
    Then it reads every `items/*.result.json` and assembles the Suggestions
    document per the format in `tomo/.claude/agents/suggestion-builder.md`
  - [ ] Given 3+ results have `needs_new_moc: true` with matching
    `proposed_moc_topic`, When Phase C runs, Then it emits a `Proposed MOC`
    section grouping those items (per current Classification Guard logic)
  - [ ] Given any items are `failed`, When Phase C writes the Suggestions
    document, Then a `Needs Attention` section lists the failures with
    error messages
  - [ ] Given the document is assembled, When written to the vault, Then the
    agent uses `mcp__kado__kado-write` (never Bash heredoc, never `Write` tool
    for vault paths)

#### Feature 4: Resumability

- **User Story:** As a Tomo user, if `/inbox` is interrupted, I want to re-run
  it and have only the un-processed items picked up.
- **Acceptance Criteria:**
  - [ ] Given a run was interrupted mid-Phase-B with half the items `done`,
    When the user re-runs `/inbox`, Then Tomo detects the existing
    `inbox-state.jsonl` and processes only items with status `pending` or
    `failed`
  - [ ] Given a prior run completed fully, When the user re-runs `/inbox`,
    Then Tomo asks (via AskUserQuestion) whether to start a fresh run or
    inspect the prior run

#### Feature 5: Per-item polymorphic actions

- **User Story:** As a Tomo user, I want one inbox item to produce multiple
  proposed actions (e.g. both a new atomic note AND a daily-tracker update)
  so that nothing about a note gets lost between Pass 1 and Pass 2.
- **Acceptance Criteria:**
  - [ ] Given a per-item result, When written to `result.json`, Then it
    contains an `actions[]` array with one or more action objects
  - [ ] Given an item's content matches both atomic-note-worthiness and a
    tracker field, When the subagent processes it, Then both
    `create_atomic_note` and `update_daily` appear in `actions[]`
  - [ ] Given an item's content is purely a tracker entry (e.g. "slept 7h"),
    When the subagent processes it, Then only `update_daily` is emitted
    (no `create_atomic_note`)
  - [ ] Given the Suggestions document is rendered, When a section has
    multiple actions, Then each action gets its own tri-state
    approve/skip/delete checkboxes under the S-section heading

#### Feature 6: Daily-note tracker updates

- **User Story:** As a Tomo user with daily notes enabled, I want inbox
  items that imply tracker values (e.g. "morning run") to propose updates
  to the right daily note's tracker fields.
- **Acceptance Criteria:**
  - [ ] Given `vault-config.yaml` has `calendar.granularities.daily`
    configured, When Phase A builds shared-ctx, Then it includes
    `daily_notes.tracker_fields[]` with each field's name, type, section,
    syntax, and content keywords
  - [ ] Given `calendar.granularities.daily` is NOT configured, When Phase A
    builds shared-ctx, Then the `daily_notes` section is omitted and
    subagents never emit `update_daily` actions
  - [ ] Given a subagent detects a date reference in content or filename
    (matching `daily_notes.date_formats`) AND detects one or more tracker
    keywords, When it builds `actions[]`, Then it appends an `update_daily`
    action with `date`, `daily_note_path`, and `updates[]`
  - [ ] Given the daily note for the computed date does not exist yet,
    When Pass 2 renders the instruction, Then the instruction includes
    "create the daily note first, then add the tracker update"
    (handled by existing `instruction-builder` Step 6 — unchanged)

#### Feature 7: User-configurable tag-prefix scope

- **User Story:** As a Tomo user, I want to control which tag prefixes the
  classifier may propose so that structural or lifecycle tags (like `status/*`
  or `projects/*`) are never suggested as new tags on an inbox item.
- **Acceptance Criteria:**
  - [ ] Given `vault-config.yaml` lists `tomo.suggestions.proposable_tag_prefixes:
    ["topic"]`, When a subagent analyses an item, Then it may only propose
    tags whose prefix matches `topic`
  - [ ] Given a user has not configured the setting, When shared-ctx is
    built, Then the default `["topic"]` is applied
  - [ ] Given the user runs `/tomo-setup rules` (or the tagging wizard),
    When the wizard reaches the tag-prefix question, Then it presents the
    discovered prefixes from the vault and lets the user multi-select which
    ones become proposable

### Should Have Features

- Progress reporting to the user during Phase B (N of M done)
- Per-item timing in the result JSON for performance tracking

### Could Have Features

- Configurable parallelism (default 5, override via flag)
- Dry-run mode that stops after Phase A so a developer can inspect `shared-ctx`
  and `items/*.jsonl` without calling Kado writes

### Won't Have (This Phase)

- Vault-wide MOC-proposal scanning (separate future `/mocs-propose` command)
- Incremental re-classification of already-filed notes
- Duplicate detection against existing vault notes
- Related-note linking in Suggestions (no existing-note lookup in shared-ctx)

## Detailed Feature Specifications

### Feature: Phase B — Per-item subagent fan-out

**Description:** The orchestrator dispatches one subagent per pending item, up
to 5 in parallel, until the inbox-state.jsonl is drained. Each subagent receives
only the distilled shared context plus the path of its assigned item and is
responsible for:

1. Reading the item's content via `kado-read`
2. Classifying the item (type, confidence)
3. Matching against candidate MOCs in shared-ctx
4. Proposing `new tags to add` (if any)
5. Flagging `needs_new_moc` if no thematic MOC scores above threshold
6. Writing exactly one result JSON file

**Business Rules:**

- Subagent has no knowledge of other inbox items
- Subagent never writes to the vault — only to `tomo-tmp/items/<stem>.result.json`
- Subagent classification uses the same heuristics as today's `inbox-analyst`
  Steps 4-9; only the orchestration changes
- If `candidate_mocs` in shared-ctx includes only classification-level MOCs
  (Dewey layer), subagent flags `needs_new_moc: true` rather than pre-checking
  a classification MOC (Classification Guard rule carries over)

**Edge Cases:**

- Kado read times out mid-batch → item marked `failed`, run continues
- Subagent returns invalid JSON → orchestrator marks `failed`, run continues
- Two items produce identical `proposed_moc_topic` but from different batches
  of 5 → orchestrator sees them together in Phase C; clustering is correct

## Success Metrics

### Key Performance Indicators

- **Correctness:** 100-item fixture inbox runs to completion on standard Claude
  context without abort
- **Context headroom:** peak context usage during Phase B stays under 80K
  tokens per subagent (measured via logged run-metadata)
- **Parallelism:** observed concurrency during Phase B reaches 3-5 on a machine
  with healthy Kado
- **Resumability:** a run interrupted at 50% completion resumes correctly,
  producing identical final output to an uninterrupted run on the same inbox

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| phase_a_complete | items_total, shared_ctx_bytes | Confirm compact context built |
| phase_b_item | stem, status (done/failed), duration_ms, error? | Per-item visibility |
| phase_c_complete | items_done, items_failed, moc_proposals | Batch summary |

Emitted as log lines / state-file updates — no telemetry to external systems.

## Constraints and Assumptions

### Constraints

- Must run inside the Tomo Docker container with current tooling (Kado MCP,
  Python 3.11, `scripts/lib/kado_client.py`)
- No new top-level Python/library dependencies — reuse `kado_client` and the
  standard library. New scripts under `scripts/` are fine (and expected) — e.g.
  a Phase-A builder, a Phase-C reducer.
- All writes to the vault go through `mcp__kado__kado-write` only
- Scratch writes go to `tomo-tmp/` only
- Must stay compatible with the existing Suggestions document format (users
  review the same shape they review today)

### Assumptions

- Kado tolerates 3-5 concurrent read requests without degradation (Kado v0.2.0+)
- Discovery cache is populated before `/inbox` runs (enforced by `/tomo-setup`)
- Subagents can be spawned via the Agent tool with per-invocation `tools` scoping
- `mcp__kado__kado-write` is available to the orchestrator (verified: listed in
  agent frontmatter and implemented at `scripts/lib/kado_client.py:206`)

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Kado becomes the bottleneck even at 3 concurrency | Med | Med | Configurable parallelism; default 5, degrade to 3 if errors spike |
| Shared-ctx distillation drops a MOC the classifier needed | Med | Low | Phase A logs dropped MOCs; diagnostic flag to include all |
| Subagent produces invalid JSON, orchestrator silently skips | High | Low | JSON-schema validation on every `result.json`; structured errors in Needs Attention |
| Resumability confuses users on partial runs | Low | Med | `AskUserQuestion` on re-run: fresh / resume / inspect |
| Cross-item clustering misses proposed MOCs because topic strings differ by casing/plural | Med | Med | Normalise `proposed_moc_topic` to lowercase singular in Phase C clustering |

## Resolved Decisions

- **Orchestrator:** new agent `inbox-orchestrator` (clean separation from
  Suggestions rendering)
- **Per-item subagent:** prefer reusing the existing `inbox-analyst` (tighten
  its tools list if necessary). Introduce a new `item-processor` agent only if
  reuse blocks a constraint (e.g., must return JSON-only, no narrative).
- **Error details:** embedded inline in the result JSON (`issues[]` field)
  and in the state-file row — no separate error-log files
- **Hard upper bound on items per run:** none. The fan-out pipeline is
  explicitly designed to scale; a cap would contradict the vision. Monitor
  peak context and Kado load instead.

## Open Questions

(None at this time — all previously open items resolved above.)

---

## Supporting Research

### Competitive Analysis

Not applicable — this is an internal architecture refactor of an existing
feature, not a market-facing product.

### User Research

Evidence gathered from the current session:

- 37-item inbox ran into parser-abort on Suggestions-document write
- Hallucinated-tool reports (claiming `kado-write` was missing)
- Example-bleed-through on small batches — classifier repeated example titles
  for dissimilar source notes, suggesting overloaded context

### Market Data

Not applicable for internal tooling.
