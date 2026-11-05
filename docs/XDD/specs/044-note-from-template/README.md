# Specification: 044-note-from-template

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-11-04 |
| **Current Phase** | Ready |
| **Decomposition tier** | Incremental |
| **Model tier** | hard |
| **Last Updated** | 2026-11-04 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | v1.0: 9 features, 52 criteria; approved by the owner 2026-11-04 |
| solution.md | completed | v1.0: 15 components, ADR-1 to ADR-8 confirmed, 52 EARS criteria (1:1 with the PRD); review findings worked in; approved by the owner 2026-11-04 |
| plan/ | completed | 4 phases, 22 tasks (T1.1 Kado read check is the gate); approved by the owner 2026-11-04 |

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
| 2026-11-04 | Plan approved, spec Ready for /implement 044 | Owner approval; the plan-alignment validation run was skipped by the owner |
| 2026-11-04 | Implementation started: Standard mode, commits stay on docs/169-note-from-template | Owner choice |
| 2026-11-04 | T1.1 passed on the owner's word: the owner's Kado key lists and reads `templates.base_path`; no live run | Owner decision |
| 2026-11-04 | keep_source freezes once instructions_json has landed (SDD `stage` rule extended) | Owner choice; a later flip would make a resume rebuild a different instruction set, with delete_source added or removed |
| 2026-11-04 | F2-AC4 extended: on an empty listing or an unreadable template, Tomo tells the user to grant the key read access to the template folder or not use `/note` | Owner requirement; another user's key may lack the right, and the old wording named the cause without a remedy |
| 2026-11-05 | Phase 1 drift check: Needs Attention (0 FAIL, 3 MEDIUM, 19 LOW); owner chose to fix the MEDIUMs and the correctness and privacy LOWs before Phase 2 | Owner choice |
| 2026-11-05 | A started delivery killed between steps is a kept draft, never a stale stage (SDD start output, Error Handling, glossary) | Drift M1; a stale stage is dropped silently, but part of that delivery is already in the vault |
| 2026-11-05 | ADR-5 amended: refuse only a duplicate key the edit introduces, name a pre-existing one; keep CRLF; atomic write. The shared CRLF-tolerant header check also applies to the older writer subcommands (no behaviour change, they read with universal newlines) | Drift M2 and the T1.4 review; a pre-existing duplicate elsewhere must not block saving note_include |
| 2026-11-05 | Phase 1 complete: drift fixes reviewed (43ae8e42, 104bedc8 + eaa5f646, 0883e6e5 + 9eb75ab1); full suite 6915 passed, 4 skipped; ruff clean | T1.5 gate |
| 2026-11-05 | {{source_link}} resolves at `stage` from keep_source: [[source]] when kept, empty text when the source will be deleted | Owner choice; a link to a source that apply deletes would dangle. Resolved at stage, not at outline, because keep_source can change in the dialogue |
| 2026-11-05 | NoteDraftMeta gains `profile`, fixed at `new` | T2.5 finding; `deliver` must rebuild identical files on resume, so the profile cannot be re-read from a config that may have changed |
| 2026-11-05 | note-session.py start: the --process stem is the rest of the text, config read with yaml.safe_load, listing one level deep | T2.3 deviations accepted by spec review; SDD algorithm updated to match |
| 2026-11-05 | Accepted as documented, not changed: fences at any indent, indented ATX headings and quoted frontmatter keys not recognised, `--stdout` previews only the key lines, atomic write only in templates-include | LOW drift findings; realistic templates are unaffected |

## Context

`/note`: the user hands Tomo rough material for a kind of note. Tomo picks a vault template, asks for what is missing, shows a draft and delivers the note with a Hashi instruction set. The brainstorm file is the handoff contract; GitHub issue #169.

---
*This file is managed by the xdd-meta skill.*
