# Obsidian-Power Roadmap

> Created: 2026-05-06.
> Track for adding deeper Obsidian-native workflows on top of Tomo + Tomo-Hashi MVP.
> Lives next to `backlog.md`; per-item detail goes into `backlog.md` F-IDs and (when picked up) into XDD specs under `specs/`.

## Context

Tomo + Hashi MVP work end-to-end: inbox capture → Pass 1 suggestions → user review → Pass 2 instructions → Hashi apply. The MOC-trigger logic (F-34/F-35) is pending but additive. This roadmap captures the **next layer** of features that turn Tomo from "inbox processor" into "comprehensive Obsidian assistant" — proactive workflows that operate on the existing vault, not just incoming items.

External skill sources evaluated 2026-05-06:
- `obsidian-bases`, `obsidian-markdown`, `json-canvas` (aitmpl.com) — absorb as **reference skills** (lazy-loaded, not user-invocable). Bases is in active use in Marcus's vault.
- `obsidian-ops-team` (davila7/claude-code-templates) — **not importable** (hardcoded VAULT01 paths, bypasses Kado MCP, conflicts with 2-pass model). Used as decomposition sanity-check only.

## Sequencing principle

Each item depends on the prior; later items reuse earlier infrastructure. **Do not parallelise** — Tomo is in stabilisation mode (`feedback_near_mvp_no_breakage.md`); one workflow at a time, each with live-vault validation against `Privat-Test/` before merge.

## The five tracks

### 1. MOC-creation skill — **next up**

**Goal.** Proactive MOC proposal/creation outside the inbox flow. User can invoke `/moc-propose` to scan a topic-area and get MOC suggestions; user can invoke `/moc-create` to materialise an approved proposal with proper structure, bidirectional `up:`/`down:` links, and section organisation.

**Why first.** MOCs are the navigation backbone of the user's vault. Every later track (garden-audit, weekly-review, tag-audit) reasons about MOCs as first-class structures — building those first without a MOC-creation primitive makes them harder to validate.

**Backlog hook:** F-43 (new — to be added)
**Related:** F-34/F-35 (inbox-driven MOC triggers — complementary, not blocking)
**Reference-skill prerequisites:** `obsidian-markdown` (link/embed/callout syntax) imported as part of this track.

### 2. Knowledge-garden audit — **after MOC**

**Goal.** Periodic vault-health scan: orphaned notes (no incoming/outgoing links), dead wikilinks, broken `up:`/`down:`, duplicate stems, stale MOCs (no updates >N months). Output: a review document with prioritised fix actions, applied via the existing 2-pass model.

**Why after MOC.** Orphan/connection logic depends on knowing what a MOC is and how `up:`/`down:` should look. Builds on F-34/F-35 trigger logic by extending it from "this item" to "the whole vault".

**Backlog hook:** F-44 (new)
**Related:** F-13 (`/scan-mocs`), F-16 (relationship marker config), F-20 (orphan detection script — phase-4 stub).

### 3. Weekly/Monthly review — **after Garden-Audit**

**Goal.** Roll-up across the past N daily notes: what got done, what threads are open, which MOCs gained content, which tasks are stale. Output: a periodic-note (weekly / monthly) following the existing daily-note infrastructure.

**Why after Garden-Audit.** Review semantics rely on link integrity (Garden-Audit ensures it) and MOC structure (MOC-creation ensures it). Without both, the review surfaces noise.

**Backlog hook:** F-45 (new)
**Related:** F-02 (periodic notes beyond daily — explicit prereq).

### 4. Tag-audit skill — **after Weekly Review**

**Goal.** Vault-wide tag taxonomy normalisation against `vault-config.yaml::tags.prefixes`: detect inconsistencies (`langchain` vs `LangChain`), hierarchy violations (deeper than declared), unused declared tags, undeclared tags in heavy use. Propose normalisation actions via 2-pass model.

**Why after Weekly Review.** Lower urgency — current tag config is already deterministic and inbox-analyst respects it. Audit is for retroactive cleanup of pre-Tomo content.

**Backlog hook:** F-46 (new)
**Related:** Decision in `backlog.md::Deliberate Design Decisions` re: no profile baseline for tag taxonomy (still holds — config IS the source of truth, audit just enforces it).

### 5. Suggestions doc UX pass — **F-42, after items 1–4**

**Goal.** Rework the suggestions document (rendered by `suggestions-reducer.py`) for scannability after we have real-volume experience with the new workflows.

**Why last.** The suggestions doc shape needs to absorb proposals from MOC, Garden, Review, and Tag-audit flows — polishing it before those flows exist would target the wrong feature set.

**Backlog hook:** F-42 (already in `backlog.md`).

## Reference-skill absorption (background work)

| Skill | When to absorb | Used by |
|-------|----------------|---------|
| `obsidian-markdown` | During MOC-creation track (item 1) | MOC-creation, Weekly Review |
| `json-canvas` | During Garden-Audit (item 2), optional | Future canvas-based MOC variant |
| `obsidian-bases` | When a feature actually generates a Base | Future "propose Base from tag-cluster" idea |

All three live as `tomo/skills/<name>/` (lazy-loaded, `user-invocable: false`). Not their own roadmap items — pulled in when their consumer track needs them.

## Out of scope for this roadmap

- **Voice / transcription** (already shipped — XDD 009).
- **Task management / project tracking** as separate Tomo workflows. Tomo-Hashi handles execution of decided plans; task surfacing is implicit in Weekly Review (item 3). Revisit if Weekly Review proves insufficient.
- **Reading-processing** (Readwise/Kindle import). Belongs in inbox-processing extension, not in Obsidian-power track.
- **Web-clipping templates** (`obsidian-clipper-template-creator`). Workflow-specific; defer until user signals demand.
- **Vault optimization** (file size, attachment compression — `obsidian-ops-team::vault-optimizer`). Niche, post-MVP.

## Update protocol

- Each item gets its own XDD spec (`docs/XDD/specs/0NN-<slug>/`) when picked up — PRD → SDD → plan/phase-N.md.
- Status updates flow into the corresponding F-ID in `backlog.md` (✅ Done / In Progress / blocked-on-X).
- This roadmap doc is **the order**, not the spec. Don't expand items here — link to backlog/specs.
