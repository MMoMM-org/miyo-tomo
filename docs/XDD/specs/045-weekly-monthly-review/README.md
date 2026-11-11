# Specification: 045-weekly-monthly-review

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-11-08 |
| **Current Phase** | SDD |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Model tier** | {{MODEL_TIER}} |
| **Last Updated** | 2026-11-11 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | v1.1: 8 features, 57 criteria; approved by the owner 2026-11-11 |
| solution.md | pending | |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

**Model tier**: `routine` | `hard` | `frontier`. The classifier recommends it at the decomposition step and the user confirms it; leave the placeholder until then. `spec.py --read` treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-08 | Spec scaffolded for #31 (F-45) on branch docs/31-weekly-monthly-review | Owner chose #31 as the next P1 item after #182 was closed |
| 2026-11-08 | Start with PRD; research in Agent Team mode (4 researchers: domain, technical, integration, UX/cost) | Owner choice |
| 2026-11-08 | The needed part of F-02 is in this spec: weekly/monthly config, ISO name format, template mapping, date→path resolver, instance config | Owner choice (recommended); quarterly/yearly stay out |
| 2026-11-08 | Periods: the last finished ISO week / calendar month by default, earlier periods on request; no running period | Owner choice (recommended); lets the live walk use March 2026 without writing dailies |
| 2026-11-08 | Output: a section in the existing weekly/monthly note, else a new note from the user's template; delivered through a suggestions doc the user accepts and edits (2-pass, like /inbox), never a black box | Owner: "eine Blackbox wo der Nutzer keine Möglichkeiten hat die Dinge zu ändern … halte ich für falsch" |
| 2026-11-08 | Sources: the whole daily note (trackers/sport, Dayplanner, vault review, 5 Year Journal, Obsidian ToDos, Daily Log, the user's own review text), MOC activity, notes new in the period | Owner choice; must work without Dataview/Quoth for other users while supporting the owner's setup fully |
| 2026-11-08 | Review language = the vault locale | Default; the owner's dailies carry `locale: de` |
| 2026-11-08 | v1 review doc is markdown edited in Obsidian (moc-proposal precedent), parsed by Tomo; no Hashi editor tab, no Hashi handoff | Owner choice (recommended); a Hashi editor view is a later spec |
| 2026-11-08 | Pass 2 is triggered by /review itself, not /inbox | Owner choice (recommended); keeps every eval-gated file untouched |
| 2026-11-11 | Monthly review reads the dailies AND the weekly notes of its weeks; marks what only the weeklies hold and what they left out | Owner: weekly reviews add links and themes in hindsight that no daily holds |
| 2026-11-11 | Rate limit: pace and retry until Kado accepts instead of stopping at a call budget; report retries and suggest raising Kado's limit, slow down further, name what still failed | Owner: a hard budget at 20 calls / 5 s would read almost nothing |
| 2026-11-11 | Arguments name the period by themselves (`W13`, `2026-W13`, `2026-03`, `@`-picked note); `week` word dropped, `month` kept for "last month" | Owner note; the instance's @-picker already offers vault notes via Kado |
| 2026-11-11 | First day of the week is a setup value; `/review setup` reopens the setup | Owner note: not every user starts the week on Monday |
| 2026-11-11 | Readable instructions next to the instruction set for users without Hashi | Owner note; same pattern as /inbox and /note |
| 2026-11-11 | Markdown review document is 80/20; edits it cannot carry safely go to the later Hashi editor spec | Owner note |
| 2026-11-11 | PRD v1.1 approved; phase PRD → SDD | Owner: "passt so" |

## Context

Issue #31 (part of #16, backlog F-45): a weekly / monthly review that rolls up the past N daily notes (completed work, open threads, MOCs that gained content, recurring themes) into a periodic note. The roadmap (`docs/XDD/roadmap-obsidian-power.md` §3) names F-02 (periodic-notes rendering; config present) as a hard prerequisite and orders it after the garden audit (#30, closed). Spec 044 (`/note`) already creates filled notes from vault templates. `tomo/profiles/miyo.yaml` enables weekly (`Calendar/302 Weekly/`) and monthly (`Calendar/303 Monthly/`); `tomo/config/vault-example.yaml` carries their name formats and templates.

---
*This file is managed by the xdd-meta skill.*
