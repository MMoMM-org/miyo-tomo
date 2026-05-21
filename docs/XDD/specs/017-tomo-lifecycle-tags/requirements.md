---
title: "Tomo Lifecycle State — Unified Frontmatter Block + byFrontmatter Discovery"
status: in_review
version: "1.2"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain (OQ6 + OQ14 resolved in v1.1 — see §10)
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS

- [x] Problem validated by evidence (F-43 T6.2 live-validation findings, 2026-05-20)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed
- [x] Every metric has corresponding tracking events
- [x] No technical implementation details (state-machine semantics + flow shapes only; code-level architecture deferred to SDD)
- [x] A new team member could understand this PRD

---

## 1. Product Overview

### Vision

Every Tomo-produced file in the inbox carries its lifecycle in a single structured frontmatter field (`tomo.state`), so `/inbox` and `/moc-propose` know what to do next from one `byFrontmatter` lookup — no body-reads, no filename-pattern matching, no scattered state logic, no mirrored tag to keep in sync.

### Problem Statement

F-43 T6.2 live-validation surfaced three concrete defects in Tomo's inbox detection model on 2026-05-20:

1. **Token waste**: `/inbox` Auto-Discovery does `listDir + 3× full-body kado-read` (~2,000–4,000 tokens per file) just to count `[x] Applied` / `[x] Approved` checkboxes — for state, which would fit in 5 frontmatter lines.
2. **F-43 acceptance-flow blocked**: `tomo-moc-proposal-*.md` (introduced by F-43) has no state model at all. The `/inbox` Auto-Discovery never sees it; `state-init.py` SKIP_SUFFIXES doesn't match it (suffix-vs-prefix bug); the accepted-clusters path that should convert proposal → instructions has no trigger. F-43 T6.2 and T6.4 are paused indefinitely until this is fixed.
3. **Scattered state model**: source items use a frontmatter tag (`#<prefix>/captured`); suggestions use body checkboxes (`[x] Approved`); instructions use per-action body checkboxes (`[x] Applied`); proposal-docs use nothing. Four mechanisms for what should be one. New doc-types (F-44 garden-audit, F-45 weekly-review, F-46 tag-audit) will inherit whatever Tomo locks now — paying interest on the inconsistency forever.

Quantified: a steady-state `/inbox` run today costs ~4,850 in-context tokens just on discovery; a heavy-backlog run hits ~12,000. The model produces correct results only because every consumer re-reads bodies to verify state — bypassing what the existing `#<prefix>/captured` tag already encodes. F-47 collapses all four mechanisms into one frontmatter field (`tomo.state`) and replaces the tag with a structured `tomo:` block.

### Value Proposition

A structured `tomo:` frontmatter block (`doc_type`, `state`, `run_id`, `updated_at`, `source_*` refs) on every Tomo-produced doc, discovered via `kado-search operation=byFrontmatter` with `filter.path` server-side narrowing (Kado 0.11.0, live in vault). Outcome:

- **Single source of truth for lifecycle state** — `tomo.state` is THE field. No mirrored tag, no body-checkbox-derived state, no filename-suffix heuristic. One write, one read, one place to be wrong.
- **−53% to −62% in-context tokens** per `/inbox` run on discovery — the byFrontmatter-first design likely does better than baseline estimates predicted (one Kado call returns paths + frontmatter inline, no chained per-doc reads).
- **F-43 acceptance-flow unblocked** — accepted proposal-doc clusters become a `tomo.state` transition that `/inbox` routes through the existing Pass-2 machinery, with bundled `create_moc` + child-relationship-update actions.
- **One state model for every Tomo doc-type** — extensible to F-44/F-45/F-46 without re-debate. Hashi's cleanup contract is state-driven and doc-type-agnostic (iterates `tomo.source_*` generically) so new doc-types ship with zero Hashi changes.
- **Non-linear scenarios handled** — mixed pending + new notes, parallel pending-apply + new sources, drift detection, and the two-run transcription gate all derive from the same single byFrontmatter query (see §6.3/6.4).
- **Frontmatter-level mutations** via Kado 0.10.0 `kado-write operation=frontmatter` eliminate the regex-YAML-edit bug class (resolves `feedback_frontmatter_newline_guard.md` at the Tomo layer too).
- **No backward-compat tax** — Tomo is solo-developer today, so the cut is clean.

---

## 2. User Personas

### Primary Persona: Marcus (Solo-developer Tomo user)

- **Demographics:** Software architect, PKM power user, runs Tomo end-to-end as a personal workflow tool. Comfortable inspecting `tomo-tmp/` state, reads Tomo's `/inbox` traces, opens Obsidian files manually.
- **Goals:**
  - Process daily inbox items into structured PKM artefacts (atomic notes, MOCs, daily-log entries) without manual file-state bookkeeping.
  - Run `/moc-propose` for under-organised topic clusters and accept clusters with a single `[x]` tick.
  - Trust that re-running `/inbox` does not re-process already-handled items, regardless of which workflow doc-type they belong to.
- **Pain Points:**
  - F-43 acceptance-flow non-functional today — accepted MOC clusters have no path to instructions.
  - `/inbox` Auto-Discovery re-reads stale instructions docs (54 actions, 19 days old) on every run, polluting context.
  - Three different "is this done?" semantics across doc-types are hard to keep in mental model.

### Secondary Persona: Future MiYo-power-user (F-44/F-45/F-46 scope)

- **Demographics:** Anyone running Tomo against their own vault once F-44 (garden-audit), F-45 (weekly-review), F-46 (tag-audit) ship. Will use Tomo doc-types that don't exist yet.
- **Goals:** Workflow-doc lifecycle that feels consistent across all `/garden-audit`, `/weekly-review`, `/tag-audit` review documents. Same accept-checkbox → state-promotion → cleanup pattern as `/inbox` and `/moc-propose`.
- **Pain Points (anticipated):** if F-47 doesn't lock the schema now, F-44/F-45/F-46 will each introduce their own state model, replaying the F-43 acceptance-gap bug.

---

## 3. User Journey Maps

### Primary Journey: `/inbox` lifecycle (Pass-1 → Pass-2 → Hashi cleanup)

1. **Source items arrive** — Marcus drops `.md` notes into `100 Inbox/` (manual, via Obsidian, via voice transcript). No `tomo:` block yet → fresh.
2. **`/inbox` Pass 1** — Marcus runs `/inbox` in Tomo container. Orchestrator runs unified discovery (byFrontmatter returns 0 pending-* hits on first run; listDir finds untagged source items), dispatches inbox-analyst subagents, produces `<ts>_suggestions.md` written via Kado with `tomo.state=pending-approval`. `tag-captured.py` (renamed conceptually — see §4 Feature 6) flips source items to `tomo.state=captured`.
3. **Review** — Marcus opens `<ts>_suggestions.md` in Obsidian, reviews per-item Accept checkboxes, ticks `[x] Approved` at the header when satisfied. Saves.
4. **`/inbox` Pass 2** — Marcus re-runs `/inbox`. Orchestrator's state-promoter queries `tomo.state=pending-*` (one byFrontmatter call), finds the suggestions doc, reads its body for `[x] Approved`, dispatches `instruction-builder`. Resulting `<ts>_instructions.md` lands with `tomo.state=pending-apply` + `tomo.source_suggestions: <path>`. Suggestions doc flips to `tomo.state=approved`.
5. **Execute** — Hashi (Obsidian plugin) reads the instructions doc, applies actions one by one, flips per-action `[x] Applied` checkboxes. When all actions applied, Hashi flips file-level `tomo.state=applied`, then trashes the instructions doc + `<ts>_suggestions.md` (per `tomo.source_suggestions` ref) into Obsidian system trash.
6. **Steady state** — inbox is empty (or holds only fresh source items + abandoned `pending-*` orphans Marcus chooses to delete manually).

### Secondary Journey: `/moc-propose` lifecycle (Discovery → Accept → Instructions → Hashi cleanup)

1. **Trigger** — Marcus types `/moc-propose tag:topic/knowledge/lyt` (or folder/class/title/free-text/no-args mode).
2. **Discovery** — moc-architect agent runs the 2-pass discovery (Phase-1 emit → topic extraction → Phase-2 resume); suggestions-reducer renders the proposal-doc; agent kado-writes it to `<ts>_moc-proposal-<slug>.md` with a `tomo:` block carrying `doc_type=moc-proposal`, `state=pending-accept`.
3. **Review** — Marcus opens proposal-doc in Obsidian, reviews clusters (up to 5 + overflow note), ticks `[x] Accept` per cluster he wants. Optionally Override-checkbox per child with existing `up::`. Saves.
4. **`/inbox` MOC-consumption** — Marcus runs `/inbox`. Orchestrator's state-promoter discovers the proposal-doc via the same byFrontmatter query (`tomo.state=pending-*`), reads body for any ticked `[x] Accept`, dispatches the MOC-branch of `instruction-builder`. Resulting `<ts>_instructions.md` lands with `tomo.state=pending-apply` + `tomo.source_moc_proposal: <path>`, and bundles `create_moc` actions (target paths in inbox folder, `<YYYY-MM-DD>_<slug>.md` convention) + child-relationship updates (`up::`, `related::`). Proposal-doc flips to `tomo.state=accepted`. Un-ticked clusters are persisted to squelch as before (F-43 mechanism).
5. **Execute + Cleanup** — same as journey 1 step 5. Hashi applies actions, trashes instructions + proposal-doc.

### Non-Linear Scenarios

The primary/secondary journeys describe the best case — a clean linear run. In practice `/inbox` is invoked repeatedly against an inbox in mixed states. The state-promoter must handle the following scenarios from a single query of vault frontmatter.

#### N1: Mixed pending docs + new untagged notes in one `/inbox` run

State at start: `<ts1>_suggestions.md → pending-approval` (already ticked Approved) + `note-B.md` (new, untagged) + possibly `<ts2>_moc-proposal-*.md → pending-accept` (also ticked).

Behaviour: unified discovery surfaces all three buckets. State-promoter processes pending docs **sequentially** (one at a time, each producing its own `<ts>_instructions.md`), then Pass-1 runs against new sources. End state: 1–2 new instructions docs + suggestions doc for the fresh note. User sees explicit summary at end: *"Processed: 1 suggestions → instructions, 1 moc-proposal → instructions, 1 new note → suggestions. You now have 3 docs awaiting your attention."*

#### N2: Stale `pending-apply` instructions + new notes

State at start: `<ts0>_instructions.md → pending-apply` (Hashi hasn't run, or Marcus hasn't opened Obsidian yet) + `note-C.md` untagged.

Behaviour: state-promoter sees pending-apply but does **not** dispatch (Hashi owns that doc now). Pass-1 runs against `note-C.md` → produces `<ts1>_suggestions.md`. Inbox now holds **two parallel workflows**. User gets an explicit warning: *"⚠ An additional instructions/suggestions file was created. You still have 1 instructions doc pending Hashi-apply (`<ts0>`). Apply both — Hashi handles them independently."* Hashi's cleanup contract (Feature 4) must handle N concurrent instructions docs.

#### N3: Drift — captured sources without workflow docs

State at start: N notes carrying `tomo.state=captured` but zero pending-* docs and zero instructions docs in inbox. Two interpretations:
- (a) **Steady state** — Hashi already ran cleanup; captured notes are residual artefacts the user will manually file or delete. No action needed.
- (b) **Drift** — a suggestions or instructions file was deleted manually mid-flow (or a run crashed); captured tag was applied but downstream artefacts never landed.

Behaviour: `/inbox` cannot distinguish (a) from (b) from vault state alone. It surfaces a hint: *"⚠ N captured notes have no associated workflow doc. If you recently deleted a suggestions/instructions file, run `/inbox --recover` to redo Pass-1 on these. Otherwise ignore."* User decides. No auto-recovery (risk of duplicates if it was actually steady state).

#### N4: Media transcription mid-flow

State at start: `voice-recording.mp3` arrives in inbox (untagged, non-`.md`).

Behaviour: `/inbox` detects media files, runs transcription → produces `voice-recording.md` (untagged). `/inbox` then **stops** with message *"N transcript(s) created — review/edit them, then re-run `/inbox` to process."* The transcript does NOT auto-flow into Pass-1 in the same run. On next `/inbox` invocation, the transcript is treated as a plain untagged source and flows through the normal path.

---

## 4. Feature Requirements

### Must Have Features

#### Feature 1: `tomo:` Frontmatter Block on Every Tomo Doc

**User Story:** As Marcus, I want every Tomo-produced doc in the inbox to declare its doc-type and current lifecycle state in a single frontmatter field, so that `/inbox` knows exactly what to do with it from one query against `tomo.state`.

**`tomo:` block schema (minimum required fields):**

```yaml
tomo:
  doc_type: <suggestions | suggestions-fan | moc-proposal | instructions | source>
  state:    <pending-approval | pending-accept | pending-apply |
             approved | accepted | applied | captured>
  run_id:   <string — run that produced this doc>
  updated_at: <ISO-8601 timestamp>
  # optional cross-references:
  source_suggestions:     "<path>"   # on instructions docs derived from suggestions
  source_suggestions_fan: "<path>"   # on instructions docs derived from XDD 012 fan-resolve
  source_moc_proposal:    "<path>"   # on instructions docs derived from moc-proposal
  source_<doc_type>:      "<path>"   # generic — F-44/45/46 extend here
```

**Note on `suggestions-fan`** (added post-PRD-v1.2, 2026-05-21): XDD 012 (Force Atomic Synthesis, shipped 2026-04-23) produces a `<date>_suggestions-fan.md` companion doc when a user ticks `[x] Force Atomic Note` on a log-entry without an analyst-proposed atomic section. This doc has the same lifecycle shape as the main suggestions doc (pending-approval → approved) but is distinguished by `doc_type=suggestions-fan` so byFrontmatter queries can target it explicitly. F-47.P1 producer sweep extends `suggestions-reducer.py --fan-resolve` to emit the `tomo:` block.

**Acceptance Criteria:**

- [ ] **AC-1.1** Given a fresh source item arrives in `100 Inbox/` without a `tomo:` block, When `/inbox` Pass 1 dispatches the inbox-analyst against it, Then the captured-state writer (formerly `tag-captured.py`, see Feature 6) writes `tomo.state=captured`, `tomo.doc_type=source`, plus `run_id` and `updated_at` via `kado_client.write_frontmatter(mode='merge')`.
- [ ] **AC-1.2** Given Pass 1 completes for N source items, When the orchestrator writes `<ts>_suggestions.md`, Then the doc's `tomo:` block contains `doc_type: suggestions`, `state: pending-approval`, `run_id: <run_id>`, `updated_at: <iso8601>`.
- [ ] **AC-1.3** Given Pass 2 runs against an approved suggestions doc, When the orchestrator writes `<ts>_instructions.md`, Then the doc's `tomo:` block contains `doc_type: instructions`, `state: pending-apply`, `source_suggestions: "<path>"` referring to the upstream suggestions doc.
- [ ] **AC-1.4** Given `/moc-propose` completes, When the moc-architect agent writes the proposal-doc, Then the doc's `tomo:` block contains `doc_type: moc-proposal`, `state: pending-accept`, plus the run_id.
- [ ] **AC-1.5** Given any Tomo producer writes a doc, When the `tomo:` block is rendered, Then it is validated against `tomo/schemas/doc-frontmatter.schema.json` (CI gate + dev-mode runtime assert per Feature 7). Producers that emit malformed blocks fail the dev-mode write.

#### Feature 2: Unified `byFrontmatter` Discovery in `/inbox`

**User Story:** As Marcus, I want `/inbox` to discover work via a single `kado-search byFrontmatter` query (filtered by `tomo.state` directly) instead of body-reading or per-doc frontmatter-reading every file, so that runs are cheap and consistent regardless of inbox accumulation.

**Discovery contract (Kado 0.11.0):**

```
kado-search operation=byFrontmatter
  query: "tomo.state=pending-*"   # or specific states per dispatch branch
  filter:
    path: "<inbox_path>/"          # server-side path narrowing
    modifiedAfter: <ms>            # optional, for incremental discovery (deferred — see backlog)
→ [{path, modified, frontmatter}]  # paths + frontmatter inline, no body transfer
```

Plus one `listDir <inbox_path>` for untagged fresh-source enumeration. Set-diff: `newSources = listDir.paths − discoveryHits.paths`.

**Acceptance Criteria:**

- [ ] **AC-2.1** Given the inbox holds N Tomo-managed docs and M untagged fresh source items, When `/inbox` runs Phase A discovery, Then it executes EXACTLY ONE `kado-search byFrontmatter` call (filtered by `tomo.state` + `filter.path`) AND ONE `listDir` call (for fresh-item enumeration). No per-doc `read_frontmatter` and no body-reads on non-pending docs.
- [ ] **AC-2.2** Given the inbox holds workflow docs in non-pending states (e.g. `applied` instructions that Hashi has not yet trashed because the user opened Hashi mid-cleanup), When `/inbox` runs Phase A discovery, Then those docs are NOT returned by the byFrontmatter query (because the query targets `pending-*` states only). No body-read, no further filtering needed.
- [ ] **AC-2.3** Given the inbox is empty of `tomo.state=pending-*` docs (fresh first run, or after Hashi cleanup), When `/inbox` runs Phase A, Then byFrontmatter returns zero results AND listDir is used to find untagged source items (hybrid path; both calls execute every run).
- [ ] **AC-2.4** Given `filter.path` server-side narrowing is active, When users manually apply `tomo.state=...` to a doc outside `<inbox_path>` (vault-wide pollution), Then `/inbox` byFrontmatter does NOT return that hit — server-side filter excludes it. No client-side path-filter required.

#### Feature 3: State-Promoter (Pending-State Body Reads, Tag Flips)

**User Story:** As Marcus, I want ticking `[x] Approved` (or `[x] Accept` per cluster) in a workflow doc to be the only action needed — `/inbox` figures out what to do next from the tick, no manual tag editing.

**Acceptance Criteria:**

- [ ] **AC-3.1** Given a doc with `tomo.state=pending-approval` and `[x] Approved` ticked in the body, When `/inbox` Phase A runs the state-promoter, Then it dispatches `instruction-builder` against this doc; after Pass-2 success, the suggestions doc's `tomo.state` is set to `approved` via `kado-write operation=frontmatter mode=merge`.
- [ ] **AC-3.2** Given a doc with `tomo.state=pending-accept` and at least one `[x] Accept` ticked in the body, When `/inbox` Phase A runs the state-promoter, Then it dispatches the MOC-consumption branch of `instruction-builder`; after success, the proposal-doc's `tomo.state` is set to `accepted`.
- [ ] **AC-3.3** Given a `pending-*` doc with NO accept checkbox ticked, When `/inbox` runs the state-promoter, Then nothing happens to the doc (it stays in pending state for Marcus to revisit).
- [ ] **AC-3.4** Given the state-promoter encounters an invalid transition request (e.g. an `applied` instructions doc — somehow tag-corruption — being scanned), When it processes the doc, Then the transition is rejected with a logged warning, NO write happens, and the orchestrator continues with the next doc.
- [ ] **AC-3.5** Given the state-promoter's pending-doc body-read returns malformed content (e.g. corrupted file), When the read fails, Then the doc is logged as a warning and skipped; subsequent docs are still processed.

#### Feature 4: Hashi Auto-Cleanup on Instructions-Applied (State-Driven Contract)

**User Story:** As Marcus, when Hashi finishes executing the last action of an instructions set, I want it to delete the instructions doc and every upstream Tomo doc that produced it, so my inbox returns to its working set without manual cleanup. Hashi must work the same way whether there's one instructions doc or several pending in parallel.

**Contract framing (changed from filename-driven to state-driven):**

Hashi's cleanup is keyed off **state**, not filename or doc-type enumeration. The Tomo-side contract Hashi consumes:

- **Trigger**: any doc reaches `tomo.state = applied` (Hashi can observe this on any doc Hashi knows about, regardless of doc_type).
- **Cleanup sources**: the doc's `tomo` block lists upstream paths under any key matching `source_*` (e.g. `source_suggestions`, `source_moc_proposal`, future `source_garden_audit`). Hashi iterates all `source_*` keys generically — Tomo can add new doc-types without Hashi code changes.
- **Concurrency**: multiple instructions docs may be pending at once. Each is independent; Hashi tracks each by its own path.

**Acceptance Criteria:**

- [ ] **AC-4.1** Given Hashi has just flipped the last `[x] Applied` checkbox in an `<ts>_instructions.md` whose `tomo:` block lists one or more `source_*` paths, When the cleanup step runs, Then Hashi flips the instructions doc's `tomo.state` from `pending-apply` to `applied` (via Kado 0.11.0 `kado-write operation=frontmatter`, `mode=merge`), then trashes the instructions doc + every path under any `tomo.source_*` key to Obsidian system trash.
- [ ] **AC-4.2** Given the upstream source doc referenced by any `tomo.source_*` key is already missing when Hashi runs cleanup (Marcus deleted it manually), When cleanup runs, Then Hashi logs a warning for the missing path AND proceeds with the cleanup of all other paths (best-effort); the instructions doc itself is always trashed last.
- [ ] **AC-4.3** Given an instructions set has 50 actions, 49 applied, the 50th errored, When cleanup is evaluated, Then NO cleanup is triggered (cleanup requires 100% applied). The instructions doc and its source(s) remain in inbox.
- [ ] **AC-4.4** Given the inbox contains multiple `pending-apply` instructions docs simultaneously (N2 scenario), When Hashi finishes applying any one of them, Then cleanup runs ONLY for that doc + its sources; the other pending docs are untouched and remain Hashi's responsibility on their own completion.
- [ ] **AC-4.5** Given a new Tomo doc-type ships in the future (F-44 garden-audit, F-45 weekly-review, F-46 tag-audit) and produces instructions referencing `tomo.source_garden_audit: <path>`, When Hashi cleanup runs, Then the new source path is trashed alongside the instructions doc — without any Hashi code change.

**Cross-repo dependency:** The state-driven contract is what Tomo will send to Hashi in the schema-lock handoff (succeeds the early-warning notice from 2026-05-20). Hashi-side implementation of the generic `source_*` iteration is independent of any specific Tomo doc-type list.


#### Feature 5: F-43 MOC-Consumption (Acceptance Gap Closure)

**User Story:** As Marcus, when I tick `[x] Accept` on a cluster in a proposal-doc and run `/inbox`, I want the accepted MOC to be created in my vault end-to-end — closing the gap that paused F-43 T6.2.

**Acceptance Criteria:**

- [ ] **AC-5.1** Given a doc with `tomo.state=pending-accept`, `doc_type=moc-proposal`, and cluster MOC01 `[x] Accept` ticked + 5 child wikilinks listed, When `/inbox` runs the state-promoter, Then `instruction-builder` MOC-branch emits ONE bundled instructions set into `<ts>_instructions.md` containing: 1× `create_moc` action (target path follows the standard Pass-1 convention: `<inbox_path>/<YYYY-MM-DD>_<slugified-moc-title>.md`) + 5× `update_frontmatter` or `update_relationships` actions on the child notes (writes `up:: [[<moc-title>]]`, optional `related::` per cluster spec). The proposal-doc's `tomo.state` flips to `accepted`.
- [ ] **AC-5.2** Given a multi-cluster proposal-doc with 3 clusters ticked Accept and 2 un-ticked, When the MOC-consumption runs, Then 3 clusters become bundled instructions actions (3× `create_moc` + N× child-relationship updates, all in one instructions doc) AND the 2 un-ticked clusters are persisted to `state/moc-squelch.json` via the existing F-43 squelch-persistence mechanism.
- [ ] **AC-5.3** Given Hashi receives the bundled instructions set from MOC-consumption and successfully applies all `create_moc` + relationship-update actions, When Hashi runs cleanup, Then Hashi trashes the instructions doc + the source proposal-doc (per `tomo.source_moc_proposal: <path>` ref). New MOC files created in the inbox folder remain — they are real vault artefacts now, not workflow scratch.
- [ ] **AC-5.4** Given new MOCs land in `<inbox_path>/` rather than a topic folder, When Marcus reviews them in Obsidian, Then they are immediately searchable + linkable (Obsidian doesn't care about folder location). Future move into a target folder (e.g. `200 MOCs/`) is a user-initiated step outside F-47 scope.

**Design note:** The bundled actions pattern means one MOC acceptance produces one instructions set, not N (one per child). This keeps Hashi's apply transactional per accepted cluster and matches the suggestions/instructions pattern (one suggestions doc → one instructions doc).

#### Feature 5a: Drift Detection (Captured Sources Without Workflow Docs)

**User Story:** As Marcus, when I've deleted a suggestions/instructions file manually (or a run crashed mid-flight), I want `/inbox` to notice that captured notes are stranded and offer to recover — rather than silently treating them as already-processed.

**Acceptance Criteria:**

- [ ] **AC-5a.1** Given Phase A discovery completes and finds: N > 0 source notes tagged `tomo.state=captured` AND zero pending-* workflow docs AND zero `pending-apply` instructions docs, When `/inbox` reports its Phase A summary, Then it surfaces a hint: *"⚠ N captured notes have no associated workflow doc. If you deleted a suggestions/instructions file, run `/inbox --recover` to redo Pass-1. Otherwise these are already-processed residuals."*
- [ ] **AC-5a.2** Given the user invokes `/inbox --recover`, When Phase A runs, Then captured notes are treated as fresh sources for the purposes of Pass-1 (orchestrator dispatches inbox-analyst against them as if they were untagged). `tag-captured.py` re-asserts the `captured` tag at run end (idempotent — no-op if already captured).
- [ ] **AC-5a.3** Given recovery produces a new `<ts>_suggestions.md`, When the user runs Pass-2 normally, Then the lifecycle resumes from there — the recovery is transparent to downstream Hashi cleanup.
- [ ] **AC-5a.4** Given the user does NOT invoke `--recover`, When `/inbox` runs normally, Then captured notes are ignored (no body-read, no dispatch). They remain in the inbox for the user to file/delete manually.

**Design note:** Drift detection is a **hint**, not an action. `/inbox` cannot distinguish "Hashi cleaned up and these are residuals" from "user deleted the suggestions file." The user makes the call. This preserves vault-as-SoT discipline (we never auto-act on ambiguous state).

#### Feature 5b: Media Transcription Stop-Gate

**User Story:** As Marcus, when I drop an audio file in the inbox, I want `/inbox` to transcribe it but stop short of capturing the resulting `.md` — so I can review/edit the transcript before it flows into Pass-1.

**Acceptance Criteria:**

- [ ] **AC-5b.1** Given the inbox contains one or more media files (`.mp3`, `.m4a`, `.wav`, configured set), When `/inbox` runs Phase A discovery, Then the transcription sub-step runs and produces a sibling `<stem>.md` per media file — but the new `.md` files are NOT picked up by the SAME `/inbox` run's Pass-1. `/inbox` exits after transcription with message: *"N transcript(s) created. Review/edit them, then re-run `/inbox` to process."*
- [ ] **AC-5b.2** Given the user re-runs `/inbox` after transcription, When Phase A discovery runs, Then the transcript `.md` is seen as an untagged source (it has no `tomo.state` field) and flows through Pass-1 normally → produces suggestions doc, tags transcript as `captured`.
- [ ] **AC-5b.3** Given a transcript was NOT edited by the user before the next `/inbox` run, When Pass-1 processes it, Then it is treated identically to a manually-dropped untagged `.md` (no special handling, no penalty). The two-run gate is the only difference from the manual-drop flow.
- [ ] **AC-5b.4** Given media files AND untagged manual `.md` notes both exist in inbox on the same run, When `/inbox` runs, Then transcription completes for media AND Pass-1 runs for the existing manual `.md` notes. Only the **newly produced transcripts** are deferred to the next run; existing notes are not gated by transcription.

### Should Have Features

#### Feature 6: `kado_client.write_frontmatter()` Wrapper (Tomo-Side)

**User Story:** As a Tomo script author, I want a single thin wrapper around Kado 0.10.0's `kado-write operation=frontmatter` op, so all state-promotion code paths converge on one call site.

**Acceptance Criteria:**

- [ ] **AC-6.1** Given `tomo/scripts/lib/kado_client.py` is updated, When any Tomo script needs to mutate a doc's frontmatter, Then it calls `client.write_frontmatter(path, fm_dict, mode='merge', expected_modified=None)` — never `client.read_note + string-edit + client.write_note`.
- [ ] **AC-6.2** Given the wrapper is in place, When the captured-state writer (today `tag-captured.py:96-184`, renamed conceptually since it no longer writes a tag — proposed new name `mark-captured.py` or kept for git-history-continuity, SDD decides) runs to set `tomo.state=captured` on a source item, Then it uses the new wrapper (not the existing regex-YAML edit). This eliminates the `feedback_frontmatter_newline_guard.md` failure class at the Tomo layer.

#### Feature 7: State-Machine Module (`scripts/lib/tomo_lifecycle.py`)

**User Story:** As a Tomo maintainer, I want one place that defines the state machines per doc-type with allowed transitions and rejection rules, so that adding F-44/F-45/F-46 doc-types means adding one entry to one file — not editing 8.

**Acceptance Criteria:**

- [ ] **AC-7.1** Given the new module exists, When any of state-init, orchestrator, state-promoter, or vault-executor needs to validate a state transition, Then they import from `tomo_lifecycle.py` (not redefine locally).
- [ ] **AC-7.2** Given the state-machine schema is in `tomo/schemas/doc-frontmatter.schema.json`, When any producer emits a `tomo:` block, Then it is validated against the schema (CI check + runtime assert in dev mode).

### Could Have Features

#### Feature 8 (Could → Resolved): MCP-Layer Discovery Optimizations

**OQ6 resolved in v1.1** — all three original candidates are either already shipped in Kado 0.10.0/0.11.0 (used directly by F-47) or deferred to a separate spec (incremental-discovery cache). See §10 for the resolution details. No additional MCP-layer work in F-47.

#### Feature 9 (Could): Tomo-Side Audit-Trail Helper

A small CLI to dump the lifecycle state of all docs in inbox (`tomo-state.py --inbox`). Useful for debugging stuck states. Not required for F-47 to ship.

### Won't Have (This Phase)

- **No Tomo-side cleanup script** — Hashi owns instructions-done cleanup; orphan cleanup stays manual (Obsidian right-click delete). Locked OQ13.
- **No bulk-rename of existing files** — going-forward only. Privat-Test resets as part of F-47 rollout. Locked OQ5.
- **No source-item arrival watcher** — source items tag at Pass 1 dispatch, not on arrival. Locked OQ2.
- **No Hashi `update_frontmatter` instruction-set action** — state-promotion stays Tomo-side (Python via the wrapper). Hashi-side state flip happens only at instructions-applied cleanup (per AC-4.1), not as an instruction set action.
- **No legacy-fallback in state-init / orchestrator** — clean cut-over. Locked OQ4.
- **No automatic squelch-clear when user re-proposes the same cluster** — F-43 squelch semantics unchanged.
- **No telemetry / analytics on lifecycle transitions** — Constitution L1 Privacy.
- **No incremental-discovery cache (last-run timestamp persistence)** — Kado 0.11.0 ships `filter.modifiedAfter` which unlocks this, but the cache layer + invalidation rules + `--full-vault` UX deserve their own spec. Tracked in `docs/XDD/backlog.md` as a precursor for F-45 weekly-review.
- **No auto-recovery on drift** — drift detection surfaces a hint; `/inbox --recover` is user-initiated (AC-5a.4). Silent re-Pass-1 could create duplicates if the drift signal is actually a steady-state residual.
- **No transcription auto-flow into Pass-1** — the two-run gate is the contract (AC-5b.1). User edits between transcribe and capture.
- **No mirrored lifecycle tag** (`#<prefix>/<doc-type>/<state>`) — `tomo.state` in frontmatter is the single SoT (v1.2 decision). Rationale: user does not browse Tomo workflow docs via Obsidian's tag pane and hides frontmatter in the editor; the tag would add per-transition write payload + drift-handling without UX benefit. Reversible if needs change — re-add via a renderer-side write.

---

## 5. Detailed Feature Specifications

### Feature: State-Promoter + Unified Discovery (the heart of the consumer-side refactor)

**Description:** The state-promoter is the new orchestrator step that runs in `/inbox` Phase A. It uses a single `byFrontmatter` query (Kado 0.11.0, paths + frontmatter inline) to discover all Tomo workflow docs in the inbox, sequentially processes each pending doc that has the corresponding user-tick in body, dispatches the matching Pass-2 branch (instruction-builder, MOC or suggestions), and flips `tomo.state` on success.

**User Flow:**

1. `/inbox` Phase A0–A2 runs as today (path resolution, scratch dir, run-id).
2. **NEW Step A2.5 — Unified Discovery + State-Promoter Scan** (replaces old A2.5 + A4 as separate phases):
   - **2.5.a Transcription pre-check**: scan inbox for media files. If any present → run transcription sub-step → exit `/inbox` with stop-gate message (AC-5b.1). Skip the rest of Phase A.
   - **2.5.b Unified discovery — two Kado calls:**
     ```
     kado-search operation=byFrontmatter
       query: "tomo.state=pending-*"   # any pending state
       filter: { path: "<inbox_path>/" }
     → [{ path, modified, frontmatter }]   # frontmatter inline, no body transfer

     kado-list operation=listDir
       path: "<inbox_path>"
       filter: { type: "file", extension: "md" }
     → [path, ...]                          # all .md paths in inbox
     ```
   - **2.5.c Bucket the results client-side:**
     - `pendingApproval`  = discoveryHits where `tomo.doc_type == suggestions`   AND `tomo.state == pending-approval`
     - `pendingAccept`    = discoveryHits where `tomo.doc_type == moc-proposal`  AND `tomo.state == pending-accept`
     - `pendingApply`     = discoveryHits where `tomo.doc_type == instructions`  AND `tomo.state == pending-apply`
     - `capturedSources`  = also from a parallel `byFrontmatter` lookup OR derived from listDir set-diff vs. pending (implementation detail — see SDD)
     - `newSources`       = listDir.paths − discoveryHits.paths − capturedSources.paths
   - **2.5.d Drift check:** if `capturedSources.count > 0` AND `pendingApproval+pendingAccept+pendingApply == 0`, emit drift hint (AC-5a.1). User must run `--recover` to act on it; default flow proceeds.
   - **2.5.e Sequential state-promotion** (one doc at a time):
     - For each doc in `pendingApproval`: `kado-read operation=note` (body only; we already have frontmatter from 2.5.b) → check `[x] Approved` marker → if ticked, dispatch instruction-builder Pass-2 → on success, flip `tomo.state` to `approved` via `kado-write operation=frontmatter mode=merge`.
     - For each doc in `pendingAccept`: same shape, dispatching instruction-builder MOC-branch.
     - For each doc in `pendingApply`: NO dispatch. Hashi owns these. If `pendingApply.count > 0` AND any new instructions were just produced (parallel-process N2 scenario), surface the explicit-warning message.
3. Phase A3 (shared-ctx-builder) runs as today (now feeds counters from 2.5).
4. **Step A4 is removed** — state-init's listDir + tag-state filter is folded into 2.5.b/2.5.c. The legacy SKIP_SUFFIXES + body-read for state detection are deleted; `tomo.state` from the byFrontmatter response is the only state signal.
5. Phase A5 (branch decision) consumes the four counters from 2.5.c.

**Business Rules:**

- **Sequential promotion** — state-promoter processes pending docs ONE AT A TIME (locked decision). Each completion produces an independent instructions doc + tag flip before the next doc is touched. No parallel Agent fan-out at the state-promotion layer.
- **Multi-pending support** — ALL pending docs found in 2.5.c are processed in the same run (subject to sequential rule). Mixed types (`pendingApproval` + `pendingAccept`) → both processed, each producing its own instructions doc.
- **No recursion** — a doc promoted from `pending-approval → approved` within this run is NOT then re-evaluated for further promotion in the same run. Each doc transitions at most once per `/inbox` invocation.
- **Transition rejections** — allowed transitions: `pending-approval → approved`; `pending-accept → accepted`; `pending-apply → applied` (Hashi-side only); `pending → captured` (Pass-1 only). Anything else is logged + skipped.
- **Body-read budget** — state-promoter body-reads ONLY the pending docs the orchestrator is actively promoting in this run (≤ pending count, typically 0–3). Non-pending docs are NEVER body-read; their frontmatter is already in hand from 2.5.b.
- **Idempotency** — re-running `/inbox` against a doc already in terminal state (`approved`, `accepted`, `applied`, `captured`) is a no-op for that doc.

**Edge Cases:**

- **Concurrent Hashi run** — Hashi flips instructions `pending-apply → applied` mid-`/inbox`. Optimistic-concurrency check on `expectedModified` (Kado 0.10.0+ supports). On conflict: retry once, then surface error.
- **Doc with `tomo:` block but no checkbox in body** (partial render bug) — log warning, skip; doc stays pending.
- **Doc with `tomo:` block but unexpected `state` value** (e.g. a manual edit set `tomo.state` to a value not in the locked state machine): state-promoter rejects the transition, logs a `lifecycle.transition_rejected` event with `attempted_from_state=<unexpected>`, and skips the doc. The Should-have schema validation (Feature 7) catches this in dev mode at write-time.
- **byFrontmatter returns same doc twice** (Kado bug or duplicate tag) — dedupe by path, process once.
- **`pendingApply` count > 0 but no new pendings to process** — emit info hint *"You have N instructions docs awaiting Hashi-apply"*; otherwise no-op.

---

## 6. Flow Diagrams (OQ14 Lock — Required PRD Content)

Four flows. Each row shows: phase, file involved, frontmatter state at that point, who writes it.

### 6.1 `/inbox` Lifecycle — Full Pass 1 + Pass 2 + Cleanup (Best Case)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Trigger: Marcus drops `note-A.md` in 100 Inbox/ (no tomo.state yet)      │
└─────────────────────────────────────────────────────────────────────────┘
  Files in inbox:                                Frontmatter state:
    note-A.md                                      (no tomo.state — fresh)

┌─────────────────────────────────────────────────────────────────────────┐
│ /inbox — Phase A (unified discovery)                                    │
│   A0  read concepts.inbox                                               │
│   A1  mkdir tomo-tmp/items                                              │
│   A2  generate RUN_ID                                                   │
│   A2.5a transcription pre-check: no media files → continue              │
│   A2.5b kado-search byFrontmatter "tomo.state=pending-*"                │
│          filter.path "100 Inbox/" → 0 hits                              │
│         kado-list listDir "100 Inbox/" → [note-A.md]                    │
│   A2.5c buckets: newSources=[note-A.md], pending*=[], captured=[]       │
│   A2.5d drift-check: skip (no captured, no pending)                     │
│   A2.5e state-promotion: skip (no pending docs)                         │
│   A3  shared-ctx-builder                                                │
│   A5  branch: items_found=1, captured=0 → Phase B                       │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ /inbox — Phase B fan-out (inbox-analyst per item)                       │
│   Each subagent classifies note-A → tomo-tmp/items/<stem>.result.json   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ /inbox — Phase C reduce + render + kado-write                           │
│   C2  suggestions-reducer.py → tomo-tmp/suggestions-doc.json            │
│   C3  suggestions-render.py → tomo-tmp/suggestions-rendered.md          │
│        (NEW: render emits `tomo:` block with doc_type, state,           │
│         run_id, updated_at — no separate lifecycle tag in v1.2)          │
│   C4  Read tomo-tmp/suggestions-rendered.md, kado-write to inbox        │
│        → writes `<ts>_suggestions.md`                                   │
│   C5  mark-captured: write_frontmatter on note-A.md                     │
│        → tomo.state: captured (no separate tag)                         │
└─────────────────────────────────────────────────────────────────────────┘
  Files in inbox:                                Frontmatter state:
    note-A.md                                      tomo.state=captured
    <ts>_suggestions.md                            tomo.state=pending-approval

┌─────────────────────────────────────────────────────────────────────────┐
│ Marcus opens <ts>_suggestions.md in Obsidian, ticks [x] Approved, saves │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ /inbox (second run) — Phase A unified discovery                         │
│   A2.5b byFrontmatter "tomo.state=pending-*" filter.path "100 Inbox/"   │
│         → 1 hit: <ts>_suggestions.md (doc_type=suggestions,             │
│                                       state=pending-approval)           │
│         listDir → [note-A.md, <ts>_suggestions.md]                      │
│   A2.5c buckets: pendingApproval=[<ts>_sugg], captured=[note-A],        │
│                  newSources=[]                                          │
│   A2.5e state-promotion (sequential):                                   │
│         read body of <ts>_suggestions.md → [x] Approved found           │
│         → dispatch instruction-builder Pass-2                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ instruction-builder (Pass 2)                                            │
│   Reads <ts>_suggestions.md + tomo-tmp/items/* (or re-runs Phase C)     │
│   Emits instructions.json + renders <ts>_instructions.md                │
│   write_frontmatter on suggestions doc (merge):                         │
│     tomo.state: approved                                                │
│   Writes <ts>_instructions.md with:                                     │
│     tomo: { doc_type: instructions, state: pending-apply,               │
│             source_suggestions: "100 Inbox/<ts>_suggestions.md",        │
│             run_id, updated_at }                                        │
└─────────────────────────────────────────────────────────────────────────┘
  Files in inbox:                                Frontmatter state:
    note-A.md                                      tomo.state=captured
    <ts>_suggestions.md                            tomo.state=approved
    <ts>_instructions.md                           tomo.state=pending-apply

┌─────────────────────────────────────────────────────────────────────────┐
│ Marcus opens <ts>_instructions.md in Obsidian (via Hashi plugin)        │
│ Hashi applies actions one by one, ticks [x] Applied per action          │
│ When last action is [x] Applied:                                        │
│   Hashi kado-write operation=frontmatter (merge):                       │
│     tomo.state: applied                                                 │
│   Hashi iterates tomo.source_* keys → finds source_suggestions          │
│   Hashi trashes (in order):                                             │
│     <ts>_suggestions.md   → Obsidian system trash                       │
│     <ts>_instructions.md  → Obsidian system trash (last)                │
│   Source note-A.md stays in inbox (tomo.state=captured)                 │
└─────────────────────────────────────────────────────────────────────────┘
  Files in inbox:                                Frontmatter state:
    note-A.md                                      tomo.state=captured
```

### 6.2 `/moc-propose` Lifecycle — Discovery → Accept → Bundled Instructions → Cleanup

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Trigger: Marcus types `/moc-propose tag:topic/knowledge/lyt`            │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ moc-architect agent (impersonated by /moc-propose)                      │
│   Step 1-3  parse mode, resolve config                                  │
│   Step 4a   moc-discovery.py --emit-phase1 → tomo-tmp/phase1.json       │
│   Step 4b   agent extracts topics for cache-miss candidates inline      │
│   Step 4c   moc-discovery.py --phase1-input → DiscoveryReport JSON      │
│   Step 6    write DiscoveryReport to tomo-tmp/                          │
│   Step 7    suggestions-reducer.py --moc-proposal-mode --output-dir     │
│              tomo-tmp/ → renders proposal-doc to tomo-tmp/              │
│              (NEW: render emits `tomo:` block with doc_type,            │
│               state, run_id — no separate lifecycle tag in v1.2)        │
│   Step 7.5  Read tomo-tmp/<ts>_moc-proposal-<slug>.md                   │
│              kado-write to inbox → <ts>_moc-proposal-<slug>.md          │
└─────────────────────────────────────────────────────────────────────────┘
  Files in inbox:                                Frontmatter state:
    <ts>_moc-proposal-notemaking.md                tomo.state=pending-accept

┌─────────────────────────────────────────────────────────────────────────┐
│ Marcus opens proposal-doc in Obsidian, ticks [x] Accept on MOC01, saves │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ /inbox — Phase A unified discovery                                      │
│   A2.5b byFrontmatter "tomo.state=pending-*" filter.path "100 Inbox/"   │
│         → 1 hit: <ts>_moc-proposal-...md                                │
│           (doc_type=moc-proposal, state=pending-accept)                 │
│   A2.5e state-promotion (sequential):                                   │
│         read body → [x] Accept on MOC01 found                           │
│         → dispatch instruction-builder MOC-branch                       │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ instruction-builder (MOC-branch via suggestion-parser MOC dispatch)     │
│   Parses proposal-doc with enumerate_all_moc_sections                   │
│   For each ticked MOC: emit BUNDLED actions into one instructions doc:  │
│     • create_moc → target: 100 Inbox/<YYYY-MM-DD>_<slug>.md             │
│     • update_frontmatter on each child:                                 │
│         up:: [[<moc-title>]], optional related:: per cluster spec       │
│   For each un-ticked MOC: persist to state/moc-squelch.json (F-43)      │
│   write_frontmatter on proposal-doc (merge):                            │
│     tomo.state: accepted                                                │
│   Writes <ts>_instructions.md with:                                     │
│     tomo: { doc_type: instructions, state: pending-apply,               │
│             source_moc_proposal: "100 Inbox/<ts>_moc-proposal-...md",   │
│             run_id, updated_at }                                        │
└─────────────────────────────────────────────────────────────────────────┘
  Files in inbox:                                Frontmatter state:
    <ts>_moc-proposal-notemaking.md                tomo.state=accepted
    <ts>_instructions.md                           tomo.state=pending-apply

┌─────────────────────────────────────────────────────────────────────────┐
│ Hashi applies bundled instructions, ticks [x] Applied per action        │
│ When last action applied:                                               │
│   Hashi kado-write frontmatter on instructions:                         │
│     tomo.state: applied                                                 │
│   Hashi iterates tomo.source_* keys → finds source_moc_proposal         │
│   Hashi trashes (in order):                                             │
│     <ts>_moc-proposal-notemaking.md → Obsidian trash                    │
│     <ts>_instructions.md            → Obsidian trash (last)             │
│   New MOC file (100 Inbox/<date>_<slug>.md) stays in vault — real       │
│   artefact now, not workflow scratch                                    │
└─────────────────────────────────────────────────────────────────────────┘
  Files in inbox after cleanup:                  Frontmatter state:
    <YYYY-MM-DD>_<moc-slug>.md                     (no tomo.state — real MOC)
    (child notes now carry `up::` relationship to the new MOC)
```

### 6.3 Mixed-State `/inbox` Run (Scenario N1 + N2)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Starting state — multi-source backlog                                   │
└─────────────────────────────────────────────────────────────────────────┘
  Files in inbox:                                Frontmatter state:
    note-old.md                                    tomo.state=captured
    <ts0>_instructions.md                          tomo.state=pending-apply
    <ts1>_suggestions.md                           tomo.state=pending-approval
    <ts2>_moc-proposal-x.md                        tomo.state=pending-accept
    note-new.md                                    (no tomo.state — fresh)

┌─────────────────────────────────────────────────────────────────────────┐
│ /inbox — Phase A unified discovery                                      │
│   A2.5b byFrontmatter "tomo.state=pending-*" filter.path "100 Inbox/"   │
│         → 3 hits: <ts0> (pending-apply), <ts1> (pending-approval),      │
│                  <ts2> (pending-accept)                                 │
│         listDir → [note-old, <ts0>, <ts1>, <ts2>, note-new]             │
│   A2.5c buckets:                                                        │
│         pendingApproval = [<ts1>]                                       │
│         pendingAccept   = [<ts2>]                                       │
│         pendingApply    = [<ts0>]    ← Hashi owns, no Tomo dispatch     │
│         newSources      = [note-new]                                    │
│         captured        = [note-old] ← non-empty + pending* non-empty,  │
│                                        no drift hint                    │
│   A2.5e state-promotion (sequential):                                   │
│         1. <ts1> body has [x] Approved → dispatch Pass-2 normal         │
│            → produces <ts3>_instructions.md (source_suggestions=<ts1>)  │
│            → flips <ts1> to tomo.state=approved                         │
│         2. <ts2> body has [x] Accept   → dispatch Pass-2 MOC            │
│            → produces <ts4>_instructions.md (source_moc_proposal=<ts2>) │
│            → flips <ts2> to tomo.state=accepted                         │
│   A3  shared-ctx-builder (counters: newSources=1, captured=1)           │
│   A5  branch: items_found=1 → Phase B Pass-1 for note-new               │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Phase B/C  Pass-1 for note-new → <ts5>_suggestions.md                   │
│            tag-captured.py: note-new → tomo.state=captured              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ /inbox final summary message (printed to stderr):                       │
│   ✓ Processed:                                                          │
│     - 1 suggestions → instructions (<ts3>)                              │
│     - 1 moc-proposal → instructions (<ts4>)                             │
│     - 1 new source → suggestions    (<ts5>)                             │
│   ⚠ You now have 3 instructions docs pending Hashi-apply (<ts0>, <ts3>, │
│     <ts4>) plus 1 suggestions doc awaiting your review (<ts5>). Apply   │
│     ALL of them — Hashi handles each independently.                     │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.4 Drift Recovery (Scenario N3)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Starting state — captured sources, no workflow docs                     │
│ (Marcus accidentally deleted <ts>_suggestions.md mid-flow)              │
└─────────────────────────────────────────────────────────────────────────┘
  Files in inbox:                                Frontmatter state:
    note-X.md                                      tomo.state=captured
    note-Y.md                                      tomo.state=captured
    note-Z.md                                      tomo.state=captured

┌─────────────────────────────────────────────────────────────────────────┐
│ /inbox — Phase A unified discovery (without --recover)                  │
│   A2.5b byFrontmatter "tomo.state=pending-*" → 0 hits                   │
│   A2.5c buckets: captured=[X,Y,Z], pending*=[], newSources=[]           │
│   A2.5d drift-check: captured>0 AND all pending counters=0              │
│         → SURFACE HINT:                                                 │
│           "⚠ 3 captured notes have no workflow doc. Run /inbox          │
│            --recover to redo Pass-1, or ignore if these are residuals."│
│   A2.5e state-promotion: nothing to do                                  │
│   A5  branch: items_found=0, captured=3, drift=true → no Phase B        │
│         → exit with hint visible                                        │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Marcus runs /inbox --recover                                            │
│   A2.5c buckets (overridden): newSources=[X,Y,Z] (treat captured as new)│
│   Pass-1 dispatches inbox-analyst against X, Y, Z                       │
│   → produces <ts>_suggestions.md                                        │
│   tag-captured.py is idempotent — X, Y, Z stay at tomo.state=captured   │
└─────────────────────────────────────────────────────────────────────────┘
  Files in inbox after recovery:                 Frontmatter state:
    note-X.md, note-Y.md, note-Z.md                tomo.state=captured
    <ts>_suggestions.md                            tomo.state=pending-approval
  (Lifecycle has resumed from the suggestions-doc step)
```

---

## 7. Success Metrics

### Key Performance Indicators

| Metric | Target | Today's Baseline |
|---|---|---|
| **Adoption** | 100% of Tomo workflow docs carry a schema-valid `tomo:` block with `state` set (no exceptions) | 0% (only source items use `#<prefix>/captured` tag today) |
| **Engagement (token cost)** | `/inbox` Phase A discovery cost ≤ 2,000 tokens (Scenario A, steady state) | ~4,850 tokens |
| **Engagement (token cost — heavy)** | `/inbox` Phase A discovery cost ≤ 6,000 tokens (Scenario B, backlog of 3 instructions + 2 suggestions + 1 moc-proposal + 5 source items) | ~12,000 tokens |
| **Quality (transition correctness)** | 100% of state transitions match the locked state machine (no invalid transitions accepted by state-promoter) | N/A (no centralized state machine today) |
| **Business impact (F-43 unblock)** | F-43 T6.2 + T6.4 resume + pass within 1 sprint of F-47.P4 ship | F-43 indefinitely paused since 2026-05-20 |
| **Bug elimination** | `feedback_frontmatter_newline_guard.md` failure mode no longer reproducible after F-47.P1 ships | Currently reproducible in `tag-captured.py:131-177` |

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| `lifecycle.transition` | `doc_type`, `from_state`, `to_state`, `run_id`, `path`, `outcome (success / rejected / skipped)` | Validate AC-1.x through AC-5.x; debug stuck states |
| `lifecycle.discovery` | `run_id`, `byFrontmatter_hits`, `listDir_hits`, `pending_body_reads`, `bucket_counts (pendingApproval, pendingAccept, pendingApply, captured, newSources)`, `drift_hint_emitted`, `phase_a_duration_ms`, `token_estimate` | Validate AC-2.x perf target; track regressions |
| `lifecycle.cleanup` | `run_id`, `instructions_path`, `source_path`, `outcome (success / source_missing / failed)` | Validate AC-4.x; surface user-facing issues |
| `lifecycle.transition_rejected` | `doc_type`, `attempted_from_state`, `attempted_to_state`, `reason` | Detect invalid-transition bugs (Constitution L1 Testing rejection rule) |

Events logged to stderr (Constitution L2 — metadata-only audit, no body content). Aggregation post-MVP if needed.

---

## 8. Constraints and Assumptions

### Constraints

**Source-of-Truth principle (locked):**
- **Vault frontmatter is authoritative** for all lifecycle state. `tomo.state` on each doc is the single field that determines what `/inbox` does next.
- **`tomo-tmp/` is per-run scratch** — never read between `/inbox` runs. Each run reconstructs its plan from vault state alone.
- **`tomo-instance/state/` holds persistence aids only** — F-43 squelch list lives here today; future incremental-discovery cache (backlog) would live here too. These are *hints/optimisations*, never truth. If the file is missing or corrupt, the system falls back to vault-derived behaviour (slower but correct).
- **Drift is detectable, not auto-recoverable** — if vault state is internally inconsistent (e.g. captured sources but no workflow docs), `/inbox` surfaces the situation and lets the user decide (Feature 5a).

**MiYo Constitution L1 (Must)**:
- **Privacy** — `tomo:` block holds workflow metadata only (`doc_type`, `state`, `run_id`, `updated_at`, `source_*` paths). No PKM content. No credentials. No body excerpts.
- **Local-first** — All state mutations go through Kado MCP. No external state store.
- **No telemetry** — Lifecycle events log to stderr only.
- **No main-thread blocking** — Discovery + state-promoter run via existing Phase A pattern (Bash sub-processes).
- **Bounded payloads** — byFrontmatter returns paths + frontmatter inline (no bodies); body-reads only for `pending-*` docs that the state-promoter is actively about to promote.

**MiYo Constitution L2 (Should)**:
- **Architecture L2** — Cross-component contract change (`tomo:` block consumed by Hashi). Requires Kokoro ADR drafted as F-47.P1 deliverable.
- **Code Quality L2** — State-machine logic extracted to `scripts/lib/tomo_lifecycle.py`, not duplicated across producer/consumer scripts.
- **Testing L1** — Every state transition has happy-path + rejection test. F-43 T6.2 discovery-gap regression test required.

**Cross-repo dependencies**:
- **Kado 0.10.0** (shipped 2026-05-20) — `kado-write operation=frontmatter` (`mode=merge|replace`). `_inbox/from-kado/2026-05-20_kado-to-tomo_kado-write-frontmatter-shipped.md`.
- **Kado 0.11.0** (live in vault 2026-05-21) — adds `filter.modifiedAfter/Before`, `filter.createdAfter/Before` on `kado-search`, and the op-symmetry hint in tool descriptions (nudges LLM clients to use `operation=frontmatter` on both sides for metadata-only flips). `_inbox/from-kado/2026-05-21_kado-to-tomo_frontmatter-write-shipped-plus-bonus.md`.
- **Pre-existing Kado capabilities** that F-47 relies on (no new handoff needed): `kado-search operation=byFrontmatter` (search BY frontmatter values), `filter.path` for server-side path narrowing.
- **Hashi auto-cleanup-on-applied** — Early-warning handoff sent (`_outbox/for-hashi/2026-05-20_tomo-to-hashi_auto-cleanup-on-instructions-applied.md`). Schema-lock follow-up will pivot the contract to **state-driven, doc-type-agnostic** cleanup (Feature 4 refactor — Hashi iterates `tomo.source_*` keys generically). Blocks F-47.P4 ship (Feature 5) but not F-47.P1–P3.

### Assumptions

- **Solo-developer Tomo today** — locked OQ4 (no backward-compat). If a second user appears mid-implementation, F-47 ships anyway and they migrate by resetting their inbox.
- **Privat-Test vault reset is acceptable** — locked OQ5. Marcus confirmed willing to wipe the test vault as part of F-47 rollout.
- **Kado 0.10.0+ `kado-write operation=frontmatter` `mode=merge` semantics hold** — `tags` array replaces (not appends); body byte-identical; closing-fence newline normalised. Verified in shipped notice; F-47.P1 includes a smoke test against a fixture.
- **Kado 0.11.0 `byFrontmatter` query semantics hold** — query strings like `tomo.state=pending-*` evaluate correctly against nested frontmatter keys; `filter.path` server-side prefix narrowing returns only inbox-scoped hits.
- **Hashi will accept the cleanup contract** — handoff is conservative (proposes the design, asks for ack before Tomo locks the schema). If Hashi declines, F-47.P4 falls back to manual cleanup (still ships value via P1–P3).
- **F-44/F-45/F-46 will inherit this lifecycle model** — locked in spec README. Their PRDs will reuse the doc-type / state machinery.

---

## 9. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **State-promoter introduces invalid transition due to body-read race** (Hashi flips tag mid-`/inbox`) | Medium | Low | Optimistic concurrency via `expectedModified` (Kado 0.10.0+ supports on `kado-write operation=frontmatter`); retry once on conflict; surface error if persistent |
| **Hashi handoff rejected or delayed** — auto-cleanup not implemented | Medium | Low | F-47.P1–P3 still ship value (token reduction + F-43 unblock); manual cleanup is the current state anyway. F-47.P4 ships without Hashi cleanup; auto-cleanup is a follow-up |
| **`feedback_no_nested_git_in_bind_mounts` regression** — `tomo-tmp/` lifecycle docs accidentally written to vault root | Low | Low | Existing `tomo-tmp/` discipline; reducer always writes to `tomo-tmp/`, transport via agent kado-write (T6.5.5 pattern) |
| **OQ4 (no backward-compat) burns an existing user** — someone has been silently using Tomo in production we don't know about | High | Very Low | Inbox-state migration is "delete the 3 backlog files manually before first F-47-enabled `/inbox` run"; documented in evolution log entry |
| **Schema drift between Tomo `tomo:` block and Hashi reader** | Medium | Medium | `tomo/schemas/doc-frontmatter.schema.json` is SSoT; Hashi handoff references it; Tomo runtime validates in dev mode |
| **Discovery pollution** — user manually applies `tomo.state=...` to docs outside inbox | Very Low | Very Low | Eliminated by `filter.path` server-side narrowing (Kado, since Feb 2026 — AC-2.4). Discovery sees only inbox-scoped hits. |
| **State-promoter body-read budget grows** — user accumulates 20+ pending-approval docs | Low | Medium | Body-read budget is proportional to pending-* count; if it grows, suggests user is not approving anything (no real work to do). Surface a "you have N pending docs awaiting approval" hint in `/inbox` Phase A5 |
| **F-43 T6.2 still fails after F-47.P4** — the live-validation rerun finds a new gap | Medium | Low | F-47.P4 explicitly closes the discovery + dispatch gap (AC-5.1–5.3). Anything else is a new finding, surfaced + spec'd separately |

---

## 10. Open Questions

### OQ6 — MCP / Tool-Call Layer Discovery Optimizations

**Status: RESOLVED (2026-05-21) — all three candidates either shipped or deferred to follow-on spec.**

Reassessment after Kado 0.10.0/0.11.0 dropped:

- **Candidate A (server-side path-prefix filter)** — RESOLVED. `kado-search filter.path` has been live since Phase 4 (Feb 2026, predates F-47). F-47 uses it directly (AC-2.4). No Kado handoff needed.
- **Candidate B (batched `read_frontmatter`)** — DROPPED. With the discovery layer switched to `byFrontmatter` (which returns frontmatter inline for all hits in one call), per-doc `read_frontmatter` is no longer the dominant pattern. State-promoter still reads frontmatter for the small subset of docs it is actively promoting, but N is typically 1–3 — overhead is not meaningful for the steady-state token budget. User decision: defer, take the overhead.
- **Candidate C (combined paths + tags + frontmatter op)** — SHIPPED IN A DIFFERENT FORM. `kado-search operation=byFrontmatter` already returns `[{ path, modified, frontmatter }]` per hit (Kado 0.11.0). The combined-op pattern Candidate C imagined is now the primary discovery call. F-47 adopts it directly (AC-2.1).

**Token-cost reality after these resolutions:** the §7 baseline estimates were computed against the old byTag + per-doc read_frontmatter chain. With the byFrontmatter-first design, steady-state Phase A is **2 Kado calls** (byFrontmatter + listDir, both metadata-only) regardless of inbox accumulation. SDD will measure actual token cost during P2 dogfooding; if targets are met, no further Kado handoff is needed for F-47.

Cost preference (user constraint, recorded for SDD): F-47 must keep `/inbox` runnable on **Claude Pro subscription tier (Sonnet, 200K context)** — not require Opus or Sonnet 1M. Token budget is the binding constraint, not raw latency.

### Forward-Looking Optimisation: Incremental Discovery Cache (Deferred to Separate Spec)

Kado 0.11.0's `filter.modifiedAfter` (and `createdAfter`) unlocks a **last-run timestamp cache** that would let `/moc-propose`, F-44 garden-audit, F-45 weekly-review, F-46 tag-audit narrow each subsequent run to "only notes modified since the last invocation." Sketch:

```
tomo-instance/state/discovery-cache.json
{
  "moc-propose": {
    "tag:topic/knowledge/lyt": { "last_run_ms": ..., "run_id": "..." },
    ...
  }
}
```

Default = incremental (banner "Looking at notes modified since YYYY-MM-DD"); `--full-vault` flag forces full scan; SoT principle preserved because cache is a hint, not truth (worst case = unnecessary full scan).

**Status:** Out of scope for F-47. Tracked in `docs/XDD/backlog.md`. Will likely land as a precursor to F-45 (which is inherently time-windowed) or as its own spec earlier if `/moc-propose` repeat-run cost becomes painful on Privat-Test.

### OQ14 — Flow Diagrams Requirement

**Status:** Resolved by §6 of this PRD. Four flows covered: best-case `/inbox` (§6.1), `/moc-propose` (§6.2), mixed-state run (§6.3), drift recovery (§6.4). Open for **user review** of the diagrams' accuracy and completeness before locking.

### OQ11 / OQ12 / OQ13 (Tracked as Resolved-During-Planning)

Moved to spec README Decisions Log; included here only for cross-reference:

- **OQ11 (suggestions state-machine simplification)** — 2-state (pending-approval → approved).
- **OQ12 (moc-proposal state-machine simplification)** — 2-state (pending-accept → accepted).
- **OQ13 (cleanup pattern)** — Hashi auto-cleanup on instructions-applied + manual delete for orphans.

### Items Requiring User Input Before SDD

- [x] **OQ6** — RESOLVED above (2026-05-21).
- [x] **Non-linear scenarios** — RESOLVED. §3 N1–N4 + §6.3/6.4 lock the behaviour.
- [x] **Hashi cleanup contract** — RESOLVED. State-driven, doc-type-agnostic per Feature 4 rewrite.
- [ ] **Schema review** — `tomo/schemas/doc-frontmatter.schema.json` field names need user sign-off before the Hashi schema-lock notice goes out. Specifically: confirm `source_*` key naming convention (e.g. `source_suggestions` vs `source_suggestions_path`); confirm `state` is the canonical state field name; whether `updated_at` is mandatory or optional. (Note: v1.2 dropped the lifecycle tag, so no tag-prefix decision is needed.)
- [ ] **Kokoro ADR sign-off** — Architecture L2 requires Kokoro reflection. Tomo will draft the ADR content; Marcus (or Kokoro session) commits it during F-47.P1.

---

## 11. Supporting Research

### Research Phase Findings (2026-05-20, updated 2026-05-21)

Four parallel research agents ran during the F-47 brainstorm (per `tcs-workflow:xdd` standard mode). Findings consolidated into the locked decisions above; full reports archived in session transcript. Highlights:

- **Capability discovery (2026-05-21 PRD iteration)** — Kado 0.11.0 (live in vault) ships strictly more than F-47's discovery layer needs: `kado-search operation=byFrontmatter` (queries BY frontmatter values, returns paths + frontmatter inline in one call) plus `filter.path` (server-side path narrowing, existed since Feb 2026) plus `filter.modifiedAfter/Before` (new in 0.11.0, enables future incremental-discovery cache — see §10 forward-looking section). The original PRD draft assumed byTag + chained per-doc `read_frontmatter`; this rewrite adopts the byFrontmatter-first pattern that Kado explicitly recommends in `_inbox/from-kado/2026-05-21_...`. Token-cost ceiling drops further than the §7 baseline estimates predicted.
- **Technical (Explore agent)**: Confirmed Kado has `read_frontmatter()` at `kado_client.py:135`; `write_frontmatter` shipped 2026-05-20 in Kado 0.10.0. Confirmed `instruction-render.py:388/416` calls `resolve_stem_to_path()` and `path_exists()` — these methods are missing from `kado_client.py` (separate latent bug, not F-47 scope, surfaced for follow-up).
- **Performance (general-purpose agent)**: Quantified token cost — Scenario A (steady) ~4,850 today → ~1,830 proposed (−62%); Scenario B (heavy) ~12,000 → ~5,590 (−53%). Dominant savings come from skipping done-state body-reads. v1.2 (frontmatter-only) drops a few additional tokens per write/read by not carrying a mirrored tag array. Edge case: first-run with zero `tomo:` blocks present needs listDir fallback (handled by hybrid discovery in §5).
- **Integration (general-purpose agent)**: Confirmed Kado byTag glob is suffix-only with `*` (historical relevance — F-47 v1.1 switched to byFrontmatter; v1.2 dropped the lifecycle tag entirely). Confirmed Tomo's existing `#<tag_prefix>/captured` model — F-47 v1.2 supersedes it with `tomo.state=captured`. Confirmed Hashi has no `update_frontmatter` action today (won't have, per locked Won't Have list).
- **Constitution (general-purpose agent)**: Identified hard requirements — Kokoro ADR (Architecture L2 blocker for cross-component contract); state-machine extraction to dedicated module (Code Quality L2); state-transition tests including rejection paths (Testing L1).

### Reference Materials

- **F-43 T6.2 live-validation findings** — `docs/XDD/specs/013-moc-creation-skill/plan/phase-6.md` T6.2 pause note
- **Kado 0.10.0 release** (write_frontmatter shipped) — `_inbox/from-kado/2026-05-20_kado-to-tomo_kado-write-frontmatter-shipped.md`
- **Kado 0.11.0 release** (op-symmetry hint + time-range filters) — `_inbox/from-kado/2026-05-21_kado-to-tomo_frontmatter-write-shipped-plus-bonus.md`
- **Hashi cleanup early-warning** — `_outbox/for-hashi/2026-05-20_tomo-to-hashi_auto-cleanup-on-instructions-applied.md`
- **Tomo decisions memory** — `docs/ai/memory/decisions.md` 2026-05-20 entry (vault-write pattern)
- **MiYo Constitution** — `~/Kouzou/projects/miyo/miyo-constitution.md` (L1/L2/L3 reference)
- **Locked decisions ledger** — `docs/XDD/specs/017-tomo-lifecycle-tags/README.md` Decisions Log

### Competitive Analysis

N/A — this is an internal pipeline refactor, not a user-facing product. Architectural alternatives considered:

- **Pure filename-based state (status quo)** — rejected: filename pattern bug for `tomo-moc-proposal-*` already proven; doesn't scale to F-44/F-45/F-46.
- **Sidecar state file (`state/tomo-lifecycle.json`)** — considered as OQ6 candidate. Cheaper queries (no Kado round-trip) but introduces a second SSoT alongside the file's own frontmatter; if they desync, the file is harder to debug. Frontmatter-as-SSoT is the locked choice.
- **Database / SQLite** — rejected: violates Constitution L1 local-first / Obsidian-native discipline; users editing files in Obsidian should be authoritative.

### Market Data

N/A — internal refactor. Architectural alternative considered + rejected in v1.2: mirrored lifecycle tag (`#<prefix>/<doc-type>/<state>`) alongside `tomo.state`. Rationale for rejecting: user does not browse Tomo workflow docs via Obsidian's tag pane and hides frontmatter in the editor, so the tag added no UX value while costing per-transition write payload + drift-handling edge cases. Decision is reversible (re-introducing a tag is a thin renderer change) if a future user finds tag-pane browsing valuable.
