---
title: "MOC-Propose Consolidation — vault-wide MOC discovery off the inbox hot path"
status: draft
version: "1.0"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (live-validation 2026-06-05 + 4 research agents)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No feature redundancy (check for duplicates)
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Output Schema

### PRD Status Report

| Field | Value |
|-------|-------|
| specId | 021-moc-propose-consolidation |
| title | MOC-Propose Consolidation |
| status | IN_REVIEW |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 26 |

---

## Product Overview

### Vision
Vault-wide MOC discovery — "which notes have no map, and which maps don't exist yet" — happens on a fast, cache-backed `/moc-propose` cold path, while `/inbox` stays a lean, item-local triage that still nudges the user to realise the MOC links they have already written.

### Problem Statement
F-34 (spec 015) tried to do vault-wide MOC accumulation **on the inbox hot path**: every per-item `inbox-analyst` subagent received a vault-wide `accumulation_index` inside `shared-ctx.json`. Live validation on the real vault (2026-06-05) proved this never worked and is structurally wrong:

- **Condition B never fired.** The 15 KB shared-ctx budget trimmed `accumulation_index` to **0** clusters on every run, because the envelope was 54.5 KB — dominated by `placeholder_mocs`.
- **`placeholder_mocs` was 397, of which 224 were false positives** — `moc-tree-builder.detect_placeholders` built its "known vault" set from **only the 89 discovered MOC paths**, never the real vault (Kado reports 5 393 notes, mostly daily). So every link to a real non-MOC note was wrongly flagged as a dead link.
- **The cost is paid N× over.** `shared-ctx.json` is `cat`'d into every one of the N per-item subagents (N=18 last run); the per-item subagents are 83 % of Pass-1 dollar cost. Carrying a vault-wide index there multiplies the waste.
- **It duplicates existing capability.** `/moc-propose` (`moc-discovery.py`, F-43) already does whole-vault density discovery + parent resolution + Jaccard-0.80 dedup + per-candidate `up::` validation on the cold path — the right home for this work.

Two further correctness defects surfaced during analysis:
- **`up` is recorded in two forms in this vault** — frontmatter `up:` (YAML list) AND inline `up::` — but `moc-discovery` Phase 6.5 (and `moc-tree-builder`, and `atomic-note-indexer`) only detect inline `up::`. Every frontmatter-`up:` note is falsely treated as an orphan.
- **MOC discovery is path-primary**, so real MOCs that live in the notes area (tagged `#type/others/moc` but outside the configured MOC folders) are missed. This is the cause of the 224 false placeholders — and, critically, the **same limitation silently degraded the inbox itself**: `inbox-analyst` Condition A scores new inbox items against `shared_ctx.mocs`, which derives from this same path-primary discovery, so new items were only ever matched against the ~89 MOC-folder maps and never against notes-area MOCs. This limitation **predates F-34** (it lives in `moc-tree-builder`'s discovery, not in the F-34 accumulation work); `/inbox` "worked" but always matched against an incomplete MOC set.

### Value Proposition
- **Correct, lean signals:** the inbox stops being starved/polluted; `/moc-propose` proposes against the real vault, not a 89-MOC shadow of it.
- **Faster `/moc-propose`:** a scoped, 1-day TTL cache removes the full live Kado pull on repeat same-day runs (≈ $1.85 topic-extraction tax avoided per repeat run).
- **Lower Pass-1 cost:** correcting `placeholder_mocs` (397 → ~171) removes ~20 KB from the envelope that was multiplied across N subagents — a direct win toward GH #40.
- **One mental model:** "a note/MOC with no `up` → link it to an existing MOC, or propose a new one" — applied consistently to notes and MOCs, on the cold path, with the inbox keeping only its item-local nudges (Conditions A + C).

## User Personas

### Primary Persona: The Vault Owner (Marcus)
- **Demographics:** Single power user of a large personal Obsidian/LYT vault (5 393 notes, mostly daily); technical; runs Tomo via the Docker/Kado workflow. Per `feedback_test_scope_personal_vault`, pre-launch QA targets exactly this real use case.
- **Goals:** Keep the knowledge graph navigable — every substantive note reachable from a Map of Content; surface emerging structure (clusters that deserve a new MOC) without manual auditing; keep `/inbox` cheap and fast.
- **Pain Points:** `/inbox` was expensive and produced MOC suggestions that never reflected the vault; `/moc-propose` re-pulled the whole vault each run; orphan detection mis-fired because half the vault declares `up` in frontmatter; template-vault example MOCs (`X/…`) polluted results.

### Secondary Personas
None for this phase — Tomo is single-owner; multi-user is out of scope.

## User Journey Maps

### Primary User Journey: "Map my unmapped notes"
1. **Awareness:** The user notices (or suspects) notes that aren't reachable from any MOC, or topics that have grown enough to deserve their own map.
2. **Consideration:** Rather than manually scanning folders, they run `/moc-propose` (whole-vault scan) or a scoped variant (`tag:`, `folder:`, `title:`).
3. **Adoption:** `/moc-propose` reads a fresh-enough MOC-structure cache (rebuilding inline if stale), then returns a proposal-doc.
4. **Usage:** For each orphan note/MOC the proposal-doc offers EITHER "link to existing MOC X" (top-3 candidates) OR "create new MOC Y" with a written reason. The user ticks choices; `/execute` (via Hashi) applies them.
5. **Retention:** Same-day re-runs are fast (cache hit); the inbox keeps nudging about not-yet-created MOCs the user has already linked to, so structure compounds.

### Secondary User Journeys
**"Inbox keeps offering my placeholder MOCs"** — While processing new inbox items, when an item's topic matches a placeholder MOC (a dead `[[wikilink]]` the user already wrote), `/inbox` offers to create that MOC and link the item. This stays fully in `/inbox` (Condition C), now fed by a corrected, lean placeholder list.

## Feature Requirements

### Must Have Features

#### Feature 1: Scoped, timed MOC-structure cache (tag-primary discovery)
- **User Story:** As the vault owner, I want `/moc-propose` to read MOC structure from a scoped cache that auto-rebuilds when stale, so runs are fast and reflect the real vault — including MOCs that live in the notes area.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a MOC-structure cache with `last_scan` within 24 h, When `/moc-propose` runs, Then MOC structure is read from the cache And no full live whole-vault MOC tree-build is performed.
  - [ ] Given `last_scan` older than 24 h, or the cache missing/corrupt, When `/moc-propose` runs, Then a deterministic script detects this And invokes the cache-builder inline before proposing (never proposes from stale/absent data silently).
  - [ ] Given a note tagged `#type/others/moc` located inside an in-scope path, When the cache is built, Then it appears as a MOC (`kind: moc`) And is not counted as a placeholder/orphan target.
  - [ ] Given the configured scope is `map_note + atomic_note` by default and is overridable in `vault-config`, When the cache is built, Then only in-scope paths are scanned And the scope is read from config (not hard-coded).
  - [ ] Given a note tagged `#type/others/moc` that lies inside an EXCLUDED path (daily/template), When the cache is built, Then it is NOT treated as a MOC (exclude wins over tag — protects against template-vault `X/…` noise).

#### Feature 2: Dual-form `up` detection
- **User Story:** As the vault owner, I want orphan detection to recognise BOTH frontmatter `up:` and inline `up::`, so notes that declare their parent in frontmatter are never falsely flagged as orphans.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a note with frontmatter `up:` holding a valid MOC link and no inline `up::`, When orphan detection runs, Then the note is classified as having a parent (not orphan).
  - [ ] Given a note with inline `up:: [[X]]` only, When orphan detection runs, Then it is classified as having a parent (current behaviour preserved).
  - [ ] Given a note whose `up`/`up::` target is not a known MOC, When detection runs, Then the state is `broken` (distinct from `absent`/`valid`).
  - [ ] Given a note with `up:` present-but-empty (`up:`, `up: []`, null) or inline `up::` with no `[[…]]`, When detection runs, Then it is treated as `absent` (orphan), not `valid`.

#### Feature 3: Orphan → link-or-create for notes AND MOCs
- **User Story:** As the vault owner, when `/moc-propose` finds a note or MOC with no parent, I want to be offered either a link to an existing MOC (top-3 candidates) or a new-MOC proposal with a written reason, so I don't create redundant MOCs and I understand each suggestion.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given an orphan note whose topics match one or more existing MOCs at/above the score threshold, When `/moc-propose` runs, Then the proposal-doc offers "link to existing MOC" with the top-3 candidates for the user to choose (not a new-MOC proposal).
  - [ ] Given an orphan note matching no existing MOC, When `/moc-propose` runs, Then it offers "create new MOC Y" And a human-readable reason is rendered into the proposal-doc (and emitted as an instruction to stamp into the note(s) at `/execute` time — `/moc-propose` does not write to notes itself).
  - [ ] Given a MOC that itself has no parent `up`, When `/moc-propose` runs, Then it receives the same link-to-existing-parent / create-new-parent treatment (case (a) applies to MOCs, not only atomic notes).

#### Feature 4: Retire Condition B from inbox; keep Conditions A + C with a corrected placeholder list
- **User Story:** As the vault owner, I want the inbox to stop carrying a vault-wide accumulation index, while still flagging items that need a MOC (Condition A) and matching items to placeholder MOCs I already wrote (Condition C).
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a `shared-ctx.json` without `accumulation_index`, When `/inbox` runs, Then no error occurs And Conditions A and C produce identical output to pre-021 on a fixed inbox fixture set.
  - [ ] Given an inbox item whose dominant topic matches a placeholder `target`, When `/inbox` runs, Then `needs_new_moc: true` and `proposed_moc_topic = <target>` (verbatim casing) — Condition C unchanged.
  - [ ] Given MOC bodies containing block-ref (`[[Note#^id]]`) and heading-anchor (`[[Note#Heading]]`) links to notes that exist in scope, When the placeholder list is built, Then those do not appear as placeholders (anchor-stripped, note-resolved, checked against the real in-scope vault set, deduped per note).
  - [ ] Given an item that matches both a placeholder and Condition A's inferred label, When `/inbox` runs, Then the placeholder name wins (precedence preserved even though the Condition B sub-block is removed).
  - [ ] Given the corrected placeholder list, When `shared-ctx` is built, Then `placeholder_mocs` is never trimmed by the budget enforcer And the byte budget accommodates it (see Should-Have).

#### Feature 5: Inbox MOC-matching against the complete MOC set
- **User Story:** As the vault owner, when a new inbox item is analysed, I want Condition A to score it against ALL real MOCs (MOC folder AND notes area, tagged `#type/others/moc`), not just the MOC-folder maps, so the inbox offers the correct existing-MOC links instead of falsely concluding "no MOC matches → propose a new one." This is a standalone fix that rides on Feature 1's tag-primary discovery but is verified independently.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a real MOC tagged `#type/others/moc` that lives OUTSIDE the MOC folder (in the notes area, within an in-scope path), When `/inbox` analyses an item whose topics match that MOC, Then the MOC appears in `shared_ctx.mocs` And is offered in `candidate_mocs[]` (it was invisible to Condition A under path-primary discovery).
  - [ ] Given a template-vault MOC under an excluded path (`X/…`) tagged `#type/others/moc`, When `shared_ctx.mocs` is built, Then it is NOT offered as a Condition A match (exclude wins — no template-vault noise leaks into inbox suggestions).
  - [ ] Given Feature 1's tag-primary cache, When `shared_ctx.mocs` is built, Then it derives from the single corrected `map_notes` source (no separate or path-only inbox MOC list).
  - [ ] Given an inbox item that genuinely has a matching notes-area MOC, When `/inbox` runs post-021, Then Condition A links to that existing MOC rather than firing `needs_new_moc` (no spurious new-MOC proposals for already-mapped topics).

### Should Have Features
- **Budget accommodation:** Raise the shared-ctx byte budget so the corrected, essential `placeholder_mocs` is never trimmed (Performance research: ~34–36 KB envelope after correction; placeholder is non-advisory Condition-C data). Keep `placeholder_mocs` out of the trim path entirely.
- **`up`-parsing SSoT:** Centralise frontmatter-`up:` + inline-`up::` parsing into a single shared library helper consumed by the cache-builder and `moc-discovery` Phase 6.5 (and retrofit `atomic-note-indexer`), killing the current three-way regex drift.

### Could Have Features
- **Per-item context shaping (deferred to issue #45 (epic #24)):** Pass each inbox subagent only the placeholder/MOC slices relevant to that item's topics, rather than the full envelope — the only lever that *reduces* per-subagent load instead of enlarging it. Named here so the budget raise isn't mistaken for the final answer.
- **Incremental cache rebuild** using `byFrontmatter` `filter.modifiedAfter` once the full-rebuild cost becomes a constraint.

### Won't Have (This Phase)
- Per-item context shaping implementation (Could-Have / issue #45 (epic #24)).
- New Kado capabilities (`childCount` on `listDir`, server-side `filter.path` on `byTag`, bulk inline-field projection) — every read needed by 021 already exists in `kado_client` v0.7.0; gaps are noted for the Kado team but not blocking.
- Any direct note mutation by `/moc-propose` — writes remain in the 2-pass `/execute` boundary.
- Multi-user / shared-vault behaviour.

## Detailed Feature Specifications

### Feature: Scoped, timed MOC-structure cache + orphan link-or-create
**Description:** `moc-tree-builder` is rebuilt into the builder of a scoped MOC-structure cache. Discovery is tag-primary (`#type/others/moc`), restricted to configurable in-scope paths and hard-excluding daily/template paths. For each in-scope MOC and note it records the `up` state (from frontmatter `up:` and inline `up::`), topics, tags, and stem/path. The cache carries a `last_scan` timestamp; a deterministic script (not the LLM) checks it and rebuilds inline when stale. `/moc-propose` (`moc-discovery`) reads this cache instead of pulling the whole vault live, and at its match step emits link-or-create suggestions.

**User Flow:**
1. User runs `/moc-propose` (whole-vault or scoped).
2. System (script) checks the cache `last_scan`; if stale/missing → rebuilds inline from Kado.
3. System computes clusters/candidates, validates each candidate's `up` (both forms), and for each orphan finds matching existing MOCs.
4. System writes a proposal-doc: per orphan, either top-3 "link to MOC" options or a "create new MOC" entry with a reason.
5. User ticks choices; `/execute` applies them (adds `up`, creates MOCs, stamps reasons).

**Business Rules:**
- Rule 1: A note/MOC is an orphan iff neither frontmatter `up:` nor inline `up::` yields a non-empty wikilink target.
- Rule 2: Discovery signal for "is a MOC" is the `#type/others/moc` tag; a tagged note in an excluded path is NOT a MOC (exclude wins).
- Rule 3: Scope (`scope_paths`, `exclude_paths`) is read from `vault-config`; default scope = `map_note + atomic_note`.
- Rule 4: Cache is stale when `now − last_scan > 24 h`; stale/missing/corrupt → inline rebuild before proposing.
- Rule 5: Orphan matching multiple MOCs → present the top-3 by score for the user to choose.
- Rule 6: `placeholder_mocs` is never trimmed by the shared-ctx budget enforcer.
- Rule 7: `/moc-propose` never writes to vault notes; it emits proposals only.

**Edge Cases:**
- Empty scope / zero `#type/others/moc` notes → cache builds with empty MOC set; `/moc-propose` surfaces the existing `cache-empty` message; no crash.
- Cache corrupt (invalid YAML / wrong shape) → treated as missing → inline rebuild.
- Tag present but note outside scope → not a MOC (Rule 2); exclusion matches on precise configured paths, not loose substring (guard the known trailing-space `Calendar/301 Daily/ ` config value).
- `up` points to a non-MOC note → state `broken`.
- Wikilink uses alias/title (`[[Stem|Alias]]`) → resolution honours both stem and title.
- Placeholder target that resolves to an existing in-scope note → excluded from the placeholder list (this is the 397→171 correction).
- `last_scan` in the future (clock skew) → treated as fresh.

## Success Metrics

### Key Performance Indicators
- **M1 — No live pull when fresh:** `/moc-propose` performs 0 whole-vault MOC tree-builds when the cache is within TTL (was 1 per run).
- **M2 — Placeholder false-positive drop:** placeholder count on the real vault drops **397 → ~171** (37 anchors + 224 false-positives removed).
- **M3 — Condition B removed, A/C zero-regression:** `accumulation_index` no longer read by `inbox-analyst`; A and C produce identical output to pre-021 on a fixed fixture set.
- **M4 — Tag-primary recovers notes-area MOCs:** the previously-missed `#type/others/moc` notes are recognised as MOCs and removed from the placeholder set.
- **M5 — Orphan coverage:** link-or-create emitted for orphan notes AND orphan MOCs; `up` detection covers frontmatter + inline.
- **M6 — Envelope reduction:** shared-ctx shrinks from 54.5 KB toward ~34–36 KB; net Pass-1 cost is a reduction.
- **M7 — Scope excludes daily/templates:** 0 daily/template files appear as candidates/orphans/placeholders.
- **M8 — Inbox sees the complete MOC set:** `shared_ctx.mocs` contains the notes-area MOCs previously invisible to Condition A; on a fixture where an item matches a notes-area MOC, the inbox links to it instead of proposing a new MOC. Template-vault (`X/…`) MOCs are absent.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| `moc-cache.build` | `built_at`, `mocs_count`, `notes_count`, `scope_paths`, `duration_ms`, `kado_calls` | Validate M1 (cache hits vs rebuilds), TTL behaviour, build cost |
| `moc-cache.read` | `last_scan`, `age_seconds`, `stale` (bool) | Confirm cache-hit vs inline-rebuild path taken |
| `placeholder.build` | `raw_count`, `kept_count`, `false_positive_dropped`, `anchor_dropped` | Validate M2/M4 (397→171) |
| `moc-propose.orphans` | `orphan_notes`, `orphan_mocs`, `link_suggestions`, `create_suggestions` | Validate M5 (link-or-create coverage) |
| `shared-ctx.build` (existing) | `bytes`, `placeholder_count`, `accumulation_present` (should be false), `mocs_count` | Validate M3/M6/M8 (Condition B gone, envelope, complete MOC set) |

## Constraints and Assumptions

### Constraints
- **Constitution L2 file size:** `moc-discovery.py` is already ~1 929 LOC (≈4× the 300–500 LOC guidance). New logic (cache loader, dual-`up`, case-(a)) MUST be extracted into `lib/` modules, not appended; the `moc-tree-builder` rebuild must split discovery/read/placeholder rather than reproduce one large file.
- **2-pass model:** `/moc-propose` proposes only; all note mutation happens at `/execute` (Hashi).
- **Container visibility:** runtime scripts see only the instance dir; cache + config live inside the instance.
- **Constitution L1 Testing:** every filesystem/permission path needs happy + denial coverage; orphan/permission logic must be testable without an LLM.
- **No regex YAML edits:** any eventual `up:` write routes through `kado_client.write_frontmatter(mode='merge')` — but 021 only reads frontmatter.

### Assumptions
- `#type/others/moc` is the reliable MOC signal in this vault (verified 5/5 real MOCs).
- The MOC structure changes slowly enough that a 1-day TTL is acceptable, with `/explore-vault` able to force a refresh.
- Every Kado read needed already exists in `kado_client` v0.7.0 (`search_by_tag`, `read_frontmatter`, `read_inline_fields`, `list_dir/list_notes`).
- Prompt caching bills 2nd–Nth identical analyst reads at cache-read rates, softening the cost of a larger byte budget.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Spec→schema→consumer drift silently no-ops new cache fields | High | Medium | Land the cache schema + writer BEFORE consumer reads; one loader shim projects `entries[kind==moc]`→`map_notes` so Phases 1–6 stay unchanged (`feedback_spec_schema_consumer_three_way_drift`) |
| Inline rebuild makes a `/moc-propose` run slow when cache is cold | Medium | Medium | TTL keeps same-day repeats warm; `/explore-vault` pre-warms; surface a one-line "rebuilding cache…" notice |
| Removing accumulation leaves vestigial scaffolding (atomic-note-indexer, budget Pass 6, cache lifts) | Medium | High | Treat retirement as explicit cleanup scope (`feedback_post_refactor_drop_scaffolding_not_patch`); default to delete, not patch |
| Growing `moc-discovery.py` past its already-4×-over size | Medium | High | Mandate `lib/` extraction in the SDD; reviewer gate on file size |
| Dual-`up` precedence ambiguity when both forms present | Low | Low | Define a single precedence rule in SDD (e.g. frontmatter `up:` wins) and test it |
| Budget raise re-admits bytes ×N subagents | Low | Medium | Placeholder is essential and was being silently dropped; prompt-caching softens cost; per-item shaping named as the real follow-up lever (issue #45 (epic #24)) |

## Open Questions
All blocking questions resolved with the user on 2026-06-05:
- [x] Scope = `map_note + atomic_note` default, configurable (OQ-1)
- [x] Stale cache → script-based inline auto-rebuild (OQ-2)
- [x] TTL = rolling 24 h from `last_scan` (OQ-3)
- [x] Multi-MOC match → top-3 to choose (OQ-4)
- [x] Tag-vs-scope collision → exclude wins (OQ-5)
- [x] Reason text → proposal-doc + emitted `/execute` instruction; not written by `/moc-propose` (OQ-6)
- [x] `placeholder_mocs` never trimmed; raise budget (OQ-7)

Deferred (non-blocking, for SDD/PLAN):
- [ ] Exact byte target for the raised budget (SDD's call from the corrected-envelope measurement)
- [ ] Whether `/explore-vault` and `/moc-propose` share one cache builder invocation or each trigger their own TTL check

---

## Supporting Research

### Competitive Analysis
N/A — internal single-user PKM tooling. Prior art is the existing `/moc-propose` (F-43, spec 013) and the LYT "MOC / placeholder" methodology already encoded in the `lyt-patterns` skill.

### User Research
Live validation on the real vault (2026-06-05): Condition B never fired; 397 placeholders of which 224 were false positives; `up` exists in frontmatter and inline forms (5/5 sampled MOCs); `#type/others/moc` reliable on real MOCs. Four research perspectives (Technical, Integration, Performance, Requirements) ran 2026-06-05 and converged on the decisions above; full findings in the session record and the 015 analysis doc (superseded).

### Market Data
N/A.
