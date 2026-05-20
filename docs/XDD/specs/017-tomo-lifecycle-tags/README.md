# Specification: 017-tomo-lifecycle-tags

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-05-20 |
| **Current Phase** | PRD |
| **Last Updated** | 2026-05-20 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | pending | Brainstorm-style PRD with open-questions section (OQ list) — user wants discovery-flow optimization explicitly discussed in doc, not pre-baked |
| solution.md | pending | Awaits PRD completion |
| plan/ | pending | Migration phased P1–P5 per backlog F-47 entry |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-20 | Spec ID = 017 (not 014 as initially mooted) | spec.py auto-increments from max existing (016); the 014 gap in the numbering is left as-is |
| 2026-05-20 | Workflow mode = full XDD (PRD → SDD → PLAN) | User signed off 2026-05-20; refactor touches 8+ scripts/agents + introduces new schema → too broad for thin-plan |
| 2026-05-20 | Pre-locked: `suggestions/converted` is the post-Pass-2 state name on a suggestions doc | User sign-off 2026-05-20. Alternative considered was `archived` — rejected because the file is not archived, only superseded by an instructions doc; "converted" reads naturally in the discovery log |
| 2026-05-20 | Pre-locked: State-promoter implementation = Option C (implicit body-read on pending-* docs) for v1 | User sign-off 2026-05-20. Cheaper than Option A (script run before every /inbox) and Option B (Hashi-plugin watcher), at the cost of one body-read per pending-state doc per `/inbox` run — still ~5% of today's token cost |
| 2026-05-20 | F-43 T6.2 + T6.4 marked blocked-by this spec | F-43 acceptance-flow cannot be live-validated without unified file-discovery; see `docs/XDD/specs/013-moc-creation-skill/plan/phase-6.md` T6.2 pause note |

## Context

F-47 — Unified frontmatter + byTag discovery for all Tomo-produced docs. Replaces today's scattered detection model (filename-suffix in `state-init.py` SKIP_SUFFIXES + markdown-checkbox body-reads in `/inbox` Auto-Discovery + `#<tag_prefix>/captured` frontmatter tag on source items) with a single `#tomo/<doc-type>/<state>` hierarchical tag + `tomo:` frontmatter block on every Tomo-produced doc.

Surfaced from F-43 T6.2 live-validation findings (2026-05-20): `/inbox` Auto-Discovery does `listDir + 3× kado-read` of full file bodies to count `[x] Applied` / `[x] Approved` checkboxes; `tomo-moc-proposal-*` not in SKIP_SUFFIXES (filename uses prefix not suffix); state split across 3 mechanisms. F-43 acceptance-flow for proposal-docs has no discovery path — needs unified model first.

**State machines (locked direction, details to be confirmed in PRD)**:

- **source**: `pending` → `captured` (Pass 1 Phase C via `tag-captured.py`)
- **suggestions**: `pending-approval` → `approved` → `converted` (Pass 1 writes pending-approval; user ticks `[x] Approved` → state-promoter sets approved; Pass 2 verbraucht → sets converted)
- **moc-proposal**: `pending-accept` → `accepted` → `rejected` (`/moc-propose` writes pending-accept; user ticks cluster `[x] Accept` → state-promoter sets accepted; un-accepted clusters at Pass 2 time → rejected + squelch)
- **instructions**: `pending-apply` → `applied` (Pass 2 / MOC-consumption writes pending-apply; vault-executor flips to applied after all actions done)

**Open questions for PRD brainstorm**:

- OQ1: byTag-only discovery vs hybrid byTag + listDir (for untagged fresh source items that haven't yet been seen by Pass 1)
- OQ2: source-item tagging boundary — tag on arrival (needs a watcher/script in Obsidian inbox folder) vs tag at Pass 1 dispatch (current model, but means fresh items have no `#tomo/*` tag)
- OQ3: tag hierarchy syntax — nested `#tomo/<doc-type>/<state>` (e.g. `#tomo/suggestions/pending-approval`) vs flat `#tomo-<doc-type>-<state>`
- OQ4: backward-compat duration — 2 weeks, 4 weeks, until next major release? Affects when legacy suffix+checkbox path can be removed from state-init
- OQ5: filename rename strategy — rename existing `tomo-moc-proposal-*.md` in vaults via Hashi migration, or apply new naming only going forward (legacy filename detection by content-type frontmatter)
- OQ6: any further discovery-flow optimizations beyond byTag+read_frontmatter? (user-asked: "ich frage mich ob wir den discovery flow noch optimieren können")

**Migration phases (locked)**:

| Phase | Scope | Risk |
|---|---|---|
| F-47.P1 | Producer-side writes — all scripts emit `#tomo/<type>/<state>` tag + `tomo:` frontmatter block | low — additive |
| F-47.P2 | Consumer: state-init + Auto-Discovery on byTag refactor, with legacy fallback | mid — discovery logic |
| F-47.P3 | Filename rename (`tomo-moc-proposal-*` → `YYYY-MM-DD_HHMM_moc-proposal-<slug>.md`) + `-diff.md` → `_instructions-diff.md` | low — file naming |
| F-47.P4 | MOC-consumption flow (moc-proposal/accepted → instructions/pending-apply) — closes F-43 acceptance-gap | high — new workflow branch |
| F-47.P5 | Legacy-fallback removal (after 2-4 weeks of dual-path operation) | low |

**Hard blocker for**: F-43 T6.2 + T6.4 (proposal-doc acceptance live-validation). Inherited by F-44/F-45/F-46 — they'll use the unified model from day one.

**Touch points** (preliminary, to be confirmed in SDD): `state-init.py`, `inbox.md`, `inbox-orchestrator.md` Phase A, `suggestions-render.py`, `instruction-render.py`, `suggestions-reducer.py` (--moc-proposal-mode), `tag-captured.py`, `vault-executor`, `suggestion-parser._is_moc_proposal_doc`, new `tomo/schemas/doc-frontmatter.schema.json`.

---
*This file is managed by the xdd-meta skill.*
