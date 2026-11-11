---
title: "Phase 5: Command, skill and documentation"
status: pending
version: "1.1"
phase: 5
---

# Phase 5: Command, skill and documentation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View]`: the flow the skill runs and every row of the Error Handling table.
- `[ref: SDD/User Interface & UX]`
- `[ref: SDD/Directory Map]`: runtime, documentation and test files.
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-7, ADR-9]`
- `tomo/dot_claude/commands/note.md`, `tomo/dot_claude/skills/note-from-template/SKILL.md`, `docs/tomo/dot_claude/skills/note-from-template.md`
- `PRIVACY.md`, `docs/setup.md`

**Key Decisions**:
- The command is a shim; the skill owns the order; every state change is a script call (ADR-1).
- Confirmations are plain text with a numbered choice line and the turn ends there (spec 044 lesson).
- WHY docs are written before the runtime prose; runtime prose holds imperatives only; skills are edited via `tcs-helper:skill-author`.
- The command is `/review`; Claude Code's built-in is `/code-review`, so no collision is expected — T5.2 checks it in the container first, a mod is the fallback.
- Privacy is documented, not cleaned up (ADR-9).

**Dependencies**:
- Phases 2–4 (all script interfaces exist).

---

## Tasks

This phase makes `/review` usable in the container and documents it.

- [ ] **T5.1 WHY documentation for command and skill** `[activity: documentation]`

  1. Prime: `docs/tomo/dot_claude/commands/note.md`, `docs/tomo/dot_claude/skills/note-from-template.md` `[ref: SDD/Solution Strategy; ADR-1]`
  2. Test: a doc test asserts `docs/tomo/dot_claude/commands/review.md` and `docs/tomo/dot_claude/skills/periodic-review.md` exist and name every script subcommand the skill calls (drift guard against the CLI contracts of Phases 2–4).
  3. Implement: both WHY docs — each step's reason, the plain-text approval, the open-review-first order, the week question, the setup continuing in the same session, the privacy boundary.
  4. Validate: doc test green.
  5. Success: every decision in the runtime prose has its WHY first `[ref: SDD/Pattern Documentation]`

- [ ] **T5.2 `commands/review.md` and `skills/periodic-review/SKILL.md`** `[activity: prompt-authoring]`

  1. Prime: T5.1 docs; `skills/note-from-template/SKILL.md:11-76`; memory notes on print-before-ask and AskUserQuestion limits; in a `tomo-instance` container session (owner-run), list the available slash commands and confirm a project `/review` is offered and not shadowed `[ref: SDD/Runtime View; ADR-1, ADR-7]`
  2. Test: a static test checks the shim invokes the skill in-session with `$ARGUMENTS` verbatim; the skill names only existing script subcommands and flags (CLI-contract sweep over `tomo/dot_claude/skills`); every Error Handling row with a user message has a matching skill branch (including the no-access wording, the raise-the-limit advice, the access hint, "setup then continue", abort writes nothing); no rationale prose, spec refs or dates in runtime files; `tomo-help.md` lists `/review`. Optional, owner-run paid eval case under `evals/` for the open-review-first order and the plain-text Deliver/Abort turn end.
  3. Implement: the shim, the skill (via `tcs-helper:skill-author`), the `tomo-help.md` entry; version bumps. If the container check shows `/review` is shadowed, stop and bring it to the owner (fallback: a mod or another name).
  4. Validate: static tests green; skill-author audit clean; ruff clean.
  5. Success: `/review` runs the full flow in the container `[ref: PRD/Primary User Journey; PRD/F1-AC1, F1-AC6, F1-AC7, F1-AC9, F1-AC10, F2-AC1, F2-AC8, F3-AC12, F5-AC2]`

- [ ] **T5.3 Privacy, setup docs and example config** `[activity: documentation]` `[parallel: true]`

  1. Prime: `PRIVACY.md` (esp. :63-77); `docs/setup.md`; `tomo/config/vault-example.yaml:57-134` `[ref: SDD/Constraints CON-3; ADR-9; SDD/Known Technical Issues]`
  2. Test: a doc test asserts PRIVACY.md (a) scopes "metadata only" to Tomo's own records, (b) names the session transcripts in the container home, `tomo-tmp` (including `read.json` left by a session that ended without writing or aborting), the inbox, (c) says removal is the user's choice and recommends protecting instance and home like the vault (for example an encrypted disk), (d) in the `/review` paragraph names what reaches the model — daily sections, the 5 Year Journal, tracker values such as sleep, energy and sport, paths of notes created in the period — and recommends Kado deny rules for folders not to be reviewed; `vault-example.yaml` weekly pattern is `GGGG-[W]WW` and a commented `review:` example validates against `vault-config-review.schema.json`.
  3. Implement: the PRIVACY.md changes; the `docs/setup.md` link; the example config; a README feature line.
  4. Validate: doc tests green.
  5. Success: the user knows where journal content rests and how to protect it `[ref: PRD/F7-AC2]`

- [ ] **T5.4 Privacy test over every review script** `[activity: test]` `[parallel: true]`

  1. Prime: `tests/test_note_privacy.py:1-80` `[ref: SDD/Pattern Documentation (privacy test); ADR-9]`
  2. Test: `tests/test_review_privacy.py` — markers for daily text, journal answer, tracker value, proposal text; every script and subcommand run in-process on the fake vault; no marker on stderr ever, including a forced exception while a marker-bearing line is being parsed; markers on stdout only in allowlisted fields (with reason); each allowlisted field reached; read/proposal working files absent after `write` and after abort.
  3. Implement: the test only (fixes go to the owning script).
  4. Validate: green; RED proven by printing a marker to stderr in an isolated copy and by removing a top-level handler.
  5. Success: Tomo's own records stay free of journal content `[ref: PRD/F7-AC1]`

- [ ] **T5.5 Phase Validation** `[activity: validate]`

  - Full suite, ruff, skill-author audit of the new skill, CLI-contract sweep over `tomo/dot_claude/skills`. Confirm no eval-gated file changed.
