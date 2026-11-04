---
title: "Phase 1: Prerequisite and shared libraries"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: Prerequisite and shared libraries

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Risks and Technical Debt/Known Technical Issues]`: the unverified Kado read access.
- `[ref: SDD/Building Block View/Components]`: `lib/template_syntax.py`, `lib/note_meta.py`, `lib/note_process.py`, `vault-config-writer.py templates-include`.
- `[ref: SDD/Application Data Models]`: token tables, `NoteDraftMeta`, `ProcessFile`.
- `[ref: SDD/Architecture Decisions; ADR-4, ADR-5, ADR-7]`

**Key Decisions**:
- T1.1 is a gate. If the key cannot read the template folder, stop and bring it to the owner before any other task.
- One parser (ADR-4); `template-doctor.py` and `token-render.py` keep their copies, and a parity test pins the token regex.
- The writer changes only the `note_include` lines (ADR-5).

**Dependencies**:
- None. T1.2 to T1.4 run in parallel after T1.1 passes.

---

## Tasks

This phase proves the prerequisite and builds the libraries every script uses.

- [x] **T1.1 Kado reads the template folder** (2026-11-04: owner confirmed the key reads the folder; no live run; the denial remedy was added to F2-AC4) `[activity: validate]` `[model: routine]`

  1. Prime: `inbox-author/SKILL.md:44-48`; `docs/troubleshooting.md:44`; memory "empty Kado search hides a denial" `[ref: SDD/Known Technical Issues]`
  2. Test: on `tomo-instance`, the owner asks `inbox-author` for an unmapped kind that has a template in `templates.base_path` (for example a meeting note). Record from the transcript whether `kado-search byName` returned the template and whether `kado-read` returned its body.
  3. Implement: nothing in code. Write the result into `docs/XDD/specs/044-note-from-template/README.md` Decisions Log.
  4. Validate: the transcript lines are quoted with their session id; no note body is quoted.
  5. Success: the key lists and reads the template folder, or the owner has decided how to proceed `[ref: PRD/Assumptions; SDD/Known Technical Issues]`

- [ ] **T1.2 Shared template syntax** `[activity: backend]` `[parallel: true]`

  1. Prime: `template-doctor.py:154-182,190-280`; `token-render.py:178-179,267-315`; `KNOWN_TOKENS` in `template-doctor.py:60-72`; SDD token tables `[ref: SDD/Application Data Models; ADR-4]`
  2. Test: new `tests/test_template_syntax.py` with real template shapes (frontmatter, callouts, fenced code with `{{x}}`, `\{{x}}`, Templater `<% %>`, `<%* %>`, a `tp.file.include` first line, headings with and without body):
     - leading block found, unclosed, missing;
     - tokens listed with line and `prefilled` per the SDD table;
     - headings with `level`, `text`, `line`, `has_body`;
     - Templater spans listed, never treated as points;
     - filled-note checks fail on a remaining `<%`, a remaining `{{token}}`, a user-authored `tomo:` key, a missing or unclosed fence, and pass on a clean note;
     - parity: the token regex equals `token-render.py`'s `_TOKEN_RE`.
  3. Implement: `tomo/scripts/lib/template_syntax.py` with a file-level WHY docstring and `# version: 0.1.0`; `docs/tomo/scripts/lib/template_syntax.md` first.
  4. Validate: tests pass; ruff clean.
  5. Success: outline points and filled-note checks come from one module `[ref: PRD/F3; SDD/F3-AC1, F3-AC7]`

- [ ] **T1.3 Draft state and process file libraries** `[activity: backend]` `[parallel: true]`

  1. Prime: SDD `NoteDraftMeta`, `ProcessFile`, `stale_stages`, `missing_required` `[ref: SDD/Application Data Models; ADR-7]`
  2. Test: new `tests/test_note_meta.py` and `tests/test_note_process_lib.py`:
     - `meta.json` round trip; `steps_done` updates; frozen title and destination once `steps_done` is non-empty;
     - listing stage dirs splits failed deliveries (`failed_step` set) from stale stages;
     - process file parse: full file, destination only, guidance only, decline marker alone (`declined: true`, no process), broken YAML (`error` set, no exception);
     - write rejects a required point absent from an outline; `missing_required` lists required points absent from an outline;
     - decline then write replaces the marker.
  3. Implement: `tomo/scripts/lib/note_meta.py`, `tomo/scripts/lib/note_process.py`, each with WHY docstring and version; `tomo/schemas/note-process.schema.json` as documentation; `docs/tomo/` mirrors first.
  4. Validate: tests pass; ruff clean.
  5. Success: one owner each for `meta.json` and process files `[ref: PRD/F6, F7; SDD/F6-AC1, F7-AC4, F7-AC5, F7-AC9]`

- [ ] **T1.4 Writer subcommand templates-include** `[activity: backend]` `[parallel: true]`

  1. Prime: `vault-config-writer.py:46,157-274,647-683`; `tests/test-vault-config-writer.py`; `read-config-field.py:30-78`; `vault-example.yaml:120-134` `[ref: SDD/Internal API Changes; ADR-5]`
  2. Test: extend `tests/test-vault-config-writer.py`:
     - insert into a `templates:` block without the key; replace an existing key with list continuation lines; append a `templates:` block when none exists;
     - every byte outside the `note_include` lines identical, including `mapping` comments and `custom_tokens`;
     - invalid input (empty list, empty string, non-list) exits 1 and writes nothing; result YAML checked with `yaml.safe_load`;
     - `--stdout` writes nothing.
     Add `read-config-field.py` cases: `--fields templates.note_include,... --format json` with the key absent (omitted, exit 0) and present (list).
  3. Implement: `templates-include` subcommand with `validate_templates_include_input` and the in-block helper; bump `vault-config-writer.py` 0.4.0 → 0.5.0; `tomo/schemas/vault-config-templates.schema.json`; update `docs/tomo/scripts/vault-config-writer.md` first.
  4. Validate: writer tests and existing writer tests pass; ruff clean.
  5. Success: the selection is saved without touching any other setting `[ref: PRD/F1; SDD/F1-AC3, F1-AC5]`

- [ ] **T1.5 Phase Validation** `[activity: validate]`

  - Run the full pytest command. Verify T1.2 to T1.4 against the SDD data models and ADR-4, ADR-5, ADR-7. Ruff clean.
