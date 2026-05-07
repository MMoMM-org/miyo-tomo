---
title: "F-43 — Proactive MOC-Creation Skill (`/moc-propose`)"
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

- [x] Problem is validated by evidence (not assumptions)
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

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| specId | string | Yes | Spec identifier (NNN-name format) |
| title | string | Yes | Feature title |
| status | enum: `DRAFT`, `IN_REVIEW`, `COMPLETE` | Yes | Document readiness |
| sections | SectionStatus[] | Yes | Status of each PRD section |
| clarificationsRemaining | number | Yes | Count of `[NEEDS CLARIFICATION]` markers |
| acceptanceCriteria | number | Yes | Total testable acceptance criteria defined |
| openQuestions | string[] | No | Unresolved items requiring stakeholder input |

### SectionStatus

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Section name |
| status | enum: `COMPLETE`, `NEEDS_CLARIFICATION`, `IN_PROGRESS` | Yes | Current state |
| detail | string | No | What clarification is needed or what's in progress |

---

## Product Overview

### Vision
Give Tomo users a single command — `/moc-propose` — that turns "I know I have notes scattered across topic X" into a reviewable Map-of-Content (MOC) proposal in under a minute, without waiting for inbox accumulation to surface the cluster.

### Problem Statement
Today MOCs are only proposed reactively as a side-effect of inbox processing (Conditions A/B/C in `tier-3/lyt-moc/new-moc-proposal.md`). When a user already knows a topic area is under-organised — e.g. *"I have shell, zsh, tmux, iTerm notes scattered across `Atlas/202 Notes/2611 Code Snippets/` and elsewhere"* — there is no way to ask Tomo to act on that knowledge directly. The user must either:

1. Wait for enough inbox items in that topic to trigger the existing reactive flow (uncertain timing, may never trigger),
2. Manually create the MOC and link children (tedious, easy to miss children, no profile-aware Dewey/LYT rules applied), or
3. Skip the MOC entirely (compounding the under-organised state).

Concrete impact in Marcus's vault (3,916 atomic notes, 82 MOCs per `discovery-cache.yaml`): topic clusters of 5+ notes routinely sit without a dedicated MOC because no inbox trigger fires. Each unindexed cluster is a future search-failure or "wait, where did I write that?" moment.

### Value Proposition
- **Proactive** instead of reactive — user drives the scan, not the inbox.
- **Focused scopes** — `tag:`, `folder:`, `class:`, `title:`, free-text, or whole-vault — match the way users actually think about gaps.
- **Profile-aware** — same command produces Dewey-suffixed `(MOC)` titles for MiYo and plain titles for LYT, with parent resolution honoring each profile's classification rules.
- **2-pass safety preserved** — proposal lands in inbox folder for user review and edit before any vault mutation. No MVP execution-boundary violation.
- **Foundation for the rest of the Obsidian-power roadmap** — F-44 Garden-Audit, F-45 Weekly Review, F-46 Tag-Audit all reason about MOCs as first-class structures and depend on F-43 being available.

## User Personas

### Primary Persona: Marcus (MiYo / Dewey-classification user)
- **Demographics:** Vault owner, ~3.9K atomic notes + 82 MOCs, German-speaking, daily Obsidian + Tomo user, technical (own dev environment), uses MiYo profile with classification 2000-2900 (Dewey Applied Sciences, etc.).
- **Goals:** Keep PKM organised proactively, not reactively. Spot under-MOC'd topic areas and fix them in one review session, not through accumulated inbox toil.
- **Pain Points:** Scattered notes across atomic-note subdirectories, classification MOCs (e.g. `2600 - Applied Sciences`) too generic to be useful, manual MOC creation tedious + error-prone (forgets children, breaks `up::` links), waits for inbox to trigger reactive MOC proposal that may never come.

### Secondary Persona: LYT user (Thematic, no Dewey)
- **Demographics:** Vault owner using LYT profile (plain MOC titles, no `(MOC)` suffix, thematic organisation, no classification-MOC bucket).
- **Goals:** Build thematic MOCs as topics emerge in their work, refactor topic areas when they outgrow informal organisation.
- **Pain Points:** Without classification scaffolding, parent-resolution defaults to top-level — proposals risk feeling rootless. Needs the command to handle "no resolvable parent" gracefully.

## User Journey Maps

### Primary User Journey: Topic-area MOC creation (Marcus, MiYo)
1. **Awareness:** Marcus notices during daily work that 5+ notes about `zsh` + `tmux` + `iTerm` exist scattered across `Atlas/202 Notes/2611 Code Snippets/` and other folders, with no dedicated "Shell & Terminal" MOC.
2. **Consideration:** Decides this is a F-43 use case (the ask-now path, not wait-for-inbox).
3. **Adoption:** Runs `/moc-propose tag:topic/applied/zsh` (or `folder:Atlas/202 Notes/2611 Code Snippets/`).
4. **Usage:** Tomo writes `100 Inbox/tomo-moc-proposal-20260506-1430-zsh.md` with proposed title, location, parent, 5 children, "Why" narrative. Marcus reviews in Obsidian, optionally edits Title/Location/Template inline, ticks Accept on the cluster, ticks Children to keep, optionally toggles Override on `up::`-handling. Saves the file.
5. **Retention:** Runs `/inbox`. Pass 2 emits `create_moc` + `add_relationship` actions; Hashi creates the MOC in `Atlas/200 Maps/`, links children. The shell-cluster is now first-class. Marcus repeats whenever a new under-MOC'd topic surfaces.

### Secondary User Journey: Whole-vault density scan
1. **Awareness:** User wants to do a periodic check on under-organised areas across the entire vault.
2. **Consideration:** No specific topic in mind — wants Tomo to find clusters proactively.
3. **Adoption:** Runs `/moc-propose` with no args.
4. **Usage:** Tomo scans `concept_defaults.atomic_note.{base_path,subdirectories}`, returns up to 5 highest-confidence clusters as separate `### MOCxx —` sections in one proposal-doc. User accepts/rejects/edits each independently.
5. **Retention:** "Weitere N Cluster gefunden" footer signals more available next run; user re-runs after applying current batch.

### Secondary User Journey: Title-seeded creation (LYT)
1. **Awareness:** User has a topic name in mind (e.g. "Decision-Making") and wants to seed a MOC scan around it.
2. **Consideration:** Whether enough notes exist to justify a MOC.
3. **Adoption:** Runs `/moc-propose title:"Decision-Making"`.
4. **Usage:** Tomo uses the user's title verbatim, finds candidate children via topic-match against `discovery-cache.yaml`, proposes MOC with that exact title (no `(MOC)` suffix on LYT). User reviews + accepts.
5. **Retention:** User repeats for other emerging themes.

## Feature Requirements

### Must Have Features

#### Feature 1: Single command, multi-mode CLI surface
- **User Story:** As a Tomo user, I want a single `/moc-propose` command that accepts different input modes (tag, folder, class, title, free-text, no-args) so that I can match my mental model of "where the gap is" without learning multiple commands.
- **Acceptance Criteria (Gherkin Format):**
  - [ ] Given a vault with the MiYo profile, When the user runs `/moc-propose tag:topic/applied/zsh`, Then Tomo discovers candidates via tag-prefix match and produces a proposal-doc.
  - [ ] Given a vault, When the user runs `/moc-propose folder:Atlas/202 Notes/2611 Code Snippets/`, Then Tomo discovers candidates via recursive folder listing restricted to atomic-note paths.
  - [ ] Given the MiYo profile, When the user runs `/moc-propose class:2600`, Then Tomo discovers candidates in the `2600` classification subdirectory.
  - [ ] Given any profile, When the user runs `/moc-propose title:"Shell & Terminal"`, Then Tomo uses the user input as the MOC title verbatim and discovers candidates via topic-match.
  - [ ] Given any profile, When the user runs `/moc-propose shell und terminal` (no recognised prefix), Then Tomo treats the input as a free-text topic match.
  - [ ] Given any profile, When the user runs `/moc-propose` with no args, Then Tomo performs a whole-vault density scan limited to atomic-note paths.
  - [ ] Given a non-whitelisted prefix like `/moc-propose foo:bar`, Then Tomo treats `foo:bar` as free text (not as a recognised mode), to disambiguate against titles such as `Shell: A Survey`.

#### Feature 2: Profile-aware proposal generation
- **User Story:** As a MiYo user, I want proposals that follow my Dewey conventions (`<Title> (MOC)`, classification 2000-2900 parents); as an LYT user, I want plain titles and thematic parents — so I don't have to manually rewrite proposals to match my profile.
- **Acceptance Criteria:**
  - [ ] Given the MiYo profile, When a proposal is generated, Then the proposed title ends with ` (MOC)` and the location defaults to `Atlas/200 Maps/`.
  - [ ] Given the LYT profile, When a proposal is generated, Then the proposed title is plain (no `(MOC)` suffix) and the location defaults to the LYT MOC path from the profile.
  - [ ] Given the MiYo profile and a topic that matches a `classification.categories.keywords` entry, When parent resolution runs, Then the matching classification-MOC is offered as the top parent option.
  - [ ] Given any profile, When parent resolution finds no match, Then the proposal is emitted with `parent_moc: null` and the doc shows "Kein Parent — wird Top-Level MOC".
  - [ ] Given the `title:<X>` mode, When generating titles, Then the user input is used verbatim with no transformation other than profile-suffix application.

#### Feature 3: Reviewable proposal-doc in inbox
- **User Story:** As a user, I want the proposal in a normal inbox file I can read, edit, and partially accept in Obsidian — so I stay in control and the 2-pass model is preserved.
- **Acceptance Criteria:**
  - [ ] Given a successful run, Then Tomo writes one file at `<inbox_path>/tomo-moc-proposal-<YYYYMMDD>-<HHmm>-<topic-slug>.md` (multi-cluster runs use the top-confidence cluster's slug).
  - [ ] Given the proposal-doc, Then it includes frontmatter `type: tomo-proposal`, `proposal_kind: moc`, `created`, `trigger`, `status: pending`, `tomo_skip_inbox_analysis: true`.
  - [ ] Given a single-cluster proposal, Then the body has one `### MOCxx — <Title>` section with `- [ ] Accept` as the first list item, editable text fields (Title, Location, Template), `### Parent` (single-select via list-item checkboxes), `### Children (N)` (multi-select via list-item checkboxes), `### up::-Handling Override` (single sammel-toggle), and `### Why this proposal` narrative.
  - [ ] Given a multi-cluster proposal (`/scan-mocs` mode), Then the body has up to `max_results` (default 5) `### MOCxx —` sections in one doc, each independently acceptable, with overflow noted as "Weitere N Cluster gefunden — re-run später".
  - [ ] Given the user has not run `/explore-vault` (cache empty/missing), Then `/moc-propose` aborts before discovery with the message "MOC proposal requires vault cache. Please run `/explore-vault` first to populate `discovery-cache.yaml`." and writes no proposal-doc.
  - [ ] Given a discovery run that returns 0 candidates after pre-filter, Then `/moc-propose` exits early with the message "Keine Notes zum Topic gefunden" and writes no proposal-doc.

#### Feature 4: Bidirectional linking with `up::` preservation
- **User Story:** As a user, I want accepted children to get `up::` to the new MOC by default, but I want the option to keep their existing `up::` and have the new MOC become `related::` instead — so legacy classification links aren't lost when I add a more specific MOC.
- **Acceptance Criteria:**
  - [ ] Given Override unchecked and a child with no existing `up::`, When the proposal is applied, Then the child gets `up:: <new MOC>`.
  - [ ] Given Override unchecked and a child with an existing `up:: <X>` where `<X>` resolves to a real file, When the proposal is applied, Then the child gets `up:: <new MOC>` AND `related:: <X>` (existing `up::` preserved as `related::`).
  - [ ] Given Override unchecked and a child with an existing `up:: <X>` where `<X>` is broken (target file does not exist), When the proposal is applied, Then the child gets `up:: <new MOC>` only (no `related::`), and the proposal-doc shows the per-child note "(existing up:: broken — ignored)".
  - [ ] Given Override checked and a child with an existing `up:: <X>` where `<X>` resolves, When the proposal is applied, Then the child keeps `up:: <X>` AND gains `related:: <new MOC>`.
  - [ ] Given Override checked and a child with no existing `up::`, When the proposal is applied, Then the child gets `up:: <new MOC>` (Override only flips behaviour for children with valid existing `up::`).
  - [ ] Given any Override state, When the proposal is applied, Then per-child existing `up::` targets are individually preserved (group-level Override only flips the direction; it does not collapse all children to a single target).

#### Feature 5: Pre-filter and skip-flag integration with inbox-analyst
- **User Story:** As a user, I want the proposal-doc to coexist peacefully in my inbox alongside normal notes — so `/inbox` does not try to "analyse" the proposal-doc as if it were a captured note.
- **Acceptance Criteria:**
  - [ ] Given a proposal-doc with frontmatter `tomo_skip_inbox_analysis: true`, When `/inbox` runs, Then `inbox-analyst` skips the file at the post-Kado-read pre-filter (Step 2b) without producing analysis output.
  - [ ] Given a proposal-doc, When `/inbox` Pass 2 runs, Then `suggestion-parser.py` recognises the doc by filename pattern `tomo-moc-proposal-*` OR by frontmatter `type: tomo-proposal` and dispatches to the MOC-branch.
  - [ ] Given a proposal-doc with at least one cluster's top-level `[ ] Accept` ticked, When Pass 2 emits actions, Then exactly one `create_moc` action and N `add_relationship` actions per accepted child are emitted, with `parent_moc` from the user's selected parent option (or `null` for "kein parent").
  - [ ] Given a proposal-doc with no clusters' Accept ticked, When Pass 2 emits actions, Then no `create_moc` or `add_relationship` actions are emitted (silent skip — proposal eligible for squelch tracking).

#### Feature 6: Hashi pre-flight filename-collision guard
- **User Story:** As a user, I want a destination-filename collision (proposed Title.md already exists) to be caught before vault mutation — so a duplicate-named MOC does not silently overwrite or corrupt an existing file.
- **Acceptance Criteria:**
  - [ ] Given a `create_moc` action whose destination path resolves to an existing file in the vault, When Hashi processes the action, Then the action fails with `applied: false` and `error_msg` indicating filename collision.
  - [ ] Given a failed-collision `create_moc` action, Then dependent `add_relationship` and `link_to_moc` actions for that MOC also fail (no partial application).
  - [ ] Given a successful `create_moc` action, Then dependent actions for that MOC proceed normally.

> **Cross-repo dependency:** This feature requires a Hashi-side change request — current Hashi documentation does not specify a destination-exists guard for `create_moc`. PRD records the dependency; SDD will identify the Hashi handoff item.

### Should Have Features

#### Feature 7: Configurable thresholds and caps via `vault-config.yaml`
- **User Story:** As an advanced user, I want to tune `min_notes`, `confidence_threshold`, `max_results`, `candidate_cap`, `cache_miss_max_batches`, and `squelch_runs` per my vault size and reviewing cadence — so the defaults don't lock me out of large vaults or overly chatty multi-cluster runs.
- **Acceptance Criteria:**
  - [ ] Given `vault-config.yaml::tomo.moc_proposal` overrides, When `/moc-propose` runs, Then the user's values take precedence over defaults.
  - [ ] Given missing keys in `vault-config.yaml::tomo.moc_proposal`, When `/moc-propose` runs, Then defaults from §10 of the spec apply (`min_notes: 3`, `confidence_threshold: 0.15`, `max_results: 5`, `candidate_cap: 200`, `cache_miss_max_batches: 5`, `squelch_runs: 3`).

> Configurable thresholds via UX (wizard) remain parked under F-07/F-08 (Could). F-43 ships defaults + manual config-file editing.

#### Feature 8: Squelch on rejected proposals
- **User Story:** As a user, when I reject a proposed MOC by not ticking Accept and the proposal gets archived, I don't want the same MOC re-proposed on every subsequent `/moc-propose` run — so the system doesn't badger me about rejected ideas.
- **Acceptance Criteria:**
  - [ ] Given a proposal-doc that was archived without any cluster's Accept ticked, When the same topic-cluster would be proposed again within `squelch_runs` (default 3) subsequent runs, Then the proposal is suppressed and not included in the new doc.
  - [ ] Given `squelch_runs` runs have elapsed since rejection, When the same topic-cluster surfaces, Then the proposal is allowed again.

> SDD will define the archive-path convention and squelch-state representation. PRD requires the behaviour, defers the mechanism.

### Could Have Features

- Cache-update after on-demand topic extraction (newly extracted topics flow back into `discovery-cache.yaml`).
- Granular per-child up:: override (in addition to the group sammel-toggle).
- `/scan-mocs` and `/moc-create <title>` convenience aliases.
- LLM sub-cluster + H3 sub-sectioning in proposed MOCs.
- Bases-integration when MOC has uniform-frontmatter children (separate F-ID).
- Multi-mode CLI combo (`folder:X tag:Y` AND-filter).
- Cascade parent creation (parent itself a placeholder).
- Typed templates (`t_moc_project`, `t_moc_person`, etc.).
- Synthetic test vault with generated clusters.

### Won't Have (This Phase)

- New Kado MCP tools — F-43 uses only existing `kado-search byTag`, `kado-read listDir`, `kado-read note`, `kado-write` (via Hashi). The brainstorm's "no new MCP tool" claim holds via client-side `.md` filtering on `listDir` results.
- Schema changes to `tomo/schemas/instructions.schema.json` — `create_moc`, `add_relationship`, `link_to_moc` shapes are sufficient.
- Direct vault mutation by Tomo — all writes go through Hashi via the existing 2-pass pipeline.
- Mode-switch in `inbox-analyst` — `inbox-analyst` is hot path (see `feedback_near_mvp_no_breakage.md`); only an additive Step-2b pre-filter is allowed.
- A separate `/scan-mocs` command — folded into `/moc-propose` (no args).
- F-07 / F-08 (configurable thresholds via UX) — remain parked under existing backlog items.

## Detailed Feature Specifications

### Feature: Bidirectional linking with `up::` preservation (Feature 4)
**Description:** When a new MOC is created, accepted children must be linked into the MOC's structure. The default behaviour is "new MOC becomes the canonical `up::`" — but children may already have an `up::` to a more general classification MOC (e.g. `2600 - Applied Sciences (MOC)`), and the user may want to keep that link as a `related::` instead of losing it. This feature defines the four outcomes that follow from the cross-product of (Override flag) × (existing `up::` state).

**User Flow:**
1. User reviews proposal-doc in Obsidian.
2. User sees per-child checkboxes under `### Children (N)` — each child line shows its current `up::` target inline (or "(kein up:: bisher)").
3. User decides whether to flip the group-level `### up::-Handling Override` toggle.
4. User saves the doc, runs `/inbox`.
5. Pass-2 reconciliation: for each accepted child, the renderer queries Kado at render time to read the child's current note content and extract any existing `up::` line.
6. Renderer emits one `create_moc` action plus N `add_relationship` actions (one per accepted child) — markers (`up::` vs `related::`) chosen per the four-outcome rule.
7. Hashi applies all actions in dependency order.

**Business Rules:**
- **Rule 4.1 — Default, no existing up:::** Override unchecked, child has no existing `up::` → child gets `up:: <new MOC>`.
- **Rule 4.2 — Default, valid existing up:::** Override unchecked, child has existing `up:: <X>` where `<X>` is a real file → child gets `up:: <new MOC>` AND `related:: <X>`.
- **Rule 4.3 — Default, broken existing up:::** Override unchecked, child has existing `up:: <X>` where `<X>` does not resolve → child gets `up:: <new MOC>` only. Per-child note `(existing up:: broken — ignored)` rendered in proposal-doc for transparency.
- **Rule 4.4 — Override, no existing up:::** Override checked, child has no existing `up::` → child gets `up:: <new MOC>` (Override only flips behaviour for children with valid existing `up::`).
- **Rule 4.5 — Override, valid existing up:::** Override checked, child has existing `up:: <X>` where `<X>` is a real file → child keeps `up:: <X>` AND gains `related:: <new MOC>`.
- **Rule 4.6 — Per-child preservation:** Each child's existing `up::` target is preserved individually. The group-level Override only flips direction; it does not collapse all children to one target.
- **Rule 4.7 — Render-time resolution:** Existing-`up::` extraction happens at render time, not at proposal time — to keep `supporting_items` payload lightweight (flat string of stems) and let the renderer use the freshest vault state.

**Edge Cases:**
- **Child file deleted between proposal and apply** → `add_relationship` for that child fails with `applied: false`; `create_moc` and other children's actions still proceed.
- **Child has multiple existing `up::` lines (malformed)** → renderer uses the first; subsequent ones logged as warning to the run log (post-MVP: surface in proposal-doc).
- **Child is itself a MOC** → exclude from candidate pool at Phase 1 pre-filter (`concept_defaults.atomic_note.{base_path,subdirectories}` strict scope already excludes MOCs).
- **Override box ticked but no child has an existing `up::`** → Override is a no-op; all children get `up:: <new MOC>` (Rule 4.4 applies for every child).
- **User edits Title between proposal and apply, conflicting with another existing MOC** → Hashi pre-flight filename-collision guard (Feature 6) catches this; whole `create_moc` action fails before any child link is touched.

## Success Metrics

### Key Performance Indicators

- **Adoption:** Marcus runs `/moc-propose` ≥ 3 times in the first 2 weeks post-launch on his real vault. (Single-user MVP — no broad adoption metric.)
- **Engagement:** ≥ 60% of generated proposals (single-cluster runs) result in at least one cluster accepted (Accept ticked) within 7 days of generation.
- **Quality:**
  - Parent-resolution correctness: in ≥ 80% of MiYo runs where a classification keyword matches, the top-offered parent is the one Marcus would have picked manually.
  - Zero `create_moc` actions corrupting an existing MOC (Feature 6 guard always fires when needed).
  - Zero loss of legitimate existing `up::` links (Rule 4.2 / 4.5 always emit `related::` when applicable).
- **Business Impact:** Reduction in manual MOC creation time. Baseline: manual creation of a 5-child MOC ≈ 5 minutes (open template, copy children, set up::, add to parent). Target: end-to-end `/moc-propose` → review → `/inbox` ≤ 90 seconds for the same MOC.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| `moc_propose_invoked` | `mode` (tag/folder/class/title/free-text/no-args), `trigger_arg`, `run_id` | Adoption tracking, mode-mix understanding |
| `moc_propose_aborted` | `reason` (cache-empty/zero-candidates/cache-miss-cap/candidate-cap), `run_id` | Detect failure modes, drive backlog priorities |
| `moc_proposal_written` | `clusters_count`, `top_confidence`, `run_id`, `proposal_path` | Output quality, multi-cluster frequency |
| `moc_proposal_accepted` | `cluster_id`, `children_count`, `parent_chosen` (named/null), `override_flag`, `run_id` | Engagement KPI, Rule 4.x correctness inputs |
| `moc_proposal_rejected` | `cluster_id`, `topic`, `run_id` | Squelch input, proposal-quality signal |
| `create_moc_collision` | `destination_path`, `existing_file_modified`, `run_id` | Feature 6 fired correctly |
| `up_preservation_applied` | `child_stem`, `existing_up_target`, `outcome` (preserved/related/broken-ignored), `run_id` | Rule 4.x correctness |

> Tracking lands in the existing Tomo run-log JSON (per `feedback_lifecycle_filter_breakdown.md` "report breakdown, not aggregate") — no new telemetry destination, all events stay local.

---

## Constraints and Assumptions

### Constraints
- **Hot-path additivity:** All changes to `inbox-analyst`, `shared-ctx-builder`, `moc-tree-builder` must be additive only (per `feedback_near_mvp_no_breakage.md`).
- **MVP execution boundary:** Tomo writes only to inbox folder; Hashi applies all vault mutations.
- **Schema reuse:** No changes to `tomo/schemas/instructions.schema.json`; reuse `create_moc`, `add_relationship`, `link_to_moc`.
- **MCP-tool reuse:** Use only existing Kado tools; client-side `.md` filtering on `listDir` results.
- **Profile-pure:** All profile-specific values (title pattern, MOC location, classification map) live in `tomo/profiles/{miyo,lyt}.yaml`; no profile logic in scripts.
- **Cache prerequisite:** `discovery-cache.yaml` must exist (populated by `/explore-vault`); if missing, `/moc-propose` aborts with a clear message.
- **Constitution L1:** Performance — chunked Kado responses, no main-thread UI blocking, minimal payloads to AIs (Constitution §Performance L1 lines 194-217).
- **Single-user pre-launch QA:** Tests target Marcus's real vault + MiYo architecture; synthetic test-vault is parked (`feedback_test_scope_personal_vault.md`).

### Assumptions
- The user has run `/explore-vault` at least once before invoking `/moc-propose`. If not, abort message guides them.
- Vault size is on the order of 1K–10K notes (Marcus's vault is ≈4K). `candidate_cap=200` is a reasonable per-mode hard cap; over-caps produce abort messages, not silent truncation.
- Topic extraction via cache hits the majority of candidates; cache-miss LLM extraction is a fallback bounded by `cache_miss_max_batches`.
- Hashi will accept a destination-exists guard requirement for `create_moc` (cross-repo handoff to Hashi team via `_outbox/for-hashi/`).
- Suggestion-parser already handles multi-section proposal-docs via existing `RE_SECTION_HEADER`; only the MOC-specific dispatch + children-list-parser are new.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Hashi destination-collision guard not implemented before F-43 ships | High — could overwrite existing MOC silently | Medium | Cross-repo handoff to Hashi team in PLAN; hold F-43 launch until Hashi confirms. SDD documents the dependency explicitly. |
| Render-time Kado read-per-child slows down large MOCs (10+ children) | Medium — bad UX if `/inbox` Pass 2 takes >30s on a multi-MOC run | Medium | Measure on Marcus's vault during integration test. If problematic, re-evaluate Option A vs Option B (post-MVP optimisation: enrich payload). |
| `discovery-cache.yaml` is stale (notes added/edited since last `/explore-vault`) | Medium — Phase 6 duplicate-detection uses cached topics, can miss real overlaps | Medium-High | Documented stale-cache risk in §6 of brainstorm; user expected to re-run `/explore-vault` periodically. Post-MVP: cache-update on cache-miss extraction. |
| Squelch state representation grows unbounded over time | Low — long-running vault accumulates many rejected proposals | Low | SDD specifies bounded archive (e.g. last 100 rejections). PRD requires only the behaviour. |
| Multi-cluster proposal-doc renders very long (5 clusters × 5+ children = ~750-1000 lines) | Low — Obsidian handles fine, but user review may fatigue | Low | `max_results=5` cap + "Weitere N Cluster" footer encourages incremental processing. |
| Parser regex changes break existing `tomo-suggestions-*.md` flow | High — would break inbox processing | Low | All parser changes are additive (new dispatch branch); existing patterns untouched. Regression tests on existing inbox docs in CI. |
| Hot-path `inbox-analyst` change breaks existing flow | High | Low | Step-2b additive pre-filter only; no logic change in Steps 3-12. Existing inbox-analyst integration test suite runs on every commit. |
| User runs `/moc-propose` without ever running `/explore-vault` (cold cache) | Low — gracefully aborts | High (first-time users) | Clear abort message with remediation. Documented in user-facing release notes. |

## Open Questions

- [ ] Will Hashi team accept the destination-collision guard requirement, and on what timeline? (Cross-repo handoff in PLAN.)
- [ ] Should the proposal-doc `### Why this proposal` narrative be LLM-generated or template-rendered with structured fields (cluster size, topic-overlap, missing-MOC-rationale)? Defer to SDD.
- [ ] Squelch state — file-based archive scan vs sidecar registry. Defer to SDD.
- [ ] Localisation — proposal-doc currently mixes German user-facing strings (`Kein Parent`, `Keine Notes…`) with English system prose. Acceptable for Marcus's MVP; revisit if user base broadens.

---

## Supporting Research

### Competitive Analysis
- **Obsidian core:** No native proactive MOC tooling. Users build MOCs manually or via plugins (Breadcrumbs, Various Complements) that infer relationships but don't propose new MOCs.
- **Linking Your Thinking (LYT) framework:** Defines the MOC concept and manual workflows; no automation.
- **Bases (Obsidian core, recent):** Database-style views over frontmatter — complementary, not overlapping. Bases-integration parked under Won't Have for F-43.
- **MiYo Tomo's existing reactive flow:** Conditions A/B/C in `tier-3/lyt-moc/new-moc-proposal.md` already handle inbox-driven MOC proposals. F-43 adds the proactive complement; both share the underlying `topic_clusters` algorithm and `create_moc` schema.

### User Research
- Single-user MVP — Marcus is the primary research subject (`feedback_test_scope_personal_vault.md`).
- Vault baseline (from `tomo-instance/config/discovery-cache.yaml`): 3,916 atomic notes, 82 MOCs, ~30 classification buckets in active use.
- Pain-point evidence: backlog item F-43 (Must) was upgraded from F-13 (`/scan-mocs`, originally YAGNI) after multiple sessions where Marcus identified under-MOC'd topic clusters mid-task and had no command to act on them.
- Brainstorm session 2026-05-06 (`docs/XDD/ideas/2026-05-06-moc-creation-skill.md`) settled scope, CLI surface, and architecture; PRD formalises and resolves the 14 open questions surfaced there.

### Market Data
- N/A for single-user MVP. F-43 is a foundation for the Obsidian-power roadmap (F-44 Garden-Audit, F-45 Weekly Review, F-46 Tag-Audit) — the broader value materialises only after those land.
