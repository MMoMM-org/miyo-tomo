---
title: "Phase 4: Lifecycle tag-prefix cleanup (Part B)"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: Lifecycle tag-prefix cleanup (Part B)

## Phase Context

**GATE**: Read before starting.
- `[ref: solution.md/ADR-6]` — remove tag prefix; repoint statusline probe to `byFrontmatter tomo.state`
- `[ref: requirements.md/Feature 6]` — ACs incl. the `/inbox` regression guard
- Current code: `install-tomo.sh` lifecycle-prefix step (Step 5) + `--prefix` flag (`:43,:72`) + `lifecyclePrefix` config write (`:1299`); vault-config generation `lifecycle.tag_prefix`; `tomo/scripts/state-scanner.py` (delete); `tomo/scripts/tomo-statusline.sh:142-159` (Test 2 byTag); `tomo/config/vault-example.yaml` (`tag_prefix`)
- Real model: `tomo/scripts/mark-captured.py` writes `tomo.state` frontmatter (no tags)

**Key Decisions:** ADR-6. Kept separate from Part A so the cleanup is independently reviewable.

**Dependencies:** Phase 2 (install wizard already restructured — remove the step cleanly on top of the new flow).

---

## Tasks

Removes the vestigial lifecycle tag prefix end-to-end and aligns the statusline probe with the frontmatter model — without changing `/inbox` behaviour.

- [x] **T4.1 Remove tag-prefix from the install wizard + config** `[activity: backend-api]`
  1. Prime: ADR-6 + Feature 6 ACs `[ref: solution.md/ADR-6; requirements.md/Feature 6]`.
  2. Test (RED): isolated install run asserts: no "Lifecycle tag prefix" prompt; no `--prefix` flag in help; generated `tomo-install.json` has NO `lifecyclePrefix`; generated `vault-config.yaml` has NO `lifecycle.tag_prefix` `[ref: PRD/F6-AC1]`.
  3. Implement (GREEN): delete the lifecycle-prefix `print_step` block + `--prefix` parsing + help line; drop `lifecyclePrefix` from the config write; drop `tag_prefix` from vault-config generation.
  4. Validate: `bash -n`; tests pass; bump `install-tomo.sh` `# version:`.
  5. Success: wizard no longer prompts for / writes the prefix `[ref: PRD/F6-AC1]`.

- [x] **T4.2 Delete dead `state-scanner.py`** `[activity: backend-api]` `[parallel: true]`
  1. Prime: confirm zero references in `tomo/dot_claude/` (verified this session; re-grep).
  2. Test (RED): a guard test asserts `tomo/scripts/state-scanner.py` does not exist and `rg state-scanner` finds no runtime caller `[ref: PRD/F6-AC2]`.
  3. Implement (GREEN): `git rm tomo/scripts/state-scanner.py`.
  4. Validate: full suite still green (nothing imported it).
  5. Success: dead tag-discovery removed, no references `[ref: PRD/F6-AC2]`.

- [x] **T4.3 Repoint statusline tag-access probe → frontmatter** `[activity: backend-api]`
  1. Prime: `tomo-statusline.sh:142-159` + ADR-6 `[ref: solution.md/ADR-6]`.
  2. Test (RED): statusline Test 2 issues a `byFrontmatter tomo.state=<known-state>` Kado call (read-access probe), not `byTag #<prefix>`; no longer reads `lifecycle.tag_prefix` from vault-config `[ref: PRD/F6-AC3]`.
  3. Implement (GREEN): replace the byTag block with a byFrontmatter `tomo.state` read; drop the `tag_prefix` grep.
  4. Validate: `bash -n`; tests pass; bump `tomo-statusline.sh` `# version:`.
  5. Success: probe reflects the real model `[ref: PRD/F6-AC3]`.

- [x] **T4.4 `/inbox` lifecycle regression guard** `[activity: validate]`
  1. Prime: `mark-captured.py` + inbox discovery (frontmatter-driven).
  2. Test: confirm (existing suite + a focused check) that capture→active, discovery, and cleanup still work via `tomo.state` frontmatter with the prefix gone `[ref: PRD/F6-AC4]`.
  3. Validate: full lifecycle-related test subset green.
  4. Success: no lifecycle regression after prefix removal `[ref: PRD/F6-AC4]`.

- [x] **T4.5 Phase Validation** `[activity: validate]`
  - Full suite; `bash -n`; ruff. Grep confirms no remaining runtime `tag_prefix`/`lifecyclePrefix`/`state-scanner` references (docs handled in Phase 5).
