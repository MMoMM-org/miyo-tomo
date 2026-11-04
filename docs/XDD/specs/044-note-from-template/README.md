# Specification: 044-note-from-template

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-11-04 |
| **Current Phase** | PLAN |
| **Decomposition tier** | Incremental |
| **Model tier** | hard |
| **Last Updated** | 2026-11-04 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | v1.0: 9 features, 52 criteria; approved by the owner 2026-11-04 |
| solution.md | completed | v1.0: 15 components, ADR-1 to ADR-8 confirmed, 52 EARS criteria (1:1 with the PRD); review findings worked in; approved by the owner 2026-11-04 |
| plan/ | in_progress | 4 phases, 22 tasks (T1.1 Kado read check is the gate); awaiting owner review |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

**Model tier**: `routine` | `hard` | `frontier`. The classifier recommends it at the decomposition step and the user confirms it; leave the placeholder until then. `spec.py --read` treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-04 | Spec created from the brainstorm `docs/XDD/ideas/2026-11-02-note-from-template.md` | Brainstorm design approved by the owner, spec reviewer approved (#169) |
| 2026-11-04 | Start with PRD, Standard research mode | Owner choice |
| 2026-11-04 | At most 2 question rounds before the draft; required points are still asked after that | Owner choice; without a cap the model can keep asking |
| 2026-11-04 | Skipped points are named in one console line above the draft; the note keeps the heading with an empty body | Owner choice; the owner sees no frontmatter, so the signal must be visible text |
| 2026-11-04 | A taken name offers rename or abort, never overwrite | Owner choice; stems carry seconds, so a collision is almost always different content |
| 2026-11-04 | An inbox-note source is deleted by default through a paired `delete_source`; the draft header says so and the user can keep the source in the dialogue | Owner choice; same default as Pass 2 |
| 2026-11-04 | Any non-empty answer satisfies a required point; questions follow the language of the call, the note keeps the template's headings | Decided by Claude, reported to the owner |
| 2026-11-04 | PRD approved, phase moves to SDD | Owner approval |
| 2026-11-04 | ADR-1 to ADR-8 confirmed: approach A; one delivery script; direct source merge; lib/template_syntax.py; writer subcommand templates-include; session start in note-session.py; stage dir per stem; one paid eval case, not gated | Owner confirmation; validate-json.py found to be parse-only, so wire validity is a jsonschema test |
| 2026-11-04 | SDD approved, phase moves to PLAN | Owner approval; the second review pass was not run |
| 2026-11-04 | Decomposition tier: Incremental | Classifier recommended Incremental (8 Must-Have features, 52 criteria, 11 new components). Accepted. |
| 2026-11-04 | Model tier: hard | Classifier recommended hard (adr_count=8; high_risks=3; novel_pattern=false). Accepted. |

## Context

`/note`: the user hands Tomo rough material for a kind of note. Tomo picks a vault template, asks for what is missing, shows a draft and delivers the note with a Hashi instruction set. The brainstorm file is the handoff contract; GitHub issue #169.

---
*This file is managed by the xdd-meta skill.*
