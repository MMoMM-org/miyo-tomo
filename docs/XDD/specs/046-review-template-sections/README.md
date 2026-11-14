# Specification: 046-review-template-sections

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-11-13 |
| **Current Phase** | SDD |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Model tier** | {{MODEL_TIER}} |
| **Last Updated** | 2026-11-14 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | v1.1 (approved 2026-11-14): 7 features, 47 criteria (F1 material per section is the headline; F6 quarter); no open questions |
| solution.md | pending | |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

**Model tier**: `routine` | `hard` | `frontier`. The classifier recommends it at the decomposition step and the user confirms it; leave the placeholder until then. `spec.py --read` treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-13 | Spec 046 scaffolded for #263 + #256 (and the #267 edge cases to be weighed) on branch `docs/263-review-template-sections` | Owner chose to start the follow-up spec after spec 045 shipped (PR #257) and its follow-ups #258, #260, #261, #262 merged |
| 2026-11-13 | Owner decisions carried in: Tomo may write into the owner's own sections of the weekly/monthly note; placement only by headings as before/after/under anchors, never inline fields; review material stays editable; #256 deselects a whole section of the review document with one checkbox per section | Owner, 2026-11-13, after spec 045 (the review material is a memory aid the owner edits) |
| 2026-11-13 | Subagent model: no `fable`; sonnet by default, opus where design judgment is needed | Owner, 2026-11-13: fable was not better than opus on spec 045 |
| 2026-11-14 | Research done (Standard mode, 4 perspectives on sonnet): requirements (owner templates), technical (spec 045 code paths), integration (Hashi), UX | Findings: Hashi has no replace-between-markers action; `replace_section` would wipe owner text; `after` = directly under heading, `inside` = end of section; templates differ per variant, headings repeat across kinds |
| 2026-11-14 | Re-run inside owner sections: a new Hashi action (`replace_between_markers` or equivalent) via a handoff; Tomo's block sits between invisible `%%` markers | Owner; the clean re-run; first delivery works with today's `insert_under_marker` |
| 2026-11-14 | Placement within an owner section is chosen per section at setup (before / after / end of section) | Owner |
| 2026-11-14 | Today's "Tomo Review" section stays, for groups the owner did not map; not written when nothing is left for it | Owner (recommended) |
| 2026-11-14 | Section mapping tracker-style: per section a description (what belongs there) and optional keywords; the model proposes from them, the owner confirms; the model condenses the material per section | Owner: "like the trackers … with keywords or an explanation of what he wants in there; Tomo can distil it so it doesn't get too big" |
| 2026-11-14 | Content per section is driven by its description/keywords (the model gathers from the period's notes and cites source days); the fixed groups stay for the Tomo Review section and as hints | Owner (recommended) |
| 2026-11-14 | Size: a max number of items per section, set generously so enough information remains (today's amount is fine) | Owner: "the amount is ok … a number that leaves enough information" |
| 2026-11-14 | Forward-looking sections may be mapped; the model proposes suggestions from what the period shows, each citing its source day | Owner (recommended) |
| 2026-11-14 | The per-section checkbox (#256) unticked drops the whole section, including items the owner added there, with a one-line warning; ticked means keep | Owner (recommended) |
| 2026-11-14 | PRD v1.0 drafted (6 features, 38 criteria); owner confirmed the five coordinator defaults (#267 split, never-write list stays, non-target headings, new-note rule, missing-heading choice) and three added decisions (duplicate heading = same choice as missing; unticked on re-run keeps the earlier block; default cap 8 items per section) | Owner review, 2026-11-14 |
| 2026-11-14 | NOT accepted: "a re-run before the Hashi action exists delivers without the filled sections or aborts" (F5-AC2) — left OPEN in the PRD Open Questions | Owner did not accept it; to be decided after reading the PRD |
| 2026-11-14 | Focus: the core of 046 is gathering and processing the material each section of the user's template needs ("reminders" of what happened and what will need to happen, which the user turns into their own thoughts); placing it in the right section only saves the back-and-forth. Tomo reads what the target template requires and searches the notes for it. No spec 045 feature is removed; 046 adds and changes where the information goes | Owner notes in the PRD draft |
| 2026-11-14 | Quarterly reviews join spec 046 as a third period kind (`quarter`), with the same section mapping | Owner: "i also have quarterly reviews"; chosen over a separate spec 047 |
| 2026-11-14 | Name: the command stays `/review`; the purpose is described as a review helper; a skill rename (e.g. review-helper) is decided at the skill revisit #259 | Owner (recommended); a rename touches many tests and docs |
| 2026-11-14 | F5-AC2 decided: the Hashi action exists by assumption; a re-run always replaces only Tomo's block; no fallback and no safety refusal for an older Hashi. The PR merges only after Tomo and Hashi work together in the test vault; the Hashi handoff (incl. schema JSONs) goes out as soon as the SDD defines the action; Hashi builds it | Owner notes + answer ("without any safety refusal") |
| 2026-11-14 | PRD v1.1: owner notes worked in and removed; quarter confirmed with Pass 1 ≤ $5.00 / ≤ 20 min on Q1 2026; quarter marks one level up from the month (only-in-monthly, not-in-monthly; weekly notes read as sources); calendar quarters only; yearly stays Could Have for a later spec | Owner answers 2026-11-14; test vault has `t_quarter_privat.md` and quarterly notes from 2022-Q2 |
| 2026-11-14 | PRD v1.1 approved; phase PRD → SDD | Owner; validation checklist passed (two known deviations kept from 045: the amendments subsection, no business-impact KPI) |

## Context

`/review` (spec 045) today uses the weekly/monthly template only to place one Tomo-owned section ("Tomo Review", found again by a `%% tomo-review <period> %%` marker) and the daily template's headings to choose what Pass 1 reads. The groups are fixed (done, open, themes, growth, habits, month: only in the weekly reviews). Spec 046 lets setup map the template's own headings (e.g. `t_month_privat`: "Theme of the Month", "Goals and Wishes", "I look forward to", "This will be challenging") to review material, lets Pass 1 lay the review document out by those sections with a per-section checkbox to drop a whole section, and lets Pass 2 deliver into the owner's sections by heading anchors.

Open questions for the PRD: append vs replace when an owner section already holds text; how a re-run recognises its own earlier entries inside an owner section without a marker; templates that Templater runs on creation (spec 045 walk: `t_month_privat` moves itself and renders its own frontmatter); what becomes of the "Tomo Review" section; which of the #267 edge cases belong here.

Issues: #263, #256 (both under epic #16), #267 (edge cases), #259 (skill revisit after this spec). Spec 045: `docs/XDD/specs/045-weekly-monthly-review/`.

---
*This file is managed by the xdd-meta skill.*
