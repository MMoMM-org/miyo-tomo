---
title: "Phase 4: inbox-author (rename + extend)"
status: in_progress
version: "1.0"
phase: 4
---

# Phase 4: inbox-author (rename + extend)

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/ADR-3]` — rename `default-doc-writer` → `inbox-author`, preserve 5-step pipeline + 3 STRICTs
- `[ref: SDD/ADR-4]` — direct-compose → staged → parse-gate → operation=file; gate routes by extension:
  `.canvas` (JSON) → validate-json.py, `.base` (YAML) → validate-yaml.py
- `[ref: SDD/ADR-5]` — template mapping real keys + fallback chain
- `[ref: SDD/ADR-6]` — drop format-skill pre-load (auto-load); keep `kado-write-patterns` pre-load
- `[ref: SDD/ADR-7]` — collision via `--no-overwrite` warn+ask
- `[ref: SDD/Implementation Examples; Complex Logic resolve_template]`
- `[ref: PRD/Feature 4; Detailed Feature Specifications]`
- `[ref: tomo/dot_claude/skills/default-doc-writer/SKILL.md]` — pipeline + 3 STRICTs to preserve

**Key Decisions**:
- Real template keys: `atomic_note, map_note, daily, weekly, monthly, yearly, project, source` (+ the
  `default` convention). Unknown type, no vault template → default + user note. Invalid JSON → no write.
- `sanitize_stem` on the stem only; append `.<ext>` separately.

**Dependencies**: Phase 1 (scripts), Phase 2 (format skills for auto-load), Phase 3 (kado-write-patterns).

---

## Tasks

Delivers the orchestration skill that composes correct artifacts and lands them in the inbox.

- [ ] **T4.1 Rename default-doc-writer → inbox-author** `[activity: docs-skill]`

  1. Prime: Read the current skill + its WHY mirror `[ref: tomo/dot_claude/skills/default-doc-writer/SKILL.md;
     docs/tomo/dot_claude/skills/default-doc-writer.md]`.
  2. Test (audit): `/skill-author` audit passes for the renamed skill; the 3 STRICTs are intact; the
     description matches Feature 4; `skills:` frontmatter is `[kado-write-patterns]` only.
  3. Implement via `/skill-author`: create `tomo/dot_claude/skills/inbox-author/SKILL.md` from the
     existing pipeline (Steps 1-5 + 3 STRICTs preserved), updated description, `skills: [kado-write-patterns]`
     (no format-skill pre-load). Rename WHY mirror → `docs/tomo/dot_claude/skills/inbox-author.md`,
     updating the scope rationale. Delete the old `default-doc-writer/` skill dir + WHY file. Bump version.
  4. Validate: audit clean; STRICTs preserved verbatim; no format pre-load.
  5. Success: inbox-author exists with preserved pipeline `[ref: PRD/Feature 4 AC; SDD/ADR-3,ADR-6]`.

- [ ] **T4.2 Extend inbox-author: template mapping + JSON path + collision** `[activity: docs-skill]`

  1. Prime: Read ADR-4/5/7 + resolve_template algorithm `[ref: SDD/Complex Logic]` + Phase 1 scripts.
  2. Test (`tests/test_inbox_author_pipeline.py`, fake Kado, mock at orchestrator — public entry point):
     (a) compose+write happy path lands the artifact in `concepts.inbox`; (b) the extension-routed
     parse-gate blocks the write on malformed `.canvas` (validate-json.py) / `.base` (validate-yaml.py);
     (c) `--no-overwrite` "exists" signal triggers the
     warn branch; (d) template resolution falls back to default + user note when mapping empty/missing;
     (e) writes only target the inbox.
  3. Implement via `/skill-author`: add the format dispatch (md keeps token-render; base/canvas
     direct-compose → `tomo-tmp/staged-artifact.<ext>` → parse-gate routed by extension
     (`.canvas`→validate-json.py, `.base`→validate-yaml.py) → `kado-write-file.py
     operation=file`), template mapping with the real keys + fallback chain, and the `--no-overwrite`
     warn+ask collision step. Bump version. Update WHY mirror.
  4. Validate: `./venv/bin/python -m pytest tests/test_inbox_author_pipeline.py`; audit clean.
  5. Success: all five integration behaviors pass `[ref: PRD/Feature 4 AC; SDD/Test Strategy]`.

- [ ] **T4.3 Rename fan-out** `[activity: refactor]`

  1. Prime: `rg default-doc-writer` across the repo `[ref: SDD/ADR-3 (d)]`.
  2. Test: `rg default-doc-writer` returns zero residual runtime references (historical/spec mentions
     triaged); `update-tomo.sh` prunes the old instance dir.
  3. Implement: add `default-doc-writer` to `scripts/update-tomo.sh` `RETIRED_SKILLS_DIRS`; rewrite any
     residual references (profiles, rules, commands, shipped docs); confirm version bumps so the
     version-gated sync ships the changes.
  4. Validate: `rg default-doc-writer` clean (triaged); RETIRED_SKILLS_DIRS contains it.
  5. Success: no dangling old-name references `[ref: PRD/Feature 4 AC; SDD/ADR-3]`.

- [ ] **T4.4 Phase Validation** `[activity: validate]`

  - Run `tests/test_inbox_author_pipeline.py` + full suite under `./venv/bin/python`; `/skill-author`
    audit; `rg default-doc-writer` triaged clean.
  - **Version-bump checklist (gates the T5.5 sync):** confirm `# version` was bumped on EVERY file
    touched in Phases 1-4 (validate-json.py, kado-write-file.py, all 5 skills, kado-discovery-patterns
    if its description changed). `update-tomo.sh` is version-gated — an un-bumped file is silently
    SKIPPED by the sync and the instance stays stale.
