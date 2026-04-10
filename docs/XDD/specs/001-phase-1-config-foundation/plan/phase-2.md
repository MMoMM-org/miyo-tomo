---
title: "Phase 2: Reference Templates + Config Schema"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Reference Templates + Config Schema

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `docs/specs/tier-2/components/template-system.md` — Template rendering pipeline, token syntax
- `docs/specs/tier-2/components/user-config.md` — vault-config.yaml full schema
- `docs/specs/tier-3/templates/template-files.md` — Template definitions (sections 4.1-4.5)
- `docs/specs/tier-3/config/frontmatter-schema.md` — Frontmatter schema

**Key Decisions**:
- Templates use `{{token}}` syntax — simple string replacement
- Templater `<% %>` syntax is preserved untouched
- User-named templates — no enforced `t_*_tomo` convention
- Fallback minimal template exists if file is missing

**Dependencies**:
- Phase 1 (profiles provide default frontmatter fields and concept paths)

---

## Tasks

Establishes reference templates for all MVP note types and the complete vault-config.yaml schema definition.

- [ ] **T2.1 Atomic Note Template** `[parallel: true]` `[activity: data-architecture]`

  1. Prime: Read template spec section 4.1 `[ref: docs/specs/tier-3/templates/template-files.md §4.1]` and MiYo frontmatter defaults `[ref: docs/specs/tier-3/profiles/miyo-profile.md]`
  2. Test: Template contains valid YAML frontmatter with `{{token}}` placeholders for all required fields (UUID, DateStamp, Updated, title, tags); body has `# [[{{title}}]]` heading; no unmatched `{{` delimiters
  3. Implement: Create `tomo/config/templates/t_note_tomo.md` with atomic note template per spec
  4. Validate: Frontmatter between `---` delimiters is valid YAML (after removing `{{tokens}}`); Templater syntax (if any) preserved
  5. Success: Template renders correctly when all tokens are substituted with sample values

- [ ] **T2.2 Map Note (MOC) Template** `[parallel: true]` `[activity: data-architecture]`

  1. Prime: Read template spec section 4.2 `[ref: docs/specs/tier-3/templates/template-files.md §4.2]`
  2. Test: Contains anchor overview section; key concepts section; MOC-specific frontmatter; `{{title}}` in heading
  3. Implement: Create `tomo/config/templates/t_moc_tomo.md`
  4. Validate: YAML frontmatter valid; MOC-specific sections present
  5. Success: Template matches spec structure with anchor + concepts sections

- [ ] **T2.3 Daily Note Template** `[parallel: true]` `[activity: data-architecture]`

  1. Prime: Read template spec section 4.3 `[ref: docs/specs/tier-3/templates/template-files.md §4.3]`
  2. Test: Simplified frontmatter (UUID, DateStamp, Updated, title, tags); daily-specific sections present
  3. Implement: Create `tomo/config/templates/t_daily_tomo.md`
  4. Validate: YAML frontmatter valid; structure matches daily note conventions
  5. Success: Template renders with date-specific tokens

- [ ] **T2.4 Project + Source Templates** `[parallel: true]` `[activity: data-architecture]`

  1. Prime: Read template spec sections 4.4 and 4.5 `[ref: docs/specs/tier-3/templates/template-files.md §4.4-4.5]`
  2. Test: Project template has Summary field, no vault fields; Source template has source_url and source_author fields
  3. Implement: Create `tomo/config/templates/t_project_tomo.md` and `tomo/config/templates/t_source_tomo.md`
  4. Validate: Both parse as valid YAML frontmatter with correct fields
  5. Success: Both templates match their respective spec sections

- [ ] **T2.5 Vault Config Example Update** `[activity: data-architecture]`

  1. Prime: Read user config schema `[ref: docs/specs/tier-2/components/user-config.md]` and frontmatter schema `[ref: docs/specs/tier-3/config/frontmatter-schema.md]`
  2. Test: Example contains all top-level keys (schema_version, profile, concepts, naming, lifecycle, templates, frontmatter, relationships, tags, callouts, protected_patterns); concepts maps all 9 types; templates.mapping covers all 5 note types
  3. Implement: Update `tomo/config/vault-example.yaml` with complete schema showing MiYo defaults and inline comments
  4. Validate: `python3 -c "import yaml; yaml.safe_load(open('tomo/config/vault-example.yaml'))"` passes
  5. Success: Example config is self-documenting and covers the full schema

- [ ] **T2.6 Phase Validation** `[activity: validate]`

  - All 5 templates parse (YAML frontmatter valid after token removal). Vault config example loads. Token placeholders use consistent `{{name}}` syntax across all templates. No Templater syntax is broken.
