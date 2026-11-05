---
title: "Phase 2: Scripts"
status: in_progress
version: "1.0"
phase: 2
---

# Phase 2: Scripts

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Building Block View/Internal API Changes]`: every script's arguments, output and exit codes.
- `[ref: SDD/Implementation Examples]`: the delivery order with resume and its traced walkthrough; the pattern preview table.
- `[ref: SDD/Runtime View/Error Handling; Complex Logic]`
- `[ref: SDD/Implementation Gotchas]`
- `[ref: SDD/Architecture Decisions; ADR-2, ADR-3, ADR-6]`

**Key Decisions**:
- Scripts print one JSON object and exit 0 for usable output; 3 is a taken name with `EXISTS:<path>` as the first stdout line.
- No script echoes user text (CON-3).
- `deliver` reruns the filled-note check, reuses `meta.generated`, refuses a set the guards cut, and marks the source by a direct merge (ADR-3).
- Tests use a fake Kado; nothing reaches a live vault.

**Dependencies**:
- Phase 1 complete.

---

## Tasks

This phase delivers every deterministic part of `/note`.

- [ ] **T2.1 template-outline.py** `[activity: backend]` `[parallel: true]`

  1. Prime: SDD outline interface and token tables; `kado_client.read_note` `[ref: SDD/Internal API Changes]`
  2. Test: new `tests/test_template_outline.py` (fake Kado and `--local`): points per the token tables; `--stage` writes `template.md` with prefilled tokens resolved and `outline.json`; `--out` writes the outline to the given file; `frontmatter_ok: false` exits 0; unreadable template exits 1.
  3. Implement: `tomo/scripts/template-outline.py` 0.1.0 on `lib/template_syntax.py`; `docs/tomo/scripts/template-outline.md` first. Open before coding (Phase 1 drift note): `lib/template_syntax.py` has no token resolver and the hyphenated `token-render.py` cannot be imported, so decide and record in the mirror doc how prefilled values are produced (a resolver in the library that reuses `token-render.py`'s value rules under a parity test, or a subprocess call), and read `has_source` from the stage's `meta.json` (`source_path` set) when `--stage` is given.
  4. Validate: tests pass; ruff clean.
  5. Success: every heading, frontmatter key and non-prefilled token is a point `[ref: PRD/F3; SDD/F3-AC1]`

- [x] **T2.2 template-doctor.py filled-note** `[activity: backend]` `[parallel: true]`

  1. Prime: `template-doctor.py:368-406`; `tests/test_template_doctor.py` `[ref: SDD/Internal API Changes]`
  2. Test: extend `tests/test_template_doctor.py`: `filled-note --note <file>` passes a clean note, fails on `<%`, `{{token}}`, user `tomo:` key, missing fence; existing modes unchanged; `--note` is accepted without `--template`.
  3. Implement: the mode on `lib/template_syntax.py`; bump 0.3.0 → 0.4.0; `docs/tomo/scripts/template-doctor.md` first.
  4. Validate: all template-doctor tests pass.
  5. Success: Templater remains are caught `[ref: PRD/F3; SDD/F3-AC7]`

- [x] **T2.3 note-session.py** `[activity: backend]` `[parallel: true]`

  1. Prime: SDD `start` and `match` interfaces, Complex Logic, the pattern preview table; `read-config-field.py --fields`; `kado_client.list_dir` `[ref: SDD/Complex Logic; ADR-6]`
  2. Test: new `tests/test_note_session.py` (fake Kado, tmp instance):
     - `--process t_meeting` → mode process and `process_template_path`, whatever `note_include` says; unknown stem → empty path;
     - free text → mode note, and the text appears nowhere in stdout;
     - kept drafts (failed deliveries) vs stale stages;
     - `note_include` absent → `include_configured: false`, no listing call;
     - the preview table rows of the SDD, including `daily` with `.md` stripped and always excluded;
     - `folder_listed: 0` and `listing_error` reported, exit 0.
  3. Implement: `tomo/scripts/note-session.py` 0.1.0 on `lib/note_meta.py`; mirror doc first.
  4. Validate: tests pass; ruff clean.
  5. Success: the session start is deterministic `[ref: PRD/F1, F2, F6; SDD/F1-AC6, F2-AC4, F6-AC2]`

- [ ] **T2.4 note-process.py** `[activity: backend]`

  1. Prime: SDD `note-process.py` interface; T1.3 library; T2.1 outline format `[ref: SDD/Internal API Changes]`
  2. Test: new `tests/test_note_process.py`: `read` with and without `--outline` (`missing_required`); `write` from an outline file, rejects absent required points with exit 1 and writes nothing; `decline` writes the marker; `write` after `decline` replaces it; a broken file reads with `error`.
  3. Implement: CLI over `lib/note_process.py`, 0.1.0; mirror doc first.
  4. Validate: tests pass.
  5. Success: process files are only ever written by the script `[ref: PRD/F7; SDD/F7-AC8 … F7-AC11]`

- [ ] **T2.5 note-instructions.py new, stage, drop and the action builder** `[activity: backend]`

  1. Prime: SDD `new`, `stage`, `drop`, `NoteInstructionSet`; `render_source_actions.py:53-99`; `hashi-instructions.schema.json` `move_note` and `delete_source` `[ref: SDD/Application Data Models; ADR-2, ADR-7]`
  2. Test: new `tests/test_note_actions.py` and `tests/test_note_instructions.py`:
     - `new` draws a `YYYY-MM-DD_HHMMSS` stem, a run id, `generated`; reads inbox, atomic-note path (also as the first of `paths`), profile, and the process destination; stages `source.md`;
     - `stage` records title, destination, keep-source; refuses a title or destination change once `steps_done` is non-empty and a keep-source change once `steps_done` holds `instructions_json` (both `frozen: true`); accepts a keep-source change while `steps_done` is `[note]`; reports the filled-note check;
     - built set: `move_note` with exactly the schema's allowed keys, `source_inbox_item`; `delete_source` with `depends_on: ["I01"]` only when a source exists and is not kept; validates with `jsonschema` against `hashi-instructions.schema.json`;
     - `drop` removes the stage dir.
  3. Implement: `tomo/scripts/lib/note_actions.py` 0.1.0 and the first three subcommands of `tomo/scripts/note-instructions.py` 0.1.0; mirror docs first.
  4. Validate: tests pass; ruff clean.
  5. Success: the set is wire-valid by construction `[ref: PRD/F4, F5; SDD/F4-AC3, F5-AC2, F5-AC3, F6-AC4]`

- [ ] **T2.6 note-instructions.py deliver** `[activity: backend]`

  1. Prime: SDD delivery example, traced walkthrough, Error Handling; `render_withhold.py:37,280,431`; `render_md.py:921`; `doc_frontmatter.py:87,172`; `mark-captured.py:172-190`; `inbox-triage.py:436-455,1494-1534,1603-1655` `[ref: SDD/Implementation Examples; ADR-2, ADR-3]`
  2. Test: extend `tests/test_note_instructions.py` with every walkthrough row:
     - order note → JSON → MD → source mark; a failure at each step stops all later steps and leaves the source unmarked;
     - `stage --keep-source` after a failure at `instructions_md` is refused (`frozen: true`); after a failure at `instructions_json` it is accepted;
     - a run killed between steps (`steps_done` non-empty, `failed_step` empty) is listed by `note-session.py start` as a kept draft, never as a stale stage;
     - resume: identical target counts as done; different target exits 3 with `EXISTS:` first and changes nothing;
     - destination clash before any write exits 3; a guard-withdrawn action is refused with status `withdrawn`;
     - a failing filled-note check refuses delivery;
     - two `deliver` runs produce byte-identical JSON and MD (`meta.generated`);
     - the MD peer carries `tomo.doc_type: instructions`; the note carries `rendered-note`/`pending-move`; the source merge is `build_tomo_block("source","captured",run_id)` with `mode="merge"`;
     - success removes the stage dir.
     New `tests/test_note_triage_interplay.py`: the delivered files and the marked source fed into triage's new-source and orphan logic yield no new item and no orphan warning; `--recover` treats the marked source as fresh.
     One shared test asserts exit 3 and the `EXISTS:` line for both `deliver` and `kado-write-file.py --no-overwrite`.
  3. Implement: `deliver` in `note-instructions.py`.
  4. Validate: tests pass; ruff clean.
  5. Success: delivery is ordered, never overwrites and resumes cleanly `[ref: PRD/F5, F6, F9; SDD/F5-AC1 … F5-AC7, F6-AC1, F6-AC3, F6-AC6, F9-AC2]`

- [ ] **T2.7 Privacy and survival tests** `[activity: backend]` `[parallel: true]`

  1. Prime: CON-3; `scripts/backup-tomo.sh:175`; `scripts/restore-tomo.sh:193-197`; `scripts/update-tomo.sh:360-367,466-516`; `tests/test_backup_restore_instance.py` `[ref: SDD/Quality Requirements]`
  2. Test: a marker string in the request, the source, the template body and the answers never appears in stdout or stderr of any new script; backup then restore keeps `config/note-processes/*.md` byte-identical; `update-tomo.sh` against a tmp instance (isolated `HOME`) leaves `config/note-processes/` unchanged.
  3. Implement: tests only; fix any script that leaks.
  4. Validate: tests pass and never touch `~/.tomo`.
  5. Success: no user text in output; process files survive `[ref: PRD/F5, F7; SDD/F5-AC8, F7-AC12]`

- [ ] **T2.8 Phase Validation** `[activity: validate]`

  - Run the full pytest command and ruff. Mutation-prove in an isolated copy that the order, no-overwrite, frozen-title and no-echo tests go red when their mechanism is removed. Verify against the SDD interfaces.
