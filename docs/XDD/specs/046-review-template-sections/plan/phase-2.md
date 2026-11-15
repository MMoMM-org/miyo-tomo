---
title: "Phase 2: Setup — mapping, off-limits, template choice"
status: in_progress
version: "1.0"
phase: 2
---

# Phase 2: Setup — mapping, off-limits, template choice

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Internal API Changes]` — `match` response (`sections`, `template_not_found`), `setup-input` refusals
- `[ref: SDD/Runtime View/Error Handling]` — setup rows
- `[ref: SDD/User Interface & UX]` — the one-turn confirm table and plain-text corrections
- `[ref: SDD/Architecture Decisions; ADR-3, ADR-8, ADR-9, ADR-13]`

**Key Decisions**:
- No extra question turn: rows, off-limits marks and analysis rows ride the existing Confirm / Correct step.
- Script part vs model part: scripts produce candidates, reasons, keys, defaults, saved rows and `dropped`; the model only words descriptions, keywords and group hints (ADR-9).
- `match` owns `rows-<kind>.json`; the model writes no state file (ADR-13, CON-1).
- A mistyped template is refused by `setup-input`, not by prose; the configured anchor counts only for the same template (ADR-13).

**Dependencies**: Phase 1 (T1.2, T1.3, T1.4).

---

## Tasks

Lets the vault keeper confirm, in one turn per template, which sections receive what, which are off-limits, and for the quarter where its notes live.

- [x] **T2.1 `match` proposes sections, off-limits and the quarter; template choice (#267)** `[activity: backend-api]`

  1. Prime: `tomo/scripts/lib/review_match.py` (`propose` 91-198, template resolution 130-139, anchor 142, `own_sections` 177, quarter defaults ~120-123, 170-171 — the per-kind default format and `KIND_WORDS` quarter exist since T1.4; what remains for the quarter is the `sections` block, `rows-<kind>.json` and the place/language proposal); `lib/review_templates.py` (`resolve_template` 81, `template_candidates` 56); `tests/test_review_session_templates.py` `[ref: SDD/Internal API Changes; ADR-13]`
  2. Test: `match` returns `sections.candidates` (heading_key, state, reason, flags, defaults, saved row) for a readable template and none for no template / no eligible heading (F2-AC9); for no template / no eligible heading `sections` is present with `candidates == []` and an explicit `mappable: false` (a no-op that omits `sections` must fail); saved rows come back as defaults; `rows-<kind>.json` is written with setup text only (privacy test: no note text); after a template change `dropped` names the earlier rows the new template lacks (F7-AC3); a typed or configured template that is not found returns `template_not_found` + candidates and `template: null` (F7-AC1); the configured anchor is used only when the resolved template equals the configured one (F7-AC2); a quarter with no setup proposes folder, `YYYY-[Q]Q` (or the format found in existing notes), template, place, language and rows (F6-AC1); nothing is saved by `match`.
  3. Implement: `review_match.py` and the `match` subcommand in `review-session.py`; `start` deletes a stale rows file; WHY docs first; version bumps.
  4. Validate: `test_review_session_templates.py`, `test_review_session.py` green; ruff clean.
  5. Success: one call gives the skill everything for the confirm table `[ref: PRD/F2-AC1, F2-AC9, F6-AC1, F7-AC1, F7-AC2, F7-AC3]`

- [x] **T2.2 `setup-input` refusals and saving rows** `[activity: backend-api]`

  1. Prime: `review-session.py` (`_INPUT_KEYS` 240, `writer_input` 245, `setup_input` 263); `lib/review_config.input_problems`; `lib/review_mapping.landing_off_limits` (T1.2) `[ref: SDD/Internal API Changes; SDD/Runtime View/Error Handling]`
  2. Test: refusals `template-not-found`, `section-left-out` (with its reason), `section-not-in-template`, `section-off-limits`, `landing-off-limits` (a `before` under an off-limits previous heading, an `end` whose last subsection is off-limits, the "Tomo Review" `place` inside an off-limits subtree), `analysis-not-automatic`, `duplicate-section`, `duplicate-off-limits`, `duplicate-section-id` (these three come from `review_config.input_problems`, T1.3), a malformed id as a `schema` problem at its pointer; a `mixed` heading is accepted (F2-AC4); accepted rows reach the writer input; the rows file is deleted on save; each refusal RED-proven.
  3. Implement: `setup-input` checks and `_INPUT_KEYS` / `writer_input`; WHY docs first; version bumps.
  4. Validate: tests green; ruff clean.
  5. Success: nothing ineligible or off-limits can be saved `[ref: PRD/F2-AC4, F2-AC11; Rule 4]`

- [ ] **T2.3 Skill setup step: the mapping table** `[activity: prompt-authoring]`

  1. Prime: `tomo/dot_claude/skills/periodic-review/SKILL.md` step 2 (59-100); `docs/tomo/dot_claude/skills/periodic-review.md`; `tests/test_review_skill.py`, `test_review_skill_contract.py` `[ref: SDD/User Interface & UX; ADR-8; ADR-9]`
  2. Test: skill pins (in `tests/test_review_skill*.py`) for: the table printed from `match` evidence, every left-out heading with its reason in one line, corrections as plain text in the existing Correct step (edit, remove, add, mark off-limits heading only / with sub-sections, analysis row), forward-looking sections offered with suggestion descriptions, no extra turn, the dropped headings named after a template change, the `--anchor` carve-out on a template change, the quarter in the same flow, and the review request continuing in the same session after the save (F2-AC10, an untested close-out gap in spec 044).
  3. Implement: WHY in `docs/tomo/…/periodic-review.md` first; then the imperatives in SKILL.md step 2 through `tcs-helper:skill-author`; version bump; `commands/review.md` quarter in the argument hint.
  4. Validate: skill tests green; skill-author verification; character growth recorded.
  5. Success: the vault keeper confirms or corrects the whole mapping in one turn `[ref: PRD/F2-AC2, F2-AC6]`

- [ ] **T2.4 Phase Validation** `[activity: validate]`

  - Run all Phase 2 tests and the full suite (GREEN). Drift check against SDD Internal API Changes. WHY-first order (git log) and no eval-gated file changed. Lint clean.
