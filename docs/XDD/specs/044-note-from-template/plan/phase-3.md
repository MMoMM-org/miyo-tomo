---
title: "Phase 3: Runtime prose and documentation"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Runtime prose and documentation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Runtime View]`: primary flow, error handling, the `--process` and question-budget algorithms.
- `[ref: SDD/Cross-Cutting Concepts/User Interface & UX]`: header, options, report.
- `[ref: SDD/Building Block View/Directory Map]`: runtime and docs files.
- `[ref: SDD/Implementation Boundaries]`: the narrowed `inbox-author` change.

**Key Decisions**:
- WHY first in `docs/tomo/`, runtime text second.
- Skills through `tcs-helper:skill-author`; runtime text holds imperatives only; STRICT only where a deviation was observed.
- `/note` runs in the main session, never as a dispatched subagent (it needs `AskUserQuestion`).

**Dependencies**:
- Phase 2 complete (the skill calls the scripts by their final interfaces).

---

## Tasks

This phase gives the model its instructions and the user the documentation.

- [ ] **T3.1 WHY documentation** `[activity: docs]` `[model: routine]`

  1. Prime: SDD ADRs, Error Handling, Gotchas; existing `docs/tomo/dot_claude/skills/inbox-author.md` `[ref: SDD/Architecture Decisions]`
  2. Test: `check_docs`-style link check passes; every runtime file of T3.2 and T3.3 has its mirror before its runtime edit.
  3. Implement: `docs/tomo/dot_claude/commands/note.md`, `docs/tomo/dot_claude/skills/note-from-template.md`, the redirect entry in `docs/tomo/dot_claude/skills/inbox-author.md`.
  4. Validate: mirrors exist and name each decision baked into the runtime.
  5. Success: no rationale needs to live in runtime text `[ref: CLAUDE.md runtime rule]`

- [ ] **T3.2 Command and skill** `[activity: prompt-authoring]`

  1. Prime: SDD Runtime View and UX; `commands/hashi-hook.md`; `skills/inbox-author/SKILL.md` frontmatter; vault-explorer's print-before-ask rule `[ref: SDD/Runtime View; ADR-6]`
  2. Test: new `tests/test_note_skill_prose.py` asserts the imperatives exist: print before every question; at most four questions per round and at most two rounds; required points re-asked with no skip option; the skipped line; the header fields; approval options; `drop` on every abort path; resume or drop before a new request; stale stages dropped with one line; folder empty or not readable wording with the remedy (grant read access to the template folder or do not use `/note`) on both the empty-listing and the unreadable-template path; process offer asked once with three answers and only on the three signals; rename or abort on a taken name; frozen title during resume; script calls with their exact flags. Asserts no rationale prose and a `# version:` header.
  3. Implement: `tomo/dot_claude/commands/note.md` 0.1.0 (thin, routes to the skill with `$ARGUMENTS`); `tomo/dot_claude/skills/note-from-template/SKILL.md` 0.1.0 via `tcs-helper:skill-author`.
  4. Validate: prose test passes; skill-author verification passes.
  5. Success: every dialogue criterion has an imperative `[ref: PRD/F1 … F4, F6, F7; SDD/F1-AC1, F1-AC2, F2-AC1 … F2-AC4, F3-AC2 … F3-AC8, F4-AC1 … F4-AC4, F6-AC2, F6-AC5, F7-AC3, F7-AC6, F7-AC7, F7-AC10]`

- [ ] **T3.3 inbox-author redirect** `[activity: prompt-authoring]` `[parallel: true]`

  1. Prime: `inbox-author/SKILL.md:26-60`; `tests/test_inbox_author_pipeline.py`; T1.1 result `[ref: SDD/Implementation Boundaries; F8-AC1, F8-AC2]`
  2. Test: extend `tests/test_inbox_author_pipeline.py`: the unknown-type "If found" path names `/note` and no longer saves the found template; the "not found" path, the built-in default, the mapped `default` template and the `.base`/`.canvas` steps are byte-unchanged.
  3. Implement: edit through `tcs-helper:skill-author`; bump 0.3.0 → 0.4.0.
  4. Validate: tests pass.
  5. Success: one path per request `[ref: PRD/F8]`

- [ ] **T3.4 User documentation** `[activity: docs]` `[parallel: true]` `[model: routine]`

  1. Prime: `docs/usage.md`, `docs/troubleshooting.md:44`, `docs/instructions-json.md` `[ref: PRD/F9]`
  2. Test: link check passes; the usage section names the two deletions and `/inbox --recover`.
  3. Implement: `/note` section in `docs/usage.md` (modes, first-run setup, process files through Tomo, discard); troubleshooting line that `/note` needs read access to the template folder, and that without it the user grants the right in Kado or does not use `/note`; a sentence in `docs/instructions-json.md` that `/note` produces sets of the same shape.
  4. Validate: no executor internals in user docs.
  5. Success: a wrong result costs two deletions and one command `[ref: PRD/F9; SDD/F9-AC1]`

- [ ] **T3.5 Phase Validation** `[activity: validate]`

  - Full pytest and ruff. Audit the new skill and the changed one with `tcs-helper:skill-author` audit mode. Confirm no eval-gated file changed (`git diff --stat main -- <gated files>` empty).
