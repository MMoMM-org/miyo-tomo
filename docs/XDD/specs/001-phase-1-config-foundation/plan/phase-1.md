---
title: "Phase 1: Framework Profiles"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Framework Profiles

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `docs/specs/tier-2/components/framework-profiles.md` — Profile schema, role, design rules
- `docs/specs/tier-3/profiles/miyo-profile.md` — MiYo profile details
- `docs/specs/tier-3/profiles/lyt-profile.md` — LYT profile details

**Key Decisions**:
- Profiles are pure data (YAML), no conditionals or logic
- Profiles define defaults; every field can be overridden by vault-config.yaml
- Absent fields = feature not supported by that framework

**Dependencies**:
- None — this is the foundation phase

---

## Tasks

Establishes the framework profile data layer (Knowledge Stack Layer 2). Both profiles can be built independently.

- [ ] **T1.1 MiYo Framework Profile** `[parallel: true]` `[activity: data-architecture]`

  1. Prime: Read MiYo profile spec `[ref: docs/specs/tier-3/profiles/miyo-profile.md]` and profile schema `[ref: docs/specs/tier-2/components/framework-profiles.md]`
  2. Test: YAML parses without error; all top-level keys present (name, version, base_structure, concept_defaults, classification, map_note_states, relationship_defaults, tag_conventions, callout_defaults, protected_patterns, frontmatter_defaults); concept_defaults maps all 9 concepts; classification has 10 Dewey categories (2000-2900) with keywords; relationship_defaults has parent + peer markers
  3. Implement: Create `tomo/profiles/miyo.yaml` with complete MiYo profile data per spec
  4. Validate: `python3 -c "import yaml; d=yaml.safe_load(open('tomo/profiles/miyo.yaml')); assert d['name']=='MiYo'; assert len(d['classification']['categories'])==10"`
  5. Success: Profile loads and validates; all concept paths match spec (inbox: `+/`, atomic_note: `Atlas/202 Notes/`, maps: `Atlas/200 Maps/`)

- [ ] **T1.2 LYT Framework Profile** `[parallel: true]` `[activity: data-architecture]`

  1. Prime: Read LYT profile spec `[ref: docs/specs/tier-3/profiles/lyt-profile.md]` and profile schema `[ref: docs/specs/tier-2/components/framework-profiles.md]`
  2. Test: YAML parses without error; all top-level keys present; concept_defaults uses LYT paths (Atlas/Dots/, Atlas/Maps/); classification has 10 Dewey-lite categories; MOC state tracking via mapState frontmatter field
  3. Implement: Create `tomo/profiles/lyt.yaml` with standard LYT/Ideaverse Pro conventions
  4. Validate: `python3 -c "import yaml; d=yaml.safe_load(open('tomo/profiles/lyt.yaml')); assert d['name']=='LYT'; assert d['concept_defaults']['atomic_note']=='Atlas/Dots/'"`
  5. Success: Profile loads and validates; paths match Ideaverse Pro conventions; mapState tracking present

- [ ] **T1.3 Phase Validation** `[activity: validate]`

  - Both profiles parse as valid YAML. Schema keys are consistent between profiles. Profile loader can read either profile by name. No duplicate or conflicting keys.
