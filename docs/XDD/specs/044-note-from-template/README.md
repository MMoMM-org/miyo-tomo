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
| 2026-11-05 | {{source_link}} is resolved into a new `note.md` beside `draft.md`, never inside `draft.md`; the skill prints `note.md`; `deliver` resolves `draft.md` the same way before its check and upload | T2.5 follow-up; a substitution inside draft.md could not be redone after a later keep_source change |
| 2026-11-05 | NoteDraftMeta gains `profile`, fixed at `new` | T2.5 finding; `deliver` must rebuild identical files on resume, so the profile cannot be re-read from a config that may have changed |
| 2026-11-05 | note-session.py start: the --process stem is the rest of the text, config read with yaml.safe_load, listing one level deep | T2.3 deviations accepted by spec review; SDD algorithm updated to match |
| 2026-11-05 | Model escalation: T2.5 opus → opus@max | Trigger: second review FAIL |
| 2026-11-05 | note-process.py `--required` is repeatable, one point per flag (SDD signature updated) | T2.4 spec review; a heading such as "Decisions, actions" could never be made required |
| 2026-11-05 | Accepted as documented, not changed: fences at any indent, indented ATX headings and quoted frontmatter keys not recognised, `--stdout` previews only the key lines, atomic write only in templates-include | LOW drift findings; realistic templates are unaffected |
| 2026-11-05 | /note path rules: titles and folders reject invisible format characters, line and paragraph separators, but allow the zero-width joiner and non-joiner (U+200D, U+200C) | Owner choice; joined emoji and Persian/Indic spelling must keep working |
| 2026-11-05 | One shared validator for /note folder and note paths, in a new `lib/note_paths.py`, used by note-instructions.py and note-process.py | T2.4 review: two folder normalisers had different rules, so a process destination could be saved that note-instructions later ignored |
| 2026-11-05 | Model escalation: T2.4 opus → opus@max | Trigger: second review FAIL |
| 2026-11-05 | note-instructions.py stays one file at ~550 lines after `deliver` (constitution L2 split rule not applied now) | About 500 lines without the docstring, every subcommand shares the meta, config and path helpers, and the plan has no task for a split; revisit if the script grows further |
| 2026-11-05 | A source deleted or moved before deliver marks it counts as nothing to mark: the step is done, `source_marked` is false and the stage is removed | T2.6 review; otherwise every resume failed and the draft stayed a kept draft forever although note and set were delivered |
| 2026-11-05 | Model escalation: T2.6 opus → opus@max | Trigger: second review FAIL |
| 2026-11-05 | Phase 2 gate: full suite 7527 passed, 5 skipped; ruff clean; 11 mutation proofs (order, no-overwrite, frozen title and keep_source, no-echo per script family) red and restored green; every script matches its SDD interface | T2.8 |
| 2026-11-05 | Phase 2 drift check: 4 FAIL, all SDD text lagging the reviewed code; owner chose to align the spec and the Phase 3/4 plan text and to consolidate the duplicated config reader, atomic write and fence split into libs now | Owner choice |
| 2026-11-05 | An empty `destination:` or `offer:` key in a process file reads as unset; `offer: never` beside an empty key is still a normal process, not a decline | Gate finding; matches `required:`; only a hand edit produces it |
| 2026-11-05 | Kado error text stays verbatim in `listing_error` and the outline error | SDD F2-AC4 shows `listing_error` verbatim; Kado error messages carry paths and status, not note text |
| 2026-11-05 | PRD F5-AC8 reworded to match the amended CON-3: no note, source or answer text in logs or errors; output carries only paths, states and the named fields | Spec alignment after the Phase 2 drift check; "only paths and states" contradicted the reviewed output contract |
| 2026-11-05 | Shared `lib/note_io.py` (config reader with typed errors, atomic write) used by the /note scripts and libs; the process-file fence split stays separate as a recorded ADR-4 exception; a YAML ValueError in the config now exits 2 in note-instructions instead of a traceback, and a failed atomic write removes its temp file | Owner-approved consolidation; the fence parsers differ on CR-only and Unicode line breaks |
| 2026-11-05 | note-instructions.py line count is 585 after the T2.6 fixes; the no-split decision above still holds | Alignment review; the reasons are unchanged |
| 2026-11-05 | Model escalation: T3.1 sonnet → opus | Trigger: second review FAIL |
| 2026-11-05 | Model escalation: T3.1 opus → opus@max | Trigger: second review FAIL |
| 2026-11-05 | Phase 3 drift: fix all findings before Phase 4 — `kado_connect` relabel (it fires on missing Kado config, not an outage), runtime-prose WARNs, the landed-but-unrecorded first step and unwrapped Kado transport errors, Drop naming, docs WARNs, phase-4.md refresh | Owner choice; the orphaned-note gap would surface in the live walk |
| 2026-11-05 | note-instructions.py is 592 lines after the Phase 3 hardening; the no-split decision still holds, and the next growth moves delivery (~lines 330-530) into `lib/note_delivery.py` | Phase 3 quality review |
| 2026-11-05 | Process-offer signal 2 becomes "a point skipped in the question rounds was filled through Change something before delivery" | Owner choice; the old signal needed a process file, which the offer excludes, so it could never fire |
| 2026-11-05 | A stage is frozen once a step is done or a delivery step's upload was in flight; `start` and `deliver` report `frozen` and `steps_done`, and the skill branches on them instead of recomputing the rule or reading meta.json | Hardening review: a stage killed after its first upload could be renamed on resume and leave a duplicate note |
| 2026-11-05 | The default full-suite `scripts/run-evals.sh` run skips cases marked not gated; they run only with `--case` | Owner choice; keeps the CLAUDE.md gate's cost and flake surface as it was before spec 044 (ADR-8) |
| 2026-11-06 | `claude plugin eval` cannot offer AskUserQuestion (1-run probe 2026-11-06T07-16-55Z: ToolSearch found no such tool; Write was granted via the per-case `ALLOW_TOOLS` marker). The /note eval case is regraded to the end of the run: header and note.md printed, an approval attempt, no question round, no deliver | Owner choice; the probe showed the behaviour runs correctly up to the approval point |
| 2026-11-06 | T4.1 eval evidence: case GREEN 3/3 (tomo-tmp/evals/2026-11-06T07-58-32Z, $0.40); all five mutations RED 3/3 on their target grader (header-after-delivery → 1, ask-before-draft → 2, print-draft-md → 3+4, confirm-attendees → 5 after its first form came back GREEN, deliver-before-ask → 6); spec 044 eval spend $3.31 | Verdict lines in evals/_mutations/README.md |
| 2026-11-05 | Phase 3 gate: all tasks reviewed PASS (spec + quality); drift findings fixed and re-reviewed PASS; full suite 7759 passed, 5 skipped; ruff clean; no eval-gated file changed; phase-4.md refreshed to the new interfaces | T3.5 + hardening batch |
| 2026-11-05 | `deliver` reports a guard-withdrawn action as `status: withdrawn` and the skill branches exit 1 on `status`; Kado unreachable at `deliver` gets its own non-empty `step` so the skill does not send the user to fix the draft | T3.2 quality review: withdrawn and Kado-down both shared the "exit 1, empty step = filled-note check failed" shape |
| 2026-11-05 | Phase 2 complete: T2.1–T2.8 reviewed; drift findings aligned in the spec; shared lib/note_io reviewed; full suite 7553 passed, 4 skipped; ruff clean | Phase 2 gate |
| 2026-11-06 | Unfinished drafts offered Continue / Discard (PRD F6-AC7 added, User Journey 4 widened; SDD start output `unfinished_drafts`, `stale_stages` narrowed to unreadable `meta.json`) | Live walk (session c573b7b7) showed a printed draft dropped at the next /note; owner chose to offer every unfinished stage |
| 2026-11-06 | Plain-text questions for drafts and lists: the glob setup, the template choice (numbered list, any number valid; the at-most-three-candidates rule is gone), the question rounds, the approval (1 Deliver · 2 Change something · 3 Abort), the process offer and process mode print their content and end the turn with the question; the other questions keep `AskUserQuestion`. One STRICT in `## Rules` replaces the two print-first blocks (note-from-template 0.2.7). SDD CON-4 and the PRD interaction constraint amended; PRD F2-AC2 unchanged (it fixes no option count) | Live walk: session 2e8fb1d3 called AskUserQuestion straight after a Read of note.md under the 0.2.6 STRICT blocks; the plain-text path printed the full draft (c573b7b7) and is the path the eval proved GREEN 3/3. Owner choice |
| 2026-11-06 | Numbered plain-text options: every plain-text question with options ends with them numbered on one line (glob setup `1 Confirm · 2 Correct · 3 Abort`, approval `1 Deliver · 2 Change something · 3 Abort`, process offer `1 Save · 2 Not now · 3 Never`, destination `1 Keep current · 2 Default · 3 Another folder`, renumbered without Keep current); the template choice aborts with `0 Abort` because the list owns 1..n. The number or the option word answers; unclear is asked again. | The plain-text form made the user type whole words; a number is one key (#169). | Owner decision |
| 2026-11-06 | Text, then dialog for draft and list questions: the fixed-option questions (glob setup and its reprint, template choice with at most three candidates, approval at every reprint, process offer, process destination) keep the content and numbered option line as reply text and, in the same message after it, call `AskUserQuestion` with the same options; free-text questions and candidate lists over three stay plain text only; a typed number or option word still answers (note-from-template 0.2.10). SDD CON-4 and the PRD interaction constraint amended. Revert to the 0.2.9 plain-text-only form if a live transcript shows an `AskUserQuestion` call without a preceding text block holding the content | The plain-text-only form (0.2.7 to 0.2.9) works live (5e1f413c, 657b5c02) but lost the click; the numbered option line in the text keeps the typed path complete if the dialog appears without the draft. The eval never offers `AskUserQuestion`, so 0.2.10 needs its own live check. | Owner decision |

## Context

`/note`: the user hands Tomo rough material for a kind of note. Tomo picks a vault template, asks for what is missing, shows a draft and delivers the note with a Hashi instruction set. The brainstorm file is the handoff contract; GitHub issue #169.

---
*This file is managed by the xdd-meta skill.*
